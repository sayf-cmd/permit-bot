import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://dxbinteract.com/dubai-property-prices")

        print("Login вручную в DXB.")
        input("После login нажми ENTER...")

        await context.storage_state(path="dxb_state.json")

        print("Saved login state to dxb_state.json")

        await browser.close()

asyncio.run(main())