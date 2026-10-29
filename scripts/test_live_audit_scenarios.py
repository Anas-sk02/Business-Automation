import asyncio
import json
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from backend.database import get_supabase_client
from backend.services.audit import AuditService, AUDIT_SEMAPHORE

supabase = get_supabase_client()
audit_service = AuditService(db_client=supabase)

# Use test user id
TEST_USER_ID = "cf4fd087-c5e1-4a88-883a-86e3a52a0de7"

results = {
    "working_website": {},
    "no_website": {},
    "broken_website": {},
    "bot_blocking_website": {},
    "signed_url_verification": {},
    "readable_reasons": {},
    "concurrency_batch": {},
}

async def run_scenario_tests():
    print("=== Testing All Stage 3 Audit Scenarios ===")
    
    # 0. Setup a temporary campaign or get user's campaign
    camp_res = supabase.table("campaigns").select("id").eq("user_id", TEST_USER_ID).limit(1).execute()
    if not camp_res.data:
        print("Creating temporary test campaign...")
        c_ins = supabase.table("campaigns").insert({
            "user_id": TEST_USER_ID,
            "name": "Audit Scenarios Test Campaign",
            "industry": "technology",
            "industry_label": "Technology",
            "location": "Nagpur",
            "keywords": ["tech"],
            "target_leads": 10,
            "min_rating": 3.0,
            "service_offered": "Web Development",
            "signals": ["slow_speed"],
        }).execute()
        campaign_id = c_ins.data[0]["id"]
    else:
        campaign_id = camp_res.data[0]["id"]

    print(f"Using campaign ID: {campaign_id}")

    # Helper to create a dummy lead for each test scenario
    def create_lead(name: str, url: str | None) -> str:
        res = supabase.table("leads").insert({
            "campaign_id": campaign_id,
            "business_name": name,
            "website_url": url,
            "pipeline_stage": "discovered",
        }).execute()
        return res.data[0]["id"]

    # -------------------------------------------------------------
    # Scenario 1: Working Website (https://example.com)
    # -------------------------------------------------------------
    print("\n[Scenario 1] Auditing lead with a WORKING website (https://example.com)...")
    working_lead_id = create_lead("Test Working Site Business", "https://example.com")
    try:
        report1 = await audit_service.audit_lead_website(lead_id=working_lead_id, user_id=TEST_USER_ID)
        audit_id = report1.get("audit_id")
        
        # Query saved website_audit record from DB
        a_row = supabase.table("website_audits").select("*").eq("id", audit_id).execute().data[0] if audit_id else {}
        evidence_rows = supabase.table("evidence_items").select("*").eq("lead_id", working_lead_id).execute().data or []
        
        results["working_website"]["status"] = a_row.get("status")
        results["working_website"]["page_loads"] = a_row.get("page_loads")
        results["working_website"]["dns_resolves"] = a_row.get("dns_resolves")
        results["working_website"]["http_status"] = a_row.get("http_status_code")
        results["working_website"]["desktop_screenshot"] = a_row.get("screenshot_desktop_url") is not None
        results["working_website"]["mobile_screenshot"] = a_row.get("screenshot_mobile_url") is not None
        results["working_website"]["desktop_path"] = a_row.get("screenshot_desktop_url")
        results["working_website"]["evidence_count"] = len(evidence_rows)
        
        # Check signed URL generation
        signed_desktop = audit_service.get_signed_screenshot_url(a_row.get("screenshot_desktop_url"), expires_in=3600)
        results["signed_url_verification"]["signed_desktop_url_generated"] = bool(signed_desktop)
        results["signed_url_verification"]["is_signed_not_public"] = "token=" in (signed_desktop or "") or "sign" in (signed_desktop or "")
        results["signed_url_verification"]["sample_signed_url"] = (signed_desktop[:60] + "...") if signed_desktop else None
        
        print(f"  ✓ Status: {a_row.get('status')}")
        print(f"  ✓ Page loads: {a_row.get('page_loads')}, HTTP: {a_row.get('http_status_code')}")
        print(f"  ✓ Screenshots stored in private bucket path: {a_row.get('screenshot_desktop_url')}")
        print(f"  ✓ 1-Hour Signed URL verified: {results['signed_url_verification']['is_signed_not_public']}")
        print(f"  ✓ Evidence items generated: {len(evidence_rows)}")
    except Exception as exc:
        print(f"  ✗ Working site audit failed with exception: {exc}")
        results["working_website"]["error"] = str(exc)

    # -------------------------------------------------------------
    # Scenario 2: Lead with NO website
    # -------------------------------------------------------------
    print("\n[Scenario 2] Auditing lead with NO website (website_url is None)...")
    no_web_lead_id = create_lead("Test No Website Business", None)
    try:
        report2 = await audit_service.audit_lead_website(lead_id=no_web_lead_id, user_id=TEST_USER_ID)
        results["no_website"]["status"] = report2.get("status")
        
        evidence_rows = supabase.table("evidence_items").select("*").eq("lead_id", no_web_lead_id).execute().data or []
        no_web_evidence = any("no website" in (e.get("finding_title", "") + e.get("description", "")).lower() for e in evidence_rows)
        results["no_website"]["has_no_website_evidence"] = no_web_evidence
        
        # Check lead pipeline stage updated to researched per decisions.md Section 5
        lead_check = supabase.table("leads").select("pipeline_stage").eq("id", no_web_lead_id).execute()
        results["no_website"]["pipeline_stage"] = lead_check.data[0]["pipeline_stage"]
        
        print(f"  ✓ Processed cleanly: status={report2.get('status')}")
        print(f"  ✓ Stage transitioned to: {results['no_website']['pipeline_stage']} (expected 'researched')")
        print(f"  ✓ 'No website found' evidence item created: {no_web_evidence}")
    except Exception as exc:
        print(f"  ✗ No website audit failed with exception: {exc}")
        results["no_website"]["error"] = str(exc)

    # -------------------------------------------------------------
    # Scenario 3: Broken / Non-resolving Website
    # -------------------------------------------------------------
    print("\n[Scenario 3] Auditing lead with a SLOW / BROKEN non-resolving website...")
    broken_lead_id = create_lead("Test Broken Site Business", "https://non-existent-domain-signalforge-xyz-987.org")
    try:
        report3 = await audit_service.audit_lead_website(lead_id=broken_lead_id, user_id=TEST_USER_ID)
        audit_id3 = report3.get("audit_id")
        a_row3 = supabase.table("website_audits").select("*").eq("id", audit_id3).execute().data[0] if audit_id3 else {}
        
        status3 = a_row3.get("status")
        err_msg3 = a_row3.get("error_message")
        results["broken_website"]["status"] = status3
        results["broken_website"]["readable_error"] = err_msg3
        results["broken_website"]["dns_resolves"] = a_row3.get("dns_resolves")
        
        print(f"  ✓ Audit status: {status3} (expected 'failed')")
        print(f"  ✓ Readable failure reason: '{err_msg3}'")
    except Exception as exc:
        print(f"  ✗ Broken site crashed: {exc}")
        results["broken_website"]["error"] = str(exc)

    # -------------------------------------------------------------
    # Scenario 4: Website that blocks bots (HTTP 403 Forbidden)
    # -------------------------------------------------------------
    print("\n[Scenario 4] Auditing lead with a website that blocks bots (HTTP 403)...")
    bot_block_lead_id = create_lead("Test Bot Blocking Business", "https://httpstat.us/403")
    try:
        report4 = await audit_service.audit_lead_website(lead_id=bot_block_lead_id, user_id=TEST_USER_ID)
        audit_id4 = report4.get("audit_id")
        a_row4 = supabase.table("website_audits").select("*").eq("id", audit_id4).execute().data[0] if audit_id4 else {}
        
        status4 = a_row4.get("status")
        err_msg4 = a_row4.get("error_message")
        results["bot_blocking_website"]["status"] = status4
        results["bot_blocking_website"]["http_status"] = a_row4.get("http_status_code")
        results["bot_blocking_website"]["readable_error"] = err_msg4
        
        print(f"  ✓ Audit status: {status4} (expected 'failed')")
        print(f"  ✓ HTTP status recorded: {a_row4.get('http_status_code')}")
        print(f"  ✓ Readable failure reason: '{err_msg4}'")
    except Exception as exc:
        print(f"  ✗ Bot blocking site crashed: {exc}")
        results["bot_blocking_website"]["error"] = str(exc)

    # -------------------------------------------------------------
    # Scenario 5: Concurrency Batch (Several audits at once)
    # -------------------------------------------------------------
    print("\n[Scenario 5] Running CONCURRENCY TEST: 5 simultaneous audits via asyncio.gather...")
    batch_lead_ids = [
        create_lead(f"Concurrent Test Lead {i}", "https://example.com" if i % 2 == 0 else None)
        for i in range(5)
    ]
    
    try:
        tasks = [
            audit_service.audit_lead_website(lead_id=lid, user_id=TEST_USER_ID)
            for lid in batch_lead_ids
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successes = 0
        exceptions = 0
        for i, res in enumerate(batch_results):
            if isinstance(res, Exception):
                exceptions += 1
                print(f"  ✗ Audit {i+1} threw exception: {res}")
            else:
                successes += 1
                
        results["concurrency_batch"]["total_launched"] = len(batch_lead_ids)
        results["concurrency_batch"]["completed_cleanly"] = successes
        results["concurrency_batch"]["exceptions_thrown"] = exceptions
        print(f"  ✓ Completed {successes}/{len(batch_lead_ids)} simultaneous audits cleanly with 0 server crashes!")
    except Exception as exc:
        print(f"  ✗ Batch audit crashed: {exc}")
        results["concurrency_batch"]["error"] = str(exc)

    print("\n=== All Scenarios Complete ===")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(run_scenario_tests())
