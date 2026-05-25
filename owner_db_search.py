import json
import re
import sqlite3
from pathlib import Path

DB_PATH = "/var/data/owners_index.db"

PHONE_COLUMNS = [
    "mobile",
    "secondary mobile",
    "phone",
    "phone 1",
    "phone 2",
    "mobile 1",
    "mobile 2",
    "telephone",
    "telephone number",
    "contact 1",
    "contact 2",
    "phone mobile",
    "tel",
    "alternate mobile",
    "landline",
]

BUILDING_COLUMNS = [
    "building name",
    "buildingnameen",
    "buildingname 2",
    "building 1",
    "building",
    "project",
    "project name",
    "project_name_en",
    "master project",
    "property name",
]

UNIT_COLUMNS = [
    "unitnumber",
    "unit number",
    "unit no",
    "unit no.",
    "unit",
    "property_number",
    "property number",
]

DATE_COLUMNS = [
    "date",
    "regis",
    "registration",
    "booking date",
    "transaction date",
]

PRICE_COLUMNS = [
    "procedurevalue",
    "procedure value",
    "transaction amount",
    "transaction_amount",
    "price",
    "amount",
    "value",
]


def clean(value):
    return str(value or "").strip()


def norm(value):
    return clean(value).lower().replace("_", " ")


def exact_find(row_dict, candidates):
    for candidate in candidates:
        for key, value in row_dict.items():
            if norm(key) == norm(candidate):
                val = clean(value)
                if val and val.lower() not in ["null", "nan", "#н/д"]:
                    return val
    return ""


def normalize_phone(value):
    digits = re.sub(r"\D", "", clean(value))

    if len(digits) < 7 or len(digits) > 15:
        return ""

    if digits.startswith("00"):
        digits = digits[2:]

    if digits.startswith("971") and len(digits) in [11, 12]:
        return "+" + digits

    if digits.startswith("05") and len(digits) == 10:
        return "+971" + digits[1:]

    if digits.startswith("5") and len(digits) == 9:
        return "+971" + digits

    return "+" + digits


def extract_phones_from_columns(row_dict):
    phones = []

    for key, value in row_dict.items():
        if exact_find({key: value}, PHONE_COLUMNS):
            phone = normalize_phone(value)

            if phone and phone not in phones:
                phones.append(phone)

    return phones


def search_owner_everywhere(owner_name, max_results=50):
    if not DB_PATH.exists():
        return []

    owner = norm(owner_name)
    parts = [p for p in owner.split() if len(p) > 1]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if len(parts) >= 2:
        where = " AND ".join(["row_text like ?" for _ in parts])
        params = [f"%{p}%" for p in parts]
    else:
        where = "row_text like ?"
        params = [f"%{owner}%"]

    rows = cur.execute(
        f"""
        select *
        from rows
        where {where}
        limit ?
        """,
        params + [max_results * 10],
    ).fetchall()

    conn.close()

    results = []
    seen = set()

    for row in rows:
        row_text = row["row_text"]

        if len(parts) >= 2:
            if not all(p in row_text for p in parts):
                continue
        else:
            if owner not in row_text:
                continue

        row_dict = json.loads(row["row_json"])

        building = exact_find(row_dict, BUILDING_COLUMNS)
        unit = exact_find(row_dict, UNIT_COLUMNS)
        date = exact_find(row_dict, DATE_COLUMNS)
        price = exact_find(row_dict, PRICE_COLUMNS)
        phones = extract_phones_from_columns(row_dict)

        duplicate_key = (
            norm(building),
            norm(unit),
            norm(date),
            norm(price),
            tuple(phones),
        )

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)

        results.append(
            {
                "source_folder": row["source_folder"],
                "file_name": row["file_name"],
                "sheet_name": row["sheet_name"],
                "row_number": row["row_number"],
                "building_name": building,
                "unit_number": unit,
                "owner_name": owner_name,
                "phones": phones,
                "date": date,
                "price": price,
                "full_row": row_dict,
            }
        )

        if len(results) >= max_results:
            break

    return results


def format_results_for_telegram(results):
    if not results:
        return "Ничего не найдено."

    total_records = len(results)

    unique_units = len(
        set(
            r["unit_number"]
            for r in results
            if r.get("unit_number")
        )
    )

    unique_owners = len(
        set(
            r["owner_name"]
            for r in results
            if r.get("owner_name")
        )
    )

    unique_phones = len(
        set(
            phone
            for r in results
            for phone in r.get("phones", [])
            if phone
        )
    )

    MAX_RESULTS = 10

    visible_results = results[:MAX_RESULTS]

    messages = []

    header = (
        f"🔍 Search Results\n\n"
        f"📊 Found: {total_records} records\n"
        f"🏠 Unique units: {unique_units}\n"
        f"👤 Unique owners: {unique_owners}\n"
        f"📞 Unique phones: {unique_phones}\n\n"
        f"Showing first {min(total_records, MAX_RESULTS)} results:\n"
    )

    messages.append(header)

    for i, r in enumerate(visible_results, start=1):
        phones = ", ".join(r["phones"]) if r["phones"] else "Not available"

        msg = (
            f"🔎 #{i}\n"
            f"🏢 {r['building_name'] or '-'}\n"
            f"🏠 Unit: {r['unit_number'] or '-'}\n"
            f"👤 Owner: {r['owner_name']}\n"
            f"📞 Phone: {phones}\n"
            f"💰 Price: {r['price'] or '-'}\n"
            f"📅 Date: {r['date'] or '-'}\n"
            f"📁 Source: {r['source_folder']} / {r['file_name']}"
        )

        messages.append(msg)

    remaining = total_records - MAX_RESULTS

    if remaining > 0:
        messages.append(
            f"\n... and {remaining} more records."
        )

    return "\n\n".join(messages)

def normalize_phone_query(value):
    return re.sub(r"\D", "", clean(value))


def search_phone_everywhere(phone_query, max_results=50):
    if not DB_PATH.exists():
        return []

    digits = normalize_phone_query(phone_query)

    if len(digits) < 6:
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        """
        select *
        from rows
        where row_text like ?
        limit ?
        """,
        (f"%{digits[-7:]}%", max_results * 20),
    ).fetchall()

    conn.close()

    results = []
    seen = set()

    for row in rows:
        row_dict = json.loads(row["row_json"])

        phones = extract_phones_from_columns(row_dict)

        phone_digits_list = [
            re.sub(r"\D", "", phone)
            for phone in phones
        ]

        matched = any(
            digits.endswith(p[-7:]) or p.endswith(digits[-7:])
            for p in phone_digits_list
            if len(p) >= 7
        )

        if not matched:
            continue

        building = exact_find(row_dict, BUILDING_COLUMNS)
        unit = exact_find(row_dict, UNIT_COLUMNS)
        date = exact_find(row_dict, DATE_COLUMNS)
        price = exact_find(row_dict, PRICE_COLUMNS)

        owner = (
            exact_find(row_dict, ["owner name", "name", "nameen", "customer name", "full name"])
            or "-"
        )

        duplicate_key = (
            norm(owner),
            norm(building),
            norm(unit),
            norm(date),
            tuple(phones),
        )

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)

        results.append({
            "source_folder": row["source_folder"],
            "file_name": row["file_name"],
            "sheet_name": row["sheet_name"],
            "row_number": row["row_number"],
            "building_name": building,
            "unit_number": unit,
            "owner_name": owner,
            "phones": phones,
            "date": date,
            "price": price,
            "full_row": row_dict,
        })

        if len(results) >= max_results:
            break

    return results

def search_project_unit(query, max_results=50):
    if not DB_PATH.exists():
        return []

    q = norm(query)
    parts = [p for p in q.split() if len(p) > 1]

    if not parts:
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    where = " AND ".join(["row_text like ?" for _ in parts])
    params = [f"%{p}%" for p in parts]

    rows = cur.execute(
        f"""
        select *
        from rows
        where {where}
        limit ?
        """,
        params + [max_results * 20],
    ).fetchall()

    conn.close()

    results = []
    seen = set()

    for row in rows:
        row_dict = json.loads(row["row_json"])

        building = exact_find(row_dict, BUILDING_COLUMNS)
        unit = exact_find(row_dict, UNIT_COLUMNS)
        date = exact_find(row_dict, DATE_COLUMNS)
        price = exact_find(row_dict, PRICE_COLUMNS)
        phones = extract_phones_from_columns(row_dict)

        owner = (
            exact_find(
                row_dict,
                ["owner name", "name", "nameen", "customer name", "full name"]
            )
            or "-"
        )

        full_check = norm(" ".join([building, unit, owner, row["row_text"]]))

        if not all(p in full_check for p in parts):
            continue

        duplicate_key = (
            norm(owner),
            norm(building),
            norm(unit),
            norm(date),
            norm(price),
        )

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)

        results.append({
            "source_folder": row["source_folder"],
            "file_name": row["file_name"],
            "sheet_name": row["sheet_name"],
            "row_number": row["row_number"],
            "building_name": building,
            "unit_number": unit,
            "owner_name": owner,
            "phones": phones,
            "date": date,
            "price": price,
            "full_row": row_dict,
        })

        if len(results) >= max_results:
            break

    return results