import asyncio
import re
from datetime import datetime
from difflib import SequenceMatcher

from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize(text):
    return clean(text).lower().replace("-", " ")


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def extract(pattern, text, default="-"):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else default


def is_active_rent(end_date):
    months = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
    }

    try:
        end_month_str, end_year_str = end_date.replace(",", "").split()
        end_month = months[end_month_str]
        end_year = int(end_year_str)

        now = datetime.now()

        return end_year > now.year or (
            end_year == now.year and end_month >= now.month
        )

    except Exception:
        return False


def parse_dxb_text(text):
    text = clean(text)

    building = extract(r"Project / Building\s+(.+?)\s+Property No#", text)
    size = extract(r"Size\s+(.+?\s+Sqft)", text)
    bedrooms = extract(r"Bedrooms\s+([0-9]+|Studio)", text)
    balcony = extract(r"Balcony\s+(.+?\s+Sqft|No balcony)", text)
    parking = extract(r"Parking\s+(.+?)\s+[0-9.]+%\s+Rental yield", text)
    rental_yield = extract(r"([0-9.]+%)\s+Rental yield", text)

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
            lines.append(f"• {date} — AED {price} — Sold by: {seller}")
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


async def get_visible_inputs(page):
    inputs = page.locator("input:visible")
    result = []

    for i in range(await inputs.count()):
        el = inputs.nth(i)
        box = await el.bounding_box()

        if box:
            result.append((el, box))

    return result


async def fill_project_input(page, value):
    inputs = await get_visible_inputs(page)

    candidates = [
        (el, box)
        for el, box in inputs
        if box["width"] > 250 and box["x"] > 300
    ]

    if not candidates:
        raise Exception("Project input not found")

    el, box = candidates[0]

    await el.click()
    await el.press("Meta+A")
    await el.fill(value)

    return box


async def fill_unit_input(page, value):
    inputs = await get_visible_inputs(page)

    candidates = [
        (el, box)
        for el, box in inputs
        if box["width"] < 250 and box["x"] > 700
    ]

    if not candidates:
        raise Exception("Unit input not found")

    el, box = candidates[0]

    await el.click()
    await el.press("Meta+A")
    await el.fill(value)

    return box
async def main():
    building = input("Building name: ").strip()
    unit = input("Unit number: ").strip()

    result = await search_dxb_unit(building, unit)

    print("\n========== DXB RESULT ==========\n")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())