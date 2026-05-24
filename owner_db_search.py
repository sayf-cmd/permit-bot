import json
import re
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path

DB_PATH = Path("owners_index.db")

PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-\(\)]{7,}\d)")

BUILDING_KEYS = ["building", "building name", "project", "property", "tower"]
UNIT_KEYS = ["unit", "unit number", "unit no", "plot", "plot no"]
DATE_KEYS = ["date", "regis", "transaction date", "procedure date"]
PRICE_KEYS = ["price", "value", "procedurevalue", "amount"]


def clean(value):
    return str(value or "").strip()


def norm(value):
    return clean(value).lower()


def similarity(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def extract_phones(text):
    phones = []

    for match in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", match)

        if len(digits) < 7:
            continue

        if digits.startswith("971"):
            phone = "+" + digits
        elif digits.startswith("05") and len(digits) == 10:
            phone = "+971" + digits[1:]
        elif digits.startswith("5") and len(digits) == 9:
            phone = "+971" + digits
        else:
            phone = "+" + digits

        if phone not in phones:
            phones.append(phone)

    return phones


def find_by_keys(row_dict, keys):
    for key, value in row_dict.items():
        key_norm = norm(key)

        for wanted in keys:
            if wanted in key_norm and clean(value):
                return clean(value)

    return ""


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
        params + [max_results * 5],
    ).fetchall()

    conn.close()

    results = []

    for row in rows:
        row_text = row["row_text"]

        strong_match = owner in row_text

        if not strong_match and len(parts) >= 2:
            strong_match = all(p in row_text for p in parts)

        if not strong_match:
            continue

        row_dict = json.loads(row["row_json"])

        full_text = " | ".join(str(v) for v in row_dict.values())

        results.append({
            "source_folder": row["source_folder"],
            "file_name": row["file_name"],
            "sheet_name": row["sheet_name"],
            "row_number": row["row_number"],
            "building_name": find_by_keys(row_dict, BUILDING_KEYS),
            "unit_number": find_by_keys(row_dict, UNIT_KEYS),
            "owner_name": owner_name,
            "phones": extract_phones(full_text),
            "date": find_by_keys(row_dict, DATE_KEYS),
            "price": find_by_keys(row_dict, PRICE_KEYS),
            "full_row": row_dict,
        })

        if len(results) >= max_results:
            break

    return results


def format_results_for_telegram(results):
    if not results:
        return "Ничего не найдено."

    messages = []

    for i, r in enumerate(results, start=1):
        phones = ", ".join(r["phones"]) if r["phones"] else "-"

        msg = (
            f"🔎 RESULT #{i}\n"
            f"Folder: {r['source_folder']}\n"
            f"File: {r['file_name']}\n"
            f"Sheet: {r['sheet_name']}\n"
            f"Row: {r['row_number']}\n\n"
            f"Owner: {r['owner_name']}\n"
            f"Building: {r['building_name'] or '-'}\n"
            f"Unit: {r['unit_number'] or '-'}\n"
            f"Date: {r['date'] or '-'}\n"
            f"Price: {r['price'] or '-'}\n"
            f"Phones: {phones}"
        )

        messages.append(msg)

    return "\n\n".join(messages)