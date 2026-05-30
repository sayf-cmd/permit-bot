import re
import json
import asyncio
import requests
from urllib.parse import parse_qs
from difflib import SequenceMatcher
from playwright.async_api import async_playwright

LOV_URL = "https://fam-erp.com/property/website/DLDLOV?RETURN_COLUMN=LOCATION_URL"
PROFILE_DIR = "dxb_profile"

MANUAL_LOCATION_NAMES = {
    "acacia c": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    "acacia building c": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    "acacia at park heights building c": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    "st regis downtown residences tower 1": "The St. Regis Residences Tower 1, Downtown Dubai",
    "st.regis downtown residences tower 1": "The St. Regis Residences Tower 1, Downtown Dubai",
    "st regis downtown residences tower 2": "The St. Regis Residences Tower 2, Downtown Dubai",
    "st.regis downtown residences tower 2": "The St. Regis Residences Tower 2, Downtown Dubai",
    "vida dubai mall tower 1": "VIDA Dubai Mall Tower 1, Downtown Dubai",
    "vida dubai mall tower 2": "VIDA Dubai Mall Tower 2, Downtown Dubai",
}


def normalize(text):
    text = str(text or "").lower().strip()
    text = text.replace(".", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def apply_manual_name(building_name):
    q = normalize(building_name)
    for alias, name in MANUAL_LOCATION_NAMES.items():
        if normalize(alias) in q:
            return name
    return building_name


def find_best_location(building_name):
    wanted = apply_manual_name(building_name)

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
    query = normalize(wanted)
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

        score = similarity(query, target) * 10

        shared = query_words & target_words
        missing = query_words - target_words

        score += len(shared) * 8
        score -= len(missing) * 2

        if query == target:
            score += 80
        if query in target:
            score += 45
        if target.startswith(query):
            score += 30

        if "dubai hills" in query and "dubai hills" in target:
            score += 60
        if "downtown" in query and "downtown" in target:
            score += 60
        if "business bay" in query and "business bay" in target:
            score += 60

        if "dubai hills" in query and "damac hills 2" in target:
            score -= 150

        if score > best_score:
            best_score = score
            best = item

    if best_score < 20:
        return None

    return best


def extract(pattern, text, default="-"):
    m = re.search(pattern, text or "", re.I | re.S)
    return m.group(1).strip() if m else default


def parse_sales_from_html(html):
    return re.findall(
        r"<h5[^>]*>\s*([^<]+?)\s*</h5>.*?"
        r"AED\s*([\d,]+).*?"
        r"Sold by:\s*<span[^>]*>\s*([^<]+?)\s*</span>",
        html or "",
        re.I | re.S,
    )


def parse_details_from_html(html):
    size = extract(r"Size</p>\s*<p[^>]*><b>([^<]+)</b>\s*<sup>Sqft</sup>", html)
    bedrooms = extract(r"Bedrooms</p>\s*<p[^>]*><b>([^<]+)</b>", html)
    balcony = extract(r"Balcony</p>\s*<p[^>]*><b>([^<]+)</b>\s*<sup>Sqft</sup>", html)
    parking = extract(r"Parking</p>\s*<p[^>]*><b>([^<]+)</b>", html)

    if size != "-":
        size = f"{size} Sqft"
    if balcony != "-" and "balcony" not in balcony.lower() and "sqft" not in balcony.lower():
        balcony = f"{balcony} Sqft"

    return {
        "size": size,
        "bedrooms": bedrooms,
        "balcony": balcony,
        "parking": parking,
    }


def parse_rents_from_html(html):
    rents = re.findall(
        r"Rental contract\s*.*?([A-Za-z]{3},\s*\d{4}).*?START.*?AED\s*([\d,]+).*?([A-Za-z]{3},\s*\d{4}).*?END",
        html or "",
        re.I | re.S,
    )
    return rents


def format_result(data):
    prop_id = data.get("prop_id", "")
    trakheesi = f"71{prop_id}" if prop_id else "-"

    sales = data.get("sales") or []
    sales_text = "• No sale history found"
    if sales:
        sales_text = "\n".join(
            f"• {date.strip()} — AED {price.strip()} — {seller.strip()}"
            for date, price, seller in sales
        )

    rents = data.get("rents") or []
    rent_text = "• No rental contracts found"
    if rents:
        rent_text = "\n".join(
            f"• {start.strip()} → {end.strip()} — AED {amount.strip()}"
            for start, amount, end in rents
        )

    ejari_line = ""
    if data.get("ejari_id"):
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


async def capture_apex_flow(page, location_id, unit_number):
    captured = {
        "location_name": None,
        "prop_id": None,
        "ejari_id": None,
        "coord": None,
        "details_html": "",
        "sales_html": "",
        "rent_html": "",
    }

    async def on_response(response):
        if "wwv_flow.ajax" not in response.url:
            return

        try:
            req = response.request
            post = req.post_data or ""
            parsed = parse_qs(post)

            p_json_raw = parsed.get("p_json", [""])[0]
            p_request = parsed.get("p_request", [""])[0]
            x01 = parsed.get("x01", [""])[0]

            text = await response.text()

            # JSON response
            if text.lstrip().startswith("{"):
                try:
                    js = json.loads(text)

                    if "values" in js and js["values"]:
                        # Location name resolver
                        val = js["values"][0]
                        if isinstance(val, str) and "," in val:
                            captured["location_name"] = val

                    for item in js.get("item", []):
                        if item.get("id") == "P142_PROP_ID":
                            captured["prop_id"] = item.get("value", "")
                        elif item.get("id") == "P142_EJARI_ID":
                            captured["ejari_id"] = item.get("value", "")
                        elif item.get("id") == "P142_COORD":
                            captured["coord"] = item.get("value", "")
                        elif item.get("id") == "P142_PATH_NAME":
                            captured["location_name"] = item.get("value", "")

                except Exception:
                    pass

            # HTML region responses
            if "propDetails_cards" in text:
                captured["details_html"] = text

            if "PropSaleHistory_cards" in text:
                captured["sales_html"] = text

            if "Rental contract" in text or "No result matching" in text:
                # rent response usually has rental region/no result
                if "P142_EJARI_ID" in p_json_raw or "DLD_EJARI" in p_json_raw or "Rental" in text:
                    captured["rent_html"] = text

        except Exception:
            return

    page.on("response", on_response)

    return captured


async def run_real_search(page, location_name, unit_number):
    # Set hidden values first, then trigger the same actions as the page.
    await page.evaluate(
        """
        ({ locationName, unitNumber }) => {
            const setVal = (id, value) => {
                const el = document.querySelector(id);
                if (el) {
                    el.value = value;
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                }
            };

            setVal("#P142_PATH_NAME", locationName);
            setVal("#P142_PROP_NO", String(unitNumber));
        }
        """,
        {
            "locationName": location_name,
            "unitNumber": str(unit_number),
        },
    )

    # Try visible autocomplete input if possible.
    try:
        inputs = await page.locator("input[type='text']").all()
        for inp in inputs[:6]:
            try:
                val = await inp.input_value()
                box = await inp.bounding_box()
                if box and box["width"] > 100:
                    await inp.click(timeout=1500)
                    await inp.press("Meta+A")
                    await inp.press("Control+A")
                    await inp.fill(location_name)
                    await page.wait_for_timeout(900)
                    try:
                        await page.get_by_text(location_name, exact=True).click(timeout=2500)
                    except Exception:
                        pass
                    break
            except Exception:
                continue
    except Exception:
        pass

    # Fill unit field.
    try:
        await page.locator("#P142_PROP_NO").fill(str(unit_number), timeout=3000)
    except Exception:
        pass

    # Click Search.
    try:
        await page.locator("button").filter(has_text="Search").first.click(timeout=7000)
    except Exception:
        try:
            await page.get_by_text("Search", exact=True).click(timeout=7000)
        except Exception:
            await page.evaluate(
                """
                () => {
                    const btn = [...document.querySelectorAll("button, a")]
                        .find(x => x.innerText.trim() === "Search");
                    if (btn) btn.click();
                }
                """
            )

    await page.wait_for_timeout(9000)

    # Open Rent tab to trigger rent region.
    try:
        await page.get_by_text("Rent", exact=True).click(timeout=7000)
        await page.wait_for_timeout(3000)
    except Exception:
        pass


async def search_dxb_unit_api(building_name: str, unit_number: str) -> str:
    location = find_best_location(building_name)

    if not location:
        return (
            "❌ Building not found or match is uncertain.\n\n"
            f"Building: {building_name}\n"
            f"Unit: {unit_number}"
        )

    initial_location_name = location.get("dv", "")
    location_id = str(location.get("id", ""))
    area = initial_location_name.split(",")[-1].strip() if "," in initial_location_name else "-"

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        captured = await capture_apex_flow(page, location_id, unit_number)

        await page.goto(
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(2500)

        try:
            await page.get_by_text("History", exact=True).click(timeout=5000)
            await page.wait_for_timeout(1000)
        except Exception:
            pass

        await run_real_search(page, initial_location_name, unit_number)

        # If visible flow failed, try direct page hidden read as fallback.
        prop_id = captured.get("prop_id") or await page.evaluate(
            """() => document.querySelector("#P142_PROP_ID")?.value || "" """
        )
        ejari_id = captured.get("ejari_id") or await page.evaluate(
            """() => document.querySelector("#P142_EJARI_ID")?.value || "" """
        )
        page_location_name = captured.get("location_name") or await page.evaluate(
            """() => document.querySelector("#P142_PATH_NAME")?.value || "" """
        )

        if not page_location_name:
            page_location_name = initial_location_name

        area = page_location_name.split(",")[-1].strip() if "," in page_location_name else area

        if not prop_id:
            await context.close()
            return (
                "❌ Unit not found on DXB Interact.\n\n"
                f"🏢 Building: {page_location_name}\n"
                f"📍 Area: {area}\n"
                f"🏠 Unit: {unit_number}\n"
                f"🆔 LOCATION_ID: {location_id}"
            )

        details = parse_details_from_html(captured.get("details_html", ""))
        sales = parse_sales_from_html(captured.get("sales_html", ""))
        rents = parse_rents_from_html(captured.get("rent_html", ""))

        # Fallback body parsing if region capture did not catch details.
        if details["size"] == "-":
            body = await page.locator("body").inner_text()
            details = {
                "size": extract(r"Size\s+([\d,]+\s+Sqft)", body),
                "bedrooms": extract(r"Bedrooms\s+([0-9]+|Studio)", body),
                "balcony": extract(r"Balcony\s+(.+?\s+Sqft|No balcony)", body),
                "parking": extract(r"Parking\s+(.+?)(?:\s+[0-9.]+%\s+Rental yield|Processing|Transactions history)", body),
            }
            if not sales:
                sales = re.findall(
                    r"([A-Za-z]{3},\s+\d{4})\s+AED\s+([\d,]+)\s+Sold by:\s+([A-Za-z]+)",
                    body,
                    re.I,
                )

        status = "🔴 Status: Rented" if rents else "🟢 Status: Available"

        await context.close()

        return format_result({
            "prop_id": prop_id,
            "ejari_id": ejari_id,
            "building": page_location_name,
            "area": area,
            "unit": unit_number,
            "size": details.get("size", "-"),
            "bedrooms": details.get("bedrooms", "-"),
            "balcony": details.get("balcony", "-"),
            "parking": details.get("parking", "-"),
            "sales": sales,
            "rents": rents,
            "status": status,
        })


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
    building = input("Building: ").strip()
    unit = input("Unit: ").strip()
    print(asyncio.run(search_dxb_unit_api(building, unit)))
