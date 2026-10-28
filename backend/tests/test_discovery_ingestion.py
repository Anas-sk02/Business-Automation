"""Unit tests for Stage 2 Task 2: Deduplication, Suppression Inheritance & Lead Ingestion."""

from unittest.mock import MagicMock
import pytest

from backend.services.discovery import DiscoveryService


def test_canonicalize_url_variations():
    """Verify URL canonicalization handles schemes, www prefix, case, and slashes."""
    assert DiscoveryService.canonicalize_url("https://www.ApexCoaching.com/") == "apexcoaching.com"
    assert DiscoveryService.canonicalize_url("http://apexcoaching.com") == "apexcoaching.com"
    assert DiscoveryService.canonicalize_url("WWW.APEXCOACHING.COM/PATH/") == "apexcoaching.com/path"
    assert DiscoveryService.canonicalize_url("apexcoaching.com/contact") == "apexcoaching.com/contact"
    assert DiscoveryService.canonicalize_url(None) is None
    assert DiscoveryService.canonicalize_url("") is None
    assert DiscoveryService.canonicalize_url("   ") is None


def test_deduplicate_batch_intra_batch():
    """Verify intra-batch deduplication discards duplicate place_id, phone, and website."""
    mock_db = MagicMock()
    # Mock empty existing leads in database
    select_query = MagicMock()
    eq_query = MagicMock()
    mock_db.table.return_value.select.return_value = select_query
    select_query.eq.return_value = eq_query
    eq_query.execute.return_value = MagicMock(data=[])

    service = DiscoveryService(db_client=mock_db)

    batch = [
        # Lead 1: base
        {
            "place_id": "place_1",
            "business_name": "Coaching Alpha",
            "phone": "+919822011111",
            "website_url": "https://alpha.com",
        },
        # Lead 2: duplicate place_id
        {
            "place_id": "place_1",
            "business_name": "Coaching Alpha Duplicate",
            "phone": "+919822022222",
            "website_url": "https://different.com",
        },
        # Lead 3: duplicate phone
        {
            "place_id": "place_3",
            "business_name": "Coaching Beta",
            "phone": "+919822011111",
            "website_url": "https://beta.com",
        },
        # Lead 4: duplicate website (with www and trailing slash)
        {
            "place_id": "place_4",
            "business_name": "Coaching Gamma",
            "phone": "+919822033333",
            "website_url": "http://www.alpha.com/",
        },
        # Lead 5: completely unique
        {
            "place_id": "place_5",
            "business_name": "Coaching Delta",
            "phone": "+919822044444",
            "website_url": "https://delta.com",
        },
    ]

    unique = service.deduplicate_batch(batch, campaign_id="camp-123")
    assert len(unique) == 2
    assert unique[0]["business_name"] == "Coaching Alpha"
    assert unique[1]["business_name"] == "Coaching Delta"


def test_deduplicate_batch_against_database():
    """Verify deduplication filters out items matching existing database leads."""
    mock_db = MagicMock()
    select_query = MagicMock()
    eq_query = MagicMock()
    mock_db.table.return_value.select.return_value = select_query
    select_query.eq.return_value = eq_query

    # DB already contains place_10, phone +919822055555, and existing.com
    eq_query.execute.return_value = MagicMock(
        data=[
            {
                "place_id": "place_10",
                "phone": "+919822055555",
                "website_url": "https://existing.com",
            }
        ]
    )

    service = DiscoveryService(db_client=mock_db)

    batch = [
        # Matches existing place_id
        {"place_id": "place_10", "business_name": "Old Place", "phone": "+919822066666", "website_url": "https://new1.com"},
        # Matches existing phone
        {"place_id": "place_11", "business_name": "Old Phone", "phone": "+919822055555", "website_url": "https://new2.com"},
        # Matches existing website
        {"place_id": "place_12", "business_name": "Old Web", "phone": "+919822077777", "website_url": "http://www.existing.com/"},
        # Brand new lead
        {"place_id": "place_13", "business_name": "Fresh Lead", "phone": "+919822088888", "website_url": "https://fresh.com"},
    ]

    unique = service.deduplicate_batch(batch, campaign_id="camp-123")
    assert len(unique) == 1
    assert unique[0]["business_name"] == "Fresh Lead"


def test_get_user_suppressed_phones():
    """Verify suppressed phone checking across campaigns of a user."""
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_leads = MagicMock()

    def router(table_name):
        if table_name == "campaigns":
            return mock_campaigns
        if table_name == "leads":
            return mock_leads
        return MagicMock()

    mock_db.table.side_effect = router

    # Mock user campaigns
    mock_campaigns.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "camp-1"}, {"id": "camp-2"}]
    )

    # Mock suppressed leads query
    (
        mock_leads.select.return_value
        .in_.return_value
        .eq.return_value
        .in_.return_value
        .execute.return_value
    ) = MagicMock(data=[{"phone": "+919822099999"}])

    service = DiscoveryService(db_client=mock_db)
    suppressed = service.get_user_suppressed_phones(
        user_id="user-123",
        phones=["+919822099999", "+919822011111"],
    )

    assert suppressed == {"+919822099999"}


def test_ingest_leads_full_flow():
    """Verify end-to-end ingestion: parsing, deduplication, suppression tagging, insert."""
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_leads = MagicMock()

    def router(table_name):
        if table_name == "campaigns":
            return mock_campaigns
        if table_name == "leads":
            return mock_leads
        return MagicMock()

    mock_db.table.side_effect = router

    # 1. Campaign ownership check: campaign exists with total_leads_found=5
    camp_select = MagicMock()
    camp_eq1 = MagicMock()
    camp_eq2 = MagicMock()
    mock_campaigns.select.return_value = camp_select
    camp_select.eq.return_value = camp_eq1
    camp_eq1.eq.return_value = camp_eq2
    camp_eq2.execute.return_value = MagicMock(data=[{"id": "camp-1", "total_leads_found": 5}])

    # 2. Existing leads in campaign: none
    leads_select = MagicMock()
    leads_eq = MagicMock()
    mock_leads.select.return_value = leads_select
    leads_select.eq.return_value = leads_eq
    leads_eq.execute.return_value = MagicMock(data=[])

    # 3. User campaigns for suppression check
    camp_select.eq.return_value.execute.return_value = MagicMock(data=[{"id": "camp-1"}])

    # 4. Suppressed leads check: +919822099999 is suppressed
    (
        mock_leads.select.return_value
        .in_.return_value
        .eq.return_value
        .in_.return_value
        .execute.return_value
    ) = MagicMock(data=[{"phone": "+919822099999"}])

    # 5. Insert mock
    mock_leads.insert.return_value.execute.return_value = MagicMock(
        data=[
            {"id": "lead-1", "business_name": "Clinic Clean"},
            {"id": "lead-2", "business_name": "Clinic Suppressed"},
        ]
    )

    # 6. Campaign update mock
    camp_update = MagicMock()
    mock_campaigns.update.return_value = camp_update
    camp_update.eq.return_value.eq.return_value.execute.return_value = MagicMock()

    service = DiscoveryService(db_client=mock_db)

    raw_places = [
        # Normal lead
        {
            "id": "places/p1",
            "displayName": {"text": "Clinic Clean"},
            "formattedAddress": "Nagpur",
            "internationalPhoneNumber": "+91 98220 11111",
            "websiteUri": "https://clinicclean.com",
            "rating": 4.5,
        },
        # Suppressed lead (matching suppressed phone)
        {
            "id": "places/p2",
            "displayName": {"text": "Clinic Suppressed"},
            "formattedAddress": "Nagpur",
            "internationalPhoneNumber": "+91 98220 99999",
            "websiteUri": "https://suppressed.com",
            "rating": 4.0,
        },
        # Intra-batch duplicate of p1
        {
            "id": "places/p1",
            "displayName": {"text": "Clinic Clean Duplicate"},
            "formattedAddress": "Nagpur",
            "internationalPhoneNumber": "+91 98220 11111",
        },
    ]

    result = service.ingest_leads(
        campaign_id="camp-1",
        user_id="user-123",
        raw_places=raw_places,
    )

    assert result["total_processed"] == 3
    assert result["inserted_count"] == 2
    assert result["duplicates_skipped"] == 1
    assert result["suppressed_count"] == 1

    # Verify leads insert was called
    mock_leads.insert.assert_called_once()
    inserted_args = mock_leads.insert.call_args[0][0]
    assert len(inserted_args) == 2

    clean_lead = next(l for l in inserted_args if l["business_name"] == "Clinic Clean")
    assert clean_lead["is_suppressed"] is False
    assert clean_lead["pipeline_stage"] == "discovered"

    suppressed_lead = next(l for l in inserted_args if l["business_name"] == "Clinic Suppressed")
    assert suppressed_lead["is_suppressed"] is True
    assert suppressed_lead["pipeline_stage"] == "opted_out"
    assert suppressed_lead["suppression_reason"] == "Previously opted out by user"

    # Verify campaign total_leads_found was updated: 5 existing + 2 new = 7
    mock_campaigns.update.assert_called_with({"total_leads_found": 7})


def test_ingest_leads_unowned_campaign():
    """Verify ValueError is raised if campaign is not owned by user."""
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_db.table.return_value = mock_campaigns

    # Campaign check returns empty
    camp_select = MagicMock()
    camp_eq1 = MagicMock()
    camp_eq2 = MagicMock()
    mock_campaigns.select.return_value = camp_select
    camp_select.eq.return_value = camp_eq1
    camp_eq1.eq.return_value = camp_eq2
    camp_eq2.execute.return_value = MagicMock(data=[])

    service = DiscoveryService(db_client=mock_db)
    with pytest.raises(ValueError, match="not found or unowned"):
        service.ingest_leads(
            campaign_id="unowned-camp",
            user_id="user-456",
            raw_places=[{"displayName": {"text": "Test"}}],
        )


def test_deduplicate_batch_unowned_campaign_guard():
    """Verify deduplicate_batch returns empty list if user_id does not own campaign."""
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_db.table.return_value = mock_campaigns

    # Ownership check returns empty
    camp_select = MagicMock()
    camp_eq1 = MagicMock()
    camp_eq2 = MagicMock()
    mock_campaigns.select.return_value = camp_select
    camp_select.eq.return_value = camp_eq1
    camp_eq1.eq.return_value = camp_eq2
    camp_eq2.execute.return_value = MagicMock(data=[])

    service = DiscoveryService(db_client=mock_db)
    result = service.deduplicate_batch(
        leads=[{"place_id": "p1", "business_name": "Test"}],
        campaign_id="camp-999",
        user_id="unauthorized-user",
    )
    assert result == []


def test_ingest_leads_malformed_items():
    """Verify non-dict items and empty place names are safely ignored."""
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_leads = MagicMock()

    def router(table_name):
        if table_name == "campaigns":
            return mock_campaigns
        if table_name == "leads":
            return mock_leads
        return MagicMock()

    mock_db.table.side_effect = router

    # Campaign ownership OK
    mock_campaigns.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "camp-1", "total_leads_found": 0}]
    )
    # Existing leads empty
    mock_leads.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    # User campaigns empty
    mock_campaigns.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    # Insert mock
    mock_leads.insert.return_value.execute.return_value = MagicMock(data=[{"id": "lead-valid"}])
    mock_campaigns.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

    service = DiscoveryService(db_client=mock_db)
    raw_places = [
        None,  # non-dict
        "invalid_string",  # non-dict
        {"id": "p_empty", "displayName": {}},  # empty name
        {"id": "p_valid", "displayName": {"text": "Valid Business"}},  # valid
    ]

    result = service.ingest_leads("camp-1", "user-1", raw_places)
    assert result["total_processed"] == 4
    assert result["inserted_count"] == 1


def test_ingest_leads_max_leads_cap():
    """Verify ingest_leads caps the number of inserted leads when max_leads is provided."""
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_leads = MagicMock()

    def router(table_name):
        if table_name == "campaigns":
            return mock_campaigns
        if table_name == "leads":
            return mock_leads
        return MagicMock()

    mock_db.table.side_effect = router

    mock_campaigns.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "camp-1", "total_leads_found": 0}]
    )
    mock_leads.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_campaigns.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_leads.insert.return_value.execute.return_value = MagicMock(data=[{"id": "l1"}])
    mock_campaigns.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

    service = DiscoveryService(db_client=mock_db)
    raw_places = [
        {"id": "p1", "displayName": {"text": "Business 1"}},
        {"id": "p2", "displayName": {"text": "Business 2"}},
        {"id": "p3", "displayName": {"text": "Business 3"}},
    ]

    result = service.ingest_leads("camp-1", "user-1", raw_places, max_leads=1)
    assert result["inserted_count"] == 1


def test_ingest_leads_database_insert_error():
    """Verify database insert errors are logged and raised."""
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_leads = MagicMock()

    def router(table_name):
        if table_name == "campaigns":
            return mock_campaigns
        if table_name == "leads":
            return mock_leads
        return MagicMock()

    mock_db.table.side_effect = router

    mock_campaigns.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "camp-1", "total_leads_found": 0}]
    )
    mock_leads.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_campaigns.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    # Simulate database error on insert
    mock_leads.insert.return_value.execute.side_effect = RuntimeError("Database connection lost")

    service = DiscoveryService(db_client=mock_db)
    raw_places = [{"id": "p1", "displayName": {"text": "Business 1"}}]

    with pytest.raises(RuntimeError, match="Database connection lost"):
        service.ingest_leads("camp-1", "user-1", raw_places)

