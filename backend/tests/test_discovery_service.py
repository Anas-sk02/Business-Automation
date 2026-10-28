"""Unit tests for DiscoveryService (Task 1: Discovery Service Core & Cost Tracking)."""

from unittest.mock import MagicMock
import httpx
import pytest

from backend.config import settings
from backend.services.discovery import (
    DiscoveryService,
    PLACES_SEARCH_TEXT_URL,
    PLACES_FIELD_MASK,
)


def test_generate_queries_basic():
    """Verify query generation returns between 4 and 8 unique queries."""
    queries = DiscoveryService.generate_queries(
        industry="Coaching / Tuition Centers",
        location="Nagpur, Maharashtra",
    )
    assert 4 <= len(queries) <= 8
    assert all("Coaching / Tuition Centers" in q or "Nagpur" in q for q in queries)
    # Check deduplication
    assert len(queries) == len(set(q.lower() for q in queries))


def test_generate_queries_with_keywords():
    """Verify keyword variations are added and capped at 8."""
    keywords = ["IIT JEE coaching", "NEET preparation", "Commerce tuition", "Science classes"]
    queries = DiscoveryService.generate_queries(
        industry="Education",
        location="Nagpur",
        keywords=keywords,
    )
    assert len(queries) <= 8
    assert any("IIT JEE" in q for q in queries)


def test_normalize_phone_valid_indian_formats():
    """Verify various Indian phone formats normalize to clean E.164."""
    # Mobile with 10 digits
    assert DiscoveryService.normalize_phone("9822012345") == "+919822012345"
    # Mobile with leading 0
    assert DiscoveryService.normalize_phone("09822012345") == "+919822012345"
    # Mobile with +91 and spaces
    assert DiscoveryService.normalize_phone("+91 98220 12345") == "+919822012345"
    # Landline with STD code
    assert DiscoveryService.normalize_phone("0712 2541234") == "+917122541234"


def test_normalize_phone_invalid_and_edge_cases():
    """Verify invalid or empty phone numbers return None safely."""
    assert DiscoveryService.normalize_phone(None) is None
    assert DiscoveryService.normalize_phone("") is None
    assert DiscoveryService.normalize_phone("   ") is None
    assert DiscoveryService.normalize_phone("abc1234") is None
    assert DiscoveryService.normalize_phone("123") is None


def test_check_budget_limits():
    """Verify budget limits and zero-budget behavior per decisions.md."""
    # 0 max_budget means unlimited
    assert DiscoveryService.check_budget({"max_budget": 0, "spent_amount": 5000}) is True

    # Under budget
    assert DiscoveryService.check_budget({"max_budget": 100, "spent_amount": 50}, estimated_cost_inr=3.0) is True

    # At exact threshold
    assert DiscoveryService.check_budget({"max_budget": 100, "spent_amount": 97}, estimated_cost_inr=3.0) is True

    # Exceeding budget
    assert DiscoveryService.check_budget({"max_budget": 100, "spent_amount": 98}, estimated_cost_inr=3.0) is False


def test_parse_place_structure():
    """Verify parsing Google Places API (New) response into lead dictionary."""
    sample_place = {
        "id": "places/ChIJ123456789",
        "displayName": {"text": "Apex Coaching Institute", "languageCode": "en"},
        "primaryType": "school",
        "types": ["school", "point_of_interest", "establishment"],
        "formattedAddress": "123 Wardha Rd, Nagpur, Maharashtra 440015",
        "location": {"latitude": 21.1458, "longitude": 79.0882},
        "internationalPhoneNumber": "+91 98220 12345",
        "websiteUri": "https://apexcoaching.example.com",
        "rating": 4.8,
        "userRatingCount": 142,
        "businessStatus": "OPERATIONAL",
        "regularOpeningHours": {"openNow": True},
    }

    parsed = DiscoveryService.parse_place(sample_place)
    assert parsed["place_id"] == "places/ChIJ123456789"
    assert parsed["business_name"] == "Apex Coaching Institute"
    assert parsed["category"] == "school"
    assert "school" in parsed["subcategories"]
    assert parsed["address"] == "123 Wardha Rd, Nagpur, Maharashtra 440015"
    assert parsed["latitude"] == 21.1458
    assert parsed["longitude"] == 79.0882
    assert parsed["phone"] == "+919822012345"
    assert parsed["website_url"] == "https://apexcoaching.example.com"
    assert parsed["rating"] == 4.8
    assert parsed["review_count"] == 142
    assert parsed["business_status"] == "OPERATIONAL"
    assert parsed["pipeline_stage"] == "discovered"


@pytest.mark.anyio
async def test_search_places_with_mock_client():
    """Verify search_places sends the expected request payload, headers, and field mask."""
    mock_response = httpx.Response(
        status_code=200,
        json={
            "places": [
                {
                    "id": "places/test1",
                    "displayName": {"text": "Test Clinic"},
                    "formattedAddress": "Nagpur",
                }
            ],
            "nextPageToken": "token123",
        },
    )

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == PLACES_SEARCH_TEXT_URL
        assert request.headers["X-Goog-FieldMask"] == PLACES_FIELD_MASK
        assert "X-Goog-Api-Key" in request.headers
        assert request.method == "POST"
        return mock_response

    mock_transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        # Temporarily ensure API key is present for test
        orig_key = settings.GOOGLE_PLACES_API_KEY
        try:
            settings.GOOGLE_PLACES_API_KEY = "test-mock-key"
            service = DiscoveryService()
            places, next_page = await service.search_places("coaching in Nagpur", client=client)
            assert len(places) == 1
            assert places[0]["id"] == "places/test1"
            assert next_page == "token123"
        finally:
            settings.GOOGLE_PLACES_API_KEY = orig_key


def test_log_api_cost():
    """Verify api_costs insert and campaign spent_amount update."""
    mock_db = MagicMock()
    mock_costs_table = MagicMock()
    mock_campaigns_table = MagicMock()

    def table_router(table_name):
        if table_name == "api_costs":
            return mock_costs_table
        if table_name == "campaigns":
            return mock_campaigns_table
        return MagicMock()

    mock_db.table.side_effect = table_router

    # Setup campaign spent_amount select
    select_query = MagicMock()
    eq_query = MagicMock()
    mock_campaigns_table.select.return_value = select_query
    select_query.eq.return_value = eq_query
    eq_query.execute.return_value = MagicMock(data=[{"spent_amount": 10.0}])

    # Setup campaign spent_amount update
    update_query = MagicMock()
    mock_campaigns_table.update.return_value = update_query
    update_query.eq.return_value = MagicMock()

    service = DiscoveryService(db_client=mock_db)
    cost = service.log_api_cost(
        campaign_id="11111111-1111-1111-1111-111111111111",
        operation="text_search",
        api_calls=1,
        metadata={"query": "test query", "results": 5},
    )

    # Cost calculation check
    expected_usd = settings.GOOGLE_PLACES_COST_PER_SEARCH_USD
    expected_inr = round(expected_usd * settings.USD_TO_INR_RATE, 2)
    assert cost["cost_usd"] == expected_usd
    assert cost["cost_inr"] == expected_inr
    assert cost["service"] == "google_places"

    # Verify api_costs insert was called
    mock_costs_table.insert.assert_called_once()
    # Verify campaigns update was called with updated spent_amount
    mock_campaigns_table.update.assert_called_once_with({"spent_amount": round(10.0 + expected_inr, 2)})


def test_generate_queries_empty_validation():
    """Verify ValueError is raised on empty industry or location."""
    with pytest.raises(ValueError, match="Industry is required"):
        DiscoveryService.generate_queries(industry="", location="Nagpur")

    with pytest.raises(ValueError, match="Industry is required"):
        DiscoveryService.generate_queries(industry="   ", location="Nagpur")

    with pytest.raises(ValueError, match="Location is required"):
        DiscoveryService.generate_queries(industry="Clinics", location="")

    with pytest.raises(ValueError, match="Location is required"):
        DiscoveryService.generate_queries(industry="Clinics", location="   ")


def test_is_near_budget_limit():
    """Verify 80% budget limit detection per decisions.md Section 11."""
    # max_budget = 0 means no limit -> should return False
    assert DiscoveryService.is_near_budget_limit({"max_budget": 0, "spent_amount": 5000}) is False

    # Below 80%
    assert DiscoveryService.is_near_budget_limit({"max_budget": 100, "spent_amount": 79.9}) is False

    # Exactly 80%
    assert DiscoveryService.is_near_budget_limit({"max_budget": 100, "spent_amount": 80.0}) is True

    # Above 80%
    assert DiscoveryService.is_near_budget_limit({"max_budget": 100, "spent_amount": 95.0}) is True


@pytest.mark.anyio
async def test_search_places_missing_api_key():
    """Verify ValueError is raised when GOOGLE_PLACES_API_KEY is not configured."""
    orig_key = settings.GOOGLE_PLACES_API_KEY
    try:
        settings.GOOGLE_PLACES_API_KEY = ""
        service = DiscoveryService()
        with pytest.raises(ValueError, match="GOOGLE_PLACES_API_KEY is not configured"):
            await service.search_places("test query")
    finally:
        settings.GOOGLE_PLACES_API_KEY = orig_key


@pytest.mark.anyio
async def test_search_places_timeout_handling():
    """Verify RuntimeError is raised on network timeout without exposing secrets."""
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out", request=request)

    mock_transport = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        orig_key = settings.GOOGLE_PLACES_API_KEY
        try:
            settings.GOOGLE_PLACES_API_KEY = "test-mock-key"
            service = DiscoveryService()
            with pytest.raises(RuntimeError, match="request timed out"):
                await service.search_places("dentists in Nagpur", client=client)
        finally:
            settings.GOOGLE_PLACES_API_KEY = orig_key


def test_log_api_cost_user_scoped():
    """Verify campaign select and update include user_id when provided."""
    mock_db = MagicMock()
    mock_costs_table = MagicMock()
    mock_campaigns_table = MagicMock()

    def table_router(table_name):
        if table_name == "api_costs":
            return mock_costs_table
        if table_name == "campaigns":
            return mock_campaigns_table
        return MagicMock()

    mock_db.table.side_effect = table_router

    # Setup campaign select query chain
    select_query = MagicMock()
    eq_id = MagicMock()
    eq_user = MagicMock()
    mock_campaigns_table.select.return_value = select_query
    select_query.eq.return_value = eq_id
    eq_id.eq.return_value = eq_user
    eq_user.execute.return_value = MagicMock(data=[{"spent_amount": 25.0}])

    # Setup campaign update query chain
    update_query = MagicMock()
    up_id = MagicMock()
    up_user = MagicMock()
    mock_campaigns_table.update.return_value = update_query
    update_query.eq.return_value = up_id
    up_id.eq.return_value = up_user

    service = DiscoveryService(db_client=mock_db)
    service.log_api_cost(
        campaign_id="11111111-1111-1111-1111-111111111111",
        operation="text_search",
        user_id="user-999",
    )

    # Verify user_id was included in select filtering
    select_query.eq.assert_called_with("id", "11111111-1111-1111-1111-111111111111")
    eq_id.eq.assert_called_with("user_id", "user-999")

    # Verify user_id was included in update filtering
    update_query.eq.assert_called_with("id", "11111111-1111-1111-1111-111111111111")
    up_id.eq.assert_called_with("user_id", "user-999")
