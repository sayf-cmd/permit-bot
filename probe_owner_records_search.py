import asyncio
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

PROFILE_DIR = "proppy_profile"
BASE = "https://app.proppy.ae"

OWNER = "SELECT GLOBAL DEVELOPMENT L.L.C"

URLS = [
    f"{BASE}/App/Properties/Records2?Owner={quote_plus(OWNER)}&Page=1&PageSize=50",
    f"{BASE}/App/Properties/Records2?OwnerName={quote_plus(OWNER)}&Page=1&PageSize=50",
    f"{BASE}/App/Properties/Records2?Search={quote_plus(OWNER)}&Page=1&PageSize=50",
    f"{BASE}/App/Properties/Records2?Keyword={quote_plus(OWNER)}&Page=1&PageSize=50",
    f"{BASE}/App/Properties/Records2?q={quote_plus(OWNER)}&Page=1&PageSize=50",
]


def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def parse_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for table in soup.find_all("table"):
        headers = [clean(th.get_text(" ", strip=True)) for th in table.find_all("th")]
        if not headers:
            continue

        for tr in table.find_all("tr")[1:]:
            cells = [clean(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if not cells:
                continue

            row = dict(zip(headers, cells))
            text = " | ".join(cells)

            if OWNER.upper() in text.upper():
                rows.append(row)

    return rows


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        for url in URLS:
            print("\n==============================")
            print("URL:", url)

            await page.goto(url, wait_until="networkidle", timeout=90000)
            html = await page.content()

            rows = parse_rows(html)

            print("MATCHED ROWS:", len(rows))

            for i, row in enumerate(rows[:5], start=1):
                print(f"\nROW {i}")
                for k, v in row.items():
                    print(f"{k}: {v}")

        await context.close()


asyncio.run(main())
