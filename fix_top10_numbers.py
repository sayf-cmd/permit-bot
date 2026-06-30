from pathlib import Path

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_top10_numbers")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

start = text.find("def format_proppy_all_numbers(data):")
end = text.find("\n\nasync def handle_proppy_numbers", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл format_proppy_all_numbers или handle_proppy_numbers")

new_func = r'''def format_proppy_all_numbers(data):
    rows = data.get("actual_owners", []) or []

    area = str(data.get("location_area") or data.get("area") or "").strip()
    project = str(data.get("project") or "").strip()
    permit = str(data.get("permit") or data.get("link") or "").strip()

    lines = ["📞 Все номера по объекту"]

    if permit:
        lines.append(f"🔗 Permit: {permit}")

    def norm(value):
        return " ".join(str(value or "").strip().upper().split())

    def clean_phone(value):
        return str(value or "").strip()

    cards = {}

    for row in rows:
        building = _proppy_row_value(row, "building", "Building") or project
        unit = _proppy_row_value(row, "unit", "Unit", "unit_number", "Unit Number")
        owner = _proppy_row_value(row, "owner", "Owner", "name", "Name")
        phone = _proppy_row_value(row, "phone", "Phone", "mobile", "Mobile")
        price = _proppy_row_value(row, "price", "Price")

        # Duplicate rule: Building + Unit + Owner
        key = (norm(building), norm(unit), norm(owner))

        if not any(key):
            continue

        if key not in cards:
            cards[key] = {
                "building": building,
                "unit": unit,
                "owner": owner,
                "phones": [],
                "price": price,
                "has_phone": False,
            }

        if phone:
            for part in phone.replace(";", ",").split(","):
                part = clean_phone(part)
                if part and part not in cards[key]["phones"]:
                    cards[key]["phones"].append(part)
            cards[key]["has_phone"] = True

        if not cards[key].get("price") and price:
            cards[key]["price"] = price

    # Fallback if Records2 rows are empty
    if not cards:
        owner = str(data.get("actual_owner") or data.get("records2_owners") or "").strip()
        phone = str(data.get("actual_mobile") or data.get("actual_phone") or data.get("records2_phones") or "").strip()
        building = str(data.get("database_building") or project).strip()
        unit = str(data.get("database_unit") or data.get("property_number") or "").strip()
        price = str(data.get("price") or "").strip()

        if not owner and not phone:
            return "No additional numbers found."

        cards[(norm(building), norm(unit), norm(owner))] = {
            "building": building,
            "unit": unit,
            "owner": owner,
            "phones": [phone] if phone else [],
            "price": price,
            "has_phone": bool(phone),
        }

    all_cards = list(cards.values())

    # Priority: records with phone first
    all_cards.sort(
        key=lambda x: (
            not x.get("has_phone", False),
            norm(x.get("building")),
            norm(x.get("unit")),
            norm(x.get("owner")),
        )
    )

    total_unique = len(all_cards)
    shown_cards = all_cards[:10]

    for card in shown_cards:
        building = card.get("building", "")
        unit = card.get("unit", "")
        owner = card.get("owner", "")
        phones = card.get("phones", [])
        price = card.get("price", "")

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━")

        if area:
            lines.append(f"📍 {area}")
        if building:
            lines.append(f"🏢 {building}")
        if unit:
            lines.append(f"🏠 Unit: {unit}")
        if owner:
            lines.append(f"👤 Owner: {owner}")
        if phones:
            phone_text = ", ".join(phones)
            phone_label = "Phones" if len(phones) > 1 else "Phone"
            lines.append(f"📞 {phone_label}: {phone_text}")
        if price:
            lines.append(f"💰 Price: {price}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append(f"Показано: {len(shown_cards)} из {total_unique} уникальных записей")

    hidden = total_unique - len(shown_cards)
    if hidden > 0:
        lines.append(f"Скрыто: {hidden}")

    return "\n".join(lines)
'''

text = text[:start] + new_func + text[end:]
p.write_text(text, encoding="utf-8")

print("DONE: top 10, no duplicates, phone priority added")
