import asyncio
import csv
import re
from dxb_interact_api import search_dxb_unit_api

BUILDING = input("Building name: ").strip()
START_UNIT = int(input("Start unit: ").strip())
END_UNIT = int(input("End unit: ").strip())

OUTPUT_FILE = "dxb_building_permits.csv"


def extract(label, text):
    m = re.search(rf"{re.escape(label)}:\s*(.+)", text)
    return m.group(1).strip() if m else ""


async def main():
    rows = []

    for unit in range(START_UNIT, END_UNIT + 1):
        unit = str(unit)
        print(f"Checking {BUILDING} {unit}...")

        result = await search_dxb_unit_api(BUILDING, unit)

        if result.startswith("❌"):
            print("NOT FOUND")
            continue

        row = {
            "Permit": extract("🆔 Trakheesi", result),
            "Building": extract("🏢 Building", result),
            "Unit": extract("🏠 Unit", result),
            "Size": extract("📐 Size", result),
            "Room": extract("🛏 Bedrooms", result),
        }

        rows.append(row)
        print("FOUND:", row)

        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Permit", "Building", "Unit", "Size", "Room"],
            )
            writer.writeheader()
            writer.writerows(rows)

    print(f"Done. Found {len(rows)} units. Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
