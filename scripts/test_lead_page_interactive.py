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

FRONTEND_URL = "http://localhost:3000"
API_BASE_URL = "http://localhost:8000"
SUPABASE_URL = "https://pfccofklivdxncpeabln.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmY2NvZmtsaXZkeG5jcGVhYmxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwOTc4MDksImV4cCI6MjEwODY3MzgwOX0.jMdhWVafB5atMXtMvkaohLilz0Ezouh_F2clsW2S1bI"

TEST_EMAIL = "mdanas12.2007@gmail.com"
TEST_PASSWORD = "Anas1234"

CAMPAIGN_ID = "6c4bee06-511c-4c44-9c3e-0cc6f32135d9"
LEAD_ID = "e7dc4690-07ec-423a-baf7-899ebd510a45"

results = {
    "campaign_page": {},
    "lead_detail_page": {},
    "tabs": {},
    "console_errors": [],
    "console_warnings": [],
    "ui_ux": {},
}

async def run_lead_interaction_test():
    print("=== Testing Lead Detail & Campaign UI with Playwright ===")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # Listen to console
        def handle_console(msg):
            if msg.type == "error":
                results["console_errors"].append(msg.text)
            elif msg.type == "warning":
                results["console_warnings"].append(msg.text)

        page.on("console", handle_console)
        page.on("pageerror", lambda err: results["console_errors"].append(str(err)))

        # 1. Log in
        print("  Logging in via /login...")
        await page.goto(f"{FRONTEND_URL}/login")
        await page.wait_for_load_state("networkidle")
        await page.fill("input[type='email']", TEST_EMAIL)
        await page.fill("input[type='password']", TEST_PASSWORD)
        await page.click("button[type='submit']")
        await page.wait_for_url(lambda u: "/login" not in u, timeout=10000)
        print("  ✓ Authenticated. Navigating to Campaign Detail...")

        # 2. Campaign Detail Page
        await page.goto(f"{FRONTEND_URL}/campaigns/{CAMPAIGN_ID}")
        await page.wait_for_load_state("networkidle")
        campaign_html = await page.content()
        results["campaign_page"]["title_present"] = "Nagpur Medical Clinic" in campaign_html
        
        # Verify table presence
        table_el = await page.query_selector("table")
        results["campaign_page"]["table_rendered"] = table_el is not None
        print(f"  ✓ Campaign page loaded: title found = {results['campaign_page']['title_present']}, table found = {results['campaign_page']['table_rendered']}")

        # 3. Lead Detail Page
        print(f"  Navigating directly to Lead Detail: /leads/{LEAD_ID}...")
        await page.goto(f"{FRONTEND_URL}/leads/{LEAD_ID}")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)

        lead_html = await page.content()
        lead_h1 = await page.query_selector("h1")
        h1_text = await lead_h1.inner_text() if lead_h1 else ""
        results["lead_detail_page"]["h1_text"] = h1_text
        print(f"  ✓ Lead detail loaded with header: '{h1_text}'")

        # Check font class on h1
        h1_class = await lead_h1.get_attribute("class") if lead_h1 else ""
        results["ui_ux"]["h1_font_serif"] = "font-serif" in (h1_class or "")
        print(f"  ✓ Business name serif font applied: {results['ui_ux']['h1_font_serif']}")

        # Check ScoreLedger component
        ledger = await page.query_selector("div:has-text('Fit score ledger')")
        results["ui_ux"]["score_ledger_present"] = ledger is not None
        print(f"  ✓ Score ledger present: {ledger is not None}")

        # Check Qualify 60 tick mark
        qualify_tick = "Qualify (60)" in lead_html
        results["ui_ux"]["qualify_60_tick"] = qualify_tick
        print(f"  ✓ Qualify line tick (60) label present: {qualify_tick}")

        # Check Tab navigation
        for tab_name in ["Audit", "Analysis", "WhatsApp", "Tasks"]:
            tab_btn = await page.query_selector(f"button:has-text('{tab_name}')")
            results["tabs"][tab_name] = tab_btn is not None
            if tab_btn:
                await tab_btn.click()
                await page.wait_for_timeout(300)
                tab_content = await page.content()
                if tab_name == "Analysis":
                    results["tabs"]["Analysis_content"] = "AI analysis workspace" in tab_content
                elif tab_name == "WhatsApp":
                    results["tabs"]["WhatsApp_content"] = "WhatsApp outreach workspace" in tab_content
                elif tab_name == "Tasks":
                    results["tabs"]["Tasks_content"] = "Tasks and activity" in tab_content
        print(f"  ✓ Tabs switched cleanly: {results['tabs']}")

        # Switch back to Audit tab
        audit_tab_btn = await page.query_selector("button:has-text('Audit')")
        if audit_tab_btn:
            await audit_tab_btn.click()
            await page.wait_for_timeout(300)

        # Check Next Step Panel
        next_step_el = await page.query_selector("div:has-text('Recommended next step')")
        results["ui_ux"]["next_step_panel_present"] = next_step_el is not None
        print(f"  ✓ Recommended next step panel present: {next_step_el is not None}")

        # Check Contact Info Card
        contact_el = await page.query_selector("div:has-text('Contact information')")
        results["ui_ux"]["contact_card_present"] = contact_el is not None
        print(f"  ✓ Contact information card present: {contact_el is not None}")

        # Check Start Audit button
        start_audit_btn = await page.query_selector("button:has-text('Start audit')")
        results["lead_detail_page"]["start_audit_button_present"] = start_audit_btn is not None
        print(f"  ✓ 'Start audit' button present: {start_audit_btn is not None}")

        # 4. Check for forbidden fake data in lead page
        forbidden_mocks = ["john doe", "jane doe", "acme", "lorem ipsum", "555-0199"]
        found = [m for m in forbidden_mocks if m in lead_html.lower()]
        results["ui_ux"]["forbidden_data_found"] = found
        print(f"  ✓ Forbidden mock data scan: {found if found else 'None (Clean)'}")

        await browser.close()

    print("\nSUMMARY OF RESULTS:")
    print(json.dumps(results, indent=2))
    return results

if __name__ == "__main__":
    asyncio.run(run_lead_interaction_test())

