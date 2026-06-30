import asyncio
import re
from pathlib import Path
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE = "https://app.proppy.ae"
PROFILE_DIR = "proppy_profile"

PERMITS_FILE = Path("permit.txt")


def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def parse_rows(html, permit):
    soup = BeautifulSoup(html, "html.parser")
    text = clean(soup.get_text(" ", strip=True))

    rows = []

    for table in soup.find_all("table"):
        headers = [clean(th.get_text(" ", strip=True)) for th in table.find_all("th")]

        for tr in table.find_all("tr")[1:]:
            cells = [clean(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if not cells:
                continue

            row_text = " | ".join(cells)
            row = dict(zip(headers, cells)) if headers else {"row_text": row_text}

            if permit in row_text or permit in text:
                rows.append(row)

    return rows, text[:1000]


async def main():
    if not PERMITS_FILE.exists():
        raise SystemExit("permit.txt not found")

    permits = [
        clean(x)
        for x in PERMITS_FILE.read_text(encoding="utf-8").splitlines()
        if clean(x)
    ]

    if not permits:
        raise SystemExit("permit.txt is empty")

    permit = permits[0]
    q = quote_plus(permit)

    urls = [
        f"{BASE}/App/Properties/Records2?link={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records2?Permit={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records2?PermitNumber={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records2?Trakheesi={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records2?Search={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records2?Keyword={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records2?q={q}&Page=1&PageSize=50",

        f"{BASE}/App/Properties/Records?link={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records?Permit={q}&Page=1&PageSize=50",
        f"{BASE}/App/Properties/Records?PermitNumber={q}&Page=1&PageSize=50",
    ]

    print("TEST PERMIT:", permit)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        for url in urls:
            print("\n==============================")
            print("URL:", url)

            try:
                await page.goto(url, wait_until="networkidle", timeout=90000)
                html = await page.content()
                rows, preview = parse_rows(html, permit)

                print("MATCHED ROWS:", len(rows))

                for i, row in enumerate(rows[:5], start=1):
                    print(f"\nROW {i}")
                    for k, v in row.items():
                        print(f"{k}: {v}")

                if not rows:
                    print("PAGE PREVIEW:", preview[:300])

            except Exception as e:
                print("ERROR:", e)

        await context.close()


asyncio.run(main())
