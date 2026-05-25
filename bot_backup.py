import os
import re
import json
from datetime import datetime

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from owner_db_search import (
    search_owner_everywhere,
    search_phone_everywhere,
    search_project_unit,
    format_results_for_telegram,
)

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


TOKEN = os.environ["TELEGRAM_TOKEN"]

SHEET_CSV_URL = os.environ.get("SHEET_CSV_URL", "")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "10000"))

ADMIN_USERNAME = "@Sayf_Jr"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["👤 My Profile", "📩 Contact Admin"],
        ["💳 Tariffs", "📍 Available Areas"],
    ],
    resize_keyboard=True,
)


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_gspread_client():
    creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet():
    client = get_gspread_client()
    return client.open_by_url(GOOGLE_SHEET_URL)


def get_users_sheet():
    return get_spreadsheet().worksheet("Users")


def get_history_sheet():
    return get_spreadsheet().worksheet("SearchHistory")


def get_summary_sheet():
    return get_spreadsheet().worksheet("summary")


def clean_phone(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() in ["null", "nan", "none"]:
        return ""

    digits = re.sub(r"\D", "", value)

    if len(digits) < 7:
        return ""

    return digits


def load_data():
    df = pd.read_csv(SHEET_CSV_URL, low_memory=False)
    df.columns = [str(col).strip() for col in df.columns]

    permit_col = "Permit_number"
    building_col = "Building_name"
    unit_col = "Unit_number"

    latest_phone_1_col = "Latest_phone_1"
    latest_phone_2_col = "Latest_phone_2"
    latest_phone_3_col = "Latest_phone_3"
    latest_phone_4_col = "Latest_phone_4"

    df[permit_col] = (
        df[permit_col]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.replace(r"\D", "", regex=True)
    )

    for col in [
        latest_phone_1_col,
        latest_phone_2_col,
        latest_phone_3_col,
        latest_phone_4_col,
    ]:
        df[col] = df[col].apply(clean_phone)

    return (
        df,
        permit_col,
        building_col,
        unit_col,
        latest_phone_1_col,
        latest_phone_2_col,
        latest_phone_3_col,
        latest_phone_4_col,
    )


try:
    if SHEET_CSV_URL and SHEET_CSV_URL != "test":
        (
            df,
            permit_col,
            building_col,
            unit_col,
            latest_phone_1_col,
            latest_phone_2_col,
            latest_phone_3_col,
            latest_phone_4_col,
        ) = load_data()
    else:
        raise Exception("Permit CSV disabled locally")
except Exception as e:
    print("PERMIT DATA DISABLED:", e)

    df = None
    permit_col = ""
    building_col = ""
    unit_col = ""
    latest_phone_1_col = ""
    latest_phone_2_col = ""
    latest_phone_3_col = ""
    latest_phone_4_col = ""


def get_user_record(user_id):
    sheet = get_users_sheet()
    user_ids = sheet.col_values(1)

    for idx, existing_user_id in enumerate(user_ids[1:], start=2):
        if str(existing_user_id).strip() == str(user_id):
            row = sheet.row_values(idx)

            record = {
                "user_id": row[0] if len(row) > 0 else "",
                "username": row[1] if len(row) > 1 else "",
                "requests_used": row[2] if len(row) > 2 else 0,
                "request_limit": row[3] if len(row) > 3 else 5,
                "status": row[4] if len(row) > 4 else "active",
                "last_used_at": row[5] if len(row) > 5 else "",
            }

            return sheet, idx, record

    return sheet, None, None


def find_or_create_user(user_id, username):
    sheet, row_number, record = get_user_record(user_id)

    if record is not None:
        return sheet, row_number, record

    user_ids = sheet.col_values(1)
    next_row = max(len(user_ids) + 1, 2)

    new_row = [
        str(user_id),
        username or "",
        0,
        5,
        "active",
        "",
    ]

    sheet.update(f"A{next_row}:F{next_row}", [new_row])

    return get_user_record(user_id)


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


def increment_user_usage(row_number, current_used):
    sheet = get_users_sheet()
    sheet.update_cell(row_number, 3, int(current_used) + 1)


def update_last_used(row_number):
    sheet = get_users_sheet()
    sheet.update_cell(row_number, 6, now_text())


def normalize_permit(value):
    return re.sub(r"\D", "", str(value or "").strip())


def already_searched(user_id, permit_number):
    sheet = get_history_sheet()
    rows = sheet.get_all_values()

    user_id = str(user_id).strip()
    permit_number = normalize_permit(permit_number)

    for row in rows[1:]:
        if len(row) < 4:
            continue

        history_user_id = str(row[1]).strip()
        history_permit = normalize_permit(row[3])

        if history_user_id == user_id and history_permit == permit_number:
            return True

    return False


def add_search_history(user_id, username, permit_number, result, charged):
    sheet = get_history_sheet()

    sheet.append_row(
        [
            now_text(),
            str(user_id),
            username or "",
            str(permit_number),
            result,
            "yes" if charged else "no",
        ],
        value_input_option="USER_ENTERED",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Property Permit Finder.\n\n"
        "Commands:\n"
        "/name OWNER NAME\n"
        "/phone PHONE NUMBER\n\n"
        "Or send permit number.",
        reply_markup=MENU_KEYBOARD,
    )


async def reload_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Reload disabled for SQLite owner search.",
        reply_markup=MENU_KEYBOARD,
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tg_user = update.effective_user

        _, row_number, record = find_or_create_user(
            tg_user.id,
            tg_user.username or "",
        )

        update_last_used(row_number)

        status, requests_used, request_limit = normalize_user_record(record)
        remaining = max(request_limit - requests_used, 0)

        username_text = f"@{tg_user.username}" if tg_user.username else "Not set"

        text = (
            "👤 Profile\n\n"
            f"Username: {username_text}\n"
            f"User ID: {tg_user.id}\n"
            f"Status: {status}\n"
            f"Used searches: {requests_used}\n"
            f"Free searches left: {remaining}"
        )

        await update.message.reply_text(text, reply_markup=MENU_KEYBOARD)

    except Exception:
        await update.message.reply_text(
            "Profile is unavailable in local test mode.",
            reply_markup=MENU_KEYBOARD,
        )


async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_link = f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Contact Admin", url=admin_link)]]
    )

    await update.message.reply_text(
        "📩 If you need more searches or support, contact the administrator:",
        reply_markup=keyboard,
    )


async def tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_link = f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Buy / Contact Admin", url=admin_link)]]
    )

    text = (
        "💳 Tariffs\n\n"
        "🔹 50 Searches — 200 AED\n"
        "🔹 100 Searches — 300 AED\n"
        "🔹 300 Searches — 500 AED\n\n"
        "📩 To purchase access, contact the administrator."
    )

    await update.message.reply_text(text, reply_markup=keyboard)


async def available_areas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sheet = get_summary_sheet()
        rows = sheet.get_all_values()

        lines = []
        total_line = ""

        for row in rows:
            if len(row) < 2:
                continue

            area = str(row[0]).strip()
            count_raw = str(row[1]).replace(",", "").strip()

            if not area or not count_raw.isdigit():
                continue

            count = int(count_raw)

            if area.upper() == "TOTAL":
                total_line = f"\n📊 Total — {count:,} units"
                continue

            if count >= 80000:
                indicator = "🟩"
            elif count >= 30000:
                indicator = "🟨"
            elif count >= 10000:
                indicator = "🟧"
            else:
                indicator = "🟥"

            lines.append(f"{indicator} {area} — {count:,} units")

        text = "📍 Available Areas\n\n" + "\n".join(lines) + total_line

        await update.message.reply_text(text, reply_markup=MENU_KEYBOARD)

    except Exception:
        await update.message.reply_text(
            "Areas are unavailable in local test mode.",
            reply_markup=MENU_KEYBOARD,
        )


async def handle_name_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        owner_name = " ".join(context.args).strip()

        if not owner_name:
            await update.message.reply_text(
                "Напиши так:\n/name LEONID MINKOV",
                reply_markup=MENU_KEYBOARD,
            )
            return

        await update.message.reply_text("Ищу по имени...")

        results = search_owner_everywhere(owner_name)
        text = format_results_for_telegram(results)

        if len(text) > 3900:
            for i in range(0, len(text), 3900):
                await update.message.reply_text(text[i:i + 3900])
        else:
            await update.message.reply_text(text)

    except Exception as e:
        print("NAME SEARCH ERROR:", e)

        await update.message.reply_text(
            "Name search error.",
            reply_markup=MENU_KEYBOARD,
        )


async def handle_phone_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        phone = " ".join(context.args).strip()

        if not phone:
            await update.message.reply_text(
                "Напиши так:\n/phone 971585071125",
                reply_markup=MENU_KEYBOARD,
            )
            return

        await update.message.reply_text("Ищу по номеру...")

        results = search_phone_everywhere(phone)
        text = format_results_for_telegram(results)

        if len(text) > 3900:
            for i in range(0, len(text), 3900):
                await update.message.reply_text(text[i:i + 3900])
        else:
            await update.message.reply_text(text)

    except Exception as e:
        print("PHONE SEARCH ERROR:", e)

        await update.message.reply_text(
            "Phone search error.",
            reply_markup=MENU_KEYBOARD,
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

        if user_text == "💳 Tariffs":
            await tariffs(update, context)
            return

        if user_text == "📍 Available Areas":
            await available_areas(update, context)
            return

        if df is None:
            await update.message.reply_text(
                "Permit search is disabled in local SQLite test mode.\n\n"
                "Use:\n/name OWNER NAME\n/phone PHONE",
                reply_markup=MENU_KEYBOARD,
            )
            return

        tg_user = update.effective_user

        _, row_number, record = find_or_create_user(
            tg_user.id,
            tg_user.username or "",
        )

        update_last_used(row_number)

        status, requests_used, request_limit = normalize_user_record(record)

        if status != "active":
            await update.message.reply_text(
                "Your access is currently inactive.\nPlease contact the administrator.",
                reply_markup=MENU_KEYBOARD,
            )
            return

        digits = normalize_permit(user_text)

        if not digits:
            await update.message.reply_text(
                "Please send a valid permit number.",
                reply_markup=MENU_KEYBOARD,
            )
            return

        is_duplicate = already_searched(tg_user.id, digits)

        if requests_used >= request_limit and not is_duplicate:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    "Contact Admin",
                    url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}",
                )]]
            )

            await update.message.reply_text(
                "You have reached your search limit.\nPlease contact the administrator for more access.",
                reply_markup=keyboard,
            )
            return

        variants = [digits]

        if len(digits) > 2:
            variants.append(digits[2:])

        if len(digits) > 4:
            variants.append(digits[2:-2])

        result = df[df[permit_col].isin(variants)]

        if result.empty:
            add_search_history(
                tg_user.id,
                tg_user.username or "",
                digits,
                "not_found",
                False,
            )

            await update.message.reply_text(
                "No matching property was found.\n\n"
                f"You have {request_limit - requests_used} free searches left.",
                reply_markup=MENU_KEYBOARD,
            )
            return

        row = result.iloc[0]

        phones = [
            row.get(latest_phone_1_col, ""),
            row.get(latest_phone_2_col, ""),
            row.get(latest_phone_3_col, ""),
            row.get(latest_phone_4_col, ""),
        ]

        phones = [
            str(phone).strip()
            for phone in phones
            if str(phone).strip()
        ]

        charged = not is_duplicate

        if charged:
            increment_user_usage(row_number, requests_used)
            remaining_after_search = max(request_limit - requests_used - 1, 0)
        else:
            remaining_after_search = max(request_limit - requests_used, 0)

        add_search_history(
            tg_user.id,
            tg_user.username or "",
            digits,
            "found",
            charged,
        )

        duplicate_note = ""
        if is_duplicate:
            duplicate_note = "\n♻️ Repeated search — no search was charged.\n"

        reply = (
            "🏠 Property Overview\n\n"
            f"🏢 Unit Number: {row[unit_col]}\n"
            f"🏛️ Building: {row[building_col]}\n"
            f"📍 Zone: {row['Area_name']}\n\n"
            "👤 Public Owner Information\n"
            f"🧑 Name: {str(row['Latest_owner']).title()}\n"
            f"📞 Phone: {', '.join(phones) if phones else 'Not available'}\n"
            f"{duplicate_note}\n"
            f"❗ You have {remaining_after_search} free searches left."
        )

        await update.message.reply_text(reply, reply_markup=MENU_KEYBOARD)

    except Exception as e:
        print(f"ERROR in handle_message: {e}")

        await update.message.reply_text(
            "Temporary error. Please try again.",
            reply_markup=MENU_KEYBOARD,
        )


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("reload", reload_data))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(CommandHandler("contact", contact_admin))
app.add_handler(CommandHandler("tariffs", tariffs))
app.add_handler(CommandHandler("areas", available_areas))
app.add_handler(CommandHandler("name", handle_name_search))
app.add_handler(CommandHandler("phone", handle_phone_search))

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message,
    )
)


if __name__ == "__main__":
    if WEBHOOK_URL and WEBHOOK_URL != "test":
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
        )
    else:
        print("BOT STARTED IN LOCAL POLLING MODE")
        app.run_polling()

async def handle_project_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = " ".join(context.args).strip()

        if not query:
            await update.message.reply_text(
                "Напиши так:\n/project THE EDGE A2506",
                reply_markup=MENU_KEYBOARD,
            )
            return

        await update.message.reply_text("Ищу по project / unit...")

        results = search_project_unit(query)
        text = format_results_for_telegram(results)

        if len(text) > 3900:
            for i in range(0, len(text), 3900):
                await update.message.reply_text(text[i:i + 3900])
        else:
            await update.message.reply_text(text)

    except Exception as e:
        print("PROJECT SEARCH ERROR:", e)

        await update.message.reply_text(
            "Project search error.",
            reply_markup=MENU_KEYBOARD,
        )


app.add_handler(CommandHandler("project", handle_project_search))


if __name__ == "__main__":
    if WEBHOOK_URL and WEBHOOK_URL != "test":
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
        )
    else:
        print("BOT STARTED IN LOCAL POLLING MODE")
        app.run_polling()