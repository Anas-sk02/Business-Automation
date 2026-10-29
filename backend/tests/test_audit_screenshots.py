"""Unit tests for Stage 3 Task 2: Playwright Headless Automation & Screenshot Capture."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.services.audit import (
    DESKTOP_VIEWPORT,
    MOBILE_VIEWPORT,
    SCREENSHOTS_BUCKET,
    AuditService,
)


def test_viewport_constants():
    """Verify viewport dimensions match prd.md F4.2 & F4.3 specifications."""
    assert DESKTOP_VIEWPORT == {"width": 1920, "height": 1080}
    assert MOBILE_VIEWPORT == {"width": 375, "height": 812}
    assert SCREENSHOTS_BUCKET == "screenshots"


def test_upload_screenshot_success():
    """Verify upload_screenshot calls Supabase storage with correct options."""
    mock_db = MagicMock()
    mock_bucket = MagicMock()
    mock_db.storage.from_.return_value = mock_bucket
    mock_bucket.upload.return_value = {"Key": "screenshots/user1/lead1/abc_desktop.png"}

    service = AuditService(db_client=mock_db)
    success = service.upload_screenshot("user1/lead1/abc_desktop.png", b"fake_png_data")

    assert success is True
    mock_db.storage.from_.assert_called_with(SCREENSHOTS_BUCKET)
    mock_bucket.upload.assert_called_once_with(
        path="user1/lead1/abc_desktop.png",
        file=b"fake_png_data",
        file_options={"content-type": "image/png", "upsert": "true"},
    )


def test_upload_screenshot_failure_handled():
    """Verify upload_screenshot handles storage exceptions gracefully."""
    mock_db = MagicMock()
    mock_bucket = MagicMock()
    mock_db.storage.from_.return_value = mock_bucket
    mock_bucket.upload.side_effect = Exception("Storage S3 network error")

    service = AuditService(db_client=mock_db)
    success = service.upload_screenshot("user1/lead1/bad.png", b"data")
    assert success is False


def test_get_signed_screenshot_url_success():
    """Verify get_signed_screenshot_url requests 1-hour signed URL from storage."""
    mock_db = MagicMock()
    mock_bucket = MagicMock()
    mock_db.storage.from_.return_value = mock_bucket
    mock_bucket.create_signed_url.return_value = {
        "signedURL": "https://storage.supabase.co/object/sign/screenshots/u/l/123.png?token=abc"
    }

    service = AuditService(db_client=mock_db)
    signed_url = service.get_signed_screenshot_url("u/l/123.png", expires_in=3600)

    assert signed_url == "https://storage.supabase.co/object/sign/screenshots/u/l/123.png?token=abc"
    mock_bucket.create_signed_url.assert_called_once_with(
        path="u/l/123.png",
        expires_in=3600,
    )


def test_get_signed_screenshot_url_none_or_error():
    """Verify get_signed_screenshot_url returns None on missing path or storage error."""
    mock_db = MagicMock()
    mock_bucket = MagicMock()
    mock_db.storage.from_.return_value = mock_bucket
    mock_bucket.create_signed_url.side_effect = Exception("Not found")

    service = AuditService(db_client=mock_db)
    assert service.get_signed_screenshot_url(None) is None
    assert service.get_signed_screenshot_url("u/l/missing.png") is None


@pytest.mark.anyio
async def test_capture_screenshots_mocked_playwright():
    """Verify capture_screenshots launches browser, navigates both viewports, and uploads."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    # Mock upload_screenshot and create_evidence_item
    service.upload_screenshot = MagicMock(return_value=True)
    service.create_evidence_item = MagicMock(return_value={"id": "ev-1"})

    mock_desktop_page = AsyncMock()
    mock_desktop_page.screenshot = AsyncMock(return_value=b"desktop_bytes")

    mock_mobile_page = AsyncMock()
    mock_mobile_page.screenshot = AsyncMock(return_value=b"mobile_bytes")

    mock_mobile_context = AsyncMock()
    mock_mobile_context.new_page = AsyncMock(return_value=mock_mobile_page)

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_desktop_page)
    mock_browser.new_context = AsyncMock(return_value=mock_mobile_context)

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_playwright
    mock_cm.__aexit__.return_value = None

    with patch("playwright.async_api.async_playwright", return_value=mock_cm):
        result = await service.capture_screenshots(
            url="https://apexclinic.com",
            lead_id="lead-abc",
            user_id="user-xyz",
            audit_id="audit-123",
        )

    # Verify both viewports captured and uploaded
    assert result["screenshot_desktop_url"] is not None
    assert result["screenshot_mobile_url"] is not None
    assert result["screenshot_desktop_url"].startswith("user-xyz/lead-abc/")
    assert result["screenshot_desktop_url"].endswith("_desktop.png")
    assert result["screenshot_mobile_url"].startswith("user-xyz/lead-abc/")
    assert result["screenshot_mobile_url"].endswith("_mobile.png")

    # Verify storage isolation: paths contain user_id and lead_id and NO business name
    assert "apexclinic" not in result["screenshot_desktop_url"]

    # Verify upload was called twice (desktop + mobile)
    assert service.upload_screenshot.call_count == 2
    # Verify evidence items created twice
    assert service.create_evidence_item.call_count == 2


@pytest.mark.anyio
async def test_capture_screenshots_graceful_on_playwright_error():
    """Verify capture_screenshots catches browser launch or navigation errors without crashing."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    with patch("playwright.async_api.async_playwright", side_effect=Exception("Chromium binary missing")):
        result = await service.capture_screenshots(
            url="https://failing-site.com",
            lead_id="lead-1",
            user_id="user-1",
        )

    # Returns empty paths, doesn't raise exception
    assert result["screenshot_desktop_url"] is None
    assert result["screenshot_mobile_url"] is None


@pytest.mark.anyio
async def test_capture_screenshots_blocks_ssrf_prohibited_ip():
    """Verify capture_screenshots aborts without launching browser if URL resolves to internal IP."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)

    # Mock check_dns to flag hostname as SSRF prohibited IP
    with patch.object(service, "check_dns", return_value=(False, "Access to private IP is blocked")):
        with patch("playwright.async_api.async_playwright") as mock_pw:
            result = await service.capture_screenshots(
                url="http://169.254.169.254/latest/meta-data",
                lead_id="lead-sec",
                user_id="user-sec",
            )
            # Browser must never be launched for prohibited IP
            mock_pw.assert_not_called()

    assert result["screenshot_desktop_url"] is None
    assert result["screenshot_mobile_url"] is None


@pytest.mark.anyio
async def test_capture_screenshots_path_sanitization():
    """Verify capture_screenshots sanitizes path traversal attempts in user_id or lead_id."""
    mock_db = MagicMock()
    service = AuditService(db_client=mock_db)
    service.upload_screenshot = MagicMock(return_value=True)
    service.create_evidence_item = MagicMock(return_value={"id": "ev"})

    mock_page = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"data")
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_pw

    with patch("playwright.async_api.async_playwright", return_value=mock_cm):
        result = await service.capture_screenshots(
            url="https://example.com",
            lead_id="../../etc/passwd",
            user_id="../malicious-user",
        )

    desktop_path = result["screenshot_desktop_url"]
    assert desktop_path is not None
    # No path traversal tokens remain
    assert ".." not in desktop_path
    assert not desktop_path.startswith("/")


