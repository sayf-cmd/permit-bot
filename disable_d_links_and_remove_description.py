from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_disable_d_links")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# 1) Убираем описание OWNER_LOOKUP_START_DESCRIPTION, если оно было добавлено
text = re.sub(
    r'\n?OWNER_LOOKUP_START_DESCRIPTION\s*=\s*\(\n(?:.*?\n)*?\)\n?',
    '\n',
    text,
    flags=re.S,
)

text = text.replace(
    '        await update.message.reply_text(OWNER_LOOKUP_START_DESCRIPTION)\n',
    ''
)

# 2) Убираем текст про /d из тарифов/описаний, если он где-то остался
text = re.sub(
    r'🔎 Owner Lookup\\n\\nUse /d.*?(?=💳 Tariffs)',
    '',
    text,
    flags=re.S,
)

text = text.replace(
    "Use /d to check owner details from a permit number or listing link.",
    ""
)

text = text.replace(
    "Use /d with a permit number or a listing link to check owner details.",
    ""
)

text = text.replace(
    "After the result, tap “Show more details” to view additional owner details.",
    ""
)

# 3) Убираем лишний broken import, если остался
lines = text.splitlines()
lines = [
    line for line in lines
    if "search_owner_records2_by_owner_name" not in line
]
text = "\n".join(lines) + "\n"

# 4) Убираем Show more details handler, если он ещё есть
text = re.sub(
    r'\n\s*app\.add_handler\(CallbackQueryHandler\(handle_proppy_numbers.*?\)\)',
    '',
    text,
)

start = text.find("async def handle_proppy_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):")
if start != -1:
    end = text.find("\n\nasync def handle_proppy_d", start)
    if end != -1:
        text = text[:start] + text[end+2:]

start = text.find("def format_proppy_all_numbers(data):")
if start != -1:
    end = text.find("\n\nasync def handle_proppy_numbers", start)
    if end != -1:
        text = text[:start] + text[end+2:]

# 5) Заменяем /d на permit-only без ссылок
start = text.find("async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):")
end = text.find("\nasync def handle_dxb(", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл handle_proppy_d или handle_dxb")

new_handle = r'''async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        permit = " ".join(context.args).strip()
        permit = normalize_permit(permit)

        if not permit:
            await update.message.reply_text(
                "Send permit number:\n/d 71495697794",
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

p.write_text(text, encoding="utf-8")
print("DONE: /d links disabled, /d description removed, details button removed")
