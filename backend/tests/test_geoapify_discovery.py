"""Unit tests for Geoapify Places & Geocoding discovery provider."""

from unittest.mock import MagicMock
import httpx
import pytest

from backend.config import settings
from backend.services.discovery import DiscoveryService


def test_geoapify_category_mapping():
    """Verify keyword mapping returns valid Geoapify categories."""
    assert "education" in DiscoveryService.map_query_to_geoapify_category("Coaching Centers")
    assert "education" in DiscoveryService.map_query_to_geoapify_category("NEET Tuition Classes")
    assert "healthcare.dentist" in DiscoveryService.map_query_to_geoapify_category("Dental Clinic")
    assert "commercial.supermarket" in DiscoveryService.map_query_to_geoapify_category("Supermarket near me")
    assert "catering.restaurant" in DiscoveryService.map_query_to_geoapify_category("Italian Restaurant")
    assert "sport.fitness" in DiscoveryService.map_query_to_geoapify_category("Gym & Fitness")
    # Default fallback
    assert DiscoveryService.map_query_to_geoapify_category("Unknown Enterprise") == "commercial,service,office"


def test_parse_geoapify_place():
    """Verify parsing Geoapify place feature into standard lead dictionary."""
    feature = {
        "properties": {
            "name": "Bishop Cotton School",
            "lon": 79.0820,
            "lat": 21.1498,
            "formatted": "Bishop Cotton School, Sadar, Nagpur, MH, India",
            "categories": ["education", "education.school"],
            "datasource": {
                "raw": {
                    "phone": "+91 712 254 6595",
                    "website": "https://bishopcottonnagpur.org",
                    "osm_id": 12345678,
                }
            },
            "place_id": "geo_bc_12345",
            "rating": 4.5,
            "user_ratings_total": 85,
        }
    }

    lead = DiscoveryService.parse_geoapify_place(feature)
    assert lead["business_name"] == "Bishop Cotton School"
    assert lead["place_id"] == "geo_bc_12345"
    assert lead["category"] == "education"
    assert "education.school" in lead["subcategories"]
    assert lead["address"] == "Bishop Cotton School, Sadar, Nagpur, MH, India"
    assert lead["latitude"] == 21.1498
    assert lead["longitude"] == 79.0820
    assert lead["phone"] == "+917122546595"
    assert lead["website_url"] == "https://bishopcottonnagpur.org"
    assert lead["rating"] == 4.5
    assert lead["review_count"] == 85
    assert lead["source"] == "geoapify"
    assert lead["pipeline_stage"] == "discovered"


def test_parse_place_auto_dispatches_geoapify():
    """Verify DiscoveryService.parse_place routes Geoapify features automatically."""
    feature = {
        "properties": {
            "name": "Apollo Clinic",
            "formatted": "Mumbai, MH",
            "categories": ["healthcare"],
            "place_id": "geo_apollo_999",
        }
    }
    lead = DiscoveryService.parse_place(feature)
    assert lead["business_name"] == "Apollo Clinic"
    assert lead["source"] == "geoapify"
    assert lead["place_id"] == "geo_apollo_999"


@pytest.mark.anyio
async def test_search_places_geoapify_mock():
    """Verify search_places_geoapify geocodes location and queries places."""
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "geocode" in url_str:
            return httpx.Response(
                status_code=200,
                json={
                    "features": [
                        {
                            "properties": {
                                "lon": 79.0820,
                                "lat": 21.1498,
                                "formatted": "Nagpur, Maharashtra",
                            }
                        }
                    ]
                },
            )
        elif "places" in url_str:
            return httpx.Response(
                status_code=200,
                json={
                    "features": [
                        {
                            "properties": {
                                "name": "Apex Coaching",
                                "formatted": "Dharampeth, Nagpur",
                                "categories": ["education"],
                                "place_id": "p_geo_1",
                            }
                        }
                    ]
                },
            )
        return httpx.Response(status_code=404)

    mock_transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        orig_key = settings.GEOAPIFY_API_KEY
        orig_prov = settings.DISCOVERY_PROVIDER
        settings.GEOAPIFY_API_KEY = "test-geoapify-key"
        settings.DISCOVERY_PROVIDER = "geoapify"
        try:
            service = DiscoveryService()
            places, next_page = await service.search_places("Coaching in Nagpur, Maharashtra", client=client)
            assert len(places) == 1
            assert places[0]["properties"]["name"] == "Apex Coaching"
            assert next_page is None
        finally:
            settings.GEOAPIFY_API_KEY = orig_key
            settings.DISCOVERY_PROVIDER = orig_prov


@pytest.mark.anyio
async def test_geoapify_missing_api_key():
    """Verify ValueError is raised if GEOAPIFY_API_KEY is not configured when using geoapify."""
    orig_key = settings.GEOAPIFY_API_KEY
    orig_prov = settings.DISCOVERY_PROVIDER
    settings.GEOAPIFY_API_KEY = ""
    settings.DISCOVERY_PROVIDER = "geoapify"
    try:
        service = DiscoveryService()
        with pytest.raises(ValueError, match="GEOAPIFY_API_KEY is not configured"):
            await service.search_places("Dentists in Mumbai")
    finally:
        settings.GEOAPIFY_API_KEY = orig_key
        settings.DISCOVERY_PROVIDER = orig_prov


def test_log_api_cost_geoapify_is_free():
    """Verify Geoapify discovery operations incur 0.00 USD and 0.00 INR cost."""
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

    select_query = MagicMock()
    eq_query = MagicMock()
    mock_campaigns_table.select.return_value = select_query
    select_query.eq.return_value = eq_query
    eq_query.execute.return_value = MagicMock(data=[{"spent_amount": 0.0}])

    update_query = MagicMock()
    mock_campaigns_table.update.return_value = update_query
    update_query.eq.return_value = MagicMock()

    service = DiscoveryService(db_client=mock_db)
    cost = service.log_api_cost(
        campaign_id="22222222-2222-2222-2222-222222222222",
        operation="text_search",
        api_calls=5,
        metadata={"query": "supermarket in Berlin", "results": 20},
        service="geoapify",
    )

    assert cost["service"] == "geoapify"
    assert cost["cost_usd"] == 0.0
    assert cost["cost_inr"] == 0.0
    mock_costs_table.insert.assert_called_once()
    mock_campaigns_table.update.assert_called_once_with({"spent_amount": 0.0})

