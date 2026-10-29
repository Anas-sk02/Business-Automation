import asyncio
import json
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
from playwright.async_api import async_playwright

SUPABASE_URL = "https://pfccofklivdxncpeabln.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmY2NvZmtsaXZkeG5jcGVhYmxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwOTc4MDksImV4cCI6MjEwODY3MzgwOX0.jMdhWVafB5atMXtMvkaohLilz0Ezouh_F2clsW2S1bI"
API_BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

TEST_EMAIL = "mdanas12.2007@gmail.com"
TEST_PASSWORD = "Anas1234"

report = {
    "auth": {},
    "browser_flow": {},
    "feature_tests": {},
    "data_isolation": {},
    "fake_data_audit": {},
    "ui_ux_checks": {},
    "console_logs": [],
    "failures": [],
}

async def run_live_audit():
    print("=== SignalForge AI Live System End-to-End Audit ===")
    
    # -------------------------------------------------------------
    # Step 1: Direct Authentication with Supabase
    # -------------------------------------------------------------
    print("\n[Step 1] Authenticating with Supabase Auth...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        auth_res = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        if auth_res.status_code == 200:
            auth_data = auth_res.json()
            access_token = auth_data["access_token"]
            user_id = auth_data["user"]["id"]
            report["auth"]["status"] = "PASSED"
            report["auth"]["user_id"] = user_id
            print(f"  ✓ Successfully authenticated. User ID: {user_id}")
        else:
            report["auth"]["status"] = "FAILED"
            report["auth"]["error"] = auth_res.text
            report["failures"].append(f"Supabase auth failed: {auth_res.status_code} - {auth_res.text}")
            print(f"  ✗ Auth failed: {auth_res.status_code} {auth_res.text}")
            return report

    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # -------------------------------------------------------------
    # Step 2: Backend Health & Auth Endpoints
    # -------------------------------------------------------------
    print("\n[Step 2] Testing Backend /health and /api/auth/me...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Health
        h_res = await client.get(f"{API_BASE_URL}/health")
        if h_res.status_code == 200 and h_res.json().get("status") == "healthy":
            report["feature_tests"]["health"] = "PASSED"
            print("  ✓ Backend /health is 200 OK and healthy")
        else:
            report["feature_tests"]["health"] = f"FAILED: {h_res.status_code}"
            report["failures"].append(f"Health check failed: {h_res.status_code}")

        # Auth Me
        me_res = await client.get(f"{API_BASE_URL}/api/auth/me", headers=auth_headers)
        if me_res.status_code == 200:
            profile = me_res.json().get("data", {})
            report["feature_tests"]["auth_me"] = "PASSED"
            print(f"  ✓ /api/auth/me returned profile for: {profile.get('email')}")
        else:
            report["feature_tests"]["auth_me"] = f"FAILED: {me_res.status_code}"
            report["failures"].append(f"/api/auth/me failed: {me_res.status_code} {me_res.text}")

    # -------------------------------------------------------------
    # Step 3: Playwright Browser End-to-End User Experience
    # -------------------------------------------------------------
    print("\n[Step 3] Running Playwright Headless Browser Flow...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # Track browser console and errors
        page.on("console", lambda msg: report["console_logs"].append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: report["console_logs"].append(f"[pageerror] {err}"))

        # 3.1: Login Page
        print("  Testing Login Page (normal, wrong pass, empty input)...")
        await page.goto(f"{FRONTEND_URL}/login")
        await page.wait_for_load_state("networkidle")

        # Empty submit
        await page.click("button[type='submit']")
        await page.wait_for_timeout(500)
        login_url_after_empty = page.url
        assert "/login" in login_url_after_empty, "Should remain on login page on empty submit"
        print("    ✓ Empty login correctly prevented submission")

        # Wrong credentials
        await page.fill("input[type='email']", TEST_EMAIL)
        await page.fill("input[type='password']", "WrongPassword999!")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(1500)
        content_after_wrong = await page.content()
        has_error_message = "Invalid" in content_after_wrong or "credentials" in content_after_wrong or "error" in content_after_wrong.lower()
        if has_error_message:
            print("    ✓ Wrong password displayed error feedback")
            report["browser_flow"]["wrong_login_error"] = "PASSED"
        else:
            print("    ⚠ Wrong password did not display explicit error toast/message in DOM")
            report["browser_flow"]["wrong_login_error"] = "WARNING: No error message in DOM"

        # Correct login
        await page.fill("input[type='email']", TEST_EMAIL)
        await page.fill("input[type='password']", TEST_PASSWORD)
        await page.click("button[type='submit']")
        
        # Wait for navigation
        try:
            await page.wait_for_url(lambda u: "/login" not in u, timeout=10000)
            print(f"    ✓ Successfully logged in via UI! Redirected to: {page.url}")
            report["browser_flow"]["login_success"] = "PASSED"
        except Exception as exc:
            print(f"    ✗ Login navigation timeout: {page.url}")
            report["browser_flow"]["login_success"] = f"FAILED: {exc}"
            report["failures"].append(f"Login failed to redirect: {page.url}")

        # 3.2: Dashboard UI Scan
        print("  Testing Dashboard Page (/)...")
        await page.goto(f"{FRONTEND_URL}/")
        await page.wait_for_load_state("networkidle")
        dash_content = await page.content()
        
        # Scan for forbidden mock data per docs/UI-UX.md section 2
        forbidden_mocks = ["john doe", "jane doe", "acme", "lorem ipsum", "555-0199", "sample business"]
        found_forbidden = [m for m in forbidden_mocks if m in dash_content.lower()]
        if found_forbidden:
            report["fake_data_audit"]["dashboard"] = f"FAILED: Found {found_forbidden}"
            report["failures"].append(f"Dashboard contains forbidden mock text: {found_forbidden}")
            print(f"    ✗ Forbidden mock text on dashboard: {found_forbidden}")
        else:
            report["fake_data_audit"]["dashboard"] = "PASSED: No mock data found"
            print("    ✓ No mock/hardcoded fake data on dashboard")

        # 3.3: Campaigns Page
        print("  Testing Campaigns Page (/campaigns)...")
        await page.goto(f"{FRONTEND_URL}/campaigns")
        await page.wait_for_load_state("networkidle")
        campaigns_content = await page.content()
        
        # Check buttons & navigation
        new_campaign_btn = await page.query_selector("a[href='/campaigns/new'], button:has-text('New')")
        print(f"    ✓ 'New campaign' CTA button presence: {new_campaign_btn is not None}")
        
        await browser.close()

    # -------------------------------------------------------------
    # Step 4: Stage 2 Feature API Verification (Normal, Empty, Wrong, Error)
    # -------------------------------------------------------------
    print("\n[Step 4] Testing Stage 2 API Features...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 4.1: List existing campaigns
        c_list_res = await client.get(f"{API_BASE_URL}/api/campaigns", headers=auth_headers)
        campaigns = c_list_res.json().get("data", []) if c_list_res.status_code == 200 else []
        print(f"  ✓ User has {len(campaigns)} existing campaign(s)")

        # Create a test campaign if none exists
        active_campaign = None
        if campaigns:
            active_campaign = campaigns[0]
            campaign_id = active_campaign["id"]
            print(f"  ✓ Using existing campaign: '{active_campaign['name']}' (ID: {campaign_id})")
        else:
            print("  Creating a test campaign for Stage 2 testing...")
            create_res = await client.post(
                f"{API_BASE_URL}/api/campaigns",
                headers=auth_headers,
                json={
                    "name": "Coaching Institutes Nagpur Test",
                    "industry": "education",
                    "industry_label": "Education & Coaching",
                    "location": "Nagpur, Maharashtra",
                    "keywords": ["coaching", "classes", "tuition"],
                    "target_leads": 10,
                    "min_rating": 3.5,
                    "service_offered": "Website redesign & SEO audit",
                    "signals": ["poor_mobile", "slow_speed"],
                },
            )
            if create_res.status_code == 200:
                active_campaign = create_res.json().get("data")
                campaign_id = active_campaign["id"]
                print(f"  ✓ Created test campaign ID: {campaign_id}")
            else:
                print(f"  ✗ Failed to create test campaign: {create_res.status_code} {create_res.text}")
                report["failures"].append(f"Create campaign failed: {create_res.text}")
                campaign_id = None

        if campaign_id:
            # Feature 2.1: Discovery Status Endpoint
            print(f"  Testing GET /api/campaigns/{campaign_id}/status...")
            status_res = await client.get(f"{API_BASE_URL}/api/campaigns/{campaign_id}/status", headers=auth_headers)
            if status_res.status_code == 200:
                status_data = status_res.json().get("data", {})
                report["feature_tests"]["discovery_status"] = "PASSED"
                print(f"    ✓ Discovery status: {status_data.get('status')}, leads found: {status_data.get('total_leads_found')}")
            else:
                report["feature_tests"]["discovery_status"] = f"FAILED: {status_res.status_code}"
                report["failures"].append(f"Discovery status returned {status_res.status_code}")

            # Feature 2.2: Lead List & Filters (Normal Case)
            print(f"  Testing GET /api/campaigns/{campaign_id}/leads (Normal case)...")
            leads_res = await client.get(f"{API_BASE_URL}/api/campaigns/{campaign_id}/leads", headers=auth_headers)
            if leads_res.status_code == 200:
                leads_data = leads_res.json()
                total_leads = leads_data.get("total", 0)
                leads = leads_data.get("data", [])
                report["feature_tests"]["leads_list_normal"] = "PASSED"
                print(f"    ✓ Leads list returned {len(leads)} lead(s) of total {total_leads}")
            else:
                report["feature_tests"]["leads_list_normal"] = f"FAILED: {leads_res.status_code}"
                report["failures"].append(f"Leads list failed: {leads_res.status_code}")

            # Feature 2.3: Lead List Wrong Inputs (min_score > max_score)
            print("  Testing GET /api/campaigns/{campaign_id}/leads with min_score > max_score (Wrong input)...")
            wrong_score_res = await client.get(
                f"{API_BASE_URL}/api/campaigns/{campaign_id}/leads",
                params={"min_score": 90, "max_score": 20},
                headers=auth_headers,
            )
            if wrong_score_res.status_code in (400, 422):
                report["feature_tests"]["leads_wrong_score_filter"] = "PASSED"
                print(f"    ✓ Correctly rejected invalid score range with HTTP {wrong_score_res.status_code}")
            else:
                report["feature_tests"]["leads_wrong_score_filter"] = f"FAILED: {wrong_score_res.status_code}"
                report["failures"].append(f"Invalid min_score>max_score was not rejected: {wrong_score_res.status_code}")

            # Feature 2.4: Lead List Wrong Inputs (invalid sort field)
            print("  Testing GET /api/campaigns/{campaign_id}/leads with invalid sort field (Wrong input)...")
            wrong_sort_res = await client.get(
                f"{API_BASE_URL}/api/campaigns/{campaign_id}/leads",
                params={"sort_by": "unsupported_field"},
                headers=auth_headers,
            )
            if wrong_sort_res.status_code in (400, 422):
                report["feature_tests"]["leads_invalid_sort"] = "PASSED"
                print(f"    ✓ Correctly rejected invalid sort_by with HTTP {wrong_sort_res.status_code}")
            else:
                report["feature_tests"]["leads_invalid_sort"] = f"FAILED: {wrong_sort_res.status_code}"
                report["failures"].append(f"Invalid sort_by was not rejected: {wrong_sort_res.status_code}")

            # Feature 2.5: Lead Detail & Audit (if leads exist)
            if leads:
                test_lead = leads[0]
                lead_id = test_lead["id"]
                print(f"  Testing GET /api/leads/{lead_id} (Lead Detail)...")
                lead_detail_res = await client.get(f"{API_BASE_URL}/api/leads/{lead_id}", headers=auth_headers)
                if lead_detail_res.status_code == 200:
                    ld = lead_detail_res.json().get("data", {})
                    report["feature_tests"]["lead_detail"] = "PASSED"
                    print(f"    ✓ Retrieved lead '{ld.get('business_name')}', stage: {ld.get('pipeline_stage')}, score: {ld.get('fit_score')}")
                else:
                    report["feature_tests"]["lead_detail"] = f"FAILED: {lead_detail_res.status_code}"
                    report["failures"].append(f"Lead detail failed: {lead_detail_res.status_code}")

                print(f"  Testing GET /api/leads/{lead_id}/audit (Full Audit Report)...")
                audit_res = await client.get(f"{API_BASE_URL}/api/leads/{lead_id}/audit", headers=auth_headers)
                if audit_res.status_code == 200:
                    ar = audit_res.json().get("data", {})
                    report["feature_tests"]["audit_report"] = "PASSED"
                    print(f"    ✓ Audit report retrieved: audit exists = {ar.get('audit') is not None}, evidence count = {len(ar.get('evidence', []))}")
                else:
                    report["feature_tests"]["audit_report"] = f"FAILED: {audit_res.status_code}"
                    report["failures"].append(f"Audit report endpoint failed: {audit_res.status_code}")
            else:
                print("  ℹ No leads exist in campaign yet to test lead detail")

    # -------------------------------------------------------------
    # Step 5: Data Isolation & Multi-Tenant Security Check
    # -------------------------------------------------------------
    print("\n[Step 5] Testing Multi-Tenant Data Isolation (docs/decisions.md Section 3)...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Request with unauthenticated client
        if campaign_id:
            unauth_res = await client.get(f"{API_BASE_URL}/api/campaigns/{campaign_id}/leads")
            if unauth_res.status_code in (401, 403):
                report["data_isolation"]["unauth_block"] = "PASSED"
                print(f"  ✓ Unauthenticated access correctly blocked with HTTP {unauth_res.status_code}")
            else:
                report["data_isolation"]["unauth_block"] = f"FAILED: {unauth_res.status_code}"
                report["failures"].append(f"Unauthenticated request returned {unauth_res.status_code}")

        # Request with invalid / second user token
        bogus_headers = {"Authorization": "Bearer bogus_token_123456", "Content-Type": "application/json"}
        bogus_res = await client.get(f"{API_BASE_URL}/api/campaigns/{campaign_id}/leads", headers=bogus_headers)
        if bogus_res.status_code in (401, 403):
            report["data_isolation"]["invalid_token_block"] = "PASSED"
            print(f"  ✓ Invalid user token correctly blocked with HTTP {bogus_res.status_code}")
        else:
            report["data_isolation"]["invalid_token_block"] = f"FAILED: {bogus_res.status_code}"
            report["failures"].append(f"Invalid token returned {bogus_res.status_code}")

        # Non-existent ID returns 404 (not leaking data existence)
        missing_res = await client.get(
            f"{API_BASE_URL}/api/campaigns/00000000-0000-0000-0000-000000000000/leads",
            headers=auth_headers,
        )
        if missing_res.status_code == 404:
            report["data_isolation"]["unowned_404"] = "PASSED"
            print("  ✓ Unowned / missing campaign ID returns HTTP 404 per decisions.md Section 3")
        else:
            report["data_isolation"]["unowned_404"] = f"FAILED: {missing_res.status_code}"
            report["failures"].append(f"Unowned campaign returned {missing_res.status_code} instead of 404")

    print("\n=== Live Test Complete ===")
    return report

if __name__ == "__main__":
    rep = asyncio.run(run_live_audit())
    print("\nFINAL AUDIT SUMMARY JSON:")
    print(json.dumps(rep, indent=2))
