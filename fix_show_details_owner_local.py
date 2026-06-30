from pathlib import Path

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_show_details_owner_local")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

start = text.find("def format_proppy_all_numbers(data):")
end = text.find("\n\nasync def handle_proppy_numbers", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл format_proppy_all_numbers или handle_proppy_numbers")

new_func = r'''def format_proppy_all_numbers(data):
    """
    Show more details:
    1) takes owner name from /d result
    2) searches local owner database automatically, like /name
    3) shows max top 10 unique objects
    4) duplicates = Building + Unit + Owner
    5) priority where phone exists
    """

    permit = str(data.get("permit") or data.get("link") or "").strip()

    def clean(value):
        return " ".join(str(value or "").strip().split())

    def norm(value):
        return clean(value).upper()

    def split_names(value):
        result = []
        for part in str(value or "").replace(";", ",").split(","):
            part = clean(part)
            if part and part.upper() not in ["N/A", "NONE", "NULL", "NOT AVAILABLE"]:
                result.append(part)
        return result

    def row_value(row, *keys):
        for key in keys:
            value = row.get(key)
            if value not in [None, ""]:
                return clean(value)
        return ""

    owner_names = []

    # Owners from main /d result
    owner_names += split_names(data.get("records2_owners"))
    owner_names += split_names(data.get("actual_owner"))
    owner_names += split_names(data.get("dld_owner"))

    # Owners from rows
    for row in data.get("actual_owners", []) or []:
        owner = row_value(row, "owner", "Owner", "name", "Name")
        if owner:
            owner_names.append(owner)

    # remove duplicate owner names
    unique_owner_names = []
    seen_owners = set()

    for owner in owner_names:
        key = norm(owner)
        if key and key not in seen_owners:
            seen_owners.add(key)
            unique_owner_names.append(owner)

    owner_names = unique_owner_names[:5]

    cards = {}

    def add_card(building, unit, owner, phones=None, price=""):
        building = clean(building)
        unit = clean(unit)
        owner = clean(owner)
        price = clean(price)

        if phones is None:
            phones = []

        if isinstance(phones, str):
            phones = [x.strip() for x in phones.replace(";", ",").split(",") if x.strip()]

        key = (norm(building), norm(unit), norm(owner))

        if not any(key):
            return

        if key not in cards:
            cards[key] = {
                "building": building,
                "unit": unit,
                "owner": owner,
                "phones": [],
                "price": price,
                "has_phone": False,
            }

        for phone in phones:
            phone = clean(phone)
            if phone and phone not in cards[key]["phones"]:
                cards[key]["phones"].append(phone)
                cards[key]["has_phone"] = True

        if not cards[key].get("price") and price:
            cards[key]["price"] = price

    # Main: local search by owner name, same idea as /name
    for owner_name in owner_names:
        try:
            results = search_owner_everywhere(owner_name) or []
        except Exception as e:
            print("AUTO OWNER LOCAL SEARCH ERROR:", e, flush=True)
            results = []

        for r in results:
            add_card(
                building=r.get("building_name") or r.get("building") or r.get("Building"),
                unit=r.get("unit_number") or r.get("unit") or r.get("Unit"),
                owner=r.get("owner_name") or r.get("owner") or owner_name,
                phones=r.get("phones") or [],
                price=r.get("price") or "",
            )

    # Fallback: if local database found nothing, show details from current result
    if not cards:
        project = clean(data.get("project"))

        for row in data.get("actual_owners", []) or []:
            add_card(
                building=row_value(row, "building", "Building") or project,
                unit=row_value(row, "unit", "Unit", "unit_number", "Unit Number"),
                owner=row_value(row, "owner", "Owner", "name", "Name"),
                phones=row_value(row, "phone", "Phone", "mobile", "Mobile"),
                price=row_value(row, "price", "Price"),
            )

    if not cards:
        return "No additional details found."

    all_cards = list(cards.values())

    # phone first
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

    lines = ["Details"]

    if permit:
        lines.append(f"🔗 Permit: {permit}")

    for card in shown_cards:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━")

        if card.get("building"):
            lines.append(f"🏢 {card['building']}")
        if card.get("unit"):
            lines.append(f"🏠 Unit: {card['unit']}")
        if card.get("owner"):
            lines.append(f"👤 Owner: {card['owner']}")
        if card.get("phones"):
            phone_label = "Phones" if len(card["phones"]) > 1 else "Phone"
            lines.append(f"📞 {phone_label}: {', '.join(card['phones'])}")
        if card.get("price"):
            lines.append(f"💰 Price: {card['price']}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append(f"Shown: {len(shown_cards)} of {total_unique} unique records")

    hidden = total_unique - len(shown_cards)
    if hidden > 0:
        lines.append(f"Hidden: {hidden}")

    return "\n".join(lines)
'''

text = text[:start] + new_func + text[end:]

p.write_text(text, encoding="utf-8")
print("DONE: Show more details now searches local owner database automatically")
