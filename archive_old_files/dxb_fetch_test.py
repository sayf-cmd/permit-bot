import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"


async def main():
    location_id = input("LOCATION_ID: ").strip()
    unit_number = input("UNIT: ").strip()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto(
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(3000)

        result = await page.evaluate(
            """
            async ({ locationId, unitNumber }) => {
                const url = "/wwv_flow.ajax?p_context=litedxb/property-history/17221699377089";

                const body = new URLSearchParams();

                body.set("p_flow_id", "242");
                body.set("p_flow_step_id", "142");
                body.set("p_instance", "17221699377089");
                body.set("p_debug", "");
                body.set(
                    "p_request",
                    "PLUGIN=REEgVFlQRX5-ODUwNDQ5NzU3MzkxNjUwMTY1NQ/8jhEjFi34mv72if2DynlejDWDACp2hvpj36FVAZnhR0"
                );

                body.set(
                    "p_json",
                    JSON.stringify({
                        pageItems: {
                            itemsToSubmit: [
                                { n: "P142_TYPE", v: "P" },
                                { n: "P142_PROP_NO", v: unitNumber },
                                {
                                    n: "P142_LOCATION_ID",
                                    v: locationId,
                                    ck: "7HEUshkLnmI3aV0j5cCi0HT-FMiwNkn4lIF9r6EVPko"
                                }
                            ],
                            protected:
                                "UDBfQ1VSUkVOVF9ZRUFSOlAwX1lURF9ZRUFSOlAwX1lURF9DT01QQVJFOlAwX0xP.,R0lOX1VSTDpQMF9DSEFOTkVMOlAwX0NVUlJFTkNZX1ZBTFVFOlAxNDJfUEFUSF9O.,QU1FOlAxNDJfUE9USF9OQU1FOlAxNDJfTE9DQVRJT05fSUQ6UDBfTUVUUklDX1NZTUJPTDpHX1VTRVJfQVVUSDpHX1VTRVJfTkFNRTpHX1VTRVJfSU1BR0U6R19VU0VSX0VNQUlMOkdfVVNFUl9USVRMRTpHX1VTRVJfTU9CSUxFOkdfVVNFUl9DT01QQU5ZOkdfQ09NUEFOWV9MT0dPOkdfVVNFUl9ST0xFOl9HTDpQMF9TT1VSQ0U6UDBfU0lHTlVQX01PQklMRV9DT0RF/t7N3-xEmUVm-rFAI0KoPXH64_XJM4AFHU9TX6_q9Ess",
                            rowVersion: "",
                            formRegionChecksums: []
                        },
                        salt: "98059264775643367109347651372109080611"
                    })
                );

                const res = await fetch(url, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
                    },
                    body
                });

                const text = await res.text();

                return {
                    status: res.status,
                    text
                };
            }
            """,
            {
                "locationId": location_id,
                "unitNumber": unit_number,
            },
        )

        print("\nSTATUS:", result["status"])
        print("\nTEXT:")
        print(result["text"])

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())