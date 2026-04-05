import asyncio
import re
import pandas as pd
from playwright.async_api import async_playwright

MAX_LISTINGS = 30

async def collect_urls(page):
    urls = set()

    for _ in range(10):
        links = page.locator("a[href*='/property/details-']")
        count = await links.count()

        for i in range(count):
            try:
                href = await links.nth(i).get_attribute("href")
                if href and "/property/details-" in href:
                    if href.startswith("http"):
                        urls.add(href)
                    else:
                        urls.add("https://www.bayut.com" + href)
            except:
                pass

        if len(urls) >= MAX_LISTINGS:
            break

        await page.mouse.wheel(0, 3000)
        await page.wait_for_timeout(1200)

    return list(urls)[:MAX_LISTINGS]


async def parse_listing(page, url):
    await page.goto(url)
    await page.wait_for_timeout(3000)

    body = await page.locator("body").inner_text()

    price = ""
    m = re.search(r"AED[\s,]*([\d,]+)", body)
    if m:
        price = m.group(1)

    beds = ""
    m = re.search(r"(\d+)\s*Beds?", body, re.IGNORECASE)
    if m:
        beds = m.group(1)
    elif re.search(r"Studio", body, re.IGNORECASE):
        beds = "Studio"

    sqft = ""
    m = re.search(r"([\d,]+)\s*(sqft|sq\.ft)", body, re.IGNORECASE)
    if m:
        sqft = m.group(1)

    permit = ""
    m = re.search(r"Permit(?: Number| No)?\s*[:#-]?\s*(\d+)", body, re.IGNORECASE)
    if m:
        permit = m.group(1)

    return {
        "url": url,
        "permit": permit,
        "beds": beds,
        "price_aed": price,
        "size_sqft": sqft
    }


async def run():
    data = []

    building_name = input("Введи название билдинга: ").strip()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print("Открой Bayut и настрой:")
        print("- Rent")
        print("- 1 building")
        print("- Newest")
        print("- Filters if needed")
        print("Когда будешь готов, нажми ENTER здесь")
        input()

        urls = await collect_urls(page)
        print(f"Найдено: {len(urls)}")

        for i, url in enumerate(urls, 1):
            print(f"{i}/{len(urls)}")
            try:
                item = await parse_listing(page, url)
                item["building"] = building_name
                data.append(item)
            except:
                pass

        await browser.close()

    df = pd.DataFrame(data, columns=[
        "url",
        "permit",
        "building",
        "beds",
        "price_aed",
        "size_sqft"
    ])

    df.to_excel("result.xlsx", index=False)
    print("ГОТОВО -> result.xlsx")


asyncio.run(run())
