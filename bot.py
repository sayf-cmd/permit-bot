import os
import re
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ["TELEGRAM_TOKEN"]
SHEET_CSV_URL = os.environ["SHEET_CSV_URL"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", "10000"))


def clean_phone(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() == "null":
        return ""

    digits = re.sub(r"\D", "", value)

    if len(digits) < 7:
        return ""

    return digits


def load_data():
    df = pd.read_csv(SHEET_CSV_URL, low_memory=False)
    df.columns = [str(col).strip() for col in df.columns]
    print("COLUMNS:", df.columns.tolist())

    permit_col = "Permit_number"
    building_col = "Building_name"
    unit_col = "Unit_number"
    bedroom_col = "Bedroom"
    latest_phone_1_col = "Latest_phone_1"
    latest_phone_2_col = "Latest_phone_2"
    latest_phone_3_col = "Latest_phone_3"

    df[permit_col] = (
        df[permit_col]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.replace(r"\D", "", regex=True)
    )

    for col in [latest_phone_1_col, latest_phone_2_col, latest_phone_3_col]:
        df[col] = df[col].apply(clean_phone)

    return (
        df,
        permit_col,
        building_col,
        unit_col,
        bedroom_col,
        latest_phone_1_col,
        latest_phone_2_col,
        latest_phone_3_col,
    )


(
    df,
    permit_col,
    building_col,
    unit_col,
    bedroom_col,
    latest_phone_1_col,
    latest_phone_2_col,
    latest_phone_3_col,
) = load_data()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Welcome to Property Permit Finder.\n\n"
        "This bot helps you find property details faster during your daily real estate work.\n\n"
        "Send a permit number and I will show:\n"
        "• Building Name\n"
        "• Unit Number\n"
        "• Owner Phones\n\n"
    )
    await update.message.reply_text(text)


async def reload_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df, permit_col, building_col, unit_col, bedroom_col
    global latest_phone_1_col, latest_phone_2_col, latest_phone_3_col

    (
        df,
        permit_col,
        building_col,
        unit_col,
        bedroom_col,
        latest_phone_1_col,
        latest_phone_2_col,
        latest_phone_3_col,
    ) = load_data()

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

        phones = [
            row.get(latest_phone_1_col, ""),
            row.get(latest_phone_2_col, ""),
            row.get(latest_phone_3_col, ""),
        ]

        phones = [str(phone).strip() for phone in phones if str(phone).strip() != ""]

        phone_lines = "\n".join([f"📞 Phone {i+1}: {phone}" for i, phone in enumerate(phones)])

        if not phone_lines:
            phone_lines = "📞 Phone: Not available"

        reply = (
            f"🏠 Property Overview\n"
            f"🏢 Unit Number: {row[unit_col]}\n"
            f"🏛️ Building: {row[building_col]}\n\n"
            f"👤 Public Owner Information:\n"
            f"{phone_lines}"
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
