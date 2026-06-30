from pathlib import Path
import re

p = Path("proppy_link_request_api.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_records2_always_button")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# 1) Always open Database 2.0 / Records2, even if actual_owner already exists
text = text.replace(
    'if not data.get("actual_owner") and data.get("records2_link"):',
    'if data.get("records2_link"):'
)

# 2) Replace parse_records2_html so it collects ALL owners/phones by same unit
start = text.find("def parse_records2_html(")
end = text.find("\n\nasync def search_proppy_link_request_data", start)

if start == -1 or end == -1:
    raise SystemExit("parse_records2_html block not found")

new_parse = r'''def parse_records2_html(html: str, expected_unit: str = "") -> Dict[str, Any]:
    """
    Parses Proppy Database 2.0 / Records2 page.
    Collects all matching owners and phones for the same unit.
    """
    tables = _parse_tables(html)
    rows = tables.get("actual_owners", [])

    if not rows:
        return {
            "records2_found": False,
            "records2_rows_count": 0,
        }

    def row_unit(row):
        return _first_non_empty(
            row.get("unit"),
            row.get("Unit"),
            row.get("unit_number"),
            row.get("Unit Number"),
        )

    matching_rows = []

    if expected_unit:
        for row in rows:
            if _unit_match(row_unit(row), expected_unit):
                matching_rows.append(row)

    if not matching_rows:
        matching_rows = rows

    owners = []
    phones = []

    for row in matching_rows:
        owner = _first_non_empty(
            row.get("owner"),
            row.get("Owner"),
            row.get("name"),
            row.get("Name"),
        )

        phone = _first_non_empty(
            row.get("phone"),
            row.get("Phone"),
            row.get("mobile"),
            row.get("Mobile"),
        )

        if owner and owner not in owners:
            owners.append(owner)

        if phone:
            for part in phone.replace(";", ",").split(","):
                part = _clean(part)
                if part and part not in phones:
                    phones.append(part)

    selected = matching_rows[0]

    return {
        "records2_found": True,
        "records2_rows_count": len(matching_rows),
        "actual_owners": matching_rows,

        "records2_owners": ", ".join(owners),
        "records2_phones": ", ".join(phones),

        "actual_owner": ", ".join(owners),
        "actual_mobile": ", ".join(phones),
        "actual_phone": ", ".join(phones),

        "database_building": _first_non_empty(
            selected.get("building"),
            selected.get("Building"),
        ),
        "database_unit": _first_non_empty(
            selected.get("unit"),
            selected.get("Unit"),
            selected.get("unit_number"),
            selected.get("Unit Number"),
        ),
        "price": _first_non_empty(
            selected.get("price"),
            selected.get("Price"),
        ),
        "description": _first_non_empty(
            selected.get("description"),
            selected.get("Description"),
        ),
    }
'''

text = text[:start] + new_parse + text[end:]

# 3) Merge Records2 data into main data and make actual_owners available for Telegram button
text = re.sub(
    r'''                    for key, value in records2_data\.items\(\):
.*?
                    data\["records2_opened"\] = True
''',
    '''                    for key, value in records2_data.items():
                        if value in [None, "", []]:
                            continue

                        # Important for button: keep all Database 2.0 rows
                        if key in ["actual_owners", "records2_owners", "records2_phones", "records2_found", "records2_rows_count"]:
                            data[key] = value
                            continue

                        # Owner/phone from Database 2.0 should be added even if LinkDetails already had owner
                        if key in ["actual_owner", "actual_mobile", "actual_phone"]:
                            existing = _clean(data.get(key))
                            new_value = _clean(value)

                            if existing and new_value and existing != new_value:
                                combined = []
                                for item in (existing + ", " + new_value).split(","):
                                    item = _clean(item)
                                    if item and item not in combined:
                                        combined.append(item)
                                data[key] = ", ".join(combined)
                            else:
                                data[key] = new_value or existing
                            continue

                        if not data.get(key):
                            data[key] = value

                    data["records2_opened"] = True
''',
    text,
    flags=re.S
)

# 4) Hide DmNo / ProcedureName description from Telegram main reply
text = re.sub(
    r'\n        if actual_description:\n            lines\.append\(f"📝 \{actual_description\}"\)',
    '\n        # Description hidden from Telegram output.',
    text
)

p.write_text(text, encoding="utf-8")
print("DONE: Records2 always opens and fills button data")
