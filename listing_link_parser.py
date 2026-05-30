import re
from playwright.async_api import async_playwright

PROFILE_DIR = "pf_profile"


def find_permits(text):
    permits = re.findall(r"\b71\d{7,12}\b", text or "")
    permits = sorted(set(permits), key=len)

    for p in permits:
        if len(p) in [10, 11, 12]:
            return p

    return permits[0] if permits else ""


async def extract_permit_from_listing_url(url: str) -> str:
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        await page.wait_for_timeout(5000)

        for _ in range(12):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(500)

        body = await page.locator("body").inner_text()
        html = await page.content()

        permit = find_permits(body + "\n" + html)

        await context.close()
        return permit