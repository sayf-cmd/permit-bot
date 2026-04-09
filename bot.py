import os
import re
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ["TELEGRAM_TOKEN"]
SHEET_CSV_URL = os.environ["SHEET_CSV_URL"]
GOOGLE_SHEET_URL = os.environ["GOOGLE_SHEET_URL"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", "10000"))

ADMIN_USERNAME = "@Sayf_Jr"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["👤 My Profile", "📩 Contact Admin"],
    ],
    resize_keyboard=True
)


def get_gspread_client():
    creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_users_sheet():
    client = get_gspread_client()
    spreadsheet = client.open_by_url(GOOGLE_SHEET_URL)
    return spreadsheet.worksheet("Users")


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


def get_user_record(user_id):
    sheet = get_users_sheet()
    records = sheet.get_all_records()

    for idx, record in enumerate(records, start=2):
        if str(record.get("user_id", "")).strip() == str(user_id):
            return sheet, idx, record

    return sheet, None, None


def find_or_create_user(user_id, username):
    sheet, row_number, record = get_user_record(user_id)

    if record is not None:
        return sheet, row_number, record

    new_row = [str(user_id), username or "", 0, 5, "active"]
    sheet.append_row(new_row)

    return get_user_record(user_id)


def increment_user_usage(row_number, current_used):
    sheet = get_users_sheet()
    sheet.update_cell(row_number, 3, int(current_used) + 1)


def normalize_user_record(record):
    status = str(record.get("status", "active")).strip().lower()

    try:
        requests_used = int(record.get("requests_used", 0))
    except Exception:
        requests_used = 0

    try:
        request_limit = int(record.get("request_limit", 5))
    except Exception:
        request_limit = 5

    return status, requests_used, request_limit


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
    tg_user = update.effective_user
    _, _, record = find_or_create_user(tg_user.id, tg_user.username or "")
    status, requests_used, request_limit = normalize_user_record(record)
    remaining = max(request_limit - requests_used, 0)

    text = (
        "Welcome to Property Permit Finder.\n\n"
        "Send a permit number and I will show:\n"
        "• Permit Number\n"
        "• Unit Number\n"
        "• Building\n"
        "• Latest Phones\n\n"
        f"You currently have {remaining} free searches left."
    )

    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD)


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

    await update.message.reply_text("Data reloaded successfully.", reply_markup=MENU_KEYBOARD)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    _, row_number, record = find_or_create_user(tg_user.id, tg_user.username or "")

    status, requests_used, request_limit = normalize_user_record(record)
    remaining = max(request_limit - requests_used, 0)

    text = (
        "👤 Profile\n\n"
        f"Username: @{tg_user.username}\n" if tg_user.username else "👤 Profile\n\nUsername: Not set\n"
    )
    text += (
        f"User ID: {tg_user.id}\n"
        f"Status: {status}\n"
        f"Used searches: {requests_used}\n"
        f"Free searches left: {remaining}"
    )

    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD)


async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_link = f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Contact Admin", url=admin_link)]]
    )

    await update.message.reply_text(
        "📩 If you need more searches or support, contact the administrator:",
        reply_markup=keyboard
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_text = update.message.text.strip()

        if user_text == "👤 My Profile":
            await profile(update, context)
            return

        if user_text == "📩 Contact Admin":
            await contact_admin(update, context)
            return

        tg_user = update.effective_user
        _, row_number, record = find_or_create_user(tg_user.id, tg_user.username or "")
        status, requests_used, request_limit = normalize_user_record(record)

        if status != "active":
            await update.message.reply_text(
                "Your access is currently inactive.\nPlease contact the administrator.",
                reply_markup=MENU_KEYBOARD
            )
            return

        if requests_used >= request_limit:
            keyboard =
