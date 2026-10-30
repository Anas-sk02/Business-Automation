"""Lead Fit Scoring Service for Stage 4: Deterministic Scoring & Fit Rules.

Computes the 100-point deterministic Lead Fit Score per docs/decisions.md Section 6.
Pure arithmetic calculation without AI involvement. Evaluates the 7 core components:
1. Industry match (20)
2. Location match (15)
3. Website issues (25)
4. Evidence quality (15)
5. Contact channel (10)
6. Phone available (10)
7. Rating >= 3.5 (5)
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Union

from backend.models.analysis import ScoreBreakdown, ScoreResult, VerificationResult

QUALIFY_SCORE: int = 60
INVALID_PLACEHOLDERS: Set[str] = {"none", "null", "n/a", "not listed", "unknown", "not found", "undefined", ""}


class ScoringService:
    """Deterministic scoring engine computing the Lead Fit Score and qualification status."""

    @staticmethod
    def _normalize_tokens(text: Any) -> Set[str]:
        """Normalize string into a bounded set of lowercased tokens."""
        if not text:
            return set()
        str_text = str(text)[:500].lower().replace("-", " ").replace("_", " ").replace(",", " ")
        return {tok.strip() for tok in str_text.split() if len(tok.strip()) > 1}

    @staticmethod
    def _is_valid_phone(phone: Any) -> bool:
        """Check whether a phone string contains actual digits and is not a placeholder."""
        if not phone:
            return False
        clean = str(phone).strip().lower()
        if clean in INVALID_PLACEHOLDERS:
            return False
        digits = re.sub(r"\D", "", clean)
        return len(digits) >= 7

    @staticmethod
    def _is_valid_email(email: Any) -> bool:
        """Check whether an email string is structurally plausible and not a placeholder."""
        if not email:
            return False
        clean = str(email).strip().lower()
        if clean in INVALID_PLACEHOLDERS:
            return False
        return "@" in clean and "." in clean.split("@")[-1]

    @classmethod
    def _calculate_industry_match(
        cls,
        lead: Dict[str, Any],
        campaign: Dict[str, Any],
    ) -> tuple[int, str]:
        """Component 1: Industry match (max 20 points)."""
        lead_category = str(lead.get("category") or "").strip()
        lead_types = lead.get("types") or []
        if isinstance(lead_types, str):
            lead_types = [t.strip() for t in lead_types.split(",")]
        elif not isinstance(lead_types, list):
            lead_types = [str(lead_types)]

        campaign_keywords = campaign.get("keywords") or []
        if isinstance(campaign_keywords, str):
            campaign_keywords = [k.strip() for k in campaign_keywords.split(",")]
        elif not isinstance(campaign_keywords, list):
            campaign_keywords = [str(campaign_keywords)]

        campaign_industry = str(campaign.get("industry") or "").strip()
        campaign_label = str(campaign.get("industry_label") or "").strip()

        # Build comparison token sets
        lead_tokens = cls._normalize_tokens(lead_category)
        for t in lead_types:
            lead_tokens.update(cls._normalize_tokens(t))

        campaign_tokens = cls._normalize_tokens(campaign_industry)
        campaign_tokens.update(cls._normalize_tokens(campaign_label))
        for kw in campaign_keywords:
            campaign_tokens.update(cls._normalize_tokens(kw))

        # Substring or token overlap match
        category_lower = lead_category.lower()
        industry_match = False

        if category_lower and any(str(kw).strip().lower() in category_lower for kw in campaign_keywords if str(kw).strip()):
            industry_match = True
        elif category_lower and (
            (campaign_industry and campaign_industry.lower() in category_lower)
            or (campaign_label and campaign_label.lower() in category_lower)
        ):
            industry_match = True
        elif lead_tokens and campaign_tokens and lead_tokens.intersection(campaign_tokens):
            industry_match = True

        if industry_match:
            desc = f"Category '{lead_category}' matches campaign keywords (+20)" if lead_category else "Category matches campaign keywords (+20)"
            return 20, desc
        else:
            desc = f"Category '{lead_category}' does not match campaign keywords (+0)" if lead_category else "Category does not match campaign keywords (+0)"
            return 0, desc

    @classmethod
    def _calculate_location_match(
        cls,
        lead: Dict[str, Any],
        campaign: Dict[str, Any],
    ) -> tuple[int, str]:
        """Component 2: Location match (max 15 points)."""
        campaign_loc = str(campaign.get("location") or campaign.get("city") or "").strip().lower()
        lead_addr = str(lead.get("address") or "").strip().lower()
        lead_city = str(lead.get("city") or "").strip().lower()

        if not campaign_loc:
            # If campaign specifies no location, match by default
            return 15, "Target location matches campaign area (+15)"

        loc_tokens = cls._normalize_tokens(campaign_loc)
        lead_loc_text = f"{lead_addr} {lead_city}".strip()
        lead_loc_tokens = cls._normalize_tokens(lead_loc_text)

        if campaign_loc in lead_loc_text or (loc_tokens and lead_loc_tokens and loc_tokens.intersection(lead_loc_tokens)):
            return 15, f"Address is within target area ({campaign_loc.title()}) (+15)"
        else:
            return 0, f"Address outside target area ({campaign_loc.title()}) (+0)"

    @classmethod
    def _calculate_website_issues(
        cls,
        lead: Dict[str, Any],
        audit: Optional[Dict[str, Any]] = None,
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[int, str]:
        """Component 3: Website issues (max 25 points).

        Per docs/decisions.md Section 6:
        No website = 25. Otherwise sum per finding: critical 10, high 7, medium 4, low 2, capped at 25.
        """
        audit = audit or {}
        evidence_items = evidence_items or []

        raw_url = lead.get("website_url") or audit.get("tested_url")
        website_url = str(raw_url).strip() if raw_url else ""
        if website_url.lower() in INVALID_PLACEHOLDERS:
            website_url = ""

        # Case 1: No website registered or audit confirmed no website
        if not website_url or (audit.get("page_loads") is False and not audit.get("tested_url")):
            return 25, "No website found: prime candidate for digital web setup (+25)"

        # Case 2: Website exists - sum issues from evidence items
        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for ev in evidence_items:
            if not isinstance(ev, dict):
                continue
            sev = str(ev.get("severity") or "").lower()
            if sev in severities:
                severities[sev] += 1

        points = (
            (severities["critical"] * 10)
            + (severities["high"] * 7)
            + (severities["medium"] * 4)
            + (severities["low"] * 2)
        )
        capped_points = min(25, points)

        issue_parts = []
        for sev_name, count in severities.items():
            if count > 0:
                issue_parts.append(f"{count} {sev_name}")

        if issue_parts:
            issues_summary = ", ".join(issue_parts)
            reason = f"Website has {issues_summary} issues (+{capped_points})"
        else:
            reason = "No website issues detected (+0)"

        return capped_points, reason

    @classmethod
    def _calculate_evidence_quality(
        cls,
        verification_result: Union[VerificationResult, Dict[str, Any], None],
    ) -> tuple[int, str]:
        """Component 4: Evidence quality (max 15 points).

        Per docs/decisions.md Section 6:
        15 x (verified claims / total claims). Zero claims = 0.
        """
        if not verification_result:
            return 0, "No claims evaluated (+0)"

        if isinstance(verification_result, dict):
            total_claims = int(verification_result.get("total_claims") or 0)
            verified_claims = int(verification_result.get("verified_claims") or 0)
        else:
            total_claims = getattr(verification_result, "total_claims", 0)
            verified_claims = getattr(verification_result, "verified_claims", 0)

        if total_claims <= 0:
            return 0, "No claims evaluated (+0)"

        # Clamp verified claims to not exceed total claims
        clamped_verified = min(max(0, verified_claims), total_claims)
        points = round(15.0 * (clamped_verified / total_claims))
        capped_points = min(15, max(0, points))
        reason = f"Evidence quality: {clamped_verified} of {total_claims} claims verified (+{capped_points})"
        return capped_points, reason

    @classmethod
    def _calculate_contact_channel(
        cls,
        lead: Dict[str, Any],
        audit: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, str]:
        """Component 5: Contact channel (max 10 points).

        Per docs/decisions.md Section 6:
        Email or contact form found (site or listing).
        """
        audit = audit or {}
        has_email = cls._is_valid_email(lead.get("email")) or cls._is_valid_email(audit.get("has_email_on_site"))
        has_form = bool(audit.get("has_contact_form"))

        if has_email or has_form:
            channels = []
            if has_email:
                channels.append("email")
            if has_form:
                channels.append("contact form")
            reason = f"Direct {' and '.join(channels)} available (+10)"
            return 10, reason
        else:
            return 0, "No email or contact form found (+0)"

    @classmethod
    def _calculate_phone(
        cls,
        lead: Dict[str, Any],
    ) -> tuple[int, str]:
        """Component 6: Phone available (max 10 points)."""
        if cls._is_valid_phone(lead.get("phone")):
            return 10, "Valid phone available (+10)"
        else:
            return 0, "No phone number: cannot be messaged on WhatsApp (+0)"

    @classmethod
    def _calculate_rating(
        cls,
        lead: Dict[str, Any],
    ) -> tuple[int, str]:
        """Component 7: Rating (max 5 points).

        Per docs/decisions.md Section 6:
        Rating >= 3.5 = +5. Otherwise 0.
        """
        raw_rating = lead.get("rating")
        if raw_rating is not None:
            try:
                rating = float(raw_rating)
                if not math.isnan(rating) and not math.isinf(rating) and 3.5 <= rating <= 5.0:
                    return 5, f"Google rating {rating:.1f} >= 3.5 (+5)"
                elif not math.isnan(rating) and not math.isinf(rating) and 0.0 <= rating < 3.5:
                    return 0, f"Google rating {rating:.1f} below 3.5 threshold (+0)"
            except (ValueError, TypeError):
                pass
        return 0, "Google rating not listed (+0)"

    @classmethod
    def calculate_score(
        cls,
        lead: Dict[str, Any],
        campaign: Dict[str, Any],
        audit: Optional[Dict[str, Any]] = None,
        evidence_items: Optional[List[Dict[str, Any]]] = None,
        verification_result: Union[VerificationResult, Dict[str, Any], None] = None,
    ) -> ScoreResult:
        """Calculate the complete 7-component Lead Fit Score.

        Follows docs/decisions.md Section 6. Clamps total score to [0, 100].
        No valid phone blocks qualification regardless of score.
        """
        lead = lead or {}
        campaign = campaign or {}
        audit = audit or {}
        evidence_items = evidence_items or []

        # 1. Industry (max 20)
        p_industry, r_industry = cls._calculate_industry_match(lead, campaign)

        # 2. Location (max 15)
        p_location, r_location = cls._calculate_location_match(lead, campaign)

        # 3. Website issues (max 25)
        p_website, r_website = cls._calculate_website_issues(lead, audit, evidence_items)

        # 4. Evidence quality (max 15)
        p_evidence, r_evidence = cls._calculate_evidence_quality(verification_result)

        # 5. Contact channel (max 10)
        p_contact, r_contact = cls._calculate_contact_channel(lead, audit)

        # 6. Phone (max 10)
        p_phone, r_phone = cls._calculate_phone(lead)

        # 7. Rating (max 5)
        p_rating, r_rating = cls._calculate_rating(lead)

        # Total points & clamping
        raw_total = (
            p_industry
            + p_location
            + p_website
            + p_evidence
            + p_contact
            + p_phone
            + p_rating
        )
        fit_score = min(100, max(0, raw_total))

        # Phone and WhatsApp qualifications
        has_valid_phone = cls._is_valid_phone(lead.get("phone"))
        is_suppressed = bool(lead.get("is_suppressed"))
        contactable_via_whatsapp = has_valid_phone and not is_suppressed

        # Per decisions.md Section 6: "No valid phone: the score is still computed,
        # but the lead is flagged 'not contactable via WhatsApp' and can never reach qualified."
        qualifies = (fit_score >= QUALIFY_SCORE) and has_valid_phone

        breakdown = ScoreBreakdown(
            industry=p_industry,
            location=p_location,
            website=p_website,
            evidence=p_evidence,
            contact=p_contact,
            phone=p_phone,
            rating=p_rating,
        )

        reasons = [
            r_industry,
            r_location,
            r_website,
            r_evidence,
            r_contact,
            r_phone,
            r_rating,
        ]

        return ScoreResult(
            fit_score=fit_score,
            breakdown=breakdown,
            reasons=reasons,
            qualifies=qualifies,
            has_valid_phone=has_valid_phone,
            contactable_via_whatsapp=contactable_via_whatsapp,
        )
