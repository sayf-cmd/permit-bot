import re
import requests
from difflib import SequenceMatcher
from playwright.async_api import async_playwright

LOV_URL = "https://fam-erp.com/property/website/DLDLOV?RETURN_COLUMN=LOCATION_URL"
PROFILE_DIR = "dxb_profile"

# Manual mappings for buildings that exist in DXB UI autocomplete
# but are missing / weak in the public LOV endpoint.
MANUAL_LOCATIONS = {
    "acacia c": {
        "id": 35567,
        "dv": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    },
    "acacia building c": {
        "id": 35567,
        "dv": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    },
    "acacia at park heights building c": {
        "id": 35567,
        "dv": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    },
}

# Manual unit mappings for cases where DXB needs internal APEX unit lookup
# and hidden-field UI search does not populate PROP_ID.
MANUAL_PROPS = {
    ("acacia c", "607"): {
        "prop_id": "22111450",
        "ejari_id": "1324341876",
    },
    ("acacia building c", "607"): {
        "prop_id": "22111450",
        "ejari_id": "1324341876",
    },
    ("acacia at park heights building c", "607"): {
        "prop_id": "22111450",
        "ejari_id": "1324341876",
    },
}

BUILDING_ALIASES = {
    "st regis downtown residences tower 1": "The St. Regis Residences Tower 1",
    "st regis downtown residences tower 2": "The St. Regis Residences Tower 2",
    "st.regis downtown residences tower 1": "The St. Regis Residences Tower 1",
    "st.regis downtown residences tower 2": "The St. Regis Residences Tower 2",
    "vida dubai mall tower 1": "VIDA Dubai Mall Tower 1",
    "vida dubai mall tower 2": "VIDA Dubai Mall Tower 2",
}


def normalize(text):
    text = str(text or "").lower().strip()
    text = text.replace(".", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def apply_alias(building_name):
    query = normalize(building_name)

    for alias, location in MANUAL_LOCATIONS.items():
        if normalize(alias) in query:
            return location

    for alias, actual in BUILDING_ALIASES.items():
        if normalize(alias) in query:
            return actual

    return building_name


def get_manual_prop(building_name, unit_number):
    query = normalize(building_name)
    unit = str(unit_number).strip()

    for (alias, manual_unit), value in MANUAL_PROPS.items():
        if normalize(alias) in query and manual_unit == unit:
            return value

    return None


def find_best_location(building_name):
    mapped = apply_alias(building_name)

    if isinstance(mapped, dict):
        return mapped

    r = requests.get(
        LOV_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    r.raise_for_status()

    items = r.json().get("items", [])
    query = normalize(mapped)
    query_words = set(query.split())

    best = None
    best_score = -999

    for item in items:
        name = item.get("dv", "")
        flag = item.get("flag", "")

        if flag not in ["P", "B"]:
            continue

        target = normalize(name)
        target_words = set(target.split())

        score = 0
        score += similarity(query, target) * 10

        shared = query_words.intersection(target_words)
        missing = query_words - target_words

        score += len(shared) * 8
        score -= len(missing) * 2

        if query == target:
            score += 60

        if query in target:
            score += 35

        if target.startswith(query):
            score += 25

        if "dubai hills" in query and "dubai hills" in target:
            score += 50

        if "downtown" in query and "downtown" in target:
            score += 50

        if "business bay" in query and "business bay" in target:
            score += 50

        if "dubai hills" in query and "damac hills 2" in target:
            score -= 120

        if score > best_score:
            best_score = score
            best = item

    if best_score < 25:
        return None

    return best


def extract(pattern, text, default="-"):
    m = re.search(pattern, text, re.I | re.S)
    return m.group(1).strip() if m else default


def parse_sales(text):
    return re.findall(
        r"([A-Za-z]{3},\s+\d{4})\s+AED\s+([\d,]+)\s+Sold by:\s+([A-Za-z]+)",
        text,
        re.I,
    )


def parse_rents(text):
    return re.findall(
        r"Rental contract\s+([A-Za-z]{3},\s+\d{4})\s+START\s+AED\s+([\d,]+).*?([A-Za-z]{3},\s+\d{4})\s+END",
        text,
        re.I | re.S,
    )


def format_result(data):
    prop_id = data.get("prop_id", "")
    trakheesi = f"71{prop_id}" if prop_id else "-"

    sales_text = "• No sale history found"
    if data.get("sales"):
        sales_text = "\n".join(
            f"• {date} — AED {price} — {seller}"
            for date, price, seller in data["sales"]
        )

    rent_text = "• No rental contracts found"
    if data.get("rents"):
        rent_text = "\n".join(
            f"• {start} → {end} — AED {amount}"
            for start, amount, end in data["rents"]
        )

    ejari_line = ""
    if data.get("ejari_id") and data.get("ejari_id") != "-":
        ejari_line = f"🆔 EJARI ID: {data.get('ejari_id')}\n"

    return (
        f"🆔 Trakheesi: {trakheesi}\n"
        f"{ejari_line}"
        f"🏢 Building: {data.get('building', '-')}\n"
        f"📍 Area: {data.get('area', '-')}\n"
        f"🏠 Unit: {data.get('unit', '-')}\n\n"
        f"🛏 Bedrooms: {data.get('bedrooms', '-')}\n"
        f"📐 Size: {data.get('size', '-')}\n"
        f"🌇 Balcony: {data.get('balcony', '-')}\n"
        f"🅿️ Parking: {data.get('parking', '-')}\n\n"
        f"{data.get('status', '🟢 Status: Available')}\n\n"
        f"💰 Sale History\n"
        f"{sales_text}\n\n"
        f"🏡 Rental Contracts\n"
        f"{rent_text}"
    )


async def search_dxb_unit_api(building_name: str, unit_number: str) -> str:
    location = find_best_location(building_name)

    if not location:
        return (
            "❌ Building not found or match is uncertain.\n\n"
            f"Building: {building_name}\n"
            f"Unit: {unit_number}"
        )

    manual_prop = get_manual_prop(building_name, unit_number)

    location_name = location["dv"]
    location_id = str(location["id"])
    area = location_name.split(",")[-1].strip() if "," in location_name else "-"

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
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(2000)

        await page.evaluate(
            """
            ({ locationId, locationName, unitNumber }) => {
                const setVal = (id, value) => {
                    const el = document.querySelector(id);
                    if (el) {
                        el.value = value;
                        el.dispatchEvent(new Event("input", { bubbles: true }));
                        el.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                };

                setVal("#P142_LOCATION_ID", String(locationId));
                setVal("#P142_PATH_NAME", locationName);
                setVal("#P142_PROP_NO", String(unitNumber));
            }
            """,
            {
                "locationId": location_id,
                "locationName": location_name,
                "unitNumber": unit_number,
            },
        )

        try:
            await page.locator("button").filter(
                has_text="Search"
            ).first.click(timeout=10000)

        except Exception:
            await page.evaluate(
                """
                () => {
                    const buttons = [...document.querySelectorAll("button, a")];
                    const btn = buttons.find(
                        x => x.innerText.trim() === "Search"
                    );

                    if (btn) btn.click();
                }
                """
            )

        await page.wait_for_timeout(7000)

        body_sale = await page.locator("body").inner_text()

        prop_id = await page.evaluate(
            """() => document.querySelector("#P142_PROP_ID")?.value || "" """
        )

        ejari_id = await page.evaluate(
            """() => document.querySelector("#P142_EJARI_ID")?.value || "" """
        )

        if manual_prop:
            prop_id = manual_prop["prop_id"]
            ejari_id = manual_prop["ejari_id"]

        if not prop_id:
            await context.close()
            return (
                "❌ Unit not found on DXB Interact.\n\n"
                f"🏢 Building: {location_name}\n"
                f"📍 Area: {area}\n"
                f"🏠 Unit: {unit_number}\n"
                f"🆔 LOCATION_ID: {location_id}"
            )

        try:
            await page.get_by_text("Rent", exact=True).click(timeout=10000)
            await page.wait_for_timeout(2500)
        except Exception:
            pass

        body_rent = await page.locator("body").inner_text()

        rents = parse_rents(body_rent)

        status = "🟢 Status: Available"
        if rents:
            status = "🔴 Status: Rented"

        data = {
            "prop_id": prop_id,
            "ejari_id": ejari_id or "-",
            "building": location_name,
            "area": area,
            "unit": unit_number,
            "size": extract(r"Size\s+([\d,]+\s+Sqft)", body_sale),
            "bedrooms": extract(r"Bedrooms\s+([0-9]+|Studio)", body_sale),
            "balcony": extract(r"Balcony\s+(.+?\s+Sqft|No balcony)", body_sale),
            "parking": extract(
                r"Parking\s+(.+?)(?:\s+[0-9.]+%\s+Rental yield|Processing|Transactions history)",
                body_sale,
            ),
            "sales": parse_sales(body_sale),
            "rents": rents,
            "status": status,
        }

        await context.close()
        return format_result(data)


def debug_locations(query, limit=10):
    r = requests.get(LOV_URL, timeout=30).json()
    items = r.get("items", [])

    query_norm = normalize(query)
    scored = []

    for item in items:
        if item.get("flag") not in ["P", "B"]:
            continue

        name = item.get("dv", "")
        score = similarity(query_norm, normalize(name))
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    for score, item in scored[:limit]:
        print(round(score, 3), item)


if __name__ == "__main__":
    import asyncio

    building = input("Building: ").strip()
    unit = input("Unit: ").strip()
    print(asyncio.run(search_dxb_unit_api(building, unit)))
