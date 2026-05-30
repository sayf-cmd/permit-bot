import asyncio
import json
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

        data = await page.evaluate(
            """
            () => {
                return {
                    pFlowId: document.querySelector("#pFlowId")?.value || "",
                    pFlowStepId: document.querySelector("#pFlowStepId")?.value || "",
                    pInstance: document.querySelector("#pInstance")?.value || "",
                    pContext: document.querySelector("#pContext")?.value || "",
                    pSalt: document.querySelector("#pSalt")?.value || "",
                    protected: apex?.page?.itemsToSubmit ? "" : "",
                    pageText: document.body.innerText.slice(0, 1000)
                };
            }
            """
        )

        print("\nPAGE DATA:")
        print(json.dumps(data, indent=2))

        print("\nТеперь вручную выбери building и введи unit на странице, но НЕ нажимай ENTER в терминале.")
        input("Когда на странице появится результат — нажми ENTER здесь...")

        # После ручного действия читаем реальные значения скрытых полей
        values = await page.evaluate(
            """
            () => {
                const get = (id) => document.querySelector(id)?.value || "";
                return {
                    P142_LOCATION_ID: get("#P142_LOCATION_ID"),
                    P142_PROP_NO: get("#P142_PROP_NO"),
                    P142_PROP_ID: get("#P142_PROP_ID"),
                    P142_EJARI_ID: get("#P142_EJARI_ID"),
                    P142_DLD_ID: get("#P142_DLD_ID"),
                    P142_PATH_NAME: get("#P142_PATH_NAME"),
                    P142_COORD: get("#P142_COORD"),
                    body: document.body.innerText.slice(0, 3000)
                };
            }
            """
        )

        print("\nPAGE VALUES AFTER SEARCH:")
        print(json.dumps(values, indent=2, ensure_ascii=False))

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())