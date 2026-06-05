import os
import re
import json
import uuid
import inspect
from datetime import datetime
from io import StringIO
import requests
from listing_link_parser import extract_permit_from_listing_url
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from owner_db_search import (
    search_owner_everywhere,
    search_phone_everywhere,
    search_project_unit,
    format_results_for_telegram,
)

from dxb_interact_api import search_dxb_unit_api
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


TOKEN = (
    os.environ.get("TELEGRAM_TOKEN")
    or os.environ.get("BOT_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
)

SHEET_CSV_URL = (
    os.environ.get("SHEET_CSV_URL")
    or os.environ.get("CSV_URL")
    or os.environ.get("PROPERTY_CSV_URL")
    or os.environ.get("CSV_LINK")
    or ""
)

print("SHEET_CSV_URL FROM ENV:", repr(SHEET_CSV_URL))

GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_TOKEN / BOT_TOKEN / TELEGRAM_BOT_TOKEN env variable")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_USERNAME = "@Sayf_Jr"
ADMIN_IDS = {816494430}
WELCOME_IMAGE_PATH = os.environ.get("WELCOME_IMAGE_PATH", "welcome_cover.png")


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔎 Find Property", "👤 My Profile"],
        ["📘 How It Works", "💳 Tariffs"],
        ["📩 Contact Admin", "📍 Available Areas"],
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


def pick_column(df, candidates, required=True):
    """Return the real dataframe column name from possible aliases."""
    columns = {str(col).strip().lower(): col for col in df.columns}

    for candidate in candidates:
        key = str(candidate).strip().lower()
        if key in columns:
            return columns[key]

    if required:
        raise KeyError(
            f"Missing required column. Tried {candidates}. "
            f"Available columns: {list(df.columns)}"
        )

    return ""


def ensure_column(df, name):
    if name not in df.columns:
        df[name] = ""
    return name


def load_data():
    if not SHEET_CSV_URL or SHEET_CSV_URL == "test":
        raise RuntimeError("SHEET_CSV_URL / CSV_URL is empty or disabled")

    response = requests.get(
        SHEET_CSV_URL,
        timeout=30,
        allow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    preview = response.text[:200].lower()
    content_type = response.headers.get("content-type", "")

    if "<html" in preview:
        raise RuntimeError(
            f"CSV URL returned HTML instead of CSV. content-type={content_type}"
        )

    df = pd.read_csv(StringIO(response.text), dtype=str, low_memory=False)
    df.columns = [str(col).strip() for col in df.columns]

    print("CSV LOADED ROWS:", len(df))
    print("CSV COLUMNS:", df.columns.tolist())

    permit_col = pick_column(df, ["Permit_number", "Permit Number", "Permit", "TRAKHESSI"])
    building_col = pick_column(df, ["Building_name", "Building Name", "Building No", "BUILDING"])
    unit_col = pick_column(df, ["Unit_number", "Unit Number", "Unit No", "UNIT"])

    area_col = pick_column(df, ["Area_name", "Area Name", "Area", "Zone"], required=False)
    if not area_col:
        area_col = ensure_column(df, "Area")

    latest_owner_col = pick_column(df, ["Latest_owner", "Latest_Owner", "Owner Name", "Owner"], required=False)
    if not latest_owner_col:
        latest_owner_col = ensure_column(df, "Latest_Owner")

    latest_phone_1_col = pick_column(df, ["Latest_phone_1", "Latest_Phone_1", "Mobile 1"], required=False)
    latest_phone_2_col = pick_column(df, ["Latest_phone_2", "Latest_Phone_2", "Mobile 2"], required=False)
    latest_phone_3_col = pick_column(df, ["Latest_phone_3", "Latest_Phone_3", "Mobile 3"], required=False)
    latest_phone_4_col = pick_column(df, ["Latest_phone_4", "Latest_Phone_4", "Mobile 4"], required=False)

    latest_phone_1_col = latest_phone_1_col or ensure_column(df, "Latest_Phone_1")
    latest_phone_2_col = latest_phone_2_col or ensure_column(df, "Latest_Phone_2")
    latest_phone_3_col = latest_phone_3_col or ensure_column(df, "Latest_Phone_3")
    latest_phone_4_col = latest_phone_4_col or ensure_column(df, "Latest_Phone_4")

    df[permit_col] = (
        df[permit_col]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.replace(r"\D", "", regex=True)
    )

    df[building_col] = df[building_col].astype(str).str.strip()
    df[unit_col] = (
        df[unit_col]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
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
        area_col,
        latest_owner_col,
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
            area_col,
            latest_owner_col,
            latest_phone_1_col,
            latest_phone_2_col,
            latest_phone_3_col,
            latest_phone_4_col,
        ) = load_data()
    else:
        raise Exception("Permit CSV disabled locally")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("DXB ERROR:", e)

    df = None
    permit_col = ""
    building_col = ""
    unit_col = ""
    area_col = ""
    latest_owner_col = ""
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


def has_special_access(record):
    status = str(record.get("status", "active")).strip().lower()
    return status in ["premium", "admin"]


async def require_special_access(update: Update):
    tg_user = update.effective_user

    _, row_number, record = find_or_create_user(
        tg_user.id,
        tg_user.username or "",
    )

    update_last_used(row_number)

    if not has_special_access(record):
        await update.message.reply_text(
            "🔒 This feature is available only for premium users.\n\n"
            "Please contact admin to unlock advanced owner search.",
            reply_markup=MENU_KEYBOARD,
        )
        return False

    return True


def increment_user_usage(row_number, current_used):
    try:
        sheet = get_users_sheet()
        sheet.update_cell(row_number, 3, int(current_used) + 1)
    except Exception as e:
        print("USER USAGE UPDATE ERROR:", e, flush=True)


def update_last_used(row_number):
    try:
        sheet = get_users_sheet()
        sheet.update_cell(row_number, 6, now_text())
    except Exception as e:
        print("LAST USED UPDATE ERROR:", e, flush=True)


def normalize_permit(value):
    return re.sub(r"\D", "", str(value or "").strip())


def normalize_dxb_key(building_name, unit_number):
    building = re.sub(r"\s+", " ", str(building_name or "").strip()).lower()
    unit = re.sub(r"\.0$", "", str(unit_number or "").strip())
    return f"DXB:{building}|{unit}"


def normalize_history_key(value):
    value = str(value or "").strip()
    if value.upper().startswith("DXB:"):
        return value.lower()
    return normalize_permit(value)


async def extract_permit_safe(listing_url):
    """Extract permit from a listing URL without crashing the whole bot.

    Supports both async and sync implementations of
    extract_permit_from_listing_url, and also tries a simple numeric fallback.
    """
    try:
        result = extract_permit_from_listing_url(listing_url)

        if inspect.isawaitable(result):
            result = await result

        permit = normalize_permit(result)

        if permit:
            return permit

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"LINK EXTRACTOR ERROR: {e}", flush=True)

    # Fallback: sometimes a user sends a URL/text that already contains
    # the Trakheesi / permit number. Prefer numbers with the Dubai prefix 71.
    candidates = re.findall(r"\d{8,15}", str(listing_url or ""))

    for candidate in candidates:
        candidate = normalize_permit(candidate)

        if len(candidate) == 11 and candidate.startswith("71"):
            return candidate

    for candidate in candidates:
        candidate = normalize_permit(candidate)

        if 8 <= len(candidate) <= 12:
            return candidate

    return ""


def already_searched(user_id, permit_number):
    try:
        sheet = get_history_sheet()
        rows = sheet.get_all_values()

        user_id = str(user_id).strip()
        search_key = normalize_history_key(permit_number)

        for row in rows[1:]:
            if len(row) < 4:
                continue

            history_user_id = str(row[1]).strip()
            history_key = normalize_history_key(row[3])

            if history_user_id == user_id and history_key == search_key:
                return True

        return False

    except Exception as e:
        print("SEARCH HISTORY READ ERROR:", e, flush=True)
        return False


def add_search_history(user_id, username, permit_number, result, charged):
    try:
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

    except Exception as e:
        print("SEARCH HISTORY WRITE ERROR:", e, flush=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    try:
        _, row_number, record = find_or_create_user(tg_user.id, tg_user.username or "")
        update_last_used(row_number)
        _, requests_used, request_limit = normalize_user_record(record)
        remaining = max(request_limit - requests_used, 0)
    except Exception:
        remaining = 5

    text = (
        "🏙 DXB Intelligence Bot\n\n"
        "Dubai property intelligence in seconds.\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔎 Find Property\n"
        "Use:\n"
        "/find Building Name Unit\n\n"
        "Example:\n"
        "/find Burj Royale 903\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "📊 Includes\n"
        "• Sale history\n"
        "• Rental contracts\n"
        "• Unit details\n"
        "• Availability status\n"
        "• Parking & balcony info\n\n"
        f"🆔 Your Telegram ID: {tg_user.id}\n"
        f"❗ You have {remaining} free searches left."
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔎 Find Property", callback_data="help_find")],
            [InlineKeyboardButton("📘 How It Works", callback_data="help_how")],
            [InlineKeyboardButton("💳 Buy Plan", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("🆘 Support", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
        ]
    )

    if os.path.exists(WELCOME_IMAGE_PATH):
        with open(WELCOME_IMAGE_PATH, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 How To Use\n\n"
        "🔎 DXB live property search:\n"
        "/find Building Name Unit\n\n"
        "Example:\n"
        "/find Burj Royale 903\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Owner database commands:\n"
        "• /project Building Unit\n"
        "• /name Owner Name\n"
        "• /phone Phone Number\n\n"
        "🎁 Every user gets 5 free searches."
    )
    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD)


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_find":
        text = (
            "🔎 Find Property\n\n"
            "Send command in this format:\n\n"
            "/find Building Name Unit\n\n"
            "Examples:\n"
            "• /find Burj Royale 903\n"
            "• /find Grande 1507\n"
            "• /find Peninsula One 3011"
        )
    elif query.data == "help_how":
        text = (
            "📘 How It Works\n\n"
            "1. Send /find with building and unit number.\n"
            "2. The bot checks DXB live data.\n"
            "3. You receive a clean property report.\n\n"
            "Advanced commands:\n"
            "• /project Building Unit — owners & contacts for a unit\n"
            "• /name Owner Name — owner intelligence\n"
            "• /phone Phone Number — phone intelligence"
        )
    else:
        text = "Use /find Building Name Unit"

    await query.message.reply_text(text, reply_markup=MENU_KEYBOARD)


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

        access_text = "Premium" if status in ["premium", "admin"] else "Basic"

        text = (
            "👤 Profile\n\n"
            f"Username: {username_text}\n"
            f"User ID: {tg_user.id}\n"
            f"Status: {status}\n"
            f"Access: {access_text}\n"
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




def format_price(value):
    raw = str(value or "").replace(",", "").strip()
    if not raw or raw.lower() in ["nan", "none", "null"]:
        return ""
    try:
        amount = float(raw)
    except Exception:
        return str(value).strip()
    return f"AED {amount:,.0f}"


def format_date(value):
    raw = str(value or "").strip()
    if not raw or raw.lower() in ["nan", "none", "null"]:
        return ""
    try:
        dt = pd.to_datetime(raw, errors="coerce")
        if pd.isna(dt):
            return raw
        return dt.strftime("%d %b %Y")
    except Exception:
        return raw


def normalize_text_value(value):
    raw = str(value or "").strip()
    if raw.lower() in ["nan", "none", "null", ""]:
        return ""
    return raw


def normalize_result_record(record):
    phones = record.get("phones", []) or []
    if isinstance(phones, str):
        phones = [phones]
    phones = [clean_phone(phone) for phone in phones]
    phones = [phone for phone in phones if phone]

    source_parts = []
    if normalize_text_value(record.get("source_folder")):
        source_parts.append(normalize_text_value(record.get("source_folder")))
    if normalize_text_value(record.get("file_name")):
        source_parts.append(normalize_text_value(record.get("file_name")))

    return {
        "building": normalize_text_value(record.get("building_name") or record.get("building") or record.get("Building")),
        "unit": normalize_text_value(record.get("unit_number") or record.get("unit") or record.get("Unit")),
        "owner": normalize_text_value(record.get("owner_name") or record.get("owner") or record.get("Owner")),
        "phones": phones,
        "price": normalize_text_value(record.get("price") or record.get("transaction_amount") or record.get("amount")),
        "date": normalize_text_value(record.get("date") or record.get("transaction_date") or record.get("Date")),
        "source": " / ".join(source_parts),
    }


def sort_records_newest(records):
    def key(record):
        dt = pd.to_datetime(record.get("date", ""), errors="coerce")
        if pd.isna(dt):
            return pd.Timestamp.min
        return dt
    return sorted(records, key=key, reverse=True)


def dedupe_records(records):
    cleaned = []
    seen = set()

    for r in records:
        key = (
            r.get("building", "").lower(),
            r.get("unit", "").lower(),
            r.get("owner", "").lower(),
            tuple(r.get("phones", [])),
            r.get("source", "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(r)

    return cleaned


def source_line(source):
    return f"📁 Source: {source}" if source else "📁 Source: Not available"


def format_owner_block(owner, phones, sources):
    lines = [f"👤 {owner or 'Owner not available'}"]

    if phones:
        for phone in phones[:6]:
            lines.append(f"📞 {phone}")
    else:
        lines.append("📞 Not available")

    for src in sources[:5]:
        lines.append(source_line(src))

    return "\n".join(lines)


def format_name_results(query, results):
    if not results:
        return f"👤 OWNER SEARCH\n\n🔎 Query: {query}\n\n❌ No owners found."

    records = [normalize_result_record(r) for r in results]
    records = [r for r in records if r["building"] or r["unit"] or r["owner"]]
    records = dedupe_records(sort_records_newest(records))

    unique_units = {(r["building"].lower(), r["unit"].lower()) for r in records if r["building"] or r["unit"]}
    unique_owners = {r["owner"].lower() for r in records if r["owner"]}
    unique_phones = {p for r in records for p in r["phones"]}

    lines = [
        "👤 OWNER SEARCH",
        "━━━━━━━━━━━━━━━",
        "",
        f"🔎 Query: {query}",
        "",
        f"📊 Matches: {len(records)}",
        f"🏠 Units: {len(unique_units)}",
        f"👥 Owners: {len(unique_owners)}",
        f"📞 Phones: {len(unique_phones)}",
    ]

    for r in records[:25]:
        lines.extend([
            "",
            "━━━━━━━━━━━━━━",
            f"🏢 {r['building'] or '-'}",
            f"🏠 Unit: {r['unit'] or '-'}",
            f"👤 {r['owner'] or '-'}",
        ])

        if r["phones"]:
            for phone in r["phones"][:6]:
                lines.append(f"📞 {phone}")
        else:
            lines.append("📞 Not available")

        lines.append(source_line(r["source"]))

    if len(records) > 25:
        lines.append(f"\nShowing first 25 of {len(records)} records.")

    return "\n".join(lines).strip()


def format_phone_results(query, results):
    if not results:
        return f"📞 PHONE SEARCH\n\n🔎 Query: {query}\n\n❌ No records found."

    records = [normalize_result_record(r) for r in results]
    records = [r for r in records if r["building"] or r["unit"] or r["owner"] or r["phones"]]
    records = dedupe_records(sort_records_newest(records))

    unique_units = {(r["building"].lower(), r["unit"].lower()) for r in records if r["building"] or r["unit"]}
    unique_owners = {r["owner"].lower() for r in records if r["owner"]}

    lines = [
        "📞 PHONE SEARCH",
        "━━━━━━━━━━━━━━━",
        "",
        f"🔎 Query: {query}",
        "",
        f"📊 Matches: {len(records)}",
        f"🏠 Units: {len(unique_units)}",
        f"👥 Owners: {len(unique_owners)}",
    ]

    for r in records[:25]:
        lines.extend([
            "",
            "━━━━━━━━━━━━━━",
            f"👤 {r['owner'] or '-'}",
            f"🏢 {r['building'] or '-'}",
            f"🏠 Unit: {r['unit'] or '-'}",
        ])

        for phone in r["phones"][:6]:
            lines.append(f"📞 {phone}")

        lines.append(source_line(r["source"]))

    if len(records) > 25:
        lines.append(f"\nShowing first 25 of {len(records)} records.")

    return "\n".join(lines).strip()


def format_project_results(query, results):
    if not results:
        return (
            "🏢 PROJECT / UNIT SEARCH\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🔎 Query: {query}\n\n"
            "❌ No owners found for this unit."
        )

    records = [normalize_result_record(r) for r in results]
    records = [r for r in records if r["building"] or r["unit"] or r["owner"] or r["phones"]]
    records = dedupe_records(sort_records_newest(records))

    building = next((r["building"] for r in records if r["building"]), "Unknown Building")
    unit = next((r["unit"] for r in records if r["unit"]), "")

    owners = {}
    for r in records:
        owner = r["owner"] or "Owner not available"
        owners.setdefault(owner, {"phones": [], "sources": []})

        for phone in r["phones"]:
            if phone and phone not in owners[owner]["phones"]:
                owners[owner]["phones"].append(phone)

        if r["source"] and r["source"] not in owners[owner]["sources"]:
            owners[owner]["sources"].append(r["source"])

    all_phones = {phone for data in owners.values() for phone in data["phones"]}

    lines = [
        "🏢 PROJECT / UNIT SEARCH",
        "━━━━━━━━━━━━━━━",
        "",
        f"🔎 Query: {query}",
        "",
        f"🏢 Building: {building}",
    ]

    if unit:
        lines.append(f"🏠 Unit: {unit}")

    lines.extend([
        "",
        f"👥 Owners found: {len(owners)}",
        f"📞 Phones found: {len(all_phones)}",
        "",
        "━━━━━━━━━━━━━━",
    ])

    for idx, (owner, data) in enumerate(owners.items(), start=1):
        lines.extend([
            "",
            f"{idx}️⃣",
            format_owner_block(owner, data["phones"], data["sources"]),
        ])

    return "\n".join(lines).strip()


def split_long_text(text, limit=3900):
    text = str(text or "")
    if len(text) <= limit:
        return [text]
    chunks = []
    current = ""
    for block in text.split("\n━━━━━━━━━━━━━━\n"):
        candidate = block if not current else current + "\n━━━━━━━━━━━━━━\n" + block
        if len(candidate) > limit and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks

async def handle_name_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # if not await require_special_access(update):
        #     return

        owner_name = " ".join(context.args).strip()

        if not owner_name:
            await update.message.reply_text(
                "Напиши так:\n/name LEONID MINKOV",
                reply_markup=MENU_KEYBOARD,
            )
            return

        await update.message.reply_text("Searching owner database...")

        results = search_owner_everywhere(owner_name)
        text = format_name_results(owner_name, results)

        for chunk in split_long_text(text):
            await update.message.reply_text(chunk)

    except Exception as e:
        print("NAME SEARCH ERROR:", e)

        await update.message.reply_text(
            "Name search error.",
            reply_markup=MENU_KEYBOARD,
        )

async def handle_phone_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not await require_special_access(update):
            return

        phone = " ".join(context.args).strip()

        if not phone:
            await update.message.reply_text(
                "Напиши так:\n/phone 971585071125",
                reply_markup=MENU_KEYBOARD,
            )
            return

        await update.message.reply_text("Searching phone database...")

        results = search_phone_everywhere(phone)
        text = format_phone_results(phone, results)

        for chunk in split_long_text(text):
            await update.message.reply_text(chunk)

    except Exception as e:
        print("PHONE SEARCH ERROR:", e)

        await update.message.reply_text(
            "Phone search error.",
            reply_markup=MENU_KEYBOARD,
        )

async def handle_project_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not await require_special_access(update):
            return

        query = " ".join(context.args).strip()

        if not query:
            await update.message.reply_text(
                "Напиши так:\n/project Peninsula One 3011",
                reply_markup=MENU_KEYBOARD,
            )
            return

        await update.message.reply_text("Searching unit owners...")

        results = search_project_unit(query)

        # smarter unit filtering
        if context.args:
            unit_number = context.args[-1].strip()
            unit_clean = re.sub(r"\.0$", "", unit_number)

            filtered_results = []

            for r in results:
                result_unit = str(
                    r.get("unit_number", "")
                ).strip()

                result_unit = re.sub(
                    r"\.0$",
                    "",
                    result_unit,
                )

                full_row = str(
                    r.get("full_row", "")
                ).lower()

                if (
                    result_unit == unit_clean
                    or unit_clean in full_row
                ):
                    filtered_results.append(r)

            if filtered_results:
                results = filtered_results

        text = format_project_results(
            query,
            results,
        )

        for chunk in split_long_text(text):
            await update.message.reply_text(chunk)

    except Exception as e:
        print("PROJECT SEARCH ERROR:", e)

        await update.message.reply_text(
            "Project search error.",
            reply_markup=MENU_KEYBOARD,
        )

async def handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not await require_special_access(update):
            return

        owner_name = " ".join(context.args).strip()

        if not owner_name:
            await update.message.reply_text(
                "Напиши так:\n/export LEONID MINKOV",
                reply_markup=MENU_KEYBOARD,
            )
            return

        await update.message.reply_text("Preparing Excel export...")

        results = search_owner_everywhere(owner_name)

        if not results:
            await update.message.reply_text(
                "Ничего не найдено.",
                reply_markup=MENU_KEYBOARD,
            )
            return

        MAX_EXPORT_ROWS = 5000

        if len(results) > MAX_EXPORT_ROWS:
            await update.message.reply_text(
                f"Too many results ({len(results)}).\n"
                f"Maximum export limit: {MAX_EXPORT_ROWS}",
                reply_markup=MENU_KEYBOARD,
            )
            return

        export_rows = []

        for r in results:
            export_rows.append(
                {
                    "Building": r.get("building_name"),
                    "Unit": r.get("unit_number"),
                    "Owner": r.get("owner_name"),
                    "Phones": ", ".join(r.get("phones", [])),
                    "Price": r.get("price"),
                    "Date": r.get("date"),
                    "Source Folder": r.get("source_folder"),
                    "Source File": r.get("file_name"),
                }
            )

        export_df = pd.DataFrame(export_rows)

        temp_file_name = f"export_{uuid.uuid4().hex}.xlsx"
        export_df.to_excel(temp_file_name, index=False)

        safe_owner_name = re.sub(r"[^A-Za-z0-9_ -]", "", owner_name).strip()

        if not safe_owner_name:
            safe_owner_name = "owner"

        telegram_file_name = f"{safe_owner_name}_export.xlsx"

        with open(temp_file_name, "rb") as file:
            await update.message.reply_document(
                document=file,
                filename=telegram_file_name,
                caption=f"Excel export for {owner_name}",
            )

        os.remove(temp_file_name)

    except Exception as e:
        print("EXPORT ERROR:", e)

        await update.message.reply_text(
            "Export error.",
            reply_markup=MENU_KEYBOARD,
        )




async def handle_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Напиши так:\n/find Grande 4702",
                reply_markup=MENU_KEYBOARD,
            )
            return

        if supabase is None:
            await update.message.reply_text(
                "❌ DXB queue is not configured. Missing SUPABASE_URL or SUPABASE_KEY.",
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

        if status == "blocked":
            await update.message.reply_text(
                "Your access is currently inactive. Please contact the administrator.",
                reply_markup=MENU_KEYBOARD,
            )
            return

        unit_number = context.args[-1].strip()
        building_name = " ".join(context.args[:-1]).strip()
        request_key = normalize_dxb_key(building_name, unit_number)
        is_duplicate = already_searched(tg_user.id, request_key)

        if requests_used >= request_limit and not is_duplicate:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Admin", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")]]
            )
            await update.message.reply_text(
                "You have reached your search limit.\nPlease contact the administrator for more access.",
                reply_markup=keyboard,
            )
            return

        job = {
            "chat_id": str(update.effective_chat.id),
            "user_id": str(tg_user.id),
            "username": tg_user.username or "",
            "building": building_name,
            "unit": unit_number,
            "request_key": request_key,
            "status": "pending",
        }

        try:
            supabase.table("dxb_jobs").insert(job).execute()
        except Exception:
            # Fallback for older dxb_jobs tables that only have basic columns.
            # For full limits/history on /find, add user_id, username and request_key columns.
            supabase.table("dxb_jobs").insert({
                "chat_id": str(update.effective_chat.id),
                "building": building_name,
                "unit": unit_number,
                "status": "pending",
            }).execute()

        duplicate_note = "\n♻️ Repeated object — no search will be charged." if is_duplicate else ""

        await update.message.reply_text(
            f"⏳ DXB request added to queue...{duplicate_note}",
            reply_markup=MENU_KEYBOARD,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("FIND/DXB ERROR:", e, flush=True)

        await update.message.reply_text(
            "❌ DXB error. Try again later.",
            reply_markup=MENU_KEYBOARD,
        )


async def handle_dxb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Backward compatible alias. Main command is /find.
    await handle_find(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_text = update.message.text.strip()

        is_listing_link = (
            user_text.startswith("http://")
            or user_text.startswith("https://")
        )

        if is_listing_link and (
            "propertyfinder.ae" in user_text
            or "bayut.com" in user_text
        ):
            await update.message.reply_text("🔎 Extracting permit from listing link...")

            permit_from_link = await extract_permit_safe(user_text)

            if not permit_from_link:
                await update.message.reply_text(
                    "❌ Could not find permit number in this listing.\n\n"
                    "Send the Permit / Trakheesi number manually, or try another listing link.",
                    reply_markup=MENU_KEYBOARD,
                )
                return

            user_text = permit_from_link

        if user_text == "🔎 Find Property":
            await update.message.reply_text(
                "🔎 Send command like this:\n/find Burj Royale 903",
                reply_markup=MENU_KEYBOARD,
            )
            return

        if user_text == "📘 How It Works":
            await help_command(update, context)
            return

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
        if user_text in ["📘 How It Works", "🔎 Find Property"]:
            await help_command(update, context)
            return

        if df is None:
            await update.message.reply_text(
                "⚠️ Property database is temporarily unavailable.\n\n"
                "Please try again later.",
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

        if status == "blocked":
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
                [
                    [
                        InlineKeyboardButton(
                            "Contact Admin",
                            url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}",
                        )
                    ]
                ]
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

        df[permit_col] = (
            df[permit_col]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.replace(r"\D", "", regex=True)
        )

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
                f"❗ You have {request_limit - requests_used} free searches left.",
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
            f"📍 Zone: {row.get(area_col, '')}\n\n"
            "👤 Public Owner Information\n"
            f"🧑 Name: {str(row.get(latest_owner_col, '')).title()}\n"
            f"📞 Phone: {', '.join(phones) if phones else 'Not available'}\n"
            f"{duplicate_note}\n"
            f"❗ You have {remaining_after_search} free searches left."
        )

        await update.message.reply_text(reply, reply_markup=MENU_KEYBOARD)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR in handle_message: {e}", flush=True)

        await update.message.reply_text(
            "Temporary error. Please try again.",
            reply_markup=MENU_KEYBOARD,
        )

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CallbackQueryHandler(handle_button))
app.add_handler(CommandHandler("reload", reload_data))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(CommandHandler("contact", contact_admin))
app.add_handler(CommandHandler("tariffs", tariffs))
app.add_handler(CommandHandler("areas", available_areas))
app.add_handler(CommandHandler("name", handle_name_search))
app.add_handler(CommandHandler("phone", handle_phone_search))
app.add_handler(CommandHandler("project", handle_project_search))
app.add_handler(CommandHandler("export", handle_export))
app.add_handler(CommandHandler("find", handle_find))
app.add_handler(CommandHandler("dxb", handle_dxb))

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message,
    )
)


if __name__ == "__main__":
    print("BOT STARTED IN LOCAL POLLING MODE")
    app.run_polling()