import asyncio
import json
from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        async def log_response(response):
            url = response.url

            if "wwv_flow.ajax" not in url:
                return

            try:
                request = response.request
                post_data = request.post_data or ""
                text = await response.text()

                print("\n================ AJAX ================")
                print("URL:", url)
                print("METHOD:", request.method)
                print("\nPOST DATA:")
                print(post_data[:3000])
                print("\nRESPONSE:")
                print(text[:3000])
                print("======================================\n")

            except Exception as e:
                print("LOG ERROR:", e)

        page.on("response", log_response)

        await page.goto(
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        print("\nChrome открыт.")
        print("Теперь вручную сделай поиск на DXB:")
        print("1. Выбери building")
        print("2. Введи unit")
        print("3. Нажми Search")
        print("4. Потом нажми Rent/Sale если нужно")
        print("\nВсе AJAX requests будут печататься здесь.\n")

        input("Когда закончишь тест — нажми ENTER здесь...")

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())