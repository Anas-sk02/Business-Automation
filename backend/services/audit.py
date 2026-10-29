"""Service for automated website auditing, DNS verification, and network probing.

Adheres strictly to docs/decisions.md Sections 5, 8, 9, 11 and docs/implementation.md Stage 3.
"""

import asyncio
from datetime import datetime, timezone
import ipaddress
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid
from urllib.parse import urlparse

import httpx

from backend.database import get_supabase_client

logger = logging.getLogger("signalforge.audit")

# Global semaphore restricting concurrent audits per decisions.md Section 9
AUDIT_SEMAPHORE = asyncio.Semaphore(5)

# Per-site audit execution timeout per decisions.md Section 9
PER_SITE_TIMEOUT_SECONDS = 60.0

# HTTP probe timeout
PROBE_HTTP_TIMEOUT_SECONDS = 15.0

# Screenshot Viewport Constants per docs/prd.md F4.2 & F4.3
DESKTOP_VIEWPORT = {"width": 1920, "height": 1080}
MOBILE_VIEWPORT = {"width": 375, "height": 812}
SCREENSHOTS_BUCKET = "screenshots"


class AuditService:
    """Service managing DNS, SSL, HTTP performance, and automated audit checks."""

    def __init__(self, db_client: Any = None):
        """Initialize AuditService with database client dependency injection."""
        self._db = db_client or get_supabase_client()

    @staticmethod
    def normalize_url(raw_url: Optional[str]) -> Optional[str]:
        """Normalize URL ensuring proper protocol and stripped formatting.

        Rejects non-HTTP(S) schemes (e.g. javascript:, file:, ftp:).

        Args:
            raw_url: Input URL string or None.

        Returns:
            Normalized URL with scheme (e.g. 'https://example.com') or None.
        """
        if not raw_url or not str(raw_url).strip():
            return None

        url = str(raw_url).strip()
        parsed_initial = urlparse(url)
        if parsed_initial.scheme and parsed_initial.scheme.lower() not in ("http", "https"):
            logger.warning(f"Rejected unsupported URL scheme: {parsed_initial.scheme}")
            return None

        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"

        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            return None

        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
        reconstructed = f"{parsed.scheme.lower()}://{parsed.netloc}{path}"
        if parsed.query:
            reconstructed = f"{reconstructed}?{parsed.query}"
        return reconstructed

    @staticmethod
    def extract_hostname(url: str) -> Optional[str]:
        """Extract network hostname from a URL.

        Args:
            url: Normalized URL string.

        Returns:
            Extracted hostname (e.g. 'example.com') or None.
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.split(":")[0]
            return netloc if netloc else None
        except Exception:
            return None

    @staticmethod
    def is_prohibited_ip(ip_str: str) -> bool:
        """Check if an IP address belongs to private, loopback, link-local, or reserved ranges.

        Prevents Server-Side Request Forgery (SSRF) attacks against cloud metadata or LAN.

        Args:
            ip_str: IPv4 or IPv6 string.

        Returns:
            True if IP is prohibited/internal, False otherwise.
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or str(ip) in ("0.0.0.0", "::")
            )
        except ValueError:
            return True

    @classmethod
    async def resolve_dns_ips(cls, hostname: str) -> List[str]:
        """Resolve domain name to a list of IP addresses asynchronously.

        Args:
            hostname: Target hostname.

        Returns:
            List of IP address strings.
        """
        if not hostname:
            return []

        # Immediate check for localhost / loopback aliases
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return ["127.0.0.1"]

        loop = asyncio.get_running_loop()
        try:
            addr_info = await loop.getaddrinfo(
                hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
            )
            return [str(item[4][0]) for item in addr_info if item and len(item) > 4 and item[4]]
        except (socket.gaierror, OSError):
            return []
        except Exception as e:
            logger.warning(f"Unexpected DNS resolution error for '{hostname}': {e}")
            return []

    @classmethod
    async def check_dns(cls, hostname: str) -> Tuple[bool, Optional[str]]:
        """Perform non-blocking asynchronous DNS lookup with SSRF IP validation.

        Args:
            hostname: Target domain or hostname.

        Returns:
            Tuple of (resolves: bool, error_reason: Optional[str]).
        """
        if not hostname:
            return False, "Empty hostname"

        ips = await cls.resolve_dns_ips(hostname)
        if not ips:
            return False, f"DNS resolution failed for hostname '{hostname}'"

        # SSRF validation: verify none of the resolved IPs are private or link-local
        for ip in ips:
            if cls.is_prohibited_ip(ip):
                logger.warning(f"SSRF Guard: Hostname '{hostname}' resolved to prohibited IP '{ip}'")
                return False, f"Access to private/internal IP address '{ip}' is blocked for security"

        return True, None

    @classmethod
    async def check_http_and_ssl(
        cls,
        url: str,
        timeout: float = PROBE_HTTP_TIMEOUT_SECONDS,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Probe HTTP response, measure load time, and verify SSL certificate.

        Args:
            url: Normalized URL to probe.
            timeout: Connection/read timeout in seconds.
            client: Optional httpx.AsyncClient for testing/mocking.

        Returns:
            Dictionary containing probe metrics:
                http_status_code (int or None), ssl_valid (bool or None),
                page_loads (bool), load_time_seconds (float or None),
                final_url (str or None), error_message (str or None).
        """
        result: Dict[str, Any] = {
            "http_status_code": None,
            "ssl_valid": None,
            "page_loads": False,
            "load_time_seconds": None,
            "final_url": None,
            "error_message": None,
        }

        start_time = time.monotonic()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36 SignalForge/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async def _do_probe(c: httpx.AsyncClient) -> httpx.Response:
            return await c.get(url, headers=headers, follow_redirects=True, timeout=timeout)

        try:
            if client is not None:
                resp = await _do_probe(client)
            else:
                async with httpx.AsyncClient(verify=True) as new_client:
                    resp = await _do_probe(new_client)

            elapsed = round(time.monotonic() - start_time, 2)
            result["load_time_seconds"] = elapsed
            result["http_status_code"] = resp.status_code
            result["final_url"] = str(resp.url)
            result["page_loads"] = 200 <= resp.status_code < 400
            result["ssl_valid"] = str(resp.url).startswith("https://")
            return result

        except httpx.ConnectError as ce:
            err_str = str(ce).lower()
            is_ssl_err = "certificate" in err_str or "ssl" in err_str
            result["ssl_valid"] = False if is_ssl_err else None
            result["error_message"] = f"Connection failed: {ce}"
            logger.warning(f"HTTP connect error for '{url}': {ce}")
            return result

        except httpx.TimeoutException as te:
            result["load_time_seconds"] = round(time.monotonic() - start_time, 2)
            result["error_message"] = f"HTTP request timed out after {timeout}s: {te}"
            logger.warning(f"HTTP probe timeout for '{url}': {te}")
            return result

        except Exception as e:
            result["error_message"] = f"Probe error: {e}"
            logger.error(f"Unexpected HTTP probe error for '{url}': {e}")
            return result

    def create_evidence_item(
        self,
        lead_id: str,
        audit_id: Optional[str],
        finding_title: str,
        description: str,
        evidence_type: str = "audit_check",
        severity: str = "medium",
        verification_status: str = "verified",
        evidence_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create and store an evidence item row in public.evidence_items.

        Per decisions.md Section 7, deterministic audit checks explicitly write
        verification_status = 'verified'.

        Args:
            lead_id: Lead ID UUID.
            audit_id: Associated website_audit ID or None.
            finding_title: Short title of the finding.
            description: Detailed finding explanation.
            evidence_type: Type of evidence.
            severity: Severity level (critical, high, medium, low, info).
            verification_status: Verification level (verified, unverified, contradicted).
            evidence_data: Additional structured JSON data.

        Returns:
            Inserted evidence record dictionary or None if DB insertion failed.
        """
        payload = {
            "lead_id": lead_id,
            "audit_id": audit_id,
            "finding_title": finding_title,
            "description": description,
            "evidence_type": evidence_type,
            "severity": severity,
            "verification_status": verification_status,
            "evidence_data": evidence_data or {},
        }
        try:
            res = self._db.table("evidence_items").insert(payload).execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            logger.error(f"Failed to insert evidence item for lead {lead_id}: {e}")
            return None

    def upload_screenshot(self, object_path: str, data: bytes) -> bool:
        """Upload raw PNG image bytes to private Supabase screenshots bucket.

        Args:
            object_path: Path inside bucket, e.g. {user_id}/{lead_id}/{uuid}.png.
            data: Raw PNG file bytes.

        Returns:
            True if upload succeeded, False otherwise.
        """
        try:
            res = self._db.storage.from_(SCREENSHOTS_BUCKET).upload(
                path=object_path,
                file=data,
                file_options={"content-type": "image/png", "upsert": "true"},
            )
            return bool(res)
        except Exception as e:
            logger.error(f"Failed to upload screenshot to '{object_path}': {e}")
            return False

    def get_signed_screenshot_url(
        self, object_path: Optional[str], expires_in: int = 3600
    ) -> Optional[str]:
        """Generate a time-limited signed URL for private screenshot object.

        Per decisions.md Section 8, screenshots bucket is private and API
        responses return signed URLs expiring after 1 hour (3600s).

        Args:
            object_path: Path in storage bucket (e.g. {user_id}/{lead_id}/{uuid}.png).
            expires_in: Expiry duration in seconds (default: 3600).

        Returns:
            Signed URL string or None if generation failed.
        """
        if not object_path:
            return None

        try:
            res = self._db.storage.from_(SCREENSHOTS_BUCKET).create_signed_url(
                path=object_path,
                expires_in=expires_in,
            )
            if isinstance(res, dict):
                return res.get("signedURL") or res.get("signedUrl")
            return getattr(res, "signed_url", None) or str(res)
        except Exception as e:
            logger.warning(f"Failed to create signed URL for '{object_path}': {e}")
            return None

    async def capture_screenshots(
        self,
        url: str,
        lead_id: str,
        user_id: str,
        audit_id: Optional[str] = None,
        timeout_ms: int = 25000,
    ) -> Dict[str, Optional[str]]:
        """Capture desktop and mobile screenshots using headless Playwright.

        Per decisions.md Section 8:
        - Viewports: Desktop 1920x1080, Mobile 375x812 (iPhone-like)
        - Files stored in private Supabase 'screenshots' bucket
        - Object paths formatted as: {user_id}/{lead_id}/{uuid}_{viewport}.png
        - File names use UUIDs only, never business names

        Args:
            url: Target website URL.
            lead_id: Target lead UUID.
            user_id: Owning user UUID for multi-tenant isolation.
            audit_id: Associated website_audit UUID.
            timeout_ms: Maximum wait duration in milliseconds for rendering.

        Returns:
            Dict containing 'screenshot_desktop_url' and 'screenshot_mobile_url' storage paths.
        """
        from playwright.async_api import async_playwright

        results: Dict[str, Optional[str]] = {
            "screenshot_desktop_url": None,
            "screenshot_mobile_url": None,
        }

        # SSRF re-verification: ensure target render URL does not point to internal/prohibited IP
        render_host = self.extract_hostname(url)
        if not render_host:
            logger.warning(f"Aborting screenshot: invalid target hostname for '{url}'")
            return results

        resolves, dns_err = await self.check_dns(render_host)
        if not resolves:
            logger.warning(f"Aborting screenshot for '{url}' due to DNS/SSRF block: {dns_err}")
            return results

        # Sanitize folder identifiers to prevent path traversal
        clean_user_id = str(user_id).replace("/", "").replace("\\", "").replace("..", "")
        clean_lead_id = str(lead_id).replace("/", "").replace("\\", "").replace("..", "")

        uuid_token = uuid.uuid4().hex
        desktop_storage_path = f"{clean_user_id}/{clean_lead_id}/{uuid_token}_desktop.png"
        mobile_storage_path = f"{clean_user_id}/{clean_lead_id}/{uuid_token}_mobile.png"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                try:
                    # 1. Desktop Screenshot (1920x1080)
                    try:
                        desktop_page = await browser.new_page(
                            viewport=DESKTOP_VIEWPORT,
                            user_agent=(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/122.0.0.0 Safari/537.36 SignalForge/1.0"
                            ),
                        )
                        await desktop_page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                        desktop_bytes = await desktop_page.screenshot(type="png", full_page=False)
                        await desktop_page.close()

                        if self.upload_screenshot(desktop_storage_path, desktop_bytes):
                            results["screenshot_desktop_url"] = desktop_storage_path
                            self.create_evidence_item(
                                lead_id=lead_id,
                                audit_id=audit_id,
                                finding_title="Desktop screenshot captured",
                                description="Visual capture of desktop layout (1920x1080).",
                                evidence_type="screenshot",
                                severity="info",
                                verification_status="verified",
                                evidence_data={
                                    "storage_path": desktop_storage_path,
                                    "viewport": "desktop",
                                    "width": DESKTOP_VIEWPORT["width"],
                                    "height": DESKTOP_VIEWPORT["height"],
                                },
                            )
                    except Exception as de:
                        logger.warning(f"Desktop screenshot capture failed for '{url}': {de}")

                    # 2. Mobile Screenshot (375x812)
                    try:
                        mobile_context = await browser.new_context(
                            viewport=MOBILE_VIEWPORT,
                            is_mobile=True,
                            has_touch=True,
                            user_agent=(
                                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                                "Version/17.0 Mobile/15E148 Safari/604.1"
                            ),
                        )
                        mobile_page = await mobile_context.new_page()
                        await mobile_page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                        mobile_bytes = await mobile_page.screenshot(type="png", full_page=False)
                        await mobile_context.close()

                        if self.upload_screenshot(mobile_storage_path, mobile_bytes):
                            results["screenshot_mobile_url"] = mobile_storage_path
                            self.create_evidence_item(
                                lead_id=lead_id,
                                audit_id=audit_id,
                                finding_title="Mobile screenshot captured",
                                description="Visual capture of mobile viewport layout (375x812).",
                                evidence_type="screenshot",
                                severity="info",
                                verification_status="verified",
                                evidence_data={
                                    "storage_path": mobile_storage_path,
                                    "viewport": "mobile",
                                    "width": MOBILE_VIEWPORT["width"],
                                    "height": MOBILE_VIEWPORT["height"],
                                },
                            )
                    except Exception as me:
                        logger.warning(f"Mobile screenshot capture failed for '{url}': {me}")

                finally:
                    await browser.close()

        except Exception as e:
            logger.error(f"Playwright screenshot orchestration failed for '{url}': {e}")

        return results

    async def audit_lead_website(
        self,
        lead_id: str,
        user_id: str,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Execute complete website audit pipeline for a single lead.

        Orchestrates:
        1. Website availability check (skip if no website -> 'researched' stage).
        2. Stage transition to 'research_pending'.
        3. DNS resolution probe with SSRF protection.
        4. HTTP & SSL health check.
        5. Evidence creation for findings.
        6. Stage transition to 'researched' and status update.

        Args:
            lead_id: UUID of lead to audit.
            user_id: UUID of owning user (multi-tenant enforcement).
            http_client: Optional httpx.AsyncClient for testing/mocking.

        Returns:
            Dictionary containing audit summary and final status.
        """
        # Fetch lead and verify tenant ownership
        try:
            lead_res = (
                self._db.table("leads")
                .select("*, campaigns!inner(user_id)")
                .eq("id", lead_id)
                .eq("campaigns.user_id", user_id)
                .execute()
            )
        except Exception as e:
            logger.error(f"Database error fetching lead {lead_id}: {e}")
            raise RuntimeError(f"Database error fetching lead: {e}") from e

        if not lead_res.data:
            raise ValueError(f"Lead with ID '{lead_id}' not found or unowned")

        lead = lead_res.data[0]
        raw_website = lead.get("website_url")
        normalized_url = self.normalize_url(raw_website)

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Handle lead with NO website per decisions.md Section 5
        if not normalized_url:
            logger.info(f"Lead {lead_id} has no website. Skipping audit and advancing to 'researched'.")
            self.create_evidence_item(
                lead_id=lead_id,
                audit_id=None,
                finding_title="No website found for this business",
                description="Business listing does not have a website URL registered. Prime candidate for web design outreach.",
                evidence_type="content_scan",
                severity="critical",
                verification_status="verified",
                evidence_data={"has_website": False},
            )
            try:
                self._db.table("leads").update({
                    "pipeline_stage": "researched",
                    "updated_at": now_iso,
                }).eq("id", lead_id).execute()
            except Exception as e:
                logger.error(f"Failed to update lead {lead_id} stage to 'researched': {e}")

            return {
                "lead_id": lead_id,
                "status": "completed",
                "has_website": False,
                "message": "Lead has no website. Marked as researched with evidence.",
            }

        # 2. Transition lead stage to 'research_pending' per decisions.md Section 5
        try:
            self._db.table("leads").update({
                "pipeline_stage": "research_pending",
                "updated_at": now_iso,
            }).eq("id", lead_id).execute()
        except Exception as e:
            logger.error(f"Failed to set lead {lead_id} to 'research_pending': {e}")

        # 3. Create initial website_audits record in DB with status 'running'
        initial_audit_payload = {
            "lead_id": lead_id,
            "tested_url": normalized_url,
            "status": "running",
            "started_at": now_iso,
        }
        try:
            audit_insert = self._db.table("website_audits").insert(initial_audit_payload).execute()
            audit_row = audit_insert.data[0] if audit_insert.data else initial_audit_payload
            audit_id = audit_row.get("id")
        except Exception as e:
            logger.error(f"Failed to create website_audits record for lead {lead_id}: {e}")
            audit_id = None

        async def _execute_audit_with_semaphore() -> Dict[str, Any]:
            async with AUDIT_SEMAPHORE:
                return await self._run_probes(
                    audit_id=audit_id,
                    lead_id=lead_id,
                    user_id=user_id,
                    url=normalized_url,
                    http_client=http_client,
                )

        try:
            # Enforce 60-second execution cap per decisions.md Section 9
            result = await asyncio.wait_for(
                _execute_audit_with_semaphore(),
                timeout=PER_SITE_TIMEOUT_SECONDS,
            )
            final_status = result.get("status", "completed")
            error_msg = result.get("error_message")

        except asyncio.TimeoutError:
            logger.warning(f"Audit for lead {lead_id} timed out after {PER_SITE_TIMEOUT_SECONDS}s")
            final_status = "timeout"
            error_msg = f"Audit timed out after {PER_SITE_TIMEOUT_SECONDS}s"

            self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="Website audit timed out",
                description=f"Server did not respond within {int(PER_SITE_TIMEOUT_SECONDS)} seconds.",
                evidence_type="audit_check",
                severity="high",
                verification_status="verified",
                evidence_data={"timeout_seconds": PER_SITE_TIMEOUT_SECONDS},
            )

            if audit_id:
                try:
                    self._db.table("website_audits").update({
                        "status": "timeout",
                        "error_message": error_msg,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", audit_id).execute()
                except Exception as e:
                    logger.error(f"Failed to update audit status to timeout: {e}")

        except Exception as e:
            logger.error(f"Audit pipeline error for lead {lead_id}: {e}")
            final_status = "failed"
            error_msg = str(e)
            if audit_id:
                try:
                    self._db.table("website_audits").update({
                        "status": "failed",
                        "error_message": error_msg,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", audit_id).execute()
                except Exception as update_err:
                    logger.error(f"Failed to update audit status to failed: {update_err}")

        # 4. Advance lead stage to 'researched' per decisions.md Section 5
        try:
            self._db.table("leads").update({
                "pipeline_stage": "researched",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", lead_id).execute()
        except Exception as e:
            logger.error(f"Failed to update lead {lead_id} stage to 'researched': {e}")

        return {
            "audit_id": audit_id,
            "lead_id": lead_id,
            "status": final_status,
            "error_message": error_msg,
        }

    async def _run_probes(
        self,
        audit_id: Optional[str],
        lead_id: str,
        user_id: str,
        url: str,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Execute DNS, HTTP probe, and visual screenshot sequence for a target URL."""
        hostname = self.extract_hostname(url)
        dns_resolves, dns_error = await self.check_dns(hostname) if hostname else (False, "Missing hostname")

        complete_iso = datetime.now(timezone.utc).isoformat()

        # Handle DNS failure or SSRF block gracefully without crashing
        if not dns_resolves:
            logger.warning(f"DNS/SSRF check failed for lead {lead_id} ({url}): {dns_error}")
            error_message = dns_error or f"DNS resolution failed for hostname '{hostname}'"

            self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="Domain fails DNS resolution or blocked",
                description=error_message,
                evidence_type="audit_check",
                severity="critical",
                verification_status="verified",
                evidence_data={"hostname": hostname, "dns_resolves": False, "error": error_message},
            )

            if audit_id:
                try:
                    self._db.table("website_audits").update({
                        "dns_resolves": False,
                        "status": "failed",
                        "error_message": error_message,
                        "completed_at": complete_iso,
                    }).eq("id", audit_id).execute()
                except Exception as e:
                    logger.error(f"Failed to update audit {audit_id} on DNS failure: {e}")

            return {"status": "failed", "error_message": error_message}

        # DNS resolved, proceed to HTTP and SSL probes
        probe = await self.check_http_and_ssl(url, client=http_client)

        status = "completed" if probe["page_loads"] else "failed"

        # Create evidence items for detected HTTP/SSL issues
        if probe.get("ssl_valid") is False:
            self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="Website lacks valid SSL certificate",
                description="Connection is insecure (HTTP or invalid certificate). Browsers display security warnings.",
                evidence_type="audit_check",
                severity="high",
                verification_status="verified",
                evidence_data={"ssl_valid": False, "tested_url": url},
            )

        if probe.get("load_time_seconds") and probe["load_time_seconds"] > 3.0:
            self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="Slow initial page response",
                description=f"Initial page took {probe['load_time_seconds']}s to load, exceeding the recommended 3.0s threshold.",
                evidence_type="audit_check",
                severity="medium",
                verification_status="verified",
                evidence_data={"load_time_seconds": probe["load_time_seconds"]},
            )

        # 3. Capture screenshots if page loads successfully
        screenshots: Dict[str, Optional[str]] = {
            "screenshot_desktop_url": None,
            "screenshot_mobile_url": None,
        }
        if probe.get("page_loads"):
            target_render_url = probe.get("final_url") or url
            screenshots = await self.capture_screenshots(
                url=target_render_url,
                lead_id=lead_id,
                user_id=user_id,
                audit_id=audit_id,
            )

        if audit_id:
            try:
                self._db.table("website_audits").update({
                    "dns_resolves": True,
                    "http_status_code": probe.get("http_status_code"),
                    "ssl_valid": probe.get("ssl_valid"),
                    "page_loads": probe.get("page_loads", False),
                    "load_time_seconds": probe.get("load_time_seconds"),
                    "final_url": probe.get("final_url"),
                    "screenshot_desktop_url": screenshots.get("screenshot_desktop_url"),
                    "screenshot_mobile_url": screenshots.get("screenshot_mobile_url"),
                    "status": status,
                    "error_message": probe.get("error_message"),
                    "completed_at": complete_iso,
                }).eq("id", audit_id).execute()
            except Exception as e:
                logger.error(f"Failed to update audit {audit_id} with probe results: {e}")

        return {
            "status": status,
            "error_message": probe.get("error_message"),
            "dns_resolves": True,
            "http_status_code": probe.get("http_status_code"),
            "ssl_valid": probe.get("ssl_valid"),
            "page_loads": probe.get("page_loads", False),
            "load_time_seconds": probe.get("load_time_seconds"),
            "final_url": probe.get("final_url"),
            "screenshot_desktop_url": screenshots.get("screenshot_desktop_url"),
            "screenshot_mobile_url": screenshots.get("screenshot_mobile_url"),
        }


