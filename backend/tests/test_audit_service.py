"""Unit and integration tests for Stage 3 Task 1: AuditService & DNS/HTTP Verification."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from backend.services.audit import (
    AUDIT_SEMAPHORE,
    PER_SITE_TIMEOUT_SECONDS,
    AuditService,
)


def test_normalize_url():
    """Verify URL normalization adds scheme and cleans whitespace."""
    assert AuditService.normalize_url("apexclinic.com") == "https://apexclinic.com"
    assert AuditService.normalize_url("http://apexclinic.com/") == "http://apexclinic.com/"
    assert AuditService.normalize_url("https://apexclinic.com/contact/") == "https://apexclinic.com/contact"
    assert AuditService.normalize_url("  https://apexclinic.com?a=1  ") == "https://apexclinic.com?a=1"
    assert AuditService.normalize_url("") is None
    assert AuditService.normalize_url(None) is None


def test_normalize_url_rejects_dangerous_schemes():
    """Verify non-HTTP(S) schemes are strictly rejected to prevent security vulnerabilities."""
    assert AuditService.normalize_url("javascript:alert(1)") is None
    assert AuditService.normalize_url("file:///etc/passwd") is None
    assert AuditService.normalize_url("ftp://ftp.example.com/file") is None
    assert AuditService.normalize_url("data:text/html,<h1>test</h1>") is None


def test_extract_hostname():
    """Verify hostname extraction handles various URL shapes and ports."""
    assert AuditService.extract_hostname("https://example.com/path") == "example.com"
    assert AuditService.extract_hostname("http://sub.example.com:8080/test") == "sub.example.com"
    assert AuditService.extract_hostname("https://nagpur-dental.in") == "nagpur-dental.in"
    assert AuditService.extract_hostname("invalid_url") is None


def test_is_prohibited_ip_ssrf_protection():
    """Verify SSRF detection blocks loopback, private, link-local, and reserved IP ranges."""
    # Loopback
    assert AuditService.is_prohibited_ip("127.0.0.1") is True
    assert AuditService.is_prohibited_ip("127.0.0.2") is True
    assert AuditService.is_prohibited_ip("::1") is True

    # Cloud metadata / link-local
    assert AuditService.is_prohibited_ip("169.254.169.254") is True
    assert AuditService.is_prohibited_ip("169.254.1.1") is True

    # Private RFC 1918
    assert AuditService.is_prohibited_ip("10.0.0.1") is True
    assert AuditService.is_prohibited_ip("172.16.0.1") is True
    assert AuditService.is_prohibited_ip("192.168.1.1") is True

    # Broadcast / zero
    assert AuditService.is_prohibited_ip("0.0.0.0") is True

    # Public valid IP
    assert AuditService.is_prohibited_ip("93.184.216.34") is False
    assert AuditService.is_prohibited_ip("8.8.8.8") is False


@pytest.mark.anyio
async def test_check_dns_success_and_failure():
    """Verify check_dns handles successful resolution, socket errors, and SSRF blocks."""
    with patch.object(AuditService, "resolve_dns_ips") as mock_resolve:
        # 1. Successful resolution to public IP
        mock_resolve.return_value = ["93.184.216.34"]
        resolves, err = await AuditService.check_dns("example.com")
        assert resolves is True
        assert err is None

        # 2. Failed resolution (empty list)
        mock_resolve.return_value = []
        resolves, err = await AuditService.check_dns("nonexistent-domain-xyz-12345.org")
        assert resolves is False
        assert "DNS resolution failed" in err

        # 3. SSRF guard: resolves to private/internal IP
        mock_resolve.return_value = ["169.254.169.254"]
        resolves, err = await AuditService.check_dns("metadata.internal")
        assert resolves is False
        assert "blocked for security" in err


@pytest.mark.anyio
async def test_check_http_and_ssl_success():
    """Verify HTTP probe captures status code, SSL, load time, and final URL."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.url = "https://apexclinic.com/home"
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await AuditService.check_http_and_ssl("https://apexclinic.com", client=mock_client)

    assert result["http_status_code"] == 200
    assert result["page_loads"] is True
    assert result["ssl_valid"] is True
    assert result["final_url"] == "https://apexclinic.com/home"
    assert result["error_message"] is None
    assert isinstance(result["load_time_seconds"], float)


@pytest.mark.anyio
async def test_check_http_and_ssl_ssl_failure():
    """Verify HTTP probe identifies SSL connection failures."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("SSL: CERTIFICATE_VERIFY_FAILED"))

    result = await AuditService.check_http_and_ssl("https://expired-ssl.com", client=mock_client)

    assert result["http_status_code"] is None
    assert result["page_loads"] is False
    assert result["ssl_valid"] is False
    assert "Connection failed" in result["error_message"]


@pytest.mark.anyio
async def test_check_http_and_ssl_timeout():
    """Verify HTTP probe captures timeout gracefully without crashing."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Read timed out"))

    result = await AuditService.check_http_and_ssl("https://slow-site.com", client=mock_client)

    assert result["http_status_code"] is None
    assert result["page_loads"] is False
    assert "timed out" in result["error_message"]


def test_concurrency_semaphore_and_timeout_constants():
    """Verify decisions.md Section 9 limits: semaphore = 5, timeout = 60s."""
    assert AUDIT_SEMAPHORE._value == 5
    assert PER_SITE_TIMEOUT_SECONDS == 60.0


@pytest.mark.anyio
async def test_audit_lead_without_website():
    """Verify leads with no website skip network probes and advance to researched stage."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "lead-123", "website_url": None, "campaigns": {"user_id": "user-456"}}]
    )
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    service = AuditService(db_client=mock_db)
    result = await service.audit_lead_website(lead_id="lead-123", user_id="user-456")

    assert result["status"] == "completed"
    assert result["has_website"] is False

    calls = mock_db.table("leads").update.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0]["pipeline_stage"] == "researched"

    evidence_calls = mock_db.table("evidence_items").insert.call_args_list
    assert len(evidence_calls) == 1
    assert evidence_calls[0][0][0]["finding_title"] == "No website found for this business"
    assert evidence_calls[0][0][0]["verification_status"] == "verified"


@pytest.mark.anyio
async def test_audit_lead_dns_failure():
    """Verify DNS failure gracefully records failed audit and transitions lead to researched."""
    mock_db = MagicMock()
    lead_data = {
        "id": "lead-789",
        "website_url": "https://broken-domain-fake.org",
        "campaigns": {"user_id": "user-456"},
    }
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-999"}])
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    service = AuditService(db_client=mock_db)

    with patch.object(service, "check_dns", return_value=(False, "DNS resolution failed")):
        result = await service.audit_lead_website(lead_id="lead-789", user_id="user-456")

    assert result["status"] == "failed"
    assert "DNS resolution failed" in result["error_message"]

    lead_update_calls = mock_db.table("leads").update.call_args_list
    assert lead_update_calls[-1][0][0]["pipeline_stage"] == "researched"


@pytest.mark.anyio
async def test_audit_lead_timeout_handling():
    """Verify audit timeout after 60s transitions status to timeout and stage to researched."""
    mock_db = MagicMock()
    lead_data = {
        "id": "lead-timeout",
        "website_url": "https://hangs-forever.com",
        "campaigns": {"user_id": "user-456"},
    }
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-timeout-1"}])
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    service = AuditService(db_client=mock_db)

    async def fake_slow_probe(*args, **kwargs):
        raise asyncio.TimeoutError()

    with patch.object(service, "_run_probes", side_effect=fake_slow_probe):
        result = await service.audit_lead_website(lead_id="lead-timeout", user_id="user-456")

    assert result["status"] == "timeout"
    assert "timed out after 60" in result["error_message"]

    lead_update_calls = mock_db.table("leads").update.call_args_list
    assert lead_update_calls[-1][0][0]["pipeline_stage"] == "researched"


@pytest.mark.anyio
async def test_audit_lead_unowned_raises_value_error():
    """Verify tenant isolation: requesting audit on unowned lead raises ValueError."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    service = AuditService(db_client=mock_db)
    with pytest.raises(ValueError, match="not found or unowned"):
        await service.audit_lead_website(lead_id="lead-attacker", user_id="user-victim")


def test_create_evidence_item_database_error_handling():
    """Verify create_evidence_item catches database errors gracefully and returns None."""
    mock_db = MagicMock()
    mock_db.table.return_value.insert.side_effect = Exception("Database connection failure")

    service = AuditService(db_client=mock_db)
    res = service.create_evidence_item(
        lead_id="lead-1",
        audit_id="audit-1",
        finding_title="Test Finding",
        description="Test Desc",
    )
    assert res is None


@pytest.mark.anyio
async def test_audit_lead_full_success_with_screenshots():
    """Verify end-to-end audit success on an active website with screenshots."""
    mock_db = MagicMock()
    lead_data = {
        "id": "lead-success-1",
        "website_url": "https://apexclinic.com",
        "campaigns": {"user_id": "user-123"},
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )
    mock_leads_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    mock_audits_table = MagicMock()
    mock_audits_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-succ-1"}])
    mock_audits_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    def mock_table(name):
        if name == "leads":
            return mock_leads_table
        if name == "website_audits":
            return mock_audits_table
        return MagicMock()

    mock_db.table.side_effect = mock_table

    service = AuditService(db_client=mock_db)

    fake_probe = {
        "http_status_code": 200,
        "ssl_valid": True,
        "page_loads": True,
        "load_time_seconds": 1.25,
        "final_url": "https://apexclinic.com/",
        "error_message": None,
    }

    fake_screenshots = {
        "screenshot_desktop_url": "user-123/lead-success-1/uuid_desktop.png",
        "screenshot_mobile_url": "user-123/lead-success-1/uuid_mobile.png",
    }

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch.object(service, "check_http_and_ssl", return_value=fake_probe):
            with patch.object(service, "capture_screenshots", return_value=fake_screenshots):
                result = await service.audit_lead_website(
                    lead_id="lead-success-1",
                    user_id="user-123",
                )

    assert result["status"] == "completed"
    assert result["error_message"] is None

    # Check lead reached 'researched' stage
    lead_update_calls = mock_leads_table.update.call_args_list
    assert lead_update_calls[-1][0][0]["pipeline_stage"] == "researched"

    # Check audit record was updated with screenshot URLs
    audit_update_calls = mock_audits_table.update.call_args_list
    latest_audit_update = audit_update_calls[-1][0][0]
    assert latest_audit_update["status"] == "completed"
    assert latest_audit_update["screenshot_desktop_url"] == "user-123/lead-success-1/uuid_desktop.png"
    assert latest_audit_update["screenshot_mobile_url"] == "user-123/lead-success-1/uuid_mobile.png"

