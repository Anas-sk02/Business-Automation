"""Service for automated website auditing, DNS verification, and network probing.

Adheres strictly to docs/decisions.md Sections 5, 8, 9, 11 and docs/implementation.md Stage 3.
"""

import asyncio
from datetime import datetime, timezone
import ipaddress
import logging
import re
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid
from urllib.parse import urljoin, urlparse

import httpx
import phonenumbers

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

# Regular expressions for contact discovery
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:(?:\+|0{0,2})91[\s-]*)?[6789]\d{9}")

# Known social platforms and their domains
SOCIAL_PLATFORMS: Dict[str, Tuple[str, ...]] = {
    "facebook": ("facebook.com", "fb.com"),
    "instagram": ("instagram.com", "instagr.am"),
    "linkedin": ("linkedin.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "twitter": ("twitter.com", "x.com"),
}


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
        tested_url: Optional[str] = None,
        screenshot_url: Optional[str] = None,
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
            tested_url: URL that was probed/tested.
            screenshot_url: Associated Supabase storage screenshot path.

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
            "tested_url": tested_url,
            "screenshot_url": screenshot_url,
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
    ) -> Dict[str, Any]:
        """Capture desktop and mobile screenshots and extract initial DOM data using headless Playwright.

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
            Dict containing screenshot storage paths, DOM metadata, and mobile overflow metrics.
        """
        from playwright.async_api import async_playwright

        results: Dict[str, Any] = {
            "screenshot_desktop_url": None,
            "screenshot_mobile_url": None,
            "mobile_overflow": False,
            "mobile_overflow_pixels": 0,
            "page_title": None,
            "meta_description": None,
            "h1_headings": [],
            "has_alt_texts": True,
            "missing_alt_count": 0,
            "has_contact_form": False,
            "raw_hrefs": [],
            "body_text": "",
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
                    # 1. Desktop Screenshot (1920x1080) & DOM metadata extraction
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

                        # Extract DOM metadata and content while desktop page is active
                        try:
                            dom_eval = await desktop_page.evaluate("""() => {
                                const docEl = document.documentElement;
                                const title = document.title ? document.title.trim().slice(0, 255) : null;
                                let metaDesc = null;
                                const metaTag = document.querySelector('meta[name="description"]') || 
                                                document.querySelector('meta[property="og:description"]');
                                if (metaTag && metaTag.getAttribute('content')) {
                                    metaDesc = metaTag.getAttribute('content').trim().slice(0, 1000);
                                }
                                const h1Nodes = Array.from(document.querySelectorAll('h1'));
                                const h1Headings = h1Nodes.map(h => (h.textContent || '').trim().slice(0, 255)).filter(Boolean).slice(0, 10);

                                const images = Array.from(document.querySelectorAll('img'));
                                const totalImages = images.length;
                                const missingAltCount = images.filter(img => !img.hasAttribute('alt') || !img.getAttribute('alt').trim()).length;
                                const hasAltTexts = totalImages === 0 ? true : missingAltCount === 0;

                                const forms = Array.from(document.querySelectorAll('form'));
                                const hasContactForm = forms.some(f => {
                                    return f.querySelectorAll('input:not([type="hidden"]), textarea, select').length > 0;
                                });

                                const anchorElements = Array.from(document.querySelectorAll('a[href]'));
                                const rawHrefs = anchorElements.map(a => a.getAttribute('href') || '').filter(Boolean).slice(0, 200);
                                const bodyText = document.body ? (document.body.innerText || '') : '';

                                return {
                                    page_title: title,
                                    meta_description: metaDesc,
                                    h1_headings: h1Headings,
                                    has_alt_texts: hasAltTexts,
                                    missing_alt_count: missingAltCount,
                                    has_contact_form: hasContactForm,
                                    raw_hrefs: rawHrefs,
                                    body_text: bodyText.slice(0, 10000)
                                };
                            }""")
                            if isinstance(dom_eval, dict):
                                results.update(dom_eval)
                        except Exception as de_eval:
                            logger.warning(f"Desktop DOM extraction error for '{url}': {de_eval}")

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

                    # 2. Mobile Screenshot (375x812) & Mobile Overflow Check
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

                        # Evaluate mobile horizontal overflow
                        try:
                            overflow_eval = await mobile_page.evaluate("""() => {
                                const docEl = document.documentElement;
                                const scrollWidth = docEl ? docEl.scrollWidth : 0;
                                const clientWidth = docEl ? (docEl.clientWidth || window.innerWidth) : (window.innerWidth || 375);
                                const overflowPixels = Math.max(0, scrollWidth - clientWidth);
                                return {
                                    mobile_overflow: overflowPixels > 5,
                                    mobile_overflow_pixels: overflowPixels
                                };
                            }""")
                            if isinstance(overflow_eval, dict):
                                results["mobile_overflow"] = bool(overflow_eval.get("mobile_overflow", False))
                                results["mobile_overflow_pixels"] = int(overflow_eval.get("mobile_overflow_pixels", 0))
                        except Exception as oe_eval:
                            logger.warning(f"Mobile overflow check error for '{url}': {oe_eval}")

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

    @staticmethod
    def detect_contact_info(body_text: Optional[str], raw_hrefs: Optional[List[str]]) -> Dict[str, Any]:
        """Scan page text and anchor links for phone numbers, emails, and WhatsApp."""
        emails = set()
        phones = set()
        text = str(body_text or "").strip()
        hrefs = raw_hrefs or []

        for href in hrefs:
            if isinstance(href, str) and href.lower().startswith("mailto:"):
                clean = href[7:].split("?")[0].strip().lower()
                if "@" in clean and "." in clean:
                    emails.add(clean)

        if text:
            for match in EMAIL_REGEX.findall(text):
                clean = match.strip().lower()
                if not clean.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".js", ".css", ".ico")):
                    emails.add(clean)

        for href in hrefs:
            if isinstance(href, str) and href.lower().startswith("tel:"):
                clean = href[4:].strip()
                if clean:
                    phones.add(clean)

        if text:
            try:
                for match in phonenumbers.PhoneNumberMatcher(text, "IN"):
                    if phonenumbers.is_possible_number(match.number):
                        phones.add(phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164))
            except Exception as pe:
                logger.debug(f"phonenumbers matcher notice: {pe}")

            if not phones:
                for match in PHONE_REGEX.findall(text):
                    phones.add(match.strip())

        has_whatsapp = any(
            isinstance(h, str)
            and ("wa.me" in h.lower() or "api.whatsapp.com" in h.lower() or h.lower().startswith("whatsapp:"))
            for h in hrefs
        )

        return {
            "has_phone_on_site": len(phones) > 0,
            "has_email_on_site": len(emails) > 0,
            "has_whatsapp_link": has_whatsapp,
            "detected_phones": sorted(list(phones)),
            "detected_emails": sorted(list(emails)),
        }

    @staticmethod
    def extract_social_links(raw_hrefs: Optional[List[str]]) -> List[Dict[str, str]]:
        """Extract outbound social media links categorized by platform."""
        found = {}
        for href in (raw_hrefs or []):
            if not isinstance(href, str):
                continue
            clean = href.strip()
            lower = clean.lower()
            for platform, domains in SOCIAL_PLATFORMS.items():
                if platform not in found:
                    for d in domains:
                        if d in lower:
                            found[platform] = clean
                            break
        return [{"platform": p, "url": u} for p, u in found.items()]

    async def check_broken_links(
        self,
        raw_hrefs: Optional[List[str]],
        base_url: str,
        client: Optional[httpx.AsyncClient] = None,
        max_links: int = 10,
    ) -> Dict[str, Any]:
        """Check internal links for broken HTTP status codes (4xx/5xx).

        Tests up to `max_links` same-origin links with 5s timeout and SSRF protection.
        """
        if not base_url or not raw_hrefs:
            return {"total_internal_links": 0, "broken_links": [], "broken_link_count": 0}

        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower()

        unique_links = []
        seen = set()
        for h in raw_hrefs:
            if not isinstance(h, str) or not h or h.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                continue
            try:
                full_url = urljoin(base_url, h)
                parsed = urlparse(full_url)
                if parsed.scheme.lower() not in ("http", "https"):
                    continue
                if parsed.netloc.lower() == base_domain:
                    clean_url = parsed._replace(fragment="").geturl()
                    if clean_url != base_url and clean_url not in seen:
                        seen.add(clean_url)
                        unique_links.append(clean_url)
            except Exception:
                continue

        total_internal = len(unique_links)
        links_to_test = unique_links[:max_links]
        broken_links = []

        async def _probe_single(c: httpx.AsyncClient, link: str) -> Optional[Dict[str, Any]]:
            host = self.extract_hostname(link)
            if host:
                resolves, _ = await self.check_dns(host)
                if not resolves:
                    return {"url": link, "status": 0, "error": "Blocked or DNS failure"}
            try:
                resp = await c.head(link, timeout=5.0, follow_redirects=True)
                if resp.status_code == 405:
                    resp = await c.get(link, timeout=5.0, follow_redirects=True)

                # SSRF re-check on destination after redirects to block redirect-based SSRF
                final_host = self.extract_hostname(str(resp.url))
                if final_host and final_host.lower() != (host or "").lower():
                    resolves, _ = await self.check_dns(final_host)
                    if not resolves:
                        return {"url": link, "status": 0, "error": "Redirected to prohibited destination"}

                if resp.status_code >= 400:
                    return {"url": link, "status": resp.status_code}
            except Exception as e:
                return {"url": link, "status": 0, "error": str(e)}
            return None

        if links_to_test:
            if client is not None:
                tasks = [_probe_single(client, link) for link in links_to_test]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                async with httpx.AsyncClient(verify=True) as new_client:
                    tasks = [_probe_single(new_client, link) for link in links_to_test]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    broken_links.append(r)

        return {
            "total_internal_links": total_internal,
            "broken_links": broken_links,
            "broken_link_count": len(broken_links),
        }

    def generate_content_evidence(
        self,
        lead_id: str,
        audit_id: Optional[str],
        tested_url: str,
        screenshots_data: Dict[str, Any],
        contact_info: Dict[str, Any],
        link_audit: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate verified evidence items for all content, layout, and link findings.

        Per decisions.md Section 7, all deterministic audit checks explicitly write
        verification_status = 'verified'.
        """
        created_items = []

        # 1. Mobile overflow layout defect
        if screenshots_data.get("mobile_overflow"):
            ov_px = screenshots_data.get("mobile_overflow_pixels", 0)
            item = self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="Mobile layout has horizontal overflow",
                description=(
                    f"Page content exceeds the mobile viewport width by {ov_px}px, "
                    "causing horizontal scrolling and broken mobile usability."
                ),
                evidence_type="audit_check",
                severity="high",
                verification_status="verified",
                evidence_data={
                    "mobile_overflow": True,
                    "overflow_pixels": ov_px,
                    "viewport": "375x812",
                },
                tested_url=tested_url,
                screenshot_url=screenshots_data.get("screenshot_mobile_url"),
            )
            if item:
                created_items.append(item)

        # 2. Broken internal links
        broken_count = link_audit.get("broken_link_count", 0)
        if broken_count > 0:
            item = self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title=f"Detected {broken_count} broken internal links",
                description=(
                    f"Found {broken_count} broken internal links returning 4xx error codes "
                    "or connection failures."
                ),
                evidence_type="link_check",
                severity="medium",
                verification_status="verified",
                evidence_data={
                    "broken_link_count": broken_count,
                    "broken_links": link_audit.get("broken_links", []),
                },
                tested_url=tested_url,
            )
            if item:
                created_items.append(item)

        # 3. Missing image alt attributes
        missing_alt = screenshots_data.get("missing_alt_count", 0)
        if missing_alt > 0:
            item = self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title=f"{missing_alt} images missing alt text",
                description=(
                    f"Found {missing_alt} image elements lacking descriptive alt attributes, "
                    "affecting accessibility and search engine visibility."
                ),
                evidence_type="audit_check",
                severity="low",
                verification_status="verified",
                evidence_data={
                    "missing_alt_count": missing_alt,
                    "has_alt_texts": False,
                },
                tested_url=tested_url,
            )
            if item:
                created_items.append(item)

        # 4. Missing SEO Meta Description
        if not screenshots_data.get("meta_description"):
            item = self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="Missing meta description tag",
                description=(
                    "The webpage lacks a meta description tag, resulting in unoptimized "
                    "snippets in search results."
                ),
                evidence_type="audit_check",
                severity="low",
                verification_status="verified",
                evidence_data={"has_meta_description": False},
                tested_url=tested_url,
            )
            if item:
                created_items.append(item)

        # 5. Missing HTML Title Tag
        if not screenshots_data.get("page_title"):
            item = self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="Missing HTML page title",
                description="The webpage is missing a <title> element in its HTML markup.",
                evidence_type="audit_check",
                severity="low",
                verification_status="verified",
                evidence_data={"has_page_title": False},
                tested_url=tested_url,
            )
            if item:
                created_items.append(item)

        # 6. Absence of contact methods
        has_phone = contact_info.get("has_phone_on_site", False)
        has_email = contact_info.get("has_email_on_site", False)
        has_form = screenshots_data.get("has_contact_form", False)
        has_wa = contact_info.get("has_whatsapp_link", False)
        if not has_phone and not has_email and not has_form and not has_wa:
            item = self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="No direct contact method found on website",
                description=(
                    "The website does not display a visible telephone number, email address, "
                    "contact form, or WhatsApp link for prospective clients."
                ),
                evidence_type="content_scan",
                severity="high",
                verification_status="verified",
                evidence_data={
                    "has_phone": False,
                    "has_email": False,
                    "has_contact_form": False,
                    "has_whatsapp": False,
                },
                tested_url=tested_url,
            )
            if item:
                created_items.append(item)

        # 7. WhatsApp click-to-chat presence
        if has_wa:
            item = self.create_evidence_item(
                lead_id=lead_id,
                audit_id=audit_id,
                finding_title="WhatsApp click-to-chat enabled",
                description="Website provides a direct WhatsApp link for instant customer communication.",
                evidence_type="content_scan",
                severity="info",
                verification_status="verified",
                evidence_data={"has_whatsapp_link": True},
                tested_url=tested_url,
            )
            if item:
                created_items.append(item)

        return created_items

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

        # 3. Capture screenshots and extract DOM metrics if page loads successfully
        screenshots: Dict[str, Any] = {
            "screenshot_desktop_url": None,
            "screenshot_mobile_url": None,
            "mobile_overflow": False,
            "mobile_overflow_pixels": 0,
            "page_title": None,
            "meta_description": None,
            "h1_headings": [],
            "has_alt_texts": True,
            "missing_alt_count": 0,
            "has_contact_form": False,
            "raw_hrefs": [],
            "body_text": "",
        }
        if probe.get("page_loads"):
            target_render_url = probe.get("final_url") or url
            capture_res = await self.capture_screenshots(
                url=target_render_url,
                lead_id=lead_id,
                user_id=user_id,
                audit_id=audit_id,
            )
            screenshots.update(capture_res)

        raw_hrefs = screenshots.get("raw_hrefs") or []
        body_text = screenshots.get("body_text") or ""
        target_url = probe.get("final_url") or url

        # 4. Contact & Social media detection
        contact_info = self.detect_contact_info(body_text, raw_hrefs)
        social_links = self.extract_social_links(raw_hrefs)

        # 5. Check broken internal links
        link_audit = await self.check_broken_links(raw_hrefs, target_url, client=http_client)

        # 6. Generate verified evidence items for all content & DOM findings
        if probe.get("page_loads"):
            self.generate_content_evidence(
                lead_id=lead_id,
                audit_id=audit_id,
                tested_url=target_url,
                screenshots_data=screenshots,
                contact_info=contact_info,
                link_audit=link_audit,
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
                    "mobile_overflow": screenshots.get("mobile_overflow", False),
                    "mobile_overflow_pixels": screenshots.get("mobile_overflow_pixels", 0),
                    "has_contact_form": screenshots.get("has_contact_form", False),
                    "has_phone_on_site": contact_info.get("has_phone_on_site", False),
                    "has_email_on_site": contact_info.get("has_email_on_site", False),
                    "has_whatsapp_link": contact_info.get("has_whatsapp_link", False),
                    "has_social_links": len(social_links) > 0,
                    "social_links": social_links,
                    "page_title": screenshots.get("page_title"),
                    "meta_description": screenshots.get("meta_description"),
                    "h1_headings": screenshots.get("h1_headings", []),
                    "has_alt_texts": screenshots.get("has_alt_texts", True),
                    "missing_alt_count": screenshots.get("missing_alt_count", 0),
                    "total_internal_links": link_audit.get("total_internal_links", 0),
                    "broken_links": link_audit.get("broken_links", []),
                    "broken_link_count": link_audit.get("broken_link_count", 0),
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
            "mobile_overflow": screenshots.get("mobile_overflow", False),
            "mobile_overflow_pixels": screenshots.get("mobile_overflow_pixels", 0),
            "has_contact_form": screenshots.get("has_contact_form", False),
            "has_phone_on_site": contact_info.get("has_phone_on_site", False),
            "has_email_on_site": contact_info.get("has_email_on_site", False),
            "has_whatsapp_link": contact_info.get("has_whatsapp_link", False),
            "has_social_links": len(social_links) > 0,
            "social_links": social_links,
            "page_title": screenshots.get("page_title"),
            "meta_description": screenshots.get("meta_description"),
            "h1_headings": screenshots.get("h1_headings", []),
            "has_alt_texts": screenshots.get("has_alt_texts", True),
            "missing_alt_count": screenshots.get("missing_alt_count", 0),
            "total_internal_links": link_audit.get("total_internal_links", 0),
            "broken_links": link_audit.get("broken_links", []),
            "broken_link_count": link_audit.get("broken_link_count", 0),
        }


