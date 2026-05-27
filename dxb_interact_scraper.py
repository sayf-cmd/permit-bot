import asyncio
import re
from datetime import datetime
from difflib import SequenceMatcher

import requests
from playwright.async_api import async_playwright

STATE_FILE = "dxb_state.json"
LOV_URL = "https://fam-erp.com/property/website/DLDLOV?RETURN_COLUMN=LOCATION_URL"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize(text):
    return clean(text).lower().replace("-", " ")


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def extract(pattern, text, default="-"):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else default


def find_best_location(building_name):
    data = requests.get(LOV_URL, timeout=30).json()
    items = data.get("items", [])

    best = None
    best_score = 0

    for item in items:
        name = item.get("dv", "")
        flag = item.get("flag", "")

        if flag not in ["P", "B"]:
            continue

        score = similarity(building_name, name)

        if normalize(building_name) in normalize(name):
            score += 0.5

        for part in normalize(building_name).split():
            if len(part) > 2 and part in normalize(name):
                score += 0.08

        if score > best_score:
            best_score = score
            best = item

    if not best or best_score < 0.35:
        return None

    return best


def is_active_rent(end_date):
    months = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    try:
        end_month_str, end_year_str = end_date.replace(",", "").split()
        end_month = months[end_month_str]
        end_year = int(end_year_str)

        now = datetime.now()

        return (
            end_year > now.year
            or (
                end_year == now.year
                and end_month >= now.month
            )
        )

    except Exception:
        return False


def parse_dxb_text(text):
    text = clean(text)

    building = extract(
        r"Project / Building\s+(.+?)\s+Property No#",
        text,
    )

    size = extract(
        r"Size\s+(.+?\s+Sqft)",
        text,
    )

    bedrooms = extract(
        r"Bedrooms\s+([0-9]+|Studio)",
        text,
    )

    balcony = extract(
        r"Balcony\s+(.+?\s+Sqft|No balcony)",
        text,
    )

    parking = extract(
        r"Parking\s+(.+?)\s+[0-9.]+%\s+Rental yield",
        text,
    )

    rental_yield = extract(
        r"([0-9.]+%)\s+Rental yield",
        text,
    )

    sales = re.findall(
        r"([A-Za-z]{3},\s+[0-9]{4})\s+AED\s+([\d,]+)\s+Sold by:\s+([A-Za-z]+)",
        text,
        re.IGNORECASE,
    )

    rents = re.findall(
        r"Rental contract\s+([A-Za-z]{3},\s+[0-9]{4})\s+START\s+AED\s+([\d,]+)\s+([A-Za-z]+)\s+([A-Za-z]{3},\s+[0-9]{4})\s+END",
        text,
        re.IGNORECASE,
    )

    return {
        "building": building,
        "size": size,
        "bedrooms": bedrooms,
        "balcony": balcony,
        "parking": parking,
        "rental_yield": rental_yield,
        "sales": sales,
        "rents": rents,
    }


def format_result(data):
    lines = [
        f"🏢 Building: {data['building']}",
        f"📐 Size: {data['size']}",
        f"🛏 Bedrooms: {data['bedrooms']}",
        f"🏞 Balcony: {data['balcony']}",
        f"🅿️ Parking: {data['parking']}",
        f"📈 Rental Yield: {data['rental_yield']}",
        "",
        "💰 Sales History:",
    ]

    if data["sales"]:
        for date, price, seller in data["sales"]:
            lines.append(
                f"• {date} — AED {price} — Sold by: {seller}"
            )
    else:
        lines.append("• No sale history found")

    lines.append("")
    lines.append("🏡 Rent History:")

    if data["rents"]:
        for start_date, rent_amount, rent_type, end_date in data["rents"]:
            status = "🔴 ACTIVE RENT" if is_active_rent(end_date) else "⚪ EXPIRED"

            lines.append(
                f"{status}\n"
                f"{start_date} → {end_date}\n"
                f"AED {rent_amount} — {rent_type}"
            )
    else:
        lines.append("• No rent history found")

    return "\n".join(lines)


async def set_location_id(page, location_id, location_name):
    await page.evaluate(
        """
        ({location_id, location_name}) => {
            const hidden = document.querySelector("#P142_LOCATION_ID");
            if (hidden) {
                hidden.value = String(location_id);
                hidden.dispatchEvent(new Event("change", { bubbles: true }));
                hidden.dispatchEvent(new Event("input", { bubbles: true }));
            }

            if (window.apex && apex.item) {
                try {
                    apex.item("P142_LOCATION_ID").setValue(String(location_id));
                } catch (e) {}
            }

            const searchInput = document.querySelector("#SearchInput");
            if (searchInput) {
                searchInput.value = location_name;
                searchInput.dispatchEvent(new Event("change", { bubbles: true }));
                searchInput.dispatchEvent(new Event("input", { bubbles: true }));
            }

            const componentInput = document.querySelector("#SearchComponentInput");
            if (componentInput) {
                componentInput.value = location_name;
                componentInput.dispatchEvent(new Event("change", { bubbles: true }));
                componentInput.dispatchEvent(new Event("input", { bubbles: true }));
            }
        }
        """,
        {
            "location_id": location_id,
            "location_name": location_name,
        },
    )


async def fill_unit_number(page, unit_number):
    inputs = page.locator("input:visible")
    candidates = []

    for i in range(await inputs.count()):
        el = inputs.nth(i)
        box = await el.bounding_box()

        if not box:
            continue

        if box["width"] < 300 and box["x"] > 600:
            candidates.append((el, box))

    if not candidates:
        raise Exception("Property No input not found")

    candidates.sort(key=lambda x: x[1]["x"], reverse=True)

    el, _ = candidates[0]

    await el.click()
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(str(unit_number), delay=80)
    await page.wait_for_timeout(1000)


async def click_search(page):
    try:
        await page.get_by_text("Search", exact=True).click()
    except Exception:
        try:
            await page.locator("button:has-text('Search')").click()
        except Exception:
            await page.keyboard.press("Enter")


async def search_dxb_unit(building_name: str, unit_number: str) -> str:
    location = find_best_location(building_name)

    if not location:
        return f"❌ Building not found in DXB LOV: {building_name}"

    location_id = location["id"]
    location_name = location["dv"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = await browser.new_context(
            storage_state=STATE_FILE,
        )

        page = await context.new_page()

        await page.goto(
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(3000)

        try:
            await page.get_by_text("History", exact=True).click()
            await page.wait_for_timeout(1500)
        except Exception:
            pass

        await set_location_id(page, location_id, location_name)
        await page.wait_for_timeout(1000)

        try:
            await fill_unit_number(page, unit_number)
        except Exception as e:
            await browser.close()
            return f"❌ DXB Error: Could not fill Property No#.\n{e}"

        await click_search(page)
        await page.wait_for_timeout(7000)

        body_after_search = await page.locator("body").inner_text()

        if "No data found" in body_after_search:
            await browser.close()
            return (
                "❌ No data found on DXB Interact.\n\n"
                f"Building searched: {building_name}\n"
                f"Selected building: {location_name}\n"
                f"Location ID: {location_id}\n"
                f"Unit: {unit_number}"
            )

        try:
            await page.get_by_text("Sale", exact=True).click()
            await page.wait_for_timeout(2000)
        except Exception:
            pass

        body_sale = await page.locator("body").inner_text()

        try:
            await page.get_by_text("Rent", exact=True).click()
            await page.wait_for_timeout(2000)
        except Exception:
            pass

        body_rent = await page.locator("body").inner_text()

        data_base = parse_dxb_text(body_after_search)
        data_sale = parse_dxb_text(body_sale)
        data_rent = parse_dxb_text(body_rent)

        data_base["building"] = location_name
        data_base["sales"] = data_sale.get("sales", [])
        data_base["rents"] = data_rent.get("rents", [])

        result = format_result(data_base)

        await browser.close()

        return result


async def main():
    building = input("Building name: ").strip()
    unit = input("Unit number: ").strip()

    result = await search_dxb_unit(
        building,
        unit,
    )

    print("\n========== DXB RESULT ==========\n")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())