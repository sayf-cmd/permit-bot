import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bulk_permit_lookup import run_bulk


async def handle_bulk_permits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message

    text = message.text or ""
    payload = text.replace("/bulk", "", 1).strip()

    if not payload:
        await message.reply_text(
            "Пришли permits так:\n\n"
            "/bulk\n"
            "71524291019\n"
            "71175377977\n"
            "7122410900"
        )
        return

    wait_msg = await message.reply_text("⏳ Пробиваю permits по базе...")

    try:
        result = await asyncio.to_thread(run_bulk, payload, True)

        caption = (
            f"✅ Bulk check completed\n\n"
            f"Batch ID: {result['batch_id']}\n"
            f"Checked: {result['checked']}\n"
            f"Matched: {result['matched']}\n"
            f"Not found: {result['not_found']}\n"
            f"Sent to CRM: {result['crm_sent']}\n"
            f"CRM status: {result['crm_status']}"
        )

        excel_path = Path(result["excel_path"])

        with excel_path.open("rb") as f:
            await message.reply_document(
                document=f,
                filename=excel_path.name,
                caption=caption,
            )

        await wait_msg.delete()

    except Exception as e:
        await wait_msg.edit_text(f"❌ Bulk error:\n{e}")
