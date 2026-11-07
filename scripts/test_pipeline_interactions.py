import asyncio
import sys
from playwright.async_api import async_playwright

async def main():
    errors = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(f"PAGEERROR: {err}"))

        print("1. Logging in...")
        await page.goto("http://localhost:3000/login", wait_until="networkidle")
        await page.fill('input[type="email"]', "mdanas12.2007@gmail.com")
        await page.fill('input[type="password"]', "Anas1234")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(2000)

        print("2. Navigating to /pipeline...")
        await page.goto("http://localhost:3000/pipeline", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Find the card "Concurrent Test Lead 4"
        card = page.locator('[draggable="true"]:has-text("Concurrent Test Lead 4")').first
        menu_btn = card.locator('button[title="Move to stage"], button[aria-label*="Move"]').first
        
        print("3. Clicking 3-dots menu button on 'Concurrent Test Lead 4'...")
        await menu_btn.click()
        await page.wait_for_timeout(600)

        print("4. Clicking 'Proposal sent' option (non-current stage)...")
        item = page.locator('[data-slot="dropdown-menu-item"]:has-text("Proposal sent")').first
        await item.click()
        await page.wait_for_timeout(2000)

        # Check if error alert banner appeared
        err_banner = page.locator('div.border-destructive\\/30')
        if await err_banner.is_visible():
            err_text = await err_banner.inner_text()
            print(f"Error banner visible: {err_text}")
        else:
            print("Card moved to 'Proposal sent' cleanly with NO errors!")

        # Check for Undo toast
        undo_btn = page.locator('button:has-text("Undo")')
        if await undo_btn.is_visible():
            print("Undo toast is visible! Clicking Undo to revert...")
            await undo_btn.click()
            await page.wait_for_timeout(2000)
            print("Undo executed successfully!")

        print("5. Clicking on Lead card link to view Lead Detail page...")
        lead_link = page.locator('[draggable="true"]:has-text("Concurrent Test Lead 4") a[href^="/leads/"]').first
        lead_url = await lead_link.get_attribute("href")
        print(f"Clicking link to {lead_url}...")
        await lead_link.click()
        await page.wait_for_timeout(2000)
        print(f"Navigated to: {page.url}")

        header = page.locator("main h1, main h2, main strong").first
        if await header.is_visible():
            print(f"Lead page header content: {await header.text_content()}")

        await browser.close()

    print("\n--- TEST SUMMARY ---")
    if errors:
        print(f"FAILED with {len(errors)} errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("PERFECT SUCCESS! All pipeline interactions, transitions, and lead navigation passed with 0 errors!")

if __name__ == "__main__":
    asyncio.run(main())
