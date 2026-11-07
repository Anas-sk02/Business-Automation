import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        c = await b.new_context()
        page = await c.new_page()
        errs = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(str(e)))
        
        await page.goto("http://localhost:3000/login")
        await page.fill('input[type="email"]', "mdanas12.2007@gmail.com")
        await page.fill('input[type="password"]', "Anas1234")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(2000)
        
        await page.goto("http://localhost:3000/leads/28547deb-8cce-4acc-9e0e-aa30a6818723", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        title = await page.locator("main").inner_text()
        print("Page Loaded.")
        print("Console errors count:", len(errs))
        if errs:
            for e in errs:
                print("  ERROR:", e)
        print("Title preview:", repr(title[:120]))
        await b.close()

asyncio.run(test())
