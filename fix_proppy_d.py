from pathlib import Path
import re

path = Path("bot.py")
text = path.read_text(encoding="utf-8")

new_block = r'''
async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        permit = " ".join(context.args).strip()

        if not permit:
            await update.message.reply_text(
                "Напиши так:\n/d 71495668339",
                reply_markup=MENU_KEYBOARD,
            )
            return

        msg = await update.message.reply_text("⏳ Searching Proppy...")

        data = await search_proppy_link_request_data(permit)
        result_text = format_proppy_data(data)

        try:
            spreadsheet = get_spreadsheet()
            append_proppy_result(spreadsheet, permit, data)
            result_text += "\n\n✅ Saved to Google Sheet"
        except Exception as e:
            print("PROPPY SHEET SAVE ERROR:", e, flush=True)
            result_text += "\n\n⚠️ Found, but Google Sheet save error."

        if len(result_text) > 3900:
            await msg.delete()
            for i in range(0, len(result_text), 3900):
                await update.message.reply_text(result_text[i:i + 3900])
        else:
            await msg.edit_text(result_text)

    except Exception as e:
        import traceback

        traceback.print_exc()

        await update.message.reply_text(
            f"❌ Proppy error:\n{e}",
            reply_markup=MENU_KEYBOARD,
        )
'''

pattern = re.compile(
    r"\nasync def handle_proppy_d\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n.*?(?=\nasync def handle_dxb\()",
    re.S,
)

if not pattern.search(text):
    raise SystemExit("Не нашёл handle_proppy_d блок")

path.write_text(pattern.sub("\n" + new_block.strip() + "\n\n", text), encoding="utf-8")
print("DONE: handle_proppy_d fixed")
