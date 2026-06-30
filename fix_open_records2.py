from pathlib import Path

p = Path("proppy_link_request_api.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_records2")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

insert_before = "\nasync def search_proppy_link_request_data(permit: str) -> Dict[str, Any]:"

records2_func = r'''

def _unit_match(a: Any, b: Any) -> bool:
    a = _clean(a).upper()
    b = _clean(b).upper()

    a = re.sub(r"\.0$", "", a)
    b = re.sub(r"\.0$", "", b)

    a = re.sub(r"\s+", "", a)
    b = re.sub(r"\s+", "", b)

    return bool(a and b and a == b)


def parse_records2_html(html: str, expected_unit: str = "") -> Dict[str, Any]:
    """
    Parses Proppy Database 2.0 / Records2 page.
    Used as fallback when LinkDetails has no Actual owner table.
    """
    tables = _parse_tables(html)
    rows = tables.get("actual_owners", [])

    if not rows:
        return {
            "records2_found": False,
            "records2_rows_count": 0,
        }

    selected = None

    if expected_unit:
        for row in rows:
            row_unit = _first_non_empty(
                row.get("unit"),
                row.get("Unit"),
                row.get("unit_number"),
                row.get("Unit Number"),
            )
            if _unit_match(row_unit, expected_unit):
                selected = row
                break

    if selected is None:
        selected = rows[0]

    actual_owner = _first_non_empty(
        selected.get("owner"),
        selected.get("Owner"),
        selected.get("name"),
        selected.get("Name"),
    )

    actual_mobile = _first_non_empty(
        selected.get("phone"),
        selected.get("Phone"),
        selected.get("mobile"),
        selected.get("Mobile"),
    )

    return {
        "records2_found": True,
        "records2_rows_count": len(rows),
        "actual_owners": rows,
        "actual_owner": actual_owner,
        "actual_mobile": actual_mobile,
        "actual_phone": actual_mobile,
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

if "def parse_records2_html(" not in text:
    text = text.replace(insert_before, records2_func + insert_before)

old = '''            data = parse_linkdetails_html(html, final_url=details_url)
            data["permit"] = data.get("permit") or permit
            data["link"] = data.get("link") or permit
            data["progress"] = progress

            if not data.get("status"):
                data["status"] = progress.get("status", "")

            return data
'''

new = '''            data = parse_linkdetails_html(html, final_url=details_url)

            # Fallback: if LinkDetails does not contain Actual owner,
            # open the "Search more in Database" / Records2 page.
            if not data.get("actual_owner") and data.get("records2_link"):
                try:
                    await page.goto(
                        data["records2_link"],
                        wait_until="networkidle",
                        timeout=90000,
                    )
                    records2_html = await page.content()

                    records2_data = parse_records2_html(
                        records2_html,
                        expected_unit=data.get("property_number") or data.get("unit_number") or "",
                    )

                    for key, value in records2_data.items():
                        if key == "actual_owners":
                            data[key] = value
                        elif value not in [None, "", []]:
                            if not data.get(key):
                                data[key] = value

                    data["records2_opened"] = True

                except Exception as e:
                    data["records2_opened"] = False
                    data["records2_error"] = str(e)

            data["permit"] = data.get("permit") or permit
            data["link"] = data.get("link") or permit
            data["progress"] = progress

            if not data.get("status"):
                data["status"] = progress.get("status", "")

            return data
'''

if old not in text:
    raise SystemExit("Не нашёл нужный блок для замены. Скинь grep search_proppy_link_request_data.")
    
text = text.replace(old, new)

p.write_text(text, encoding="utf-8")
print("DONE: Records2 fallback added")
