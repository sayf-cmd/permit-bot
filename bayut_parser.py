import asyncio
import re
from playwright.async_api import async_playwright


def find_numbers(text):
    return re.findall(r"\b\d{7,15}\b", text or "")


async def parse(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        responses = []

        async def on_response(response):
            try:
                u = response.url.lower()
                if any(x in u for x in ["bayut", "graphql", "property", "listing", "detail"]):
                    text = await response.text()
                    if any(x in text.lower() for x in ["permit", "rera", "dld", "trakheesi", "reference"]):
                        responses.append((response.url, text[:5000]))
            except Exception:
                pass

        page.on("response", on_response)

        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(10000)

        for _ in range(12):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(500)

        body = await page.locator("body").inner_text()
        html = await page.content()

        print("\n========== BODY LINES ==========\n")
        for line in body.splitlines():
            low = line.lower()
            if any(x in low for x in ["permit", "rera", "dld", "reference", "trakheesi"]):
                print(line)

        print("\n========== NUMBERS IN HTML/BODY ==========\n")
        nums = sorted(set(find_numbers(body + "\n" + html)))
        for n in nums[:200]:
            print(n)

        print("\n========== NETWORK RESPONSES ==========\n")
        for u, text in responses[:20]:
            print("\nURL:", u)
            print(text[:2000])

        await browser.close()


if __name__ == "__main__":
    url = input("Bayut URL: ").strip()
    asyncio.run(parse(url))