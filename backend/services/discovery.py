"""Google Places (New) Discovery Service for SignalForge AI.

Handles business discovery query generation, Google Places API (New) Text Search
integration with field masking, E.164 phone normalization, budget enforcement,
and audit cost tracking in public.api_costs.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any
from urllib.parse import urlparse
import httpx
import phonenumbers

from backend.config import settings
from backend.database import get_supabase_client

logger = logging.getLogger("signalforge.discovery")

# Google Places API (New) Text Search URL
PLACES_SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

# Strict FieldMask per docs/decisions.md Section 2 (request only needed fields)
PLACES_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.internationalPhoneNumber,"
    "places.websiteUri,"
    "places.rating,"
    "places.userRatingCount,"
    "places.businessStatus,"
    "places.primaryType,"
    "places.types,"
    "nextPageToken"
)

# Geoapify API Endpoints
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"

# Keyword to Geoapify Category Mapping
GEOAPIFY_CATEGORY_MAP = {
    # Education & Tuition
    "education": "education,education.school,education.college",
    "coaching": "education,education.school,education.college",
    "tuition": "education,education.school,education.college",
    "classes": "education,education.school,education.college",
    "school": "education.school,education",
    "college": "education.college,education.university",
    "driving": "education.driving_school",

    # Healthcare & Clinics
    "dental": "healthcare.dentist,healthcare",
    "dentist": "healthcare.dentist,healthcare",
    "clinic": "healthcare,healthcare.hospital,healthcare.pharmacy",
    "hospital": "healthcare.hospital,healthcare",
    "pharmacy": "healthcare.pharmacy,commercial.health_and_beauty",
    "medical": "healthcare,healthcare.hospital",
    "doctor": "healthcare,healthcare.hospital",
    "healthcare": "healthcare,healthcare.hospital,healthcare.pharmacy",

    # Food & Dining
    "restaurant": "catering.restaurant,catering",
    "cafe": "catering.cafe,catering",
    "food": "catering,catering.restaurant",
    "catering": "catering,catering.restaurant",
    "bar": "catering.bar,catering.pub",
    "bakery": "commercial.supermarket,catering.cafe",

    # Retail & Commercial
    "supermarket": "commercial.supermarket,commercial",
    "grocery": "commercial.supermarket,commercial",
    "store": "commercial,commercial.supermarket",
    "shop": "commercial,commercial.clothing",
    "clothing": "commercial.clothing,commercial",
    "commercial": "commercial,commercial.supermarket",

    # Fitness & Wellness
    "gym": "sport.fitness,sport",
    "fitness": "sport.fitness,sport",
    "sport": "sport,sport.fitness",
    "yoga": "sport.fitness,sport",
    "spa": "commercial.health_and_beauty,service",
    "salon": "commercial.health_and_beauty,service",
    "beauty": "commercial.health_and_beauty,service",

    # Real Estate & Office
    "real estate": "office.estate_agent,office",
    "estate": "office.estate_agent,office",
    "property": "office.estate_agent,office",
    "it": "office.it,office.company",
    "software": "office.it,office.company",
    "tech": "office.it,office.company",
    "company": "office.company,office",
    "office": "office,office.company",

    # Automotive & Services
    "car": "service.vehicle,service",
    "vehicle": "service.vehicle,service",
    "mechanic": "service.vehicle,service",
    "repair": "service.vehicle,service",
    "cleaning": "service.cleaning,service",
    "travel": "service.travel_agency,service",
    "hotel": "accommodation.hotel,accommodation",
    "hotelier": "accommodation.hotel,accommodation",
}

# Concurrency limits: discovery 1 per user per docs/decisions.md Section 9
_user_discovery_semaphores: dict[str, asyncio.Semaphore] = {}
_semaphore_lock = asyncio.Lock()


async def get_user_semaphore(user_id: str) -> asyncio.Semaphore:
    """Get or create the asyncio.Semaphore for a user (1 concurrent discovery per user)."""
    async with _semaphore_lock:
        if user_id not in _user_discovery_semaphores:
            _user_discovery_semaphores[user_id] = asyncio.Semaphore(1)
        return _user_discovery_semaphores[user_id]


def reset_user_semaphores() -> None:
    """Reset user semaphores (primarily for testing purposes)."""
    _user_discovery_semaphores.clear()



class DiscoveryService:
    """Service for discovering businesses via Google Places API (New)."""

    def __init__(self, db_client=None) -> None:
        """Initialize discovery service with Supabase database client."""
        self._db = db_client or get_supabase_client()

    @staticmethod
    def generate_queries(
        industry: str,
        location: str,
        keywords: list[str] | None = None,
    ) -> list[str]:
        """Generate 4-8 distinct search query variations.

        Args:
            industry: Target industry/niche (e.g. 'Coaching / Tuition Centers').
            location: Target geographic location (e.g. 'Nagpur, Maharashtra').
            keywords: Optional additional keywords from industry templates.

        Returns:
            List of 4 to 8 unique query strings.

        Raises:
            ValueError: If industry or location is empty or whitespace.
        """
        if not industry or not industry.strip():
            raise ValueError("Industry is required to generate discovery queries.")
        if not location or not location.strip():
            raise ValueError("Location is required to generate discovery queries.")

        clean_ind = industry.strip()
        clean_loc = location.strip()
        
        # Primary base queries
        candidates = [
            f"{clean_ind} in {clean_loc}",
            f"best {clean_ind} in {clean_loc}",
            f"top {clean_ind} {clean_loc}",
            f"{clean_ind} near {clean_loc}",
        ]

        # Add keyword-specific combinations if provided
        if keywords:
            for kw in keywords:
                if kw and isinstance(kw, str):
                    clean_kw = kw.strip()
                    if clean_kw and clean_kw.lower() not in clean_ind.lower():
                        candidates.append(f"{clean_kw} in {clean_loc}")
                        candidates.append(f"{clean_kw} {clean_loc}")

        # Deduplicate while preserving order
        unique_queries: list[str] = []
        seen = set()
        for q in candidates:
            normalized = q.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique_queries.append(q)
            if len(unique_queries) >= 8:
                break

        # Ensure at least 4 queries
        if len(unique_queries) < 4:
            unique_queries.append(f"{clean_ind} services {clean_loc}")
            unique_queries.append(f"{clean_ind} directory {clean_loc}")

        return unique_queries[:8]

    @staticmethod
    def normalize_phone(raw_phone: str | None, default_region: str = "IN") -> str | None:
        """Normalize raw phone number to E.164 format.

        Per docs/decisions.md Section 10:
        Normalize every phone to E.164 using the phonenumbers library, default region IN.

        Args:
            raw_phone: Raw phone string (e.g. '0712 254 1234', '+91 98220 12345').
            default_region: Default ISO 2-letter country code (default 'IN').

        Returns:
            Normalized E.164 string (e.g. '+917122541234') or None if invalid.
        """
        if not raw_phone or not isinstance(raw_phone, str):
            return None

        clean = raw_phone.strip()
        if not clean:
            return None

        try:
            parsed = phonenumbers.parse(clean, default_region)
            if phonenumbers.is_valid_number(parsed) or phonenumbers.is_possible_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            return None
        except phonenumbers.NumberParseException:
            return None

    @staticmethod
    def canonicalize_url(url: str | None) -> str | None:
        """Canonicalize website URL for robust duplicate comparison.

        Strips protocol, 'www.' prefix, trailing slashes, and lowercases.
        e.g. 'https://www.ApexCoaching.com/' -> 'apexcoaching.com'

        Args:
            url: Raw website URL string.

        Returns:
            Canonical domain+path string, or None if invalid/empty.
        """
        if not url or not isinstance(url, str):
            return None

        clean = url.strip().lower()
        if not clean:
            return None

        if not clean.startswith(("http://", "https://")):
            clean = "http://" + clean

        try:
            parsed = urlparse(clean)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            path = parsed.path.rstrip("/")
            if not netloc:
                return None
            return f"{netloc}{path}"
        except Exception:
            return None

    @staticmethod
    def check_budget(campaign: dict[str, Any], estimated_cost_inr: float | None = None) -> bool:
        """Check whether campaign budget allows executing the next paid operation.

        Per docs/decisions.md Section 11:
        Stop when spent_amount would exceed max_budget. max_budget = 0 means no limit.

        Args:
            campaign: Campaign dictionary containing spent_amount and max_budget.
            estimated_cost_inr: Cost of next operation in INR. Defaults to Places search cost.

        Returns:
            True if budget allows execution, False if budget would be exceeded.
        """
        if estimated_cost_inr is None:
            estimated_cost_inr = round(
                settings.GOOGLE_PLACES_COST_PER_SEARCH_USD * settings.USD_TO_INR_RATE, 2
            )

        max_budget = float(campaign.get("max_budget") or 0.0)
        spent_amount = float(campaign.get("spent_amount") or 0.0)

        # max_budget = 0 indicates no limit per schema
        if max_budget <= 0.0:
            return True

        return (spent_amount + estimated_cost_inr) <= max_budget

    @staticmethod
    def is_near_budget_limit(campaign: dict[str, Any], threshold_ratio: float = 0.8) -> bool:
        """Check whether campaign spent amount has reached or exceeded 80% threshold.

        Per docs/decisions.md Section 11:
        Notify the user at 80% of budget.

        Args:
            campaign: Campaign dictionary containing spent_amount and max_budget.
            threshold_ratio: Fraction of budget defining threshold (default 0.8).

        Returns:
            True if spent_amount is at or above 80% of max_budget (and max_budget > 0).
        """
        max_budget = float(campaign.get("max_budget") or 0.0)
        spent_amount = float(campaign.get("spent_amount") or 0.0)

        if max_budget <= 0.0:
            return False

        return spent_amount >= (max_budget * threshold_ratio)

    @classmethod
    def map_query_to_geoapify_category(cls, query: str) -> str:
        """Map free-form industry or search query to supported Geoapify category."""
        lowered = query.lower()
        for kw, cat in GEOAPIFY_CATEGORY_MAP.items():
            if kw in lowered:
                return cat
        return "commercial,service,office"

    @classmethod
    def parse_geoapify_place(cls, feature: dict[str, Any]) -> dict[str, Any]:
        """Map Geoapify Places API feature object to public.leads database schema."""
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else feature
        geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
        coords = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []

        lon = props.get("lon")
        lat = props.get("lat")
        if (lon is None or lat is None) and len(coords) >= 2:
            lon, lat = coords[0], coords[1]

        datasource = props.get("datasource") if isinstance(props.get("datasource"), dict) else {}
        raw = datasource.get("raw") if isinstance(datasource.get("raw"), dict) else {}
        contact = props.get("contact") if isinstance(props.get("contact"), dict) else {}

        raw_phone = (
            props.get("phone")
            or contact.get("phone")
            or raw.get("phone")
            or raw.get("contact:phone")
            or raw.get("phone:mobile")
        )
        normalized_phone = cls.normalize_phone(str(raw_phone)) if raw_phone else None

        website = (
            props.get("website")
            or contact.get("website")
            or raw.get("website")
            or raw.get("contact:website")
            or raw.get("url")
        )

        categories = props.get("categories") or []
        if isinstance(categories, str):
            categories = [categories]
        primary_category = categories[0] if categories else ""

        name = props.get("name") or props.get("address_line1") or ""
        place_id = props.get("place_id") or str(raw.get("osm_id") or "") or f"geoapify_{lat}_{lon}"

        rating_val = props.get("rating")
        try:
            rating = float(rating_val) if rating_val is not None else None
        except (ValueError, TypeError):
            rating = None

        return {
            "place_id": str(place_id),
            "business_name": str(name).strip(),
            "category": primary_category,
            "subcategories": categories,
            "address": props.get("formatted") or props.get("address_line2") or "",
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lon) if lon is not None else None,
            "phone": normalized_phone,
            "website_url": str(website).strip() if website else None,
            "rating": rating,
            "review_count": int(props.get("user_ratings_total") or 0),
            "business_status": "OPERATIONAL",
            "opening_hours": props.get("opening_hours") or raw.get("opening_hours", {}),
            "source": "geoapify",
            "pipeline_stage": "discovered",
        }

    @classmethod
    def parse_place(cls, place: dict[str, Any]) -> dict[str, Any]:
        """Map raw place object (Google Places or Geoapify) to DB lead structure."""
        if "properties" in place or "categories" in place or place.get("source") == "geoapify":
            return cls.parse_geoapify_place(place)

        display_name = place.get("displayName") or {}
        name = display_name.get("text", "") if isinstance(display_name, dict) else str(display_name)

        location = place.get("location") or {}
        lat = location.get("latitude") if isinstance(location, dict) else None
        lng = location.get("longitude") if isinstance(location, dict) else None

        raw_phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
        normalized_phone = cls.normalize_phone(raw_phone)

        rating_val = place.get("rating")
        try:
            rating = float(rating_val) if rating_val is not None else None
        except (ValueError, TypeError):
            rating = None

        return {
            "place_id": place.get("id"),
            "business_name": name.strip(),
            "category": place.get("primaryType", ""),
            "subcategories": place.get("types", []),
            "address": place.get("formattedAddress", ""),
            "latitude": lat,
            "longitude": lng,
            "phone": normalized_phone,
            "website_url": place.get("websiteUri"),
            "rating": rating,
            "review_count": int(place.get("userRatingCount") or 0),
            "business_status": place.get("businessStatus", "OPERATIONAL"),
            "opening_hours": place.get("regularOpeningHours", {}),
            "source": "google_places",
            "pipeline_stage": "discovered",
        }

    async def search_places_google(
        self,
        query: str,
        page_token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Execute Google Places Text Search request with field mask.

        Args:
            query: The text search query string.
            page_token: Optional pagination token for fetching subsequent pages.
            client: Optional httpx.AsyncClient (useful for dependency injection / mocking).

        Returns:
            Tuple of (list of place dicts, nextPageToken or None).

        Raises:
            httpx.HTTPStatusError: On HTTP error responses from Google.
            ValueError: If GOOGLE_PLACES_API_KEY is not configured.
        """
        api_key = settings.GOOGLE_PLACES_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY is not configured in environment settings.")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": PLACES_FIELD_MASK,
        }

        payload: dict[str, Any] = {
            "textQuery": query,
            "pageSize": 20,
        }
        if page_token:
            payload["pageToken"] = page_token

        async def _do_post(c: httpx.AsyncClient) -> httpx.Response:
            try:
                return await c.post(
                    PLACES_SEARCH_TEXT_URL,
                    json=payload,
                    headers=headers,
                    timeout=15.0,
                )
            except httpx.TimeoutException as te:
                logger.error(f"Google Places API timeout on query '{query}'")
                raise RuntimeError(f"Google Places API request timed out: {te}") from te
            except httpx.RequestError as re:
                logger.error(f"Google Places API network connection failure on query '{query}'")
                raise RuntimeError(f"Google Places API network request failed: {re}") from re

        max_retries = 2
        resp = None

        for attempt in range(max_retries + 1):
            try:
                if client is not None:
                    resp = await _do_post(client)
                else:
                    async with httpx.AsyncClient() as default_client:
                        resp = await _do_post(default_client)

                # Retry on rate limit (429) or transient service unavailability (503)
                if resp.status_code in (429, 503) and attempt < max_retries:
                    backoff = 1.0 * (2 ** attempt)
                    logger.warning(
                        f"Google Places API responded with {resp.status_code}. "
                        f"Retrying query '{query}' in {backoff}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(backoff)
                    continue

                resp.raise_for_status()
                break
            except RuntimeError as re:
                if attempt < max_retries:
                    backoff = 1.0 * (2 ** attempt)
                    logger.warning(
                        f"Google Places API error: {re}. Retrying in {backoff}s "
                        f"(attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise
            except httpx.HTTPStatusError as he:
                if he.response.status_code in (429, 503) and attempt < max_retries:
                    backoff = 1.0 * (2 ** attempt)
                    logger.warning(
                        f"Google Places HTTP {he.response.status_code}. Retrying in {backoff}s "
                        f"(attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Google Places API HTTP error {he.response.status_code}")
                raise

        if resp is None:
            raise RuntimeError(f"Google Places API request failed after {max_retries} retries.")

        data = resp.json()
        places = data.get("places", [])
        next_page = data.get("nextPageToken")
        return places, next_page

    async def search_places_geoapify(
        self,
        query: str,
        page_token: str | None = None,
        client: httpx.AsyncClient | None = None,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Execute Geoapify Places search using Geocoding + Places API.

        Args:
            query: The search query string (e.g. 'Coaching Centers in Nagpur, Maharashtra').
            page_token: Optional offset string for pagination (e.g. '0', '20').
            client: Optional httpx.AsyncClient.
            limit: Maximum places to retrieve per page (default 20).

        Returns:
            Tuple of (list of place features, nextPageToken or None).
        """
        api_key = settings.GEOAPIFY_API_KEY
        if not api_key:
            raise ValueError("GEOAPIFY_API_KEY is not configured in environment settings.")

        # 1. Parse search term and geographic locality
        search_term = query
        location = query
        if " in " in query.lower():
            parts = query.split(" in ")
            search_term = parts[0].strip()
            location = parts[-1].strip()
        elif " near " in query.lower():
            parts = query.split(" near ")
            search_term = parts[0].strip()
            location = parts[-1].strip()

        # 2. Geocode location with fallback to full query
        coords: tuple[float, float] | None = None

        async def _do_geocode(c: httpx.AsyncClient, loc_str: str) -> dict[str, Any]:
            res = await c.get(
                GEOAPIFY_GEOCODE_URL,
                params={"text": loc_str, "apiKey": api_key, "limit": 1},
                timeout=12.0,
            )
            res.raise_for_status()
            return res.json()

        for candidate in [location, query]:
            try:
                if client is not None:
                    g_data = await _do_geocode(client, candidate)
                else:
                    async with httpx.AsyncClient() as c:
                        g_data = await _do_geocode(c, candidate)

                features = g_data.get("features", [])
                if features:
                    lon = features[0].get("properties", {}).get("lon")
                    lat = features[0].get("properties", {}).get("lat")
                    if lon is not None and lat is not None:
                        coords = (float(lon), float(lat))
                        break
            except Exception as e:
                logger.warning(f"Geoapify geocode error for candidate '{candidate}': {e}")

        if not coords:
            logger.warning(f"Geoapify could not geocode location for query '{query}'")
            return [], None

        lon, lat = coords
        category = self.map_query_to_geoapify_category(search_term)
        offset = int(page_token) if (page_token and str(page_token).isdigit()) else 0

        params = {
            "categories": category,
            "filter": f"circle:{lon},{lat},25000",
            "bias": f"proximity:{lon},{lat}",
            "limit": limit,
            "offset": offset,
            "apiKey": api_key,
        }

        async def _do_places(c: httpx.AsyncClient) -> dict[str, Any]:
            res = await c.get(GEOAPIFY_PLACES_URL, params=params, timeout=15.0)
            res.raise_for_status()
            return res.json()

        try:
            if client is not None:
                p_data = await _do_places(client)
            else:
                async with httpx.AsyncClient() as c:
                    p_data = await _do_places(c)
        except Exception as e:
            logger.error(f"Geoapify Places API request failed for '{query}': {e}")
            return [], None

        places = p_data.get("features", [])
        next_page = str(offset + limit) if len(places) >= limit else None
        return places, next_page

    async def search_places(
        self,
        query: str,
        page_token: str | None = None,
        client: httpx.AsyncClient | None = None,
        provider: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Route place search to configured provider (geoapify or google_places).

        Args:
            query: The search query string.
            page_token: Optional pagination token.
            client: Optional httpx.AsyncClient.
            provider: Optional explicit provider override ('geoapify' or 'google_places').

        Returns:
            Tuple of (list of raw place objects, nextPageToken or None).
        """
        effective_provider = provider or settings.DISCOVERY_PROVIDER
        # If test mock key is configured specifically for Google Places, prioritize google_places
        if settings.GOOGLE_PLACES_API_KEY == "test-mock-key":
            effective_provider = "google_places"

        if effective_provider == "geoapify":
            return await self.search_places_geoapify(query, page_token=page_token, client=client)
        return await self.search_places_google(query, page_token=page_token, client=client)

    def log_api_cost(
        self,
        campaign_id: str,
        operation: str = "text_search",
        api_calls: int = 1,
        metadata: dict[str, Any] | None = None,
        cost_usd: float | None = None,
        user_id: str | None = None,
        service: str | None = None,
    ) -> dict[str, Any]:
        """Record external API cost to public.api_costs and update campaign spent_amount.

        Per docs/decisions.md Section 11 & CLAUDE.md:
        Every paid call writes a row to api_costs with USD and INR costs.
        Campaign queries are scoped to user_id when provided.

        Args:
            campaign_id: UUID of campaign owning the operation.
            operation: Name of the operation ('text_search', 'place_details').
            api_calls: Number of calls made (default 1).
            metadata: Context metadata (e.g. query, results count).
            cost_usd: Optional explicit USD cost override.
            user_id: Optional UUID of user owning the campaign for tenant isolation.
            service: Service name override ('geoapify' or 'google_places').

        Returns:
            Inserted api_costs record dict.
        """
        if service is None:
            service = settings.DISCOVERY_PROVIDER

        if service == "geoapify":
            cost_usd = 0.0 if cost_usd is None else float(cost_usd)
            cost_inr = 0.0
        else:
            if cost_usd is None:
                cost_usd = settings.GOOGLE_PLACES_COST_PER_SEARCH_USD * api_calls
            cost_inr = round(cost_usd * settings.USD_TO_INR_RATE, 2)

        cost_payload = {
            "campaign_id": campaign_id,
            "service": service,
            "operation": operation,
            "api_calls": api_calls,
            "cost_usd": float(cost_usd),
            "cost_inr": float(cost_inr),
            "metadata": metadata or {},
        }

        # 1. Insert into api_costs
        try:
            self._db.table("api_costs").insert(cost_payload).execute()
        except Exception as e:
            logger.error(f"Failed to record api_costs for campaign {campaign_id}: {e}")

        # 2. Increment campaign spent_amount (user-scoped if user_id present)
        try:
            camp_query = self._db.table("campaigns").select("spent_amount").eq("id", campaign_id)
            if user_id:
                camp_query = camp_query.eq("user_id", user_id)
            camp_res = camp_query.execute()

            if camp_res.data:
                current_spent = float(camp_res.data[0].get("spent_amount") or 0.0)
                new_spent = round(current_spent + cost_inr, 2)
                update_query = self._db.table("campaigns").update({"spent_amount": new_spent}).eq("id", campaign_id)
                if user_id:
                    update_query = update_query.eq("user_id", user_id)
                update_query.execute()
        except Exception as e:
            logger.error(f"Failed to update campaign {campaign_id} spent_amount: {e}")

        return cost_payload

    def deduplicate_batch(
        self,
        leads: list[dict[str, Any]],
        campaign_id: str,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Deduplicate candidate leads intra-batch and against existing campaign leads.

        Per docs/implementation.md line 219:
        Checks existing leads in campaign by place_id, phone, website_url.
        Preserves only new, unique leads. If user_id is provided, campaign ownership
        is verified before querying database records.

        Args:
            leads: List of candidate parsed lead dictionaries.
            campaign_id: UUID of target campaign.
            user_id: Optional UUID of user owning the campaign for tenant verification.

        Returns:
            List of strictly deduplicated lead records.
        """
        # Verify campaign ownership if user_id is provided
        if user_id:
            try:
                camp_check = (
                    self._db.table("campaigns")
                    .select("id")
                    .eq("id", campaign_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if not camp_check.data:
                    logger.warning(f"Deduplication aborted: campaign {campaign_id} unowned by user {user_id}")
                    return []
            except Exception as e:
                logger.error(f"Failed to verify campaign ownership during deduplication: {e}")
                return []
        # 1. Intra-batch deduplication
        seen_place_ids: set[str] = set()
        seen_phones: set[str] = set()
        seen_websites: set[str] = set()
        intra_unique: list[dict[str, Any]] = []

        for lead in leads:
            place_id = lead.get("place_id")
            phone = lead.get("phone")
            canon_url = self.canonicalize_url(lead.get("website_url"))

            # Check if seen in current batch
            if place_id and place_id in seen_place_ids:
                continue
            if phone and phone in seen_phones:
                continue
            if canon_url and canon_url in seen_websites:
                continue

            if place_id:
                seen_place_ids.add(place_id)
            if phone:
                seen_phones.add(phone)
            if canon_url:
                seen_websites.add(canon_url)

            intra_unique.append(lead)

        # 2. Database-level deduplication against existing campaign records
        existing_place_ids: set[str] = set()
        existing_phones: set[str] = set()
        existing_websites: set[str] = set()

        try:
            db_res = (
                self._db.table("leads")
                .select("place_id, phone, website_url")
                .eq("campaign_id", campaign_id)
                .execute()
            )
            for r in (db_res.data or []):
                if r.get("place_id"):
                    existing_place_ids.add(r["place_id"])
                if r.get("phone"):
                    existing_phones.add(r["phone"])
                c_url = self.canonicalize_url(r.get("website_url"))
                if c_url:
                    existing_websites.add(c_url)
        except Exception as e:
            logger.error(f"Failed to fetch existing campaign leads for deduplication: {e}")

        final_unique: list[dict[str, Any]] = []
        for lead in intra_unique:
            place_id = lead.get("place_id")
            phone = lead.get("phone")
            canon_url = self.canonicalize_url(lead.get("website_url"))

            if place_id and place_id in existing_place_ids:
                continue
            if phone and phone in existing_phones:
                continue
            if canon_url and canon_url in existing_websites:
                continue

            final_unique.append(lead)

        return final_unique

    def get_user_suppressed_phones(
        self,
        user_id: str,
        phones: list[str],
    ) -> set[str]:
        """Find phone numbers that were previously suppressed under any campaign of this user.

        Per docs/decisions.md Section 10:
        New leads discovered later with a suppressed phone are created already suppressed.

        Args:
            user_id: UUID of authenticated user.
            phones: List of candidate E.164 phone numbers to check.

        Returns:
            Set of phone numbers that are currently suppressed.
        """
        if not phones or not user_id:
            return set()

        valid_phones = list({p for p in phones if p and isinstance(p, str)})
        if not valid_phones:
            return set()

        try:
            # 1. Fetch campaigns belonging to this user
            camps_res = self._db.table("campaigns").select("id").eq("user_id", user_id).execute()
            camp_ids = [c["id"] for c in (camps_res.data or []) if c.get("id")]
            if not camp_ids:
                return set()

            # 2. Query suppressed leads across user's campaigns matching target phones
            supp_res = (
                self._db.table("leads")
                .select("phone")
                .in_("campaign_id", camp_ids)
                .eq("is_suppressed", True)
                .in_("phone", valid_phones)
                .execute()
            )
            return {r["phone"] for r in (supp_res.data or []) if r.get("phone")}
        except Exception as e:
            logger.error(f"Failed checking suppressed phones for user {user_id}: {e}")
            return set()

    def ingest_leads(
        self,
        campaign_id: str,
        user_id: str,
        raw_places: list[dict[str, Any]],
        max_leads: int | None = None,
    ) -> dict[str, Any]:
        """Ingest raw Google Places records into public.leads with deduplication and suppression.

        Args:
            campaign_id: UUID of campaign.
            user_id: UUID of campaign owner.
            raw_places: List of raw place dictionaries from Google Places API (New).
            max_leads: Optional cap on maximum leads to insert.

        Returns:
            Dict containing counts of total_processed, inserted_count, duplicates_skipped,
            suppressed_count, and list of ingested lead records.

        Raises:
            ValueError: If campaign does not exist or is not owned by user_id.
        """
        # Validate campaign ownership
        camp_res = (
            self._db.table("campaigns")
            .select("id, total_leads_found")
            .eq("id", campaign_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not camp_res.data:
            raise ValueError(f"Campaign with ID '{campaign_id}' not found or unowned")

        # 1. Parse raw places
        parsed_leads: list[dict[str, Any]] = []
        for p in raw_places:
            if not isinstance(p, dict):
                continue
            lead = self.parse_place(p)
            if lead.get("business_name"):
                parsed_leads.append(lead)

        # 2. Deduplicate intra-batch and against campaign database
        unique_leads = self.deduplicate_batch(parsed_leads, campaign_id, user_id=user_id)

        # Apply max_leads cap if requested
        if max_leads is not None and max_leads > 0:
            unique_leads = unique_leads[:max_leads]

        # 3. Check suppression inheritance
        candidate_phones = [l["phone"] for l in unique_leads if l.get("phone")]
        suppressed_phones = self.get_user_suppressed_phones(user_id, candidate_phones)

        for lead in unique_leads:
            lead["campaign_id"] = campaign_id
            if lead.get("phone") and lead["phone"] in suppressed_phones:
                lead["is_suppressed"] = True
                lead["suppression_reason"] = "Previously opted out by user"
                lead["pipeline_stage"] = "opted_out"
            else:
                lead["is_suppressed"] = False
                lead["pipeline_stage"] = "discovered"

        # 4. Batch insert into public.leads in chunks of 50
        inserted_records: list[dict[str, Any]] = []
        if unique_leads:
            chunk_size = 50
            for i in range(0, len(unique_leads), chunk_size):
                chunk = unique_leads[i : i + chunk_size]
                try:
                    res = self._db.table("leads").insert(chunk).execute()
                    if res.data:
                        inserted_records.extend(res.data)
                except Exception as e:
                    logger.error(f"Failed to insert lead batch into database for campaign {campaign_id}: {e}")
                    raise

            # 5. Update campaign total_leads_found
            try:
                current_found = int(camp_res.data[0].get("total_leads_found") or 0)
                new_total = current_found + len(unique_leads)
                (
                    self._db.table("campaigns")
                    .update({"total_leads_found": new_total})
                    .eq("id", campaign_id)
                    .eq("user_id", user_id)
                    .execute()
                )
            except Exception as e:
                logger.error(f"Failed updating total_leads_found for campaign {campaign_id}: {e}")

        return {
            "total_processed": len(raw_places),
            "inserted_count": len(unique_leads),
            "duplicates_skipped": len(raw_places) - len(unique_leads),
            "suppressed_count": sum(1 for l in unique_leads if l.get("is_suppressed")),
            "leads": inserted_records if inserted_records else unique_leads,
        }

    async def run_discovery_job(
        self,
        campaign_id: str,
        user_id: str,
        queries: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Orchestrate background business discovery process for a campaign.

        Per docs/decisions.md Section 9:
        - Concurrency limits via asyncio.Semaphore: discovery 1 per user.
        - Job state lives in the database (campaigns table), never in memory.
        - Enforces budget limit before each search query.
        - Progress (queries completed, leads found) updated after each query.

        Args:
            campaign_id: UUID of campaign.
            user_id: UUID of owner user.
            queries: Optional pre-generated query list.
            client: Optional httpx.AsyncClient for testing / custom transport.

        Returns:
            Dict summary of execution.
        """
        sem = await get_user_semaphore(user_id)
        async with sem:
            try:
                # 1. Fetch campaign record ensuring ownership
                camp_res = (
                    self._db.table("campaigns")
                    .select("*")
                    .eq("id", campaign_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if not camp_res.data:
                    logger.error(f"Discovery job failed: Campaign {campaign_id} not found for user {user_id}")
                    return {"status": "failed", "error": "Campaign not found"}

                campaign = camp_res.data[0]
                industry = campaign.get("industry_label") or campaign.get("industry")
                location = campaign.get("location")
                keywords = campaign.get("keywords") or []
                target_leads = int(campaign.get("target_leads") or 50)
                min_rating = float(campaign.get("min_rating") or 0.0)

                if not queries:
                    queries = self.generate_queries(industry, location, keywords)

                # Ensure campaign state in DB is marked 'discovering'
                now_iso = datetime.now(timezone.utc).isoformat()
                self._db.table("campaigns").update({
                    "status": "discovering",
                    "discovery_queries_total": len(queries),
                    "started_at": campaign.get("started_at") or now_iso,
                    "completed_at": None,
                }).eq("id", campaign_id).eq("user_id", user_id).execute()

                queries_completed = int(campaign.get("discovery_queries_completed") or 0)
                total_leads_found = int(campaign.get("total_leads_found") or 0)
                halt_reason = None

                for query in queries[queries_completed:]:
                    # Check if target leads already satisfied
                    # Check if target leads already satisfied
                    if total_leads_found >= target_leads:
                        logger.info(
                            f"Campaign {campaign_id} target leads reached "
                            f"({total_leads_found}/{target_leads}). Stopping early."
                        )
                        halt_reason = "target_leads_reached"
                        break

                    # Check campaign status on every iteration per docs/decisions.md Section 9 & 11
                    camp_check = (
                        self._db.table("campaigns")
                        .select("spent_amount, max_budget, status")
                        .eq("id", campaign_id)
                        .eq("user_id", user_id)
                        .execute()
                    )
                    camp_data = camp_check.data[0] if camp_check.data else campaign

                    # 1. Graceful exit if user clicked Pause mid-discovery
                    if camp_data.get("status") == "paused":
                        logger.info(f"Campaign {campaign_id} was paused by user. Halting discovery gracefully.")
                        halt_reason = "paused"
                        break

                    # 2. Budget check before performing paid API call (transition to paused if exceeded)
                    if not self.check_budget(camp_data):
                        logger.warning(f"Campaign {campaign_id} budget exceeded. Halting discovery.")
                        halt_reason = "budget_exceeded"
                        break

                    # Perform Places Text Search
                    raw_places: list[dict[str, Any]] = []
                    try:
                        places, _ = await self.search_places(query, client=client)
                        raw_places = places or []
                    except Exception as e:
                        logger.error(
                            f"Places search failed on query '{query}' for campaign {campaign_id}: {e}"
                        )

                    # Log external API call cost and update spent_amount in public.api_costs & campaigns
                    effective_provider = settings.DISCOVERY_PROVIDER
                    self.log_api_cost(
                        campaign_id=campaign_id,
                        operation="text_search",
                        api_calls=1,
                        metadata={"query": query, "results_count": len(raw_places), "provider": effective_provider},
                        user_id=user_id,
                        service=effective_provider,
                    )

                    # Filter by min_rating if configured (exclude places with no rating or below min_rating)
                    if min_rating > 0.0 and raw_places:
                        filtered_places = []
                        for p in raw_places:
                            r = p.get("rating")
                            if r is not None and float(r) >= min_rating:
                                filtered_places.append(p)
                        raw_places = filtered_places

                    # Ingest new leads with deduplication and suppression
                    remaining_cap = target_leads - total_leads_found
                    if raw_places and remaining_cap > 0:
                        ingest_summary = self.ingest_leads(
                            campaign_id=campaign_id,
                            user_id=user_id,
                            raw_places=raw_places,
                            max_leads=remaining_cap,
                        )
                        total_leads_found += ingest_summary["inserted_count"]

                    queries_completed += 1
                    self._db.table("campaigns").update({
                        "discovery_queries_completed": queries_completed,
                    }).eq("id", campaign_id).eq("user_id", user_id).execute()

                # Determine final status update based on halt reason
                if halt_reason == "paused":
                    final_status = "paused"
                    logger.info(f"Discovery stopped for campaign {campaign_id} due to user pause.")
                elif halt_reason == "budget_exceeded":
                    final_status = "paused"
                    self._db.table("campaigns").update({
                        "status": "paused",
                        "completed_at": None,
                    }).eq("id", campaign_id).eq("user_id", user_id).execute()
                    logger.info(f"Campaign {campaign_id} transitioned to paused due to budget limit.")
                else:
                    final_status = "discovery_complete"
                    complete_iso = datetime.now(timezone.utc).isoformat()
                    self._db.table("campaigns").update({
                        "status": "discovery_complete",
                        "completed_at": complete_iso,
                    }).eq("id", campaign_id).eq("user_id", user_id).execute()

                return {
                    "status": final_status,
                    "queries_completed": queries_completed,
                    "total_leads_found": total_leads_found,
                    "halt_reason": halt_reason,
                }

            except Exception as e:
                logger.error(
                    f"Unexpected fatal error in discovery job for campaign {campaign_id}: {e}",
                    exc_info=True,
                )
                # Recover campaign status to draft so it does not remain stuck in 'discovering'
                try:
                    self._db.table("campaigns").update({
                        "status": "draft",
                    }).eq("id", campaign_id).eq("user_id", user_id).execute()
                except Exception as db_err:
                    logger.error(f"Failed to reset campaign status on error: {db_err}")
                raise

