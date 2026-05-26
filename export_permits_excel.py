import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = "owners_index.db"

OUTPUT_FILE = "permits_export.xlsx"


PERMIT_COLUMNS = [
    "p-number",
    "P-NUMBER",
    "permit number",
    "permit no",
    "permit_no",
    "permit",
    "per-number",
    "trakheesi no",
    "trakheesi number",
]

BUILDING_COLUMNS = [
    "building name",
    "building",
    "project",
    "project name",
    "property name",
]

UNIT_COLUMNS = [
    "flat",
    "FLAT",
    "unit number",
    "unit no",
    "unit",
    "unitnumber",
]

OWNER_COLUMNS = [
    "owner name",
    "owner",
    "name",
    "customer name",
    "full name",
]

PHONE_COLUMNS = [
    "mobile",
    "mobile 1",
    "mobile 2",
    "phone",
    "phone 1",
    "phone 2",
    "telephone",
]


def clean(v):
    return str(v or "").strip()


def norm(v):
    return clean(v).lower().replace("_", " ")


def find_value(row_dict, candidates):
    for candidate in candidates:
        for key, value in row_dict.items():
            if norm(key) == norm(candidate):
                value = clean(value)

                if value and value.lower() not in ["null", "nan", "#н/д"]:
                    return value

    return ""


def normalize_phone(value):
    digits = re.sub(r"\D", "", clean(value))

    if len(digits) < 7:
        return ""

    return digits


def extract_phone(row_dict):
    phones = []

    for key, value in row_dict.items():
        for candidate in PHONE_COLUMNS:
            if norm(key) == norm(candidate):
                phone = normalize_phone(value)

                if phone and phone not in phones:
                    phones.append(phone)

    return ", ".join(phones)


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

cur = conn.cursor()

rows = cur.execute(
    """
    SELECT row_json
    FROM rows
    """
).fetchall()

print(f"TOTAL SQLITE ROWS: {len(rows)}")

export_rows = []
seen = set()

for idx, row in enumerate(rows, start=1):
    try:
        row_dict = json.loads(row["row_json"])

        permit = find_value(row_dict, PERMIT_COLUMNS)
        building = find_value(row_dict, BUILDING_COLUMNS)
        unit = find_value(row_dict, UNIT_COLUMNS)

        if not permit:
            continue

        if not building and not unit:
            continue

        owner = find_value(row_dict, OWNER_COLUMNS)
        phone = extract_phone(row_dict)

        duplicate_key = (
            permit.lower(),
            building.lower(),
            unit.lower(),
        )

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)

        export_rows.append(
            {
                "permit_number": permit,
                "building_name": building,
                "unit_number": unit,
                "owner_name": owner,
                "phone": phone,
            }
        )

        if idx % 100000 == 0:
            print(f"PROCESSED: {idx}")

    except Exception:
        continue

conn.close()

df = pd.DataFrame(export_rows)

print(f"FINAL ROWS: {len(df)}")

df.to_excel(OUTPUT_FILE, index=False)

print(f"EXPORTED: {OUTPUT_FILE}")