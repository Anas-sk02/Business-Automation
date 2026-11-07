import asyncio
import sys
from playwright.async_api import async_playwright

async def main():
    errors = []
    warnings = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(f"PAGEERROR: {err}"))

        print("1. Navigating to login page...")
        await page.goto("http://localhost:3000/login", wait_until="networkidle")

        print("2. Logging in with test user...")
        await page.fill('input[type="email"]', "mdanas12.2007@gmail.com")
        await page.fill('input[type="password"]', "Anas1234")
        await page.click('button[type="submit"]')

        await page.wait_for_url("http://localhost:3000/**", timeout=10000)
        await page.wait_for_timeout(2000)

        print(f"Logged in. Current URL: {page.url}")

        print("3. Navigating to /pipeline...")
        await page.goto("http://localhost:3000/pipeline", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Check for card
        cards = page.locator('[draggable="true"]')
        count = await cards.count()
        print(f"Found {count} draggable pipeline cards.")

        if count > 0:
            print("4. Testing 3-dots menu on pipeline card...")
            card = cards.first
            menu_btn = card.locator('button[title="Move to stage"], button[aria-label*="Move"]')
            menu_count = await menu_btn.count()
            print(f"Menu buttons found on card: {menu_count}")
            if menu_count > 0:
                await menu_btn.first.click()
                await page.wait_for_timeout(1000)
                
                # Check if dropdown content opened
                dropdown_content = page.locator('[data-slot="dropdown-menu-content"]')
                is_visible = await dropdown_content.is_visible()
                print(f"Dropdown content visible: {is_visible}")
                
                items = page.locator('[data-slot="dropdown-menu-item"]')
                item_count = await items.count()
                print(f"Dropdown items found: {item_count}")
                for i in range(item_count):
                    txt = await items.nth(i).inner_text()
                    print(f"  Item {i}: {txt}")

                # Close dropdown by pressing Escape or clicking outside
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)

            # Test clicking lead title link
            lead_link = card.locator('a[href^="/leads/"]').first
            lead_href = await lead_link.get_attribute("href")
            print(f"Lead link href: {lead_href}")

        print("5. Testing 'Closed' rail button...")
        closed_btn = page.locator('button:has-text("Closed")')
        if await closed_btn.count() > 0:
            await closed_btn.first.click()
            await page.wait_for_timeout(1000)
            print("Closed rail opened successfully.")
            await closed_btn.first.click()
            await page.wait_for_timeout(500)

        print("6. Navigating to /tasks...")
        await page.goto("http://localhost:3000/tasks", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        task_rows = page.locator('button[title="Task actions"], button[aria-label="Task actions"]')
        task_count = await task_rows.count()
        print(f"Found {task_count} task action buttons.")
        if task_count > 0:
            print("7. Testing 3-dots menu on first task...")
            await task_rows.first.click()
            await page.wait_for_timeout(1000)
            task_dropdown = page.locator('[data-slot="dropdown-menu-content"]')
            is_open = await task_dropdown.is_visible()
            print(f"Task dropdown visible: {is_open}")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

        await browser.close()

    print("\n--- TEST SUMMARY ---")
    if errors:
        print(f"FAILED with {len(errors)} errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("SUCCESS! Zero console errors, zero runtime exceptions on Pipeline & Tasks!")

if __name__ == "__main__":
    asyncio.run(main())
