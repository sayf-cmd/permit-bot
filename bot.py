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
    df = pd.read_csv(SHEET_CSV_URL, low_memory=False)
    df.columns = [str(col).strip() for col in df.columns]
    print("COLUMNS:", df.columns.tolist())

    permit_col = "Permit_number"
    building_col = "Building_name"
    unit_col = "Unit_number"
    bedroom_col = "Bedroom"
    latest_phone_col = "Latest_phone"

    df[permit_col] = (
        df[permit_col]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.replace(r"\D", "", regex=True)
    )

    df[latest_phone_col] = (
        df[latest_phone_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
    )

    return df, permit_col, building_col, unit_col, bedroom_col, latest_phone_col


df, permit_col, building_col, unit_col, bedroom_col, latest_phone_col = load_data()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Welcome to Property Permit Finder.\n\n"
        "This bot helps you find property details faster during your daily real estate work.\n\n"
        "Send a permit number and I will show:\n"
        "• Building Name\n"
        "• Unit Number\n"
        "• Owner Phone\n\n"
    )
    await update.message.reply_text(text)


async def reload_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df, permit_col, building_col, unit_col, bedroom_col, latest_phone_col

    df, permit_col, building_col, unit_col, bedroom_col, latest_phone_col = load_data()
    await update.message.reply_text("Data reloaded successfully.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_text = update.message.text.strip()
        print(f"Incoming text: {raw_text}")

        digits = re.sub(r"\D", "", raw_text)
        print(f"Digits: {digits}")

        variants = [digits]

        if len(digits) > 2:
            variants.append(digits[2:])

        if len(digits) > 4:
            variants.append(digits[2:-2])

        print(f"Variants: {variants}")

        result = df[df[permit_col].isin(variants)]
        print(f"Matches found: {len(result)}")

        if result.empty:
            await update.message.reply_text(
                "No matching property was found for this permit number.\n\n"
                "Please verify the permit number and try again."
            )
            return

        row = result.iloc[0]
        phone_value = str(row.get(latest_phone_col, "")).strip()

        reply = (
            f"🏠 Property Overview\n"
            f"🏢 Unit Number: {row[unit_col]}\n"
            f"🏛️ Building: {row[building_col]}\n\n"
            f"👤 Public Owner Information:\n"
            f"📞 Phone: {phone_value}"
        )

        await update.message.reply_text(reply)

    except Exception as e:
        print(f"ERROR in handle_message: {e}")
        await update.message.reply_text("Temporary error. Please try again.")


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("reload", reload_data))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
    )
