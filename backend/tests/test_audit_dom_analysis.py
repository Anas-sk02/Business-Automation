"""Unit and integration tests for Stage 3 Task 3: DOM Analysis, Content Scanning & Evidence Generation."""

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from backend.services.audit import AuditService


def test_detect_contact_info_phones_and_emails():
    """Verify contact info detection finds validated phone numbers, emails, and tel/mailto links."""
    sample_text = (
        "Welcome to Apex Healthcare Nagpur. Call our clinic at +91 98765 43210 or 0712-2555555. "
        "Email our reception at contact@apexhealth.in or support@apexhealth.in. "
        "Do not parse fake_icon@2x.png as email."
    )
    raw_hrefs = [
        "mailto:info@apexhealth.in?subject=Appointment",
        "tel:+919876543210",
        "https://apexhealth.in/about",
        "https://wa.me/919876543210?text=Hi",
    ]

    result = AuditService.detect_contact_info(sample_text, raw_hrefs)

    assert result["has_phone_on_site"] is True
    assert result["has_email_on_site"] is True
    assert result["has_whatsapp_link"] is True

    # Check detected emails include mailto and body text, excluding .png
    assert "info@apexhealth.in" in result["detected_emails"]
    assert "contact@apexhealth.in" in result["detected_emails"]
    assert "fake_icon@2x.png" not in result["detected_emails"]

    # Check detected phones contain normalized or extracted numbers
    assert any("9876543210" in p for p in result["detected_phones"])


def test_detect_contact_info_empty_when_no_contacts():
    """Verify contact info detection returns False and empty lists when no contacts exist."""
    text = "We are an anonymous site with no phone, no email, and no messaging."
    raw_hrefs = ["/about", "/privacy", "/terms"]

    result = AuditService.detect_contact_info(text, raw_hrefs)

    assert result["has_phone_on_site"] is False
    assert result["has_email_on_site"] is False
    assert result["has_whatsapp_link"] is False
    assert result["detected_phones"] == []
    assert result["detected_emails"] == []


def test_extract_social_links():
    """Verify social media link extractor maps and deduplicates known platforms."""
    raw_hrefs = [
        "https://www.facebook.com/apexhealthcare",
        "https://facebook.com/apexhealthcare/share",  # duplicate platform
        "https://instagram.com/apexhealth",
        "https://www.linkedin.com/company/apex-health",
        "https://youtube.com/@apexhealth",
        "https://x.com/apexhealth",
        "https://google.com/search",  # not a social platform
    ]

    social_links = AuditService.extract_social_links(raw_hrefs)

    platforms = {item["platform"]: item["url"] for item in social_links}
    assert len(social_links) == 5
    assert "facebook" in platforms
    assert "instagram" in platforms
    assert "linkedin" in platforms
    assert "youtube" in platforms
    assert "twitter" in platforms
    assert platforms["facebook"] == "https://www.facebook.com/apexhealthcare"


def test_extract_social_links_empty():
    """Verify social media link extractor returns empty list when no social links exist."""
    raw_hrefs = ["/home", "/services", "https://unrelated-domain.com"]
    social_links = AuditService.extract_social_links(raw_hrefs)
    assert social_links == []


@pytest.mark.anyio
async def test_check_broken_links_probes_internal_links():
    """Verify check_broken_links tests internal links and records 404s and errors."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    raw_hrefs = [
        "/about",
        "/contact",
        "/broken-page",
        "https://apexhealth.in/team",
        "https://apexhealth.in/about#team",  # fragment should be stripped and deduplicated with /about
        "https://external-site.com/resource",  # external should be skipped
        "mailto:test@apex.com",  # non-http should be skipped
    ]

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def mock_head(url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        if "broken-page" in url:
            resp.status_code = 404
        else:
            resp.status_code = 200
        return resp

    mock_client.head.side_effect = mock_head

    with patch.object(service, "check_dns", return_value=(True, None)):
        result = await service.check_broken_links(
            raw_hrefs=raw_hrefs,
            base_url="https://apexhealth.in",
            client=mock_client,
            max_links=10,
        )

    assert result["total_internal_links"] == 4  # about, contact, broken-page, team
    assert result["broken_link_count"] == 1
    assert result["broken_links"][0]["url"] == "https://apexhealth.in/broken-page"
    assert result["broken_links"][0]["status"] == 404


@pytest.mark.anyio
async def test_check_broken_links_handles_405_method_not_allowed():
    """Verify check_broken_links falls back to GET when server returns 405 on HEAD."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    raw_hrefs = ["/pricing"]
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    head_resp = MagicMock(spec=httpx.Response)
    head_resp.status_code = 405
    mock_client.head.return_value = head_resp

    get_resp = MagicMock(spec=httpx.Response)
    get_resp.status_code = 200
    mock_client.get.return_value = get_resp

    with patch.object(service, "check_dns", return_value=(True, None)):
        result = await service.check_broken_links(
            raw_hrefs=raw_hrefs,
            base_url="https://apexhealth.in",
            client=mock_client,
        )

    assert result["broken_link_count"] == 0
    mock_client.get.assert_called_once()


@pytest.mark.anyio
async def test_check_broken_links_ssrf_protection():
    """Verify internal links resolving to prohibited IPs are flagged as errors without probing."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    raw_hrefs = ["/internal-admin"]
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch.object(service, "check_dns", return_value=(False, "SSRF blocked")):
        result = await service.check_broken_links(
            raw_hrefs=raw_hrefs,
            base_url="https://apexhealth.in",
            client=mock_client,
        )

    assert result["broken_link_count"] == 1
    assert "Blocked" in result["broken_links"][0]["error"]
    mock_client.head.assert_not_called()


def test_generate_content_evidence_verified_status():
    """Verify all generated evidence items have verification_status = 'verified' per decisions.md §7."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    created_items = []

    def mock_create_evidence(**kwargs):
        created_items.append(kwargs)
        return kwargs

    service.create_evidence_item = MagicMock(side_effect=mock_create_evidence)

    screenshots_data = {
        "mobile_overflow": True,
        "mobile_overflow_pixels": 45,
        "screenshot_mobile_url": "user1/lead1/abc_mobile.png",
        "missing_alt_count": 3,
        "meta_description": None,
        "page_title": "Apex Healthcare",
        "has_contact_form": False,
    }
    contact_info = {
        "has_phone_on_site": False,
        "has_email_on_site": False,
        "has_whatsapp_link": True,
    }
    link_audit = {
        "broken_link_count": 2,
        "broken_links": [{"url": "https://apex.in/404", "status": 404}],
    }

    items = service.generate_content_evidence(
        lead_id="lead-test-1",
        audit_id="audit-test-1",
        tested_url="https://apex.in",
        screenshots_data=screenshots_data,
        contact_info=contact_info,
        link_audit=link_audit,
    )

    assert len(items) >= 4  # mobile overflow, broken links, missing alts, missing meta desc, whatsapp
    # CRITICAL RULE from decisions.md §7: verification_status MUST be 'verified'
    for item in created_items:
        assert item["verification_status"] == "verified"
        assert item["lead_id"] == "lead-test-1"
        assert item["audit_id"] == "audit-test-1"

    titles = [it["finding_title"] for it in created_items]
    assert any("Mobile layout has horizontal overflow" in t for t in titles)
    assert any("broken internal links" in t for t in titles)
    assert any("images missing alt text" in t for t in titles)
    assert any("Missing meta description" in t for t in titles)
    assert any("WhatsApp click-to-chat" in t for t in titles)


@pytest.mark.anyio
async def test_run_probes_full_pipeline_updates_database():
    """Verify _run_probes updates website_audits with all 15 audit fields in Supabase."""
    mock_db = MagicMock()
    mock_audits_table = MagicMock()
    mock_audits_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    mock_db.table.return_value = mock_audits_table

    service = AuditService(db_client=mock_db)

    fake_probe = {
        "http_status_code": 200,
        "ssl_valid": True,
        "page_loads": True,
        "load_time_seconds": 1.10,
        "final_url": "https://apexhealth.in/",
        "error_message": None,
    }

    fake_screenshots = {
        "screenshot_desktop_url": "u1/l1/desktop.png",
        "screenshot_mobile_url": "u1/l1/mobile.png",
        "mobile_overflow": False,
        "mobile_overflow_pixels": 0,
        "page_title": "Apex Health Care",
        "meta_description": "Best clinic in Nagpur",
        "h1_headings": ["Welcome to Apex"],
        "has_alt_texts": True,
        "missing_alt_count": 0,
        "has_contact_form": True,
        "raw_hrefs": [
            "tel:+919876543210",
            "mailto:info@apexhealth.in",
            "https://facebook.com/apex",
            "/about",
        ],
        "body_text": "Call us at +91 98765 43210",
    }

    service.create_evidence_item = MagicMock(return_value={"id": "ev-1"})

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch.object(service, "check_http_and_ssl", return_value=fake_probe):
            with patch.object(service, "capture_screenshots", return_value=fake_screenshots):
                mock_client = AsyncMock(spec=httpx.AsyncClient)
                head_resp = MagicMock(spec=httpx.Response)
                head_resp.status_code = 200
                mock_client.head.return_value = head_resp

                result = await service._run_probes(
                    audit_id="audit-uuid-1",
                    lead_id="lead-uuid-1",
                    user_id="user-uuid-1",
                    url="https://apexhealth.in",
                    http_client=mock_client,
                )

    assert result["status"] == "completed"
    assert result["mobile_overflow"] is False
    assert result["has_contact_form"] is True
    assert result["has_phone_on_site"] is True
    assert result["has_email_on_site"] is True
    assert result["has_social_links"] is True
    assert result["page_title"] == "Apex Health Care"
    assert result["meta_description"] == "Best clinic in Nagpur"
    assert result["h1_headings"] == ["Welcome to Apex"]

    # Verify database update call payload in Supabase
    update_call = mock_audits_table.update.call_args[0][0]
    assert update_call["mobile_overflow"] is False
    assert update_call["mobile_overflow_pixels"] == 0
    assert update_call["has_contact_form"] is True
    assert update_call["has_phone_on_site"] is True
    assert update_call["has_email_on_site"] is True
    assert update_call["has_social_links"] is True
    assert len(update_call["social_links"]) == 1
    assert update_call["social_links"][0]["platform"] == "facebook"
    assert update_call["page_title"] == "Apex Health Care"
    assert update_call["meta_description"] == "Best clinic in Nagpur"
    assert update_call["h1_headings"] == ["Welcome to Apex"]
    assert update_call["has_alt_texts"] is True
    assert update_call["missing_alt_count"] == 0


@pytest.mark.anyio
async def test_check_broken_links_redirect_ssrf_blocked():
    """Verify internal link redirecting to private IP or cloud metadata is flagged and blocked."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    raw_hrefs = ["/redirect-to-metadata"]
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Initial link resolves, but redirect points to cloud metadata IP
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.url = "http://169.254.169.254/latest/meta-data/"
    mock_client.head.return_value = resp

    async def mock_dns(host):
        if host in ("169.254.169.254", "metadata.internal"):
            return False, "SSRF blocked"
        return True, None

    with patch.object(service, "check_dns", side_effect=mock_dns):
        result = await service.check_broken_links(
            raw_hrefs=raw_hrefs,
            base_url="https://apexhealth.in",
            client=mock_client,
        )

    assert result["broken_link_count"] == 1
    assert "Redirected to prohibited destination" in result["broken_links"][0]["error"]


def test_detect_contact_and_social_none_inputs_handled():
    """Verify contact and social helper methods safely accept None inputs without throwing errors."""
    contact = AuditService.detect_contact_info(None, None)
    assert contact["has_phone_on_site"] is False
    assert contact["has_email_on_site"] is False
    assert contact["has_whatsapp_link"] is False
    assert contact["detected_phones"] == []
    assert contact["detected_emails"] == []

    social = AuditService.extract_social_links(None)
    assert social == []


@pytest.mark.anyio
async def test_check_broken_links_none_or_empty_inputs():
    """Verify check_broken_links safely handles empty or None URL/href arguments."""
    service = AuditService(db_client=MagicMock())
    res1 = await service.check_broken_links(None, "https://example.com")
    assert res1 == {"total_internal_links": 0, "broken_links": [], "broken_link_count": 0}

    res2 = await service.check_broken_links(["/test"], "")
    assert res2 == {"total_internal_links": 0, "broken_links": [], "broken_link_count": 0}

