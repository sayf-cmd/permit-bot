from pathlib import Path
import re


BOT_PATH = Path("bot.py")

NEW_HANDLE = r'''
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


def main():
    if not BOT_PATH.exists():
        raise FileNotFoundError("bot.py not found. Run this script inside your telegram_bot folder.")

    text = BOT_PATH.read_text(encoding="utf-8")

    backup = BOT_PATH.with_suffix(".py.backup_proppy_only")
    backup.write_text(text, encoding="utf-8")
    print(f"Backup saved: {backup}")

    if "from proppy_sheet_logger import append_proppy_result" not in text:
        lines = text.splitlines()
        insert_at = 0

        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1

        lines.insert(insert_at, "from proppy_sheet_logger import append_proppy_result")
        text = "\n".join(lines) + "\n"

    pattern = re.compile(
        r"\nasync def handle_proppy_d\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n.*?(?=\nasync def handle_dxb\()",
        re.S,
    )

    if not pattern.search(text):
        raise RuntimeError("Could not find handle_proppy_d block before handle_dxb. No changes applied.")

    text = pattern.sub("\n" + NEW_HANDLE.strip() + "\n\n", text)

    BOT_PATH.write_text(text, encoding="utf-8")
    print("DONE: bot.py patched to Proppy-only owner mode.")
    print("Now /d will use only Proppy LinkDetails / Database 2.0 data, not local search_project_unit().")


if __name__ == "__main__":
    main()
