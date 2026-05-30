import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs
from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"
OUT = Path("dxb_apex_templates.json")


async def main():
    templates = {
        "location_name": None,
        "prop_lookup": None,
        "search_log": None,
        "details": None,
        "sales": None,
        "rent": None,
        "roi": None,
    }

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        async def on_response(response):
            if "wwv_flow.ajax" not in response.url:
                return

            try:
                req = response.request
                post = req.post_data or ""
                parsed = parse_qs(post)
                text = await response.text()

                p_request = parsed.get("p_request", [""])[0]
                x01 = parsed.get("x01", [""])[0]
                p_json_raw = parsed.get("p_json", ["{}"])[0]

                try:
                    p_json = json.loads(p_json_raw)
                except Exception:
                    p_json = {}

                items = (
                    p_json
                    .get("pageItems", {})
                    .get("itemsToSubmit", [])
                )

                protected = (
                    p_json
                    .get("pageItems", {})
                    .get("protected", "")
                )

                salt = p_json.get("salt", "")

                names = [x.get("n") for x in items]
                region_id = x01 or ""

                record = {
                    "url": response.url,
                    "p_request": p_request,
                    "x01": x01,
                    "protected": protected,
                    "salt": salt,
                    "items": items,
                    "sample_response": text[:1000],
                }

                # building name resolver
                if names == ["P142_LOCATION_ID"] and text.strip().startswith("{"):
                    templates["location_name"] = record

                # unit -> prop id
                if (
                    "P142_PROP_NO" in names
                    and "P142_LOCATION_ID" in names
                    and "P142_PROP_ID" not in names
                    and text.strip().startswith("{")
                ):
                    templates["prop_lookup"] = record

                # search log / path
                if (
                    "P142_PROP_NO" in names
                    and "P142_PATH_NAME" in names
                    and "P142_PROP_ID" in names
                    and text.strip().startswith("{")
                ):
                    templates["search_log"] = record

                # details
                if "propDetails_cards" in text:
                    templates["details"] = record

                # sales
                if "PropSaleHistory_cards" in text:
                    templates["sales"] = record

                # rent
                if "PropRentHistory_cards" in text or "P142_EJARI_ID" in names:
                    templates["rent"] = record

                # ROI
                if "Rental yield" in text and region_id:
                    templates["roi"] = record

                OUT.write_text(
                    json.dumps(templates, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                print("\nCaptured:")
                for k, v in templates.items():
                    print(k, "✅" if v else "—")

            except Exception as e:
                print("Capture error:", e)

        page.on("response", on_response)

        await page.goto(
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        print("\nChrome открыт.")
        print("Сделай вручную успешный поиск:")
        print("1. Building")
        print("2. Unit")
        print("3. Search")
        print("4. Нажми Rent")
        print("\nКогда всё захватится, нажми ENTER в терминале.")

        input()

        await context.close()

    print(f"Saved: {OUT.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())