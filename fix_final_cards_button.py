from pathlib import Path
import re

# =========================
# 1) Fix proppy_link_request_api.py main Telegram format
# =========================

api = Path("proppy_link_request_api.py")
text = api.read_text(encoding="utf-8")

backup = api.with_suffix(".py.backup_final_cards")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

start = text.find("def format_proppy_data(")
end = text.find("\n\nasync def main", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл format_proppy_data в proppy_link_request_api.py")

new_format = r'''def format_proppy_data(data: Dict[str, Any]) -> str:
    permit = _first_non_empty(data.get("permit"), data.get("link"))
    status = _clean(data.get("status"))

    area = _clean(data.get("location_area") or data.get("area"))
    project = _clean(data.get("project"))
    unit = _clean(data.get("property_number") or data.get("unit_number"))
    property_type = _clean(data.get("property_type"))
    rooms = _clean(data.get("rooms"))
    size = _clean(data.get("property_area") or data.get("size"))

    rows = data.get("actual_owners", []) or []

    def row_value(row, *keys):
        for key in keys:
            value = row.get(key)
            if value not in [None, ""]:
                return _clean(value)
        return ""

    # Main message: show only one clean owner card.
    main_row = rows[0] if rows else {}

    actual_owner = row_value(main_row, "owner", "Owner", "name", "Name") or _clean(data.get("actual_owner"))
    actual_mobile = row_value(main_row, "phone", "Phone", "mobile", "Mobile") or _clean(data.get("actual_mobile") or data.get("actual_phone"))
    actual_building = row_value(main_row, "building", "Building") or _clean(data.get("database_building"))
    actual_unit = row_value(main_row, "unit", "Unit", "unit_number", "Unit Number") or _clean(data.get("database_unit") or unit)
    actual_price = row_value(main_row, "price", "Price") or _clean(data.get("price"))

    lines = []

    if str(status).lower() == "success":
        lines.append("🏢 Property Found")
    else:
        lines.append("🏢 Property")

    if area:
        lines.append(f"\n📍 {area}")
    if project:
        lines.append(f"🏗 {project}")

    if unit or property_type or rooms or size:
        lines.append("")
    if unit:
        lines.append(f"▫️ Unit: {unit}")
    if property_type:
        lines.append(f"▫️ Type: {property_type}")
    if rooms:
        lines.append(f"▫️ Rooms: {rooms}")
    if size:
        lines.append(f"▫️ Size: {size}")

    if status:
        if str(status).lower() == "success":
            lines.append("\n🟢 Verified")
        else:
            lines.append(f"\nStatus: {status}")

    if permit:
        lines.append(f"🔗 Permit: {permit}")

    lines.append(
        "\n\n━━━━━━━━━━━━━━━\n"
        "👤 OWNER INFORMATION\n"
        "━━━━━━━━━━━━━━━"
    )

    if actual_owner or actual_mobile or actual_building:
        lines.append("\n🟢 Actual owner")
        if actual_building:
            lines.append(f"🏢 Building: {actual_building}")
        if actual_unit:
            lines.append(f"🏠 Unit: {actual_unit}")
        if actual_owner:
            lines.append(f"👤 Owner: {actual_owner}")
        if actual_mobile:
            lines.append(f"📞 Phone: {actual_mobile}")
        if actual_price:
            lines.append(f"💰 Price: {actual_price}")
    else:
        lines.append("\nNo owner data found.")

    return "\n".join(lines)
'''

text = text[:start] + new_format + text[end:]
api.write_text(text, encoding="utf-8")


# =========================
# 2) Fix bot.py button + beautiful cards
# =========================

bot_path = Path("bot.py")
bot = bot_path.read_text(encoding="utf-8")

backup2 = bot_path.with_suffix(".py.backup_final_cards")
backup2.write_text(bot, encoding="utf-8")
print(f"Backup saved: {backup2}")

if "from telegram import InlineKeyboardButton, InlineKeyboardMarkup" not in bot:
    bot = "from telegram import InlineKeyboardButton, InlineKeyboardMarkup\n" + bot

if "from telegram.ext import CallbackQueryHandler" not in bot:
    bot = "from telegram.ext import CallbackQueryHandler\n" + bot

helper_start = bot.find("def _proppy_row_value(")
helper_end = bot.find("\n\nasync def handle_proppy_d", helper_start)

helper_block = r'''def _proppy_row_value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in [None, ""]:
            return str(value).strip()
    return ""


def format_proppy_all_numbers(data):
    rows = data.get("actual_owners", []) or []

    area = str(data.get("location_area") or data.get("area") or "").strip()
    project = str(data.get("project") or "").strip()
    permit = str(data.get("permit") or data.get("link") or "").strip()

    lines = ["📞 Все номера по объекту"]

    if permit:
        lines.append(f"🔗 Permit: {permit}")

    def norm(value):
        return " ".join(str(value or "").strip().upper().split())

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
                part = str(part or "").strip()
                if part and part not in cards[key]["phones"]:
                    cards[key]["phones"].append(part)
            cards[key]["has_phone"] = True

        if not cards[key].get("price") and price:
            cards[key]["price"] = price

    # Fallback if rows are empty
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

    # Priority: with phone first
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


async def handle_proppy_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    permit = query.data.split(":", 1)[1].strip()

    cache = context.application.bot_data.setdefault("proppy_cache", {})
    data = cache.get(permit)

    if not data:
        await query.message.reply_text("⏳ Loading numbers...")
        data = await search_proppy_link_request_data(permit)
        cache[permit] = data

    text = format_proppy_all_numbers(data)

    if len(text) > 3900:
        for i in range(0, len(text), 3900):
            await query.message.reply_text(text[i:i + 3900])
    else:
        await query.message.reply_text(text)
'''

if helper_start != -1 and helper_end != -1:
    bot = bot[:helper_start] + helper_block + bot[helper_end:]
elif "async def handle_proppy_d" in bot:
    bot = bot.replace("async def handle_proppy_d", helper_block + "\n\nasync def handle_proppy_d", 1)
else:
    raise SystemExit("Не нашёл handle_proppy_d в bot.py")

# Replace handle_proppy_d fully
start = bot.find("async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):")
end = bot.find("\nasync def handle_dxb(", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл блок handle_proppy_d / handle_dxb")

new_handle = r'''async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        permit = " ".join(context.args).strip()

        if not permit:
            await update.message.reply_text(
                "Напиши так:\n/d 71495668339",
                reply_markup=MENU_KEYBOARD,
            )
            return

        msg = await update.message.reply_text("⏳ Searching...")

        data = await search_proppy_link_request_data(permit)
        result_text = format_proppy_data(data)

        context.application.bot_data.setdefault("proppy_cache", {})[permit] = data

        rows = data.get("actual_owners", []) or []
        has_numbers_button = bool(
            rows
            or data.get("actual_mobile")
            or data.get("actual_phone")
            or data.get("records2_phones")
        )

        numbers_keyboard = None
        if has_numbers_button:
            numbers_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Показать все номера", callback_data=f"proppy_numbers:{permit}")]
            ])

        try:
            spreadsheet = get_spreadsheet()
            append_proppy_result(spreadsheet, permit, data)
        except Exception as e:
            print("PROPPY SHEET SAVE ERROR:", e, flush=True)

        if len(result_text) > 3900:
            await msg.delete()
            chunks = [result_text[i:i + 3900] for i in range(0, len(result_text), 3900)]
            for index, chunk in enumerate(chunks):
                markup = numbers_keyboard if index == len(chunks) - 1 else None
                await update.message.reply_text(chunk, reply_markup=markup)
        else:
            await msg.edit_text(result_text, reply_markup=numbers_keyboard)

    except Exception as e:
        import traceback

        traceback.print_exc()

        await update.message.reply_text(
            f"❌ Proppy error:\n{e}",
            reply_markup=MENU_KEYBOARD,
        )

'''

bot = bot[:start] + new_handle + bot[end+1:]

handler_line = 'app.add_handler(CallbackQueryHandler(handle_proppy_numbers, pattern=r"^proppy_numbers:"))'

if handler_line not in bot:
    marker = 'app.add_handler(CommandHandler("d", handle_proppy_d))'
    if marker in bot:
        bot = bot.replace(marker, marker + "\n    " + handler_line)
    else:
        run_marker = "app.run_polling"
        pos = bot.find(run_marker)
        if pos == -1:
            raise SystemExit("Не нашёл место для CallbackQueryHandler")
        line_start = bot.rfind("\n", 0, pos) + 1
        bot = bot[:line_start] + "    " + handler_line + "\n" + bot[line_start:]

bot_path.write_text(bot, encoding="utf-8")

print("DONE: clean main reply + separate beautiful numbers button")
