import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


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

        return (
            end_year > now.year or
            (end_year == now.year and end_month >= now.month)
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


import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract(pattern, text, default="-"):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else default


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
            end_year > now.year or
            (
                end_year == now.year and
                end_month >= now.month
            )
        )

    except Exception:
        return False


def parse_dxb_text(text):
    text = clean(text)

    building = extract(
        r"Project / Building\s+(.+?)\s+Property No#",
        text
    )

    size = extract(
        r"Size\s+(.+?\s+Sqft)",
        text
    )

    bedrooms = extract(
        r"Bedrooms\s+([0-9]+|Studio)",
        text
    )

    balcony = extract(
        r"Balcony\s+(.+?\s+Sqft|No balcony)",
        text
    )

    parking = extract(
        r"Parking\s+(.+?)\s+[0-9.]+%\s+Rental yield",
        text
    )

    rental_yield = extract(
        r"([0-9.]+%)\s+Rental yield",
        text
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

            status = (
                "🔴 ACTIVE RENT"
                if is_active_rent(end_date)
                else "⚪ EXPIRED"
            )

            lines.append(
                f"{status}\n"
                f"{start_date} → {end_date}\n"
                f"AED {rent_amount} — {rent_type}"
            )

    else:
        lines.append("• No rent history found")

    return "\n".join(lines)


async def main():

    async with async_playwright() as p:

        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled"
            ],
        )

        page = (
            context.pages[0]
            if context.pages
            else await context.new_page()
        )

        await page.goto(
            "https://dxbinteract.com",
            wait_until="domcontentloaded",
        )

        print("\nОткрой нужный unit вручную в History.")
        input("Когда откроешь unit — нажми ENTER...")

        body_base = await page.locator("body").inner_text()

        # SALES
        try:
            await page.get_by_text(
                "Sale",
                exact=True
            ).click()

            await page.wait_for_timeout(1500)

        except Exception:
            pass

        body_sale = await page.locator("body").inner_text()

        # RENTS
        try:
            await page.get_by_text(
                "Rent",
                exact=True
            ).click()

            await page.wait_for_timeout(1500)

        except Exception:
            pass

        body_rent = await page.locator("body").inner_text()

        data_base = parse_dxb_text(body_base)
        data_sale = parse_dxb_text(body_sale)
        data_rent = parse_dxb_text(body_rent)

        data_base["sales"] = data_sale.get("sales", [])
        data_base["rents"] = data_rent.get("rents", [])

        result = format_result(data_base)

        print("\n========== DXB RESULT ==========\n")
        print(result)

        await context.close()

async def get_dxb_current_page_result():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        body_base = await page.locator("body").inner_text()

        try:
            await page.get_by_text("Sale", exact=True).click()
            await page.wait_for_timeout(1500)
        except Exception:
            pass

        body_sale = await page.locator("body").inner_text()

        try:
            await page.get_by_text("Rent", exact=True).click()
            await page.wait_for_timeout(1500)
        except Exception:
            pass

        body_rent = await page.locator("body").inner_text()

        data_base = parse_dxb_text(body_base)
        data_sale = parse_dxb_text(body_sale)
        data_rent = parse_dxb_text(body_rent)

        data_base["sales"] = data_sale.get("sales", [])
        data_base["rents"] = data_rent.get("rents", [])

        result = format_result(data_base)

        await context.close()

        return result


if __name__ == "__main__":
    asyncio.run(main())