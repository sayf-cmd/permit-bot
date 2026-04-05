import os
import re
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ["TELEGRAM_TOKEN"]
SHEET_CSV_URL = os.environ["SHEET_CSV_URL"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", "10000"))

def load_data():
    df = pd.read_csv(SHEET_CSV_URL)
    df.columns = [str(col).strip() for col in df.columns]

    permit_col = df.columns[0]
    building_col = df.columns[1]
    unit_col = df.columns[2]
    bedroom_col = df.columns[3]

    df[permit_col] = (
        df[permit_col]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.replace(r"\D", "", regex=True)
    )

    return df, permit_col, building_col, unit_col, bedroom_col

df, permit_col, building_col, unit_col, bedroom_col = load_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Welcome.\n\n"
        "Send me a permit number and I will return:\n"
        "Building Name\n"
        "Unit Number\n"
        "Bedroom"
    )
    await update.message.reply_text(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    digits = re.sub(r"\D", "", raw_text)

    if len(digits) > 4:
        search_value = digits[2:-2]
    else:
        search_value = digits

    result = df[df[permit_col] == search_value]

    if result.empty:
        await update.message.reply_text(
            f"No data found.\n"
            f"Input: {raw_text}\n"
            f"Search Permit: {search_value}"
        )
        return

    row = result.iloc[0]

        reply = (
        f"Property Details\n\n"
        f"Permit Number: {search_value}\n"
        f"Building Name: {row[building_col]}\n"
        f"Unit Number: {row[unit_col]}\n"
        f"Bedroom: {row[bedroom_col]}"
    )


    await update.message.reply_text(reply)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
    )
