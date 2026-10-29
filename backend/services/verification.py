"""Claim Verification Service for Stage 4: AI Analysis & Evidence Grounding.

Cross-verifies AI-generated opportunities and claims against stored evidence_items
and website_audits records. Classifies claims into verified, unverified, or contradicted,
and computes calibrated confidence levels per docs/decisions.md Section 7.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.models.analysis import (
    AIAnalysisResult,
    ClaimVerificationItem,
    ConfidenceLevel,
    VerificationResult,
)

# Stopwords to filter out when performing semantic keyword matching
COMMON_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "it", "its", "this", "that", "these", "those", "their", "our", "your", "of",
    "may", "could", "might", "would", "should", "not", "no", "site", "website", "page",
}


class VerificationService:
    """Service to deterministically cross-verify AI claims against stored evidence."""

    @staticmethod
    def _normalize_tokens(text: str) -> Set[str]:
        """Extract alphanumeric words, lowercase, and discard common stopwords."""
        words = re.findall(r"\b[a-zA-Z0-9_\-]+\b", (text or "")[:2000].lower())
        return {w for w in words if len(w) > 2 and w not in COMMON_STOPWORDS}

    @classmethod
    def _check_contradiction(
        cls,
        claim_text: str,
        audit: Optional[Dict[str, Any]] = None,
        lead: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Check if an AI claim directly contradicts measured facts in audit or lead data.

        Returns explanation string if contradicted, None otherwise.
        """
        claim_lower = claim_text[:2000].lower()
        audit = audit or {}
        lead = lead or {}

        # 1. Contradiction: AI claims site is down/broken/failed, but audit loaded fine
        site_down_patterns = [
            r"\b(website|site|server|webpage|page)\s+(is\s+)?(down|offline|broken|inaccessible|crashed)\b",
            r"\b(fails?|unable|cannot)\s+to\s+load\b",
            r"\bcompletely\s+(down|inaccessible|offline)\b",
        ]
        if any(re.search(pat, claim_lower) for pat in site_down_patterns):
            if audit.get("page_loads") is True:
                http_status = audit.get("http_status", 200)
                return f"Claim asserts website is down or broken, but audit successfully loaded the page (HTTP {http_status})."

        # 2. Contradiction: AI claims no phone number exists, but phone exists
        no_phone_patterns = [
            r"\b(no|missing|lacks?)\s+(phone|contact\s+number|calling|phone\s+contact)\b",
            r"\bcannot\s+call\b",
        ]
        if any(re.search(pat, claim_lower) for pat in no_phone_patterns):
            phone = lead.get("phone") or (audit.get("has_phone_on_site") if audit else None)
            if phone:
                return "Claim asserts no phone contact available, but business has a registered phone number."

        # 3. Contradiction: AI claims no SSL / unsecure site, but SSL certificate is valid
        no_ssl_patterns = [
            r"\b(no|missing|lacks?|without)\s+(ssl|https|encryption)\b",
            r"\binsecure\s+(connection|http|website|site)\b",
        ]
        if any(re.search(pat, claim_lower) for pat in no_ssl_patterns):
            if audit.get("ssl_valid") is True:
                return "Claim asserts website lacks SSL/HTTPS, but audit verified a valid SSL certificate."

        # 4. Contradiction: AI claims no website exists, but website exists and loaded
        no_site_patterns = [
            r"\b(has\s+)?no\s+website\b",
            r"\blacks?\s+a\s+website\b",
            r"\bwithout\s+a\s+website\b",
        ]
        if any(re.search(pat, claim_lower) for pat in no_site_patterns):
            if lead.get("website_url") and audit.get("page_loads") is True:
                return "Claim asserts business has no website, but active website was audited."

        # 5. Contradiction: AI claims mobile layout has overflow, but audit tested and found no overflow
        mobile_overflow_patterns = [
            r"\bhorizontal\s+(layout\s+)?overflow\b",
            r"\boverflows?\s+mobile\b",
            r"\bmobile\s+overflow\b",
        ]
        if any(re.search(pat, claim_lower) for pat in mobile_overflow_patterns):
            if audit.get("mobile_overflow") is False:
                return "Claim asserts horizontal mobile overflow, but audit measured 0px overflow beyond 375px viewport."

        return None

    @classmethod
    def _match_evidence(
        cls,
        claim_text: str,
        evidence_items: List[Dict[str, Any]],
    ) -> Optional[Tuple[str, str]]:
        """Match claim against evidence items.

        Returns (evidence_id, matched_finding_title) if matched, None otherwise.
        """
        claim_bounded = claim_text[:2000]
        claim_tokens = cls._normalize_tokens(claim_bounded)
        claim_lower = claim_bounded.lower()

        # Dedicated domain checks for highest-accuracy matching
        for ev in evidence_items:
            if not isinstance(ev, dict):
                continue

            ev_id = str(ev.get("id") or "")
            title = str(ev.get("finding_title") or "")
            desc = str(ev.get("description") or "")
            ev_data = ev.get("evidence_data") or {}
            title_lower = title.lower()

            # Mobile overflow check
            if ("overflow" in claim_lower or "375" in claim_lower) and (
                "overflow" in title_lower or (isinstance(ev_data, dict) and ev_data.get("check") == "mobile_overflow")
            ):
                return ev_id, title

            # SSL check
            if ("ssl" in claim_lower or "https" in claim_lower) and (
                "ssl" in title_lower or "https" in title_lower or (isinstance(ev_data, dict) and ev_data.get("ssl_valid") is False)
            ):
                return ev_id, title

            # Load speed / Slow response check
            if any(term in claim_lower for term in ["slow", "speed", "load time", "seconds"]) and (
                any(term in title_lower for term in ["slow", "speed", "load time", "response"])
                or (isinstance(ev_data, dict) and "load_time_seconds" in ev_data)
            ):
                return ev_id, title

            # Contact Form check
            if ("contact form" in claim_lower or "inquiry form" in claim_lower) and (
                "contact form" in title_lower or "form" in title_lower or (isinstance(ev_data, dict) and "has_contact_form" in ev_data)
            ):
                return ev_id, title

            # WhatsApp check
            if ("whatsapp" in claim_lower or "wa.me" in claim_lower) and (
                "whatsapp" in title_lower or (isinstance(ev_data, dict) and "has_whatsapp_link" in ev_data)
            ):
                return ev_id, title

            # Broken links check
            if ("broken link" in claim_lower or "404" in claim_lower) and (
                "broken" in title_lower or ev.get("evidence_type") == "link_check"
            ):
                return ev_id, title

            # Alt tags check
            if ("alt text" in claim_lower or "alt attribute" in claim_lower or "images missing" in claim_lower) and (
                "alt" in title_lower or (isinstance(ev_data, dict) and "missing_alt" in ev_data)
            ):
                return ev_id, title

            # Meta description / title check
            if ("meta description" in claim_lower) and ("meta description" in title_lower):
                return ev_id, title
            if ("page title" in claim_lower or "title tag" in claim_lower) and ("title" in title_lower):
                return ev_id, title

            # Lighthouse check
            if ("lighthouse" in claim_lower or "accessibility" in claim_lower or "seo score" in claim_lower) and (
                ev.get("evidence_type") == "lighthouse_report"
            ):
                return ev_id, title

            # No website check
            if ("no website" in claim_lower or "not have a website" in claim_lower) and (
                "no website" in title_lower
            ):
                return ev_id, title

            # Fallback: token overlap of 3 or more distinctive words
            ev_tokens = cls._normalize_tokens(f"{title} {desc}")
            shared_tokens = claim_tokens.intersection(ev_tokens)
            if len(shared_tokens) >= 3:
                return ev_id, title

        return None

    @classmethod
    def verify_claims(
        cls,
        analysis_result: Union[AIAnalysisResult, Dict[str, Any], None],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
        audit: Optional[Dict[str, Any]] = None,
        lead: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify all opportunities in the AI analysis result against stored evidence.

        Evaluates each opportunity against deterministic audit findings and lead data.
        Returns aggregate verification result with calibrated confidence score.
        """
        evidence_items = evidence_items or []
        items: List[ClaimVerificationItem] = []

        if isinstance(analysis_result, dict):
            try:
                analysis_result = AIAnalysisResult.model_validate(analysis_result)
            except Exception:
                analysis_result = None

        opportunities = analysis_result.opportunities if analysis_result else []

        for opp in opportunities:
            opp_issue = getattr(opp, "issue", "") or ""
            opp_evidence = getattr(opp, "evidence", "") or ""
            claim_text = f"{opp_issue}: {opp_evidence}".strip(": ") or "Opportunity finding"

            # 1. Contradiction check
            contradiction_reason = cls._check_contradiction(claim_text, audit=audit, lead=lead)
            if contradiction_reason:
                items.append(
                    ClaimVerificationItem(
                        claim=opp_issue or claim_text,
                        status="contradicted",
                        matched_finding=contradiction_reason,
                    )
                )
                continue

            # 2. Evidence match check
            matched = cls._match_evidence(claim_text, evidence_items)
            if matched:
                ev_id, finding_title = matched
                items.append(
                    ClaimVerificationItem(
                        claim=opp_issue or claim_text,
                        status="verified",
                        evidence_id=ev_id if ev_id else None,
                        matched_finding=finding_title,
                    )
                )
            else:
                items.append(
                    ClaimVerificationItem(
                        claim=opp_issue or claim_text,
                        status="unverified",
                        matched_finding="No matching measured evidence found in stored audit results.",
                    )
                )

        total_claims = len(items)
        verified_claims = sum(1 for it in items if it.status == "verified")
        unverified_claims = sum(1 for it in items if it.status == "unverified")
        contradicted_claims = sum(1 for it in items if it.status == "contradicted")

        # Confidence Calibration per docs/decisions.md Section 7
        confidence: ConfidenceLevel
        if contradicted_claims > 0:
            confidence = "low"
        elif total_claims > 0:
            ratio = verified_claims / total_claims
            if ratio >= 0.70 and verified_claims >= 2:
                confidence = "high"
            elif ratio >= 0.40 and verified_claims >= 1:
                confidence = "medium"
            else:
                confidence = "low"
        else:
            # If no opportunities identified, confidence is medium if site loaded fine, else low
            confidence = "medium" if (audit and audit.get("page_loads") is True) else "low"

        return VerificationResult(
            items=items,
            total_claims=total_claims,
            verified_claims=verified_claims,
            unverified_claims=unverified_claims,
            contradicted_claims=contradicted_claims,
            confidence=confidence,
        )

    @staticmethod
    def get_verified_claims_for_messaging(
        verification_result: Optional[VerificationResult],
    ) -> List[ClaimVerificationItem]:
        """Extract only verified claims safe for outreach message generation.

        Per docs/decisions.md Section 7: 'Messages may only use verified claims.'
        """
        if not verification_result or not getattr(verification_result, "items", None):
            return []
        return [it for it in verification_result.items if it.status == "verified"]
