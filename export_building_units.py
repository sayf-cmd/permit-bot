import asyncio
import re
import csv
from dxb_interact_api import search_dxb_unit_api


BUILDING = "Burj Crown"
START_UNIT = 1501
END_UNIT = 1510

OUTPUT_FILE = "building_units_export.csv"


def extract_field(label, text):
    pattern = rf"{re.escape(label)}:\s*(.+)"
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def extract_sales(text):
    if "💰 Sale History" not in text:
        return ""

    part = text.split("💰 Sale History", 1)[1]

    if "🏡 Rental Contracts" in part:
        part = part.split("🏡 Rental Contracts", 1)[0]

    return part.strip().replace("\n", " | ")


def extract_rents(text):
    if "🏡 Rental Contracts" not in text:
        return ""

    part = text.split("🏡 Rental Contracts", 1)[1]
    return part.strip().replace("\n", " | ")


async def main():
    rows = []

    for unit in range(START_UNIT, END_UNIT + 1):
        unit = str(unit)
        print(f"Checking {BUILDING} {unit}...")

        try:
            result = await search_dxb_unit_api(BUILDING, unit)

            if result.startswith("❌"):
                continue

            rows.append({
                "Trakheesi": extract_field("🆔 Trakheesi", result),
                "Ejari ID": extract_field("🆔 EJARI ID", result),
                "Building": extract_field("🏢 Building", result),
                "Area": extract_field("📍 Area", result),
                "Unit": extract_field("🏠 Unit", result),
                "Bedrooms": extract_field("🛏 Bedrooms", result),
                "Size": extract_field("📐 Size", result),
                "Balcony": extract_field("🌇 Balcony", result),
                "Parking": extract_field("🅿️ Parking", result),
                "Status": "Rented" if "🔴 Status: Rented" in result else "Available",
                "Sale History": extract_sales(result),
                "Rental Contracts": extract_rents(result),
            })

        except Exception as e:
            print(f"Error {unit}: {e}")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Trakheesi",
                "Ejari ID",
                "Building",
                "Area",
                "Unit",
                "Bedrooms",
                "Size",
                "Balcony",
                "Parking",
                "Status",
                "Sale History",
                "Rental Contracts",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Saved: {OUTPUT_FILE}")
    print(f"Found units: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())