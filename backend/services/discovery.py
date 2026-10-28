"""Google Places (New) Discovery Service for SignalForge AI.

Handles business discovery query generation, Google Places API (New) Text Search
integration with field masking, E.164 phone normalization, budget enforcement,
and audit cost tracking in public.api_costs.
"""

import logging
from typing import Any
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
    def parse_place(cls, place: dict[str, Any]) -> dict[str, Any]:
        """Map Google Places API (New) place object to DB lead structure.

        Args:
            place: Raw place dictionary from Google Places API (New).

        Returns:
            Structured dictionary matching public.leads schema fields.
        """
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

    async def search_places(
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

        if client is not None:
            resp = await _do_post(client)
        else:
            async with httpx.AsyncClient() as default_client:
                resp = await _do_post(default_client)

        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as he:
            logger.error(f"Google Places API HTTP error {he.response.status_code}")
            raise

        data = resp.json()
        places = data.get("places", [])
        next_page = data.get("nextPageToken")
        return places, next_page

    def log_api_cost(
        self,
        campaign_id: str,
        operation: str = "text_search",
        api_calls: int = 1,
        metadata: dict[str, Any] | None = None,
        cost_usd: float | None = None,
        user_id: str | None = None,
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

        Returns:
            Inserted api_costs record dict.
        """
        if cost_usd is None:
            cost_usd = settings.GOOGLE_PLACES_COST_PER_SEARCH_USD * api_calls

        cost_inr = round(cost_usd * settings.USD_TO_INR_RATE, 2)

        cost_payload = {
            "campaign_id": campaign_id,
            "service": "google_places",
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
