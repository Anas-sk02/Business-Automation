"""Unit tests for Stage 4 Task 4: Lead Fit Scoring Service.

Validates:
- Exact canonical worked example from docs/decisions.md Section 6 (86 points)
- Component calculations for all 7 factors
- Zero phone handling (score computed, but qualification blocked per decisions.md Section 6)
- Placeholder strings (None, N/A, not listed) rejected for phone and email
- Capping website issues at 25 points and awarding 25 for no-website leads
- Evidence verification ratios and zero claims handling
- Rating threshold (>= 3.5), nan/inf safety, and malformed ratings
- Location and industry matching with token overlap
- Clamping of total score to [0, 100]
"""

import pytest
from backend.models.analysis import VerificationResult
from backend.services.scoring import ScoringService, QUALIFY_SCORE


class TestCanonicalWorkedExample:
    def test_canonical_example_from_decisions_md_section_6(self):
        """Worked example from docs/decisions.md Section 6:

        industry 20 + location 15 + website issues (1 high = 7, 1 medium = 4 so 11)
        + evidence 15 (2 of 2 verified) + email 10 + phone 10 + rating 4.8 gives 5 = 86.
        """
        lead = {
            "business_name": "Apex Coaching Hub",
            "category": "Coaching Institute",
            "address": "100ft Road, Indiranagar, Bengaluru",
            "city": "Bengaluru",
            "phone": "+91 9876543210",
            "email": "contact@apexcoaching.example.com",
            "website_url": "https://apexcoaching.example.com",
            "rating": 4.8,
        }
        campaign = {
            "industry": "coaching_institutes",
            "industry_label": "Coaching & Education Centers",
            "keywords": ["coaching", "iit jee", "tuition"],
            "location": "Bengaluru",
        }
        audit = {
            "page_loads": True,
            "tested_url": "https://apexcoaching.example.com",
            "has_contact_form": False,
        }
        evidence_items = [
            {"severity": "high", "finding_title": "Slow mobile page speed"},
            {"severity": "medium", "finding_title": "Mobile horizontal overflow"},
        ]
        verification_result = VerificationResult(
            total_claims=2,
            verified_claims=2,
            unverified_claims=0,
            contradicted_claims=0,
            confidence="high",
        )

        result = ScoringService.calculate_score(
            lead=lead,
            campaign=campaign,
            audit=audit,
            evidence_items=evidence_items,
            verification_result=verification_result,
        )

        assert result.fit_score == 86
        assert result.breakdown.industry == 20
        assert result.breakdown.location == 15
        assert result.breakdown.website == 11
        assert result.breakdown.evidence == 15
        assert result.breakdown.contact == 10
        assert result.breakdown.phone == 10
        assert result.breakdown.rating == 5
        assert result.qualifies is True
        assert result.has_valid_phone is True
        assert result.contactable_via_whatsapp is True


class TestWebsiteIssuesScoring:
    def test_no_website_lead_earns_full_25_points(self):
        lead = {
            "business_name": "Local General Mart",
            "website_url": None,
            "phone": "+91 9988776655",
        }
        campaign = {"industry": "retail", "location": "Nagpur"}

        result = ScoringService.calculate_score(
            lead=lead,
            campaign=campaign,
            audit={"page_loads": False, "tested_url": None},
            evidence_items=[],
        )

        assert result.breakdown.website == 25
        assert any("No website found" in r for r in result.reasons)

    def test_whitespace_website_url_treated_as_no_website(self):
        lead = {
            "business_name": "Local General Mart",
            "website_url": "   ",
            "phone": "+91 9988776655",
        }
        result = ScoringService.calculate_score(
            lead=lead,
            campaign={},
            evidence_items=[],
        )
        assert result.breakdown.website == 25

    def test_website_issues_capped_at_25_points(self):
        lead = {
            "website_url": "https://example.com",
            "phone": "+91 9988776655",
        }
        campaign = {}
        # 2 critical (20) + 2 high (14) = 34 -> capped at 25
        evidence_items = [
            {"severity": "critical", "finding_title": "Site down"},
            {"severity": "critical", "finding_title": "DNS error"},
            {"severity": "high", "finding_title": "Insecure SSL"},
            {"severity": "high", "finding_title": "Mobile broken"},
        ]

        result = ScoringService.calculate_score(
            lead=lead,
            campaign=campaign,
            audit={"page_loads": True, "tested_url": "https://example.com"},
            evidence_items=evidence_items,
        )

        assert result.breakdown.website == 25

    def test_clean_website_earns_zero_issue_points(self):
        lead = {
            "website_url": "https://example.com",
            "phone": "+91 9988776655",
        }
        result = ScoringService.calculate_score(
            lead=lead,
            campaign={},
            audit={"page_loads": True, "tested_url": "https://example.com"},
            evidence_items=[{"severity": "info", "finding_title": "Clean header"}],
        )

        assert result.breakdown.website == 0


class TestPhoneRequirementAndQualification:
    def test_no_phone_blocks_qualification_despite_high_score(self):
        """docs/decisions.md Section 6:

        No valid phone: the score is still computed, but the lead is flagged
        'not contactable via WhatsApp' and can never reach qualified.
        """
        lead = {
            "business_name": "Dr. Sen Clinic",
            "category": "Clinic",
            "address": "Indiranagar, Bengaluru",
            "phone": None,  # Missing phone!
            "email": "doctor@example.com",
            "website_url": None,  # +25 website
            "rating": 4.5,  # +5 rating
        }
        campaign = {
            "industry": "clinics",
            "keywords": ["clinic", "doctor"],
            "location": "Bengaluru",
        }

        result = ScoringService.calculate_score(
            lead=lead,
            campaign=campaign,
        )

        # Industry 20 + Location 15 + Website 25 + Contact 10 + Rating 5 = 75
        assert result.fit_score >= QUALIFY_SCORE
        assert result.breakdown.phone == 0
        assert result.has_valid_phone is False
        assert result.qualifies is False  # Cannot qualify without phone!
        assert result.contactable_via_whatsapp is False
        assert any("cannot be messaged on WhatsApp" in r for r in result.reasons)

    def test_placeholder_phones_rejected(self):
        for junk in ["None", "null", "N/A", "Not listed", "unknown", "123", "   "]:
            lead = {"phone": junk}
            result = ScoringService.calculate_score(lead=lead, campaign={})
            assert result.breakdown.phone == 0
            assert result.has_valid_phone is False
            assert result.qualifies is False

    def test_opted_out_lead_not_contactable_via_whatsapp(self):
        lead = {
            "business_name": "Test Store",
            "phone": "+91 9876543210",
            "is_suppressed": True,
        }
        result = ScoringService.calculate_score(
            lead=lead,
            campaign={},
        )
        assert result.has_valid_phone is True
        assert result.contactable_via_whatsapp is False


class TestEvidenceQualityScoring:
    def test_evidence_quality_zero_claims(self):
        result = ScoringService.calculate_score(
            lead={},
            campaign={},
            verification_result={"total_claims": 0, "verified_claims": 0},
        )
        assert result.breakdown.evidence == 0

    def test_evidence_quality_partial_ratio(self):
        # 1 of 3 verified -> 15 * (1/3) = 5
        result = ScoringService.calculate_score(
            lead={},
            campaign={},
            verification_result={"total_claims": 3, "verified_claims": 1},
        )
        assert result.breakdown.evidence == 5

    def test_evidence_quality_two_thirds_ratio(self):
        # 2 of 3 verified -> 15 * (2/3) = 10
        result = ScoringService.calculate_score(
            lead={},
            campaign={},
            verification_result={"total_claims": 3, "verified_claims": 2},
        )
        assert result.breakdown.evidence == 10

    def test_evidence_quality_anomalous_counts_clamped(self):
        # verified_claims > total_claims should be clamped to 15
        result = ScoringService.calculate_score(
            lead={},
            campaign={},
            verification_result={"total_claims": 2, "verified_claims": 5},
        )
        assert result.breakdown.evidence == 15


class TestRatingAndContactScoring:
    def test_rating_thresholds(self):
        # 3.5 qualifies for 5
        res_35 = ScoringService.calculate_score(lead={"rating": 3.5}, campaign={})
        assert res_35.breakdown.rating == 5

        # 3.49 does not qualify
        res_34 = ScoringService.calculate_score(lead={"rating": 3.49}, campaign={})
        assert res_34.breakdown.rating == 0

        # None or invalid string
        res_none = ScoringService.calculate_score(lead={"rating": None}, campaign={})
        assert res_none.breakdown.rating == 0

        res_str = ScoringService.calculate_score(lead={"rating": "N/A"}, campaign={})
        assert res_str.breakdown.rating == 0

    def test_rating_nan_and_inf_safe(self):
        # Nan and inf must yield 0, not 5
        res_nan = ScoringService.calculate_score(lead={"rating": float("nan")}, campaign={})
        assert res_nan.breakdown.rating == 0

        res_inf = ScoringService.calculate_score(lead={"rating": float("inf")}, campaign={})
        assert res_inf.breakdown.rating == 0

        # Out-of-bounds ratings (e.g. 10.0 or -2.0)
        res_out = ScoringService.calculate_score(lead={"rating": 10.0}, campaign={})
        assert res_out.breakdown.rating == 0

    def test_contact_channel_form_on_site(self):
        result = ScoringService.calculate_score(
            lead={"email": None},
            campaign={},
            audit={"has_contact_form": True},
        )
        assert result.breakdown.contact == 10

    def test_contact_channel_placeholder_email_rejected(self):
        result = ScoringService.calculate_score(
            lead={"email": "not listed"},
            campaign={},
            audit={"has_contact_form": False},
        )
        assert result.breakdown.contact == 0


class TestLocationAndIndustryScoring:
    def test_location_match_substring(self):
        lead = {"address": "MG Road, Indiranagar, Bengaluru"}
        campaign = {"location": "Indiranagar"}
        result = ScoringService.calculate_score(lead=lead, campaign=campaign)
        assert result.breakdown.location == 15

    def test_location_mismatch(self):
        lead = {"address": "FC Road, Pune"}
        campaign = {"location": "Bengaluru"}
        result = ScoringService.calculate_score(lead=lead, campaign=campaign)
        assert result.breakdown.location == 0

    def test_industry_mismatch(self):
        lead = {"category": "Pet Clinic"}
        campaign = {"industry": "real_estate", "keywords": ["flats", "apartments"]}
        result = ScoringService.calculate_score(lead=lead, campaign=campaign)
        assert result.breakdown.industry == 0
