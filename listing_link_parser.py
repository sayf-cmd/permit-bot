import os
import re
import requests
from playwright.async_api import async_playwright

PROFILE_DIR = os.getenv("PF_PROFILE_DIR", "pf_profile")
HEADLESS = os.getenv("PF_HEADLESS", "true").lower() not in ["0", "false", "no"]


def find_permits(text: str) -> list[str]:
    text = text or ""

    patterns = [
        r"Permit Number\s+([0-9]{7,15})",
        r"Permit Number\s*\n\s*([0-9]{7,15})",
        r"Regulatory Information.*?Permit Number\s+([0-9]{7,15})",

        r"\b71\d{7,13}\b",

        r'"permitNumber"\s*:\s*"?(71?\d{7,13})"?',
        r'"permit_number"\s*:\s*"?(71?\d{7,13})"?',
        r'"trakheesi"\s*:\s*"?(71?\d{7,13})"?',

        r"Permit Number[:\s#]*([0-9]{7,15})",
        r"Permit No\.?[:\s#]*([0-9]{7,15})",
        r"Trakheesi[:\s#]*([0-9]{7,15})",
        r"DLD Permit Number[:\s#]*([0-9]{7,15})",
    ]

    found = []

    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if isinstance(match, tuple):
                match = next((x for x in match if x), "")

            digits = re.sub(r"\D", "", str(match))

            if 7 <= len(digits) <= 15:
                found.append(digits)

    found = list(dict.fromkeys(found))
    found.sort(key=lambda x: (not x.startswith("71"), -len(x)))

    return found

def extract_from_html(html: str) -> str:
    permits = find_permits(html)
    return permits[0] if permits else ""


def extract_bayut_listing_id(url: str) -> str:
    """Extract Bayut listing ID from common Bayut URL formats."""
    url = str(url or "")

    patterns = [
        r"details-(\d+)",
        r"/property/details-(\d+)\.html",
        r"/property/details/(\d+)",
        r"(?:^|[?&])listing_id=(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return ""


def extract_bayut_permit_api(url: str) -> str:
    """Use Bayut's permitNumber endpoint when a Bayut listing ID is available."""
    listing_id = extract_bayut_listing_id(url)

    if not listing_id:
        return ""

    api_url = f"https://www.bayut.com/api/listing/{listing_id}/permitNumber"

    try:
        response = requests.get(
            api_url,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": url,
            },
        )

        if response.status_code != 200:
            print("BAYUT API STATUS:", response.status_code, flush=True)
            return ""

        data = response.json()
        permit = str(data.get("permit_number") or data.get("permitNumber") or "").strip()
        permit = re.sub(r"\D", "", permit)

        if 7 <= len(permit) <= 15:
            return permit

    except Exception as e:
        print("BAYUT API EXTRACT ERROR:", repr(e), flush=True)

    return ""


def extract_with_requests(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=30,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        html = response.text or ""
        permit = extract_from_html(html)

        if permit:
            return permit

    except Exception as e:
        print("PF REQUEST EXTRACT ERROR:", repr(e), flush=True)

    return ""


async def extract_with_playwright(url: str) -> str:
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(4000)

            for _ in range(8):
                await page.mouse.wheel(0, 1200)
                await page.wait_for_timeout(400)

            body = ""
            html = ""

            try:
                body = await page.locator("body").inner_text(timeout=10000)
                print(body[:5000], flush=True)
            except Exception:
                pass

            try:
                html = await page.content()
            except Exception:
                pass

            permit = extract_from_html(body + "\n" + html)

            await context.close()
            return permit

        except Exception as e:
            print("PF PLAYWRIGHT EXTRACT ERROR:", repr(e), flush=True)
            await context.close()
            return ""


async def extract_permit_from_listing_url(url: str) -> str:
    if "bayut.com" in str(url).lower():
        permit = extract_bayut_permit_api(url)

        if permit:
            return permit

    permit = extract_with_requests(url)

    if permit:
        return permit

    return await extract_with_playwright(url)
