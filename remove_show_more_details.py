from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_remove_show_more_details")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# 1) Убираем сломанный/лишний import search_owner_records2_by_owner_name
lines = text.splitlines()
lines = [
    line for line in lines
    if "search_owner_records2_by_owner_name" not in line
]
text = "\n".join(lines) + "\n"

# 2) Убираем CallbackQueryHandler для Show more details
text = re.sub(
    r'\n\s*app\.add_handler\(CallbackQueryHandler\(handle_proppy_numbers.*?\)\)',
    '',
    text
)

# 3) Убираем функцию handle_proppy_numbers, если есть
start = text.find("async def handle_proppy_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):")
if start != -1:
    end = text.find("\n\nasync def handle_proppy_d", start)
    if end != -1:
        text = text[:start] + text[end+2:]

# 4) Убираем функцию format_proppy_all_numbers, если есть
start = text.find("def format_proppy_all_numbers(data):")
if start != -1:
    end = text.find("\n\nasync def handle_proppy_numbers", start)
    if end != -1:
        text = text[:start] + text[end+2:]

# 5) Убираем helper _proppy_row_value, если остался
start = text.find("def _proppy_row_value(row, *keys):")
if start != -1:
    end = text.find("\n\nasync def handle_proppy_d", start)
    if end != -1:
        text = text[:start] + text[end+2:]

# 6) Заменяем handle_proppy_d на чистый вариант без кнопки
start = text.find("async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):")
end = text.find("\nasync def handle_dxb(", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл handle_proppy_d или handle_dxb")

new_handle = r'''async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_input = " ".join(context.args).strip()

        if not user_input:
            await update.message.reply_text(
                "Send permit or listing link:\n"
                "/d 71495697794\n"
                "/d https://propertyfinder.ae/...",
                reply_markup=MENU_KEYBOARD,
            )
            return

        urls = re.findall(r"https?://\S+", user_input)
        listing_url = urls[0] if urls else ""

        if listing_url:
            msg = await update.message.reply_text("🔎 Extracting permit from listing link...")

            permit = await extract_permit_safe(listing_url)

            if not permit:
                await msg.edit_text("❌ Could not find permit number in this listing link.")
                return

            await msg.edit_text("⏳ Searching...")
        else:
            permit = normalize_permit(user_input)

            if not permit:
                candidates = re.findall(r"\d{8,20}", user_input)
                permit = normalize_permit(candidates[0]) if candidates else ""

            if not permit:
                await update.message.reply_text(
                    "Please send a valid permit number or listing link after /d.",
                    reply_markup=MENU_KEYBOARD,
                )
                return

            msg = await update.message.reply_text("⏳ Searching...")

        if "get_proppy_d_free_limit_status" in globals():
            limit_ok, used_count, limit_total = get_proppy_d_free_limit_status(update)

            if not limit_ok:
                await msg.edit_text(
                    f"❌ Free /d limit finished: {used_count}/{limit_total}.\n"
                    "Please contact the administrator."
                )
                return

        data = await search_proppy_link_request_data(permit)

        if "add_proppy_d_free_usage" in globals():
            add_proppy_d_free_usage(update, permit)

        result_text = format_proppy_data(data)

        try:
            spreadsheet = get_spreadsheet()
            append_proppy_result(spreadsheet, permit, data)
        except Exception as e:
            print("OWNER LOOKUP SHEET SAVE ERROR:", e, flush=True)

        if len(result_text) > 3900:
            await msg.delete()
            chunks = [result_text[i:i + 3900] for i in range(0, len(result_text), 3900)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await msg.edit_text(result_text)

    except Exception as e:
        import traceback

        traceback.print_exc()

        await update.message.reply_text(
            f"❌ Search error:\n{e}",
            reply_markup=MENU_KEYBOARD,
        )

'''

text = text[:start] + new_handle + text[end+1:]

# 7) Убираем из /start описание про Show more details
text = text.replace(
    "After the result, tap “Show more details” to view additional owner details.",
    "Use /d to check owner details from a permit number or listing link."
)

p.write_text(text, encoding="utf-8")
print("DONE: Show more details removed")
