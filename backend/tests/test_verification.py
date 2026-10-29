"""Unit tests for Stage 4 Task 3: Claim Verification Service.

Validates:
- Deterministic verification of AI opportunities against stored evidence items
- Accurate contradiction detection against audit metrics and lead attributes
- Safe handling of unverified/hallucinated claims
- Summary metric calculations (total, verified, unverified, contradicted)
- Calibrated confidence scoring (high, medium, low)
- Extraction of verified claims for Stage 5 messaging per docs/decisions.md Section 7
- Resilience against raw dict inputs, non-dict evidence records, and None arguments
"""

import pytest
from backend.models.analysis import AIAnalysisResult, AnalysisOpportunity, VerificationResult
from backend.services.verification import VerificationService


@pytest.fixture
def sample_evidence_items():
    return [
        {
            "id": "ev-101",
            "finding_title": "Mobile layout has horizontal overflow",
            "description": "Page exceeds mobile viewport width by 82px.",
            "evidence_type": "audit_check",
            "severity": "medium",
            "verification_status": "verified",
            "evidence_data": {"check": "mobile_overflow", "pixels": 82},
        },
        {
            "id": "ev-102",
            "finding_title": "Slow initial page response",
            "description": "Initial page took 4.6s to load.",
            "evidence_type": "audit_check",
            "severity": "medium",
            "verification_status": "verified",
            "evidence_data": {"load_time_seconds": 4.6},
        },
        {
            "id": "ev-103",
            "finding_title": "Missing contact form",
            "description": "No interactive inquiry or lead capture form found on page.",
            "evidence_type": "audit_check",
            "severity": "medium",
            "verification_status": "verified",
            "evidence_data": {"has_contact_form": False},
        },
        {
            "id": "ev-104",
            "finding_title": "Detected 3 broken internal links",
            "description": "Found 3 broken internal links returning 404.",
            "evidence_type": "link_check",
            "severity": "high",
            "verification_status": "verified",
            "evidence_data": {"broken_count": 3},
        },
    ]


@pytest.fixture
def sample_audit():
    return {
        "page_loads": True,
        "http_status": 200,
        "load_time_seconds": 4.6,
        "ssl_valid": True,
        "mobile_overflow": True,
        "mobile_overflow_pixels": 82,
        "has_contact_form": False,
        "has_phone_on_site": True,
        "has_whatsapp_link": False,
    }


@pytest.fixture
def sample_lead():
    return {
        "business_name": "Indira Coaching Academy",
        "phone": "+91 9876543210",
        "website_url": "https://indiracoaching.example.com",
    }


class TestEvidenceVerification:
    def test_verify_all_matched_opportunities(self, sample_evidence_items, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Indira Coaching provides test prep.",
            strengths=["Active phone listed"],
            opportunities=[
                AnalysisOpportunity(
                    issue="Mobile horizontal layout overflow",
                    evidence="Page content extends beyond 375px viewport",
                    impact="Mobile students may struggle to read course details",
                    recommendation="Fix mobile CSS container overflow",
                ),
                AnalysisOpportunity(
                    issue="Slow initial page response",
                    evidence="Load time measured at 4.6 seconds",
                    impact="High bounce rate on slow mobile cellular connections",
                    recommendation="Enable image compression and caching",
                ),
                AnalysisOpportunity(
                    issue="Missing contact form on landing page",
                    evidence="Audit detected no interactive form elements",
                    impact="Prospective parents must call rather than submit inquiries",
                    recommendation="Embed a clean inquiry form",
                ),
            ],
            recommended_service="Mobile UI Optimization",
            pitch_angle="Fix mobile overflow and speed to capture high-intent students.",
        )

        result: VerificationResult = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.total_claims == 3
        assert result.verified_claims == 3
        assert result.unverified_claims == 0
        assert result.contradicted_claims == 0
        assert result.confidence == "high"

        # Check matched findings
        assert result.items[0].status == "verified"
        assert result.items[0].evidence_id == "ev-101"
        assert result.items[1].status == "verified"
        assert result.items[1].evidence_id == "ev-102"
        assert result.items[2].status == "verified"
        assert result.items[2].evidence_id == "ev-103"

    def test_verify_unverified_opportunity(self, sample_evidence_items, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Indira Coaching provides test prep.",
            opportunities=[
                AnalysisOpportunity(
                    issue="Competitor ad campaigns stealing market share",
                    evidence="Competitors are bidding on local coaching keywords",
                    impact="May reduce total admissions",
                    recommendation="Launch Google search campaigns",
                )
            ],
            recommended_service="Google Ads",
            pitch_angle="Run ads to protect brand search volume.",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.total_claims == 1
        assert result.verified_claims == 0
        assert result.unverified_claims == 1
        assert result.confidence == "low"
        assert result.items[0].status == "unverified"
        assert "No matching measured evidence" in (result.items[0].matched_finding or "")

    def test_raw_dict_analysis_result_input(self, sample_evidence_items, sample_audit, sample_lead):
        raw_dict = {
            "business_summary": "Indira Coaching provides test prep.",
            "opportunities": [
                {
                    "issue": "Slow initial page response",
                    "evidence": "Takes 4.6 seconds to load",
                    "impact": "May increase bounce rate",
                    "recommendation": "Optimize assets",
                }
            ],
            "recommended_service": "Speed",
            "pitch_angle": "Fix speed",
        }

        result = VerificationService.verify_claims(
            analysis_result=raw_dict,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.total_claims == 1
        assert result.verified_claims == 1
        assert result.items[0].status == "verified"


class TestContradictionDetection:
    def test_contradiction_site_down_when_page_loads(self, sample_evidence_items, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Indira Coaching.",
            opportunities=[
                AnalysisOpportunity(
                    issue="Website is completely down and inaccessible",
                    evidence="Server fails to load or return responses",
                    impact="Visitors cannot reach the academy",
                    recommendation="Restore server uptime",
                )
            ],
            recommended_service="Hosting",
            pitch_angle="Get reliable hosting.",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.total_claims == 1
        assert result.contradicted_claims == 1
        assert result.confidence == "low"
        assert result.items[0].status == "contradicted"
        assert "HTTP 200" in (result.items[0].matched_finding or "")

    def test_contradiction_no_phone_when_phone_present(self, sample_evidence_items, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Indira Coaching.",
            opportunities=[
                AnalysisOpportunity(
                    issue="No phone contact number available",
                    evidence="Cannot find any phone number for the business",
                    impact="Students cannot call the institute",
                    recommendation="Add phone number to header",
                )
            ],
            recommended_service="Contact Optimization",
            pitch_angle="Add phone number.",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.contradicted_claims == 1
        assert result.confidence == "low"
        assert result.items[0].status == "contradicted"
        assert "registered phone number" in (result.items[0].matched_finding or "")

    def test_contradiction_no_ssl_when_ssl_valid(self, sample_evidence_items, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Indira Coaching.",
            opportunities=[
                AnalysisOpportunity(
                    issue="Insecure connection with no SSL certificate",
                    evidence="Browser flags connection as insecure HTTP",
                    impact="Causes security warnings",
                    recommendation="Install SSL certificate",
                )
            ],
            recommended_service="Security Setup",
            pitch_angle="Fix SSL.",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.contradicted_claims == 1
        assert result.confidence == "low"
        assert result.items[0].status == "contradicted"
        assert "valid SSL certificate" in (result.items[0].matched_finding or "")

    def test_contradiction_mobile_overflow_when_audit_measured_no_overflow(self, sample_evidence_items, sample_lead):
        clean_audit = {
            "page_loads": True,
            "http_status": 200,
            "ssl_valid": True,
            "mobile_overflow": False,
            "mobile_overflow_pixels": 0,
        }
        analysis = AIAnalysisResult(
            business_summary="Indira Coaching.",
            opportunities=[
                AnalysisOpportunity(
                    issue="Horizontal overflow on mobile screens",
                    evidence="Page content exceeds 375px screen width",
                    impact="Layout broken on mobile",
                    recommendation="Fix viewport width",
                )
            ],
            recommended_service="Mobile Design",
            pitch_angle="Fix mobile overflow.",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=[],
            audit=clean_audit,
            lead=sample_lead,
        )

        assert result.contradicted_claims == 1
        assert result.confidence == "low"
        assert result.items[0].status == "contradicted"


class TestConfidenceCalibrationAndEdgeCases:
    def test_medium_confidence_threshold(self, sample_evidence_items, sample_audit, sample_lead):
        # 1 verified, 1 unverified -> ratio 0.50 (>= 0.40) -> medium
        analysis = AIAnalysisResult(
            business_summary="Summary",
            opportunities=[
                AnalysisOpportunity(
                    issue="Mobile horizontal layout overflow",
                    evidence="Page exceeds 375px width",
                    impact="Impact",
                    recommendation="Fix",
                ),
                AnalysisOpportunity(
                    issue="Unsubstantiated offline marketing loss",
                    evidence="Print banners are losing efficacy",
                    impact="Impact",
                    recommendation="Switch to digital",
                ),
            ],
            recommended_service="Digital Ads",
            pitch_angle="Switch to digital.",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.total_claims == 2
        assert result.verified_claims == 1
        assert result.unverified_claims == 1
        assert result.confidence == "medium"

    def test_low_confidence_below_medium_threshold(self, sample_evidence_items, sample_audit, sample_lead):
        # 1 verified, 3 unverified -> ratio 0.25 (< 0.40) -> low
        analysis = AIAnalysisResult(
            business_summary="Summary",
            opportunities=[
                AnalysisOpportunity(
                    issue="Mobile layout has horizontal overflow",
                    evidence="82px overflow",
                    impact="Impact",
                    recommendation="Fix",
                ),
                AnalysisOpportunity(issue="Hallucinated Claim 1", evidence="E1", impact="I1", recommendation="R1"),
                AnalysisOpportunity(issue="Hallucinated Claim 2", evidence="E2", impact="I2", recommendation="R2"),
                AnalysisOpportunity(issue="Hallucinated Claim 3", evidence="E3", impact="I3", recommendation="R3"),
            ],
            recommended_service="Service",
            pitch_angle="Pitch",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.verified_claims == 1
        assert result.unverified_claims == 3
        assert result.confidence == "low"

    def test_empty_opportunities_clean_audit(self, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Summary",
            opportunities=[],
            recommended_service="SEO",
            pitch_angle="Pitch",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=[],
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.total_claims == 0
        assert result.confidence == "medium"  # site loaded fine

    def test_resilience_with_non_dict_evidence_and_none_values(self, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Summary",
            opportunities=[
                AnalysisOpportunity(
                    issue="Missing contact form",
                    evidence="No form found",
                    impact="Impact",
                    recommendation="Add form",
                )
            ],
            recommended_service="Service",
            pitch_angle="Pitch",
        )

        # Pass invalid types in evidence_items list
        evidence_with_junk = [None, "invalid_str", 12345, {"id": "ev-clean", "finding_title": "Missing contact form"}]

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=evidence_with_junk,
            audit=sample_audit,
            lead=sample_lead,
        )

        assert result.total_claims == 1
        assert result.verified_claims == 1
        assert result.items[0].evidence_id == "ev-clean"

    def test_get_verified_claims_for_messaging(self, sample_evidence_items, sample_audit, sample_lead):
        analysis = AIAnalysisResult(
            business_summary="Summary",
            opportunities=[
                AnalysisOpportunity(
                    issue="Slow initial page response",
                    evidence="4.6s load time",
                    impact="Impact",
                    recommendation="Recommendation",
                ),
                AnalysisOpportunity(
                    issue="Unsubstantiated offline drop",
                    evidence="No data",
                    impact="Impact",
                    recommendation="Recommendation",
                ),
            ],
            recommended_service="Speed",
            pitch_angle="Pitch",
        )

        result = VerificationService.verify_claims(
            analysis_result=analysis,
            evidence_items=sample_evidence_items,
            audit=sample_audit,
            lead=sample_lead,
        )

        verified_only = VerificationService.get_verified_claims_for_messaging(result)
        assert len(verified_only) == 1
        assert verified_only[0].claim == "Slow initial page response"
        assert verified_only[0].status == "verified"

        # None safety
        assert VerificationService.get_verified_claims_for_messaging(None) == []
