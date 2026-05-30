import asyncio
from playwright.async_api import async_playwright

PROFILE_DIR = "dxb_profile"
OUT_FILE = "dxb_network_log.txt"


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        logs = []

        async def log_request(request):
            url = request.url
            method = request.method
            rtype = request.resource_type

            if "dxbinteract.com" not in url:
                return

            if rtype in ["xhr", "fetch", "document"] or method == "POST":
                logs.append(f"\nREQUEST {method} [{rtype}]: {url}")

                try:
                    post_data = request.post_data
                    if post_data:
                        logs.append(f"POST_DATA: {post_data[:3000]}")
                except Exception:
                    pass

        async def log_response(response):
            url = response.url
            request = response.request
            rtype = request.resource_type

            if "dxbinteract.com" not in url:
                return

            if rtype in ["xhr", "fetch", "document"] or request.method == "POST":
                logs.append(f"RESPONSE {response.status} [{rtype}]: {url}")

                try:
                    txt = await response.text()
                    if any(x in txt.lower() for x in ["grande", "4702", "349"]):
                        logs.append("BODY_PREVIEW:")
                        logs.append(txt[:5000])
                except Exception:
                    pass

        page.on("request", log_request)
        page.on("response", log_response)

        await page.goto(
            "https://dxbinteract.com/dubai-property-prices",
            wait_until="domcontentloaded",
        )

        print("\nСейчас вручную сделай поиск:")
        print("1. Building: Grande")
        print("2. Unit: 4702")
        print("3. Click Search")
        input("\nКогда результат откроется — нажми ENTER здесь...")

        await page.wait_for_timeout(3000)

        logs.append(f"\nFINAL_URL: {page.url}")

        with open(OUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(logs))

        print(f"\nSaved: {OUT_FILE}")

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())