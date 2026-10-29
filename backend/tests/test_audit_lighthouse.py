"""Unit and integration tests for Stage 3 Task 4: Lighthouse Performance/SEO Runner & Graceful Fallback."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.services.audit import AuditService


@pytest.mark.anyio
async def test_run_lighthouse_success_scores_normalized():
    """Verify run_lighthouse parses valid JSON output into 0-100 normalized integer scores."""
    service = AuditService(db_client=MagicMock())

    fake_lighthouse_json = {
        "categories": {
            "performance": {"score": 0.42},
            "seo": {"score": 0.85},
            "accessibility": {"score": 0.92},
            "best-practices": {"score": 0.79},
        }
    }
    stdout_data = json.dumps(fake_lighthouse_json).encode("utf-8")

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout_data, b""))
    mock_proc.returncode = 0

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch("shutil.which", return_value="C:\\npm\\lighthouse.cmd"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                scores = await service.run_lighthouse("https://apexhealth.in")

    assert scores["lighthouse_performance"] == 42
    assert scores["lighthouse_seo"] == 85
    assert scores["lighthouse_accessibility"] == 92
    assert scores["lighthouse_best_practices"] == 79


@pytest.mark.anyio
async def test_run_lighthouse_cli_missing_fallback():
    """Verify run_lighthouse returns None for all scores when lighthouse binary is not on PATH."""
    service = AuditService(db_client=MagicMock())

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch("shutil.which", return_value=None):
            scores = await service.run_lighthouse("https://apexhealth.in")

    assert scores == {
        "lighthouse_performance": None,
        "lighthouse_seo": None,
        "lighthouse_accessibility": None,
        "lighthouse_best_practices": None,
    }


@pytest.mark.anyio
async def test_run_lighthouse_timeout_graceful_fallback():
    """Verify run_lighthouse gracefully kills process and returns None on subprocess timeout."""
    service = AuditService(db_client=MagicMock())

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_proc.kill = MagicMock()

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch("shutil.which", return_value="/usr/local/bin/lighthouse"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                scores = await service.run_lighthouse("https://apexhealth.in", timeout_seconds=1.0)

    mock_proc.kill.assert_called_once()
    assert scores == {
        "lighthouse_performance": None,
        "lighthouse_seo": None,
        "lighthouse_accessibility": None,
        "lighthouse_best_practices": None,
    }


@pytest.mark.anyio
async def test_run_lighthouse_nonzero_exit_code():
    """Verify run_lighthouse handles non-zero exit code by returning None without raising."""
    service = AuditService(db_client=MagicMock())

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"Fatal error running Chrome"))
    mock_proc.returncode = 1

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch("shutil.which", return_value="/usr/local/bin/lighthouse"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                scores = await service.run_lighthouse("https://apexhealth.in")

    assert scores == {
        "lighthouse_performance": None,
        "lighthouse_seo": None,
        "lighthouse_accessibility": None,
        "lighthouse_best_practices": None,
    }


@pytest.mark.anyio
async def test_run_lighthouse_ssrf_blocked():
    """Verify run_lighthouse aborts without spawning subprocess if destination fails SSRF check."""
    service = AuditService(db_client=MagicMock())

    with patch.object(service, "check_dns", return_value=(False, "SSRF block")):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            scores = await service.run_lighthouse("http://169.254.169.254")

    mock_exec.assert_not_called()
    assert scores == {
        "lighthouse_performance": None,
        "lighthouse_seo": None,
        "lighthouse_accessibility": None,
        "lighthouse_best_practices": None,
    }


def test_generate_lighthouse_evidence_verified_status():
    """Verify generated Lighthouse evidence items use verification_status = 'verified' per decisions.md §7."""
    service = AuditService(db_client=MagicMock())

    created_items = []

    def mock_create_evidence(**kwargs):
        created_items.append(kwargs)
        return kwargs

    service.create_evidence_item = MagicMock(side_effect=mock_create_evidence)

    scores = {
        "lighthouse_performance": 35,  # Poor (< 50) -> High severity
        "lighthouse_seo": 68,          # Suboptimal (< 80) -> Medium severity
        "lighthouse_accessibility": 60, # Accessibility issues (< 70) -> Low severity
        "lighthouse_best_practices": 80,
    }

    items = service.generate_lighthouse_evidence(
        lead_id="lead-lh-1",
        audit_id="audit-lh-1",
        tested_url="https://apexhealth.in",
        scores=scores,
    )

    assert len(items) == 3
    for item in created_items:
        # Mandatory requirement from decisions.md §7
        assert item["verification_status"] == "verified"
        assert item["evidence_type"] == "lighthouse_report"
        assert item["lead_id"] == "lead-lh-1"
        assert item["audit_id"] == "audit-lh-1"

    severities = {it["finding_title"]: it["severity"] for it in created_items}
    perf_title = [t for t in severities if "performance" in t.lower()][0]
    seo_title = [t for t in severities if "seo" in t.lower()][0]
    a11y_title = [t for t in severities if "accessibility" in t.lower()][0]

    assert severities[perf_title] == "high"
    assert severities[seo_title] == "medium"
    assert severities[a11y_title] == "low"


def test_generate_lighthouse_evidence_empty_when_no_scores():
    """Verify generate_lighthouse_evidence returns empty list when all scores are None."""
    service = AuditService(db_client=MagicMock())
    scores = {
        "lighthouse_performance": None,
        "lighthouse_seo": None,
        "lighthouse_accessibility": None,
        "lighthouse_best_practices": None,
    }
    items = service.generate_lighthouse_evidence(
        lead_id="lead-empty",
        audit_id="audit-empty",
        tested_url="https://apexhealth.in",
        scores=scores,
    )
    assert items == []


@pytest.mark.anyio
async def test_run_probes_integrates_lighthouse_scores():
    """Verify _run_probes passes Lighthouse scores to website_audits database update."""
    mock_db = MagicMock()
    mock_audits_table = MagicMock()
    mock_audits_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    mock_db.table.return_value = mock_audits_table

    service = AuditService(db_client=mock_db)

    fake_probe = {
        "http_status_code": 200,
        "ssl_valid": True,
        "page_loads": True,
        "load_time_seconds": 0.85,
        "final_url": "https://apexhealth.in/",
        "error_message": None,
    }

    fake_scores = {
        "lighthouse_performance": 48,
        "lighthouse_seo": 82,
        "lighthouse_accessibility": 95,
        "lighthouse_best_practices": 75,
    }

    service.create_evidence_item = MagicMock(return_value={"id": "ev-lh-1"})

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch.object(service, "check_http_and_ssl", return_value=fake_probe):
            with patch.object(service, "capture_screenshots", return_value={"screenshot_desktop_url": "u/l/d.png"}):
                with patch.object(service, "check_broken_links", return_value={"total_internal_links": 0, "broken_links": [], "broken_link_count": 0}):
                    with patch.object(service, "run_lighthouse", return_value=fake_scores):
                        result = await service._run_probes(
                            audit_id="audit-uuid-lh",
                            lead_id="lead-uuid-lh",
                            user_id="user-uuid-lh",
                            url="https://apexhealth.in",
                        )

    assert result["status"] == "completed"
    assert result["lighthouse_performance"] == 48
    assert result["lighthouse_seo"] == 82
    assert result["lighthouse_accessibility"] == 95
    assert result["lighthouse_best_practices"] == 75

    update_payload = mock_audits_table.update.call_args[0][0]
    assert update_payload["lighthouse_performance"] == 48
    assert update_payload["lighthouse_seo"] == 82
    assert update_payload["lighthouse_accessibility"] == 95
    assert update_payload["lighthouse_best_practices"] == 75


@pytest.mark.anyio
async def test_run_lighthouse_rejects_invalid_scheme_or_flag_injection():
    """Verify run_lighthouse rejects non-HTTP schemes and CLI flag injection attempts without spawning subprocess."""
    service = AuditService(db_client=MagicMock())

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        # Flag injection attempt
        res1 = await service.run_lighthouse("--enable-features=NetworkService")
        assert res1 == {
            "lighthouse_performance": None,
            "lighthouse_seo": None,
            "lighthouse_accessibility": None,
            "lighthouse_best_practices": None,
        }
        mock_exec.assert_not_called()

        # Non-HTTP scheme
        res2 = await service.run_lighthouse("javascript:alert(1)")
        assert res2 == {
            "lighthouse_performance": None,
            "lighthouse_seo": None,
            "lighthouse_accessibility": None,
            "lighthouse_best_practices": None,
        }
        mock_exec.assert_not_called()


@pytest.mark.anyio
async def test_run_lighthouse_clamps_scores_between_0_and_100():
    """Verify run_lighthouse strictly clamps parsed category scores to range [0, 100]."""
    service = AuditService(db_client=MagicMock())

    fake_json = {
        "categories": {
            "performance": {"score": 1.25},  # > 1.0 -> should clamp to 100
            "seo": {"score": -0.15},        # < 0.0 -> should clamp to 0
        }
    }
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(json.dumps(fake_json).encode("utf-8"), b""))
    mock_proc.returncode = 0

    with patch.object(service, "check_dns", return_value=(True, None)):
        with patch("shutil.which", return_value="/usr/bin/lighthouse"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                scores = await service.run_lighthouse("https://apexhealth.in")

    assert scores["lighthouse_performance"] == 100
    assert scores["lighthouse_seo"] == 0


def test_generate_lighthouse_evidence_none_scores_handled():
    """Verify generate_lighthouse_evidence handles scores=None without throwing AttributeError."""
    service = AuditService(db_client=MagicMock())
    items = service.generate_lighthouse_evidence(
        lead_id="lead-none",
        audit_id="audit-none",
        tested_url="https://apexhealth.in",
        scores=None,
    )
    assert items == []

