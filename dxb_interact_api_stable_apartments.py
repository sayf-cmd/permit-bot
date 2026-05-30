import re
import json
import asyncio
import requests
from urllib.parse import parse_qs
from difflib import SequenceMatcher
from playwright.async_api import async_playwright

LOV_URL = "https://fam-erp.com/property/website/DLDLOV?RETURN_COLUMN=LOCATION_URL"
PROFILE_DIR = "dxb_profile"

MANUAL_LOCATIONS = {
    "acacia c": {
        "id": "35567",
        "dv": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    },
    "acacia building c": {
        "id": "35567",
        "dv": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    },
    "acacia at park heights building c": {
        "id": "35567",
        "dv": "Building C, Acacia At Park Heights, Dubai Hills Estate",
    },
    "mulberry 2 b1": {
        "id": "35668",
        "dv": "Mulberry 2 Building B1, Mulberry Park Heights, Dubai Hills Estate",
    },
    "mulberry b1": {
        "id": "35668",
        "dv": "Mulberry 2 Building B1, Mulberry Park Heights, Dubai Hills Estate",
    },
}

BUILDING_ALIASES = {
    "st regis downtown residences tower 1": "The St. Regis Residences Tower 1",
    "st.regis downtown residences tower 1": "The St. Regis Residences Tower 1",
    "st regis downtown residences tower 2": "The St. Regis Residences Tower 2",
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


def apply_alias(text):
    q = normalize(text)

    for alias, item in MANUAL_LOCATIONS.items():
        if normalize(alias) in q:
            return item

    for alias, actual in BUILDING_ALIASES.items():
        if normalize(alias) in q:
            return actual

    return text


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
        if item.get("flag") not in ["P", "B"]:
            continue

        name = item.get("dv", "")
        target = normalize(name)
        target_words = set(target.split())

        score = similarity(query, target) * 10
        score += len(query_words & target_words) * 8
        score -= len(query_words - target_words) * 2

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

    return {
        "id": str(best.get("id", "")),
        "dv": best.get("dv", ""),
    }


def extract(pattern, text, default="-"):
    m = re.search(pattern, text or "", re.I | re.S)
    return m.group(1).strip() if m else default


def parse_details_html(html):
    size = extract(r"Size</p>\s*<p[^>]*><b>([^<]+)</b>\s*<sup>Sqft</sup>", html)
    bedrooms = extract(r"Bedrooms</p>\s*<p[^>]*><b>([^<]+)</b>", html)
    balcony = extract(r"Balcony</p>\s*<p[^>]*><b>([^<]+)</b>\s*<sup>Sqft</sup>", html)
    parking = extract(r"Parking</p>\s*<p[^>]*[^>]*><b>([^<]+)</b>", html)

    if size != "-":
        size = f"{size} Sqft"
    if balcony != "-" and "sqft" not in balcony.lower():
        balcony = f"{balcony} Sqft"

    return {
        "size": size,
        "bedrooms": bedrooms,
        "balcony": balcony,
        "parking": parking,
    }


def parse_sales_html(html):
    return re.findall(
        r"<h5[^>]*>\s*([^<]+?)\s*</h5>.*?"
        r"AED\s*([\d,]+).*?"
        r"Sold by:\s*<span[^>]*>\s*([^<]+?)\s*</span>",
        html or "",
        re.I | re.S,
    )


def parse_rents_html(html):
    return re.findall(
        r"<h5[^>]*>\s*([^<]+?)\s*</h5>\s*<p>START</p>.*?"
        r"AED\s*([\d,]+).*?"
        r"<h5[^>]*>\s*([^<]+?)\s*</h5>\s*<p>END</p>",
        html or "",
        re.I | re.S,
    )


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


def classify_template(post_data, response_text):
    parsed = parse_qs(post_data or "")
    p_json_raw = parsed.get("p_json", ["{}"])[0]
    p_request = parsed.get("p_request", [""])[0]
    x01 = parsed.get("x01", [""])[0]
    widget_action = parsed.get("p_widget_action", [""])[0]

    try:
        p_json = json.loads(p_json_raw)
    except Exception:
        p_json = {}

    items = p_json.get("pageItems", {}).get("itemsToSubmit", [])
    names = [x.get("n") for x in items]
    protected = p_json.get("pageItems", {}).get("protected", "")
    salt = p_json.get("salt", "")

    record = {
        "p_request": p_request,
        "x01": x01,
        "widget_action": widget_action,
        "protected": protected,
        "salt": salt,
        "items": items,
    }

    text = response_text or ""

    if names == ["P142_LOCATION_ID"] and text.strip().startswith("{"):
        return "location_name", record

    if (
        "P142_PROP_NO" in names
        and "P142_LOCATION_ID" in names
        and "P142_PROP_ID" not in names
        and text.strip().startswith("{")
    ):
        return "prop_lookup", record

    if (
        "P142_PROP_NO" in names
        and "P142_PATH_NAME" in names
        and "P142_PROP_ID" in names
        and text.strip().startswith("{")
    ):
        return "search_log", record

    if "propDetails_cards" in text:
        return "details", record

    if "PropSaleHistory_cards" in text:
        return "sales", record

    if "PropRentHistory_cards" in text or "P142_EJARI_ID" in names:
        return "rent", record

    if "Rental yield" in text and x01:
        return "roi", record

    return None, record


async def capture_runtime_templates(page):
    templates = {
        "location_name": None,
        "prop_lookup": None,
        "search_log": None,
        "details": None,
        "sales": None,
        "rent": None,
        "roi": None,
    }

    async def on_response(response):
        if "wwv_flow.ajax" not in response.url:
            return
        try:
            req = response.request
            post = req.post_data or ""
            text = await response.text()
            kind, record = classify_template(post, text)
            if kind and not templates.get(kind):
                templates[kind] = record
        except Exception:
            pass

    page.on("response", on_response)
    return templates


async def do_warmup_search(page):
    """
    Automatic warmup search. This triggers DXB to emit fresh APEX templates
    for the current p_instance/session.
    """
    await page.wait_for_timeout(1500)

    await page.evaluate(
        """
        () => {
            const setVal = (id, value) => {
                const el = document.querySelector(id);
                if (el) {
                    el.value = value;
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                    el.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true }));
                }
            };

            setVal("#P142_TYPE", "P");
            setVal("#P142_LOCATION_ID", "31624");
            setVal("#P142_PATH_NAME", "The Pad, Business Bay");
            setVal("#P142_PROP_NO", "607");
        }
        """
    )

    await page.wait_for_timeout(1000)

    clicked = False

    try:
        await page.locator("button").filter(has_text="Search").first.click(
            timeout=7000,
            force=True,
        )
        clicked = True
    except Exception:
        pass

    if not clicked:
        try:
            await page.get_by_text("Search", exact=True).click(
                timeout=7000,
                force=True,
            )
            clicked = True
        except Exception:
            pass

    if not clicked:
        await page.evaluate(
            """
            () => {
                const candidates = [...document.querySelectorAll("button, a, input[type='button'], input[type='submit']")];
                const btn = candidates.find(x =>
                    (x.innerText || x.value || "").trim() === "Search"
                );
                if (!btn) throw new Error("Search button not found");
                btn.click();
            }
            """
        )

    await page.wait_for_timeout(8000)

    try:
        await page.get_by_text("Rent", exact=True).click(timeout=7000, force=True)
        await page.wait_for_timeout(3000)
    except Exception:
        pass

    try:
        await page.get_by_text("Sale", exact=True).click(timeout=5000, force=True)
        await page.wait_for_timeout(1000)
    except Exception:
        pass


async def apex_post(page, template, items, *, x01=None, widget_action=None):
    ck_by_name = {
        item.get("n"): item.get("ck")
        for item in template.get("items", [])
        if item.get("ck")
    }

    return await page.evaluate(
        """
        async ({ pRequest, items, x01, widgetAction, protectedValue, saltValue, ckByName }) => {
            const get = (id) => document.querySelector(id)?.value || "";
            const pFlowId = get("#pFlowId") || "242";
            const pFlowStepId = get("#pFlowStepId") || "142";
            const pInstance = get("#pInstance") || "";
            const pContext = get("#pContext") || "";

            const normalizedItems = items.map(item => {
                const out = { n: item.n, v: String(item.v ?? "") };
                const ck = ckByName[item.n];
                if (ck) out.ck = ck;
                if (item.ck) out.ck = item.ck;
                return out;
            });

            const body = new URLSearchParams();
            body.set("p_flow_id", pFlowId);
            body.set("p_flow_step_id", pFlowStepId);
            body.set("p_instance", pInstance);
            body.set("p_debug", "");
            body.set("p_request", pRequest);

            if (widgetAction) body.set("p_widget_action", widgetAction);
            if (x01) body.set("x01", x01);

            body.set(
                "p_json",
                JSON.stringify({
                    pageItems: {
                        itemsToSubmit: normalizedItems,
                        protected: protectedValue,
                        rowVersion: "",
                        formRegionChecksums: []
                    },
                    salt: saltValue
                })
            );

            const res = await fetch(`/wwv_flow.ajax?p_context=${pContext}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body
            });

            return await res.text();
        }
        """,
        {
            "pRequest": template["p_request"],
            "items": items,
            "x01": x01 if x01 is not None else template.get("x01", ""),
            "widgetAction": widget_action if widget_action is not None else template.get("widget_action", ""),
            "protectedValue": template.get("protected", ""),
            "saltValue": template.get("salt", ""),
            "ckByName": ck_by_name,
        },
    )


def parse_json_items(text):
    try:
        data = json.loads(text)
    except Exception:
        return {}

    out = {}

    for val in data.get("values", []) or []:
        if isinstance(val, str):
            out.setdefault("values", []).append(val)

    for item in data.get("item", []) or []:
        out[item.get("id")] = item.get("value", "")

    return out


async def search_dxb_unit_api(building_name: str, unit_number: str) -> str:
    location = find_best_location(building_name)

    if not location:
        return (
            "❌ Building not found or match is uncertain.\n\n"
            f"Building: {building_name}\n"
            f"Unit: {unit_number}"
        )

    location_id = str(location["id"])
    location_name = location["dv"]
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
        templates = await capture_runtime_templates(page)

        await page.goto(
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(2000)

        await do_warmup_search(page)

        # Wait until required templates are available.
        for _ in range(20):
            required_ok = (
                templates.get("location_name")
                and templates.get("prop_lookup")
                and templates.get("search_log")
                and templates.get("details")
                and templates.get("sales")
            )
            if required_ok:
                break
            await page.wait_for_timeout(500)

        missing = [
            k for k in ["location_name", "prop_lookup", "search_log", "details", "sales"]
            if not templates.get(k)
        ]

        if missing:
            await context.close()
            return (
                "❌ Could not capture fresh DXB APEX templates.\n\n"
                f"Missing: {', '.join(missing)}"
            )

        name_text = await apex_post(
            page,
            templates["location_name"],
            [{"n": "P142_LOCATION_ID", "v": location_id}],
        )
        name_data = parse_json_items(name_text)
        if name_data.get("values"):
            location_name = name_data["values"][0]
            area = location_name.split(",")[-1].strip() if "," in location_name else area

        prop_text = await apex_post(
            page,
            templates["prop_lookup"],
            [
                {"n": "P142_TYPE", "v": "P"},
                {"n": "P142_PROP_NO", "v": str(unit_number)},
                {"n": "P142_LOCATION_ID", "v": location_id},
            ],
        )
        prop_data = parse_json_items(prop_text)

        prop_id = prop_data.get("P142_PROP_ID", "")
        ejari_id = prop_data.get("P142_EJARI_ID", "")

        if not prop_id:
            await context.close()
            return (
                "❌ Unit not found on DXB Interact.\n\n"
                f"🏢 Building: {location_name}\n"
                f"📍 Area: {area}\n"
                f"🏠 Unit: {unit_number}\n"
                f"🆔 LOCATION_ID: {location_id}\n\n"
                f"Debug response: {prop_text[:300]}"
            )

        await apex_post(
            page,
            templates["search_log"],
            [
                {"n": "P142_TYPE", "v": "P"},
                {"n": "P142_PROP_NO", "v": str(unit_number)},
                {"n": "P142_PATH_NAME", "v": location_name},
                {"n": "P142_LOCATION_ID", "v": location_id},
                {"n": "P142_PROP_ID", "v": prop_id},
            ],
        )

        details_html = await apex_post(
            page,
            templates["details"],
            [
                {"n": "P142_TYPE", "v": "P"},
                {"n": "P142_LOCATION_ID", "v": location_id},
                {"n": "P142_PROP_ID", "v": prop_id},
            ],
            widget_action="reset",
        )

        sales_html = await apex_post(
            page,
            templates["sales"],
            [
                {"n": "P142_PROP_ID", "v": prop_id},
                {"n": "P142_DLD_ID", "v": ""},
            ],
            widget_action="reset",
        )

        rent_html = ""
        if ejari_id and templates.get("rent"):
            rent_html = await apex_post(
                page,
                templates["rent"],
                [
                    {"n": "P142_EJARI_ID", "v": ejari_id},
                    {"n": "P142_DLD_EJARI_ID", "v": ""},
                ],
                widget_action="reset",
            )

        await context.close()

    details = parse_details_html(details_html)
    sales = parse_sales_html(sales_html)
    rents = parse_rents_html(rent_html)

    status = "🔴 Status: Rented" if rents else "🟢 Status: Available"

    return format_result(
        {
            "prop_id": prop_id,
            "ejari_id": ejari_id,
            "building": location_name,
            "area": area,
            "unit": str(unit_number),
            "size": details.get("size", "-"),
            "bedrooms": details.get("bedrooms", "-"),
            "balcony": details.get("balcony", "-"),
            "parking": details.get("parking", "-"),
            "sales": sales,
            "rents": rents,
            "status": status,
        }
    )


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
