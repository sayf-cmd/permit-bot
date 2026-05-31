import asyncio
from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            channel="chrome",
            args=["--no-sandbox"],
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://dxbinteract.com/dubai-property-prices")

        input("Залогинься вручную в DXB, потом нажми ENTER здесь...")

        await context.close()

asyncio.run(main())
