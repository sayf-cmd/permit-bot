import os
import re
import time
import json
import inspect
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import gspread
from google.oauth2.service_account import Credentials
from supabase import create_client
from dxb_interact_api import search_dxb_unit_api

TELEGRAM_TOKEN = (
    os.environ.get("TELEGRAM_TOKEN")
    or os.environ.get("BOT_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
)
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

ADMIN_IDS = {816494430}
POLL_SECONDS = int(os.environ.get("DXB_WORKER_POLL_SECONDS", "3"))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
_gspread_client = None
_spreadsheet = None


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_gspread_client():
    global _gspread_client
    if _gspread_client is None:
        creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        _gspread_client = gspread.authorize(creds)
    return _gspread_client


def get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = get_gspread_client().open_by_url(GOOGLE_SHEET_URL)
    return _spreadsheet


def get_users_sheet():
    return get_spreadsheet().worksheet("Users")


def get_history_sheet():
    return get_spreadsheet().worksheet("SearchHistory")


def normalize_dxb_key(building_name, unit_number):
    building = re.sub(r"\s+", " ", str(building_name or "").strip()).lower()
    unit = re.sub(r"\.0$", "", str(unit_number or "").strip())
    return f"DXB:{building}|{unit}"


def normalize_history_key(value):
    value = str(value or "").strip()
    if value.upper().startswith("DXB:"):
        return value.lower()
    return re.sub(r"\D", "", value)


def get_user_record(user_id, username=""):
    sheet = get_users_sheet()
    user_ids = sheet.col_values(1)
    user_id = str(user_id).strip()

    for idx, existing_user_id in enumerate(user_ids[1:], start=2):
        if str(existing_user_id).strip() == user_id:
            row = sheet.row_values(idx)
            record = {
                "user_id": row[0] if len(row) > 0 else user_id,
                "username": row[1] if len(row) > 1 else username,
                "requests_used": row[2] if len(row) > 2 else 0,
                "request_limit": row[3] if len(row) > 3 else 5,
                "status": row[4] if len(row) > 4 else "active",
                "last_used_at": row[5] if len(row) > 5 else "",
            }
            return sheet, idx, record

    next_row = max(len(user_ids) + 1, 2)
    sheet.update(f"A{next_row}:F{next_row}", [[user_id, username or "", 0, 5, "active", ""]])
    return get_user_record(user_id, username)


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
    try:
        get_users_sheet().update_cell(row_number, 3, int(current_used) + 1)
    except Exception as e:
        print("USER USAGE UPDATE ERROR:", e, flush=True)


def update_last_used(row_number):
    try:
        get_users_sheet().update_cell(row_number, 6, now_text())
    except Exception as e:
        print("LAST USED UPDATE ERROR:", e, flush=True)


def already_searched(user_id, key):
    try:
        rows = get_history_sheet().get_all_values()
        user_id = str(user_id).strip()
        key = normalize_history_key(key)
        for row in rows[1:]:
            if len(row) < 4:
                continue
            if str(row[1]).strip() == user_id and normalize_history_key(row[3]) == key:
                return True
        return False
    except Exception as e:
        print("SEARCH HISTORY READ ERROR:", e, flush=True)
        return False


def add_search_history(user_id, username, key, result, charged):
    try:
        get_history_sheet().append_row(
            [now_text(), str(user_id), username or "", str(key), result, "yes" if charged else "no"],
            value_input_option="USER_ENTERED",
        )
    except Exception as e:
        print("SEARCH HISTORY WRITE ERROR:", e, flush=True)


def send_telegram(chat_id, text):
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Missing TELEGRAM_TOKEN / BOT_TOKEN")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    for chunk in chunks:
        r = requests.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=30)
        if r.status_code >= 400:
            print("TELEGRAM SEND ERROR:", r.status_code, r.text[:500], flush=True)


def extract_field(text, label):
    pattern = rf"^{re.escape(label)}:\s*(.+)$"
    m = re.search(pattern, text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def extract_section(text, title):
    lines = str(text or "").splitlines()
    out = []
    active = False
    for line in lines:
        stripped = line.strip()
        if stripped == title:
            active = True
            continue
        if active and stripped.startswith(("💰 ", "🏡 ")) and stripped != title:
            break
        if active:
            if stripped:
                out.append(stripped)
    return out


def is_found_result(text):
    t = str(text or "").lower()
    if not t.strip():
        return False
    bad = [
        "not found",
        "no matching",
        "could not",
        "error",
        "temporarily unavailable",
        "try again later",
    ]
    if any(x in t for x in bad):
        return False
    return "building:" in t or "trakheesi:" in t or "sale history" in t


def format_clean_premium(raw_text, is_admin=False):
    text = str(raw_text or "")

    permit = extract_field(text, "🆔 Trakheesi") or extract_field(text, "Trakheesi")
    building = extract_field(text, "🏢 Building") or extract_field(text, "Building")
    area = extract_field(text, "📍 Area") or extract_field(text, "Area")
    unit = extract_field(text, "🏠 Unit") or extract_field(text, "Unit")
    bedrooms = extract_field(text, "🛏 Bedrooms") or extract_field(text, "Bedrooms")
    size = extract_field(text, "📐 Size") or extract_field(text, "Size")
    balcony = extract_field(text, "🌇 Balcony") or extract_field(text, "Balcony")
    parking = extract_field(text, "🅿️ Parking") or extract_field(text, "Parking")
    status = extract_field(text, "🟢 Status") or extract_field(text, "Status")

    sales = extract_section(text, "💰 Sale History")
    rentals = extract_section(text, "🏡 Rental Contracts")

    header = "🏠 DXB Property Report"
    if building and unit:
        header = f"🏢 {building} — Unit {unit}"
    elif building:
        header = f"🏢 {building}"

    lines = [header]
    if area:
        lines.append(f"📍 {area}")
    if is_admin and permit:
        lines.append(f"🆔 Permit: {permit}")

    lines.append("\n━━━━━━━━━━━━━━")

    specs = []
    if bedrooms:
        specs.append(f"🛏 Bedrooms: {bedrooms}")
    if size:
        specs.append(f"📐 Size: {size}")
    if balcony:
        specs.append(f"🌇 Balcony: {balcony}")
    if parking:
        specs.append(f"🅿️ Parking: {parking}")
    if status:
        specs.append(f"🟢 Status: {status}")

    if specs:
        lines.extend(specs)

    lines.append("\n━━━━━━━━━━━━━━")
    lines.append("💰 Sales History")
    if sales:
        lines.extend(sales)
    else:
        lines.append("• No sale history found")

    lines.append("\n━━━━━━━━━━━━━━")
    lines.append("🏡 Rental Contracts")
    if rentals:
        cleaned_rentals = [x for x in rentals if "rental yield" not in x.lower() and x.strip() != "%"]
        lines.extend(cleaned_rentals or ["• No rental contracts found"])
    else:
        lines.append("• No rental contracts found")

    return "\n".join(lines).strip()


def call_dxb_search(building, unit):
    result = search_dxb_unit_api(building, unit)
    if inspect.isawaitable(result):
        raise RuntimeError("search_dxb_unit_api returned awaitable; use sync implementation in worker")
    return str(result or "")


def fetch_pending_jobs(limit=1):
    res = (
        supabase.table("dxb_jobs")
        .select("*")
        .eq("status", "pending")
        .limit(limit)
        .execute()
    )
    return res.data or []


def update_job(job_id, data):
    if not job_id:
        return
    try:
        supabase.table("dxb_jobs").update(data).eq("id", job_id).execute()
    except Exception as e:
        print("JOB UPDATE ERROR:", e, flush=True)


def process_job(job):
    job_id = job.get("id")
    chat_id = job.get("chat_id")
    building = job.get("building") or ""
    unit = job.get("unit") or ""
    user_id = str(job.get("user_id") or chat_id or "").strip()
    username = job.get("username") or ""
    request_key = job.get("request_key") or normalize_dxb_key(building, unit)

    print(f"Processing DXB job: {building} {unit} user={user_id}", flush=True)
    update_job(job_id, {"status": "processing"})

    _, row_number, record = get_user_record(user_id, username)
    update_last_used(row_number)
    status, requests_used, request_limit = normalize_user_record(record)
    is_duplicate = already_searched(user_id, request_key)

    if status == "blocked":
        send_telegram(chat_id, "Your access is currently inactive. Please contact the administrator.")
        update_job(job_id, {"status": "blocked"})
        return

    if requests_used >= request_limit and not is_duplicate:
        send_telegram(chat_id, "❗ You have 0 free searches left.\n\nTo get more, please select another plan.")
        update_job(job_id, {"status": "limit_reached"})
        return

    try:
        raw = call_dxb_search(building, unit)
    except Exception as e:
        print("DXB SEARCH ERROR:", e, flush=True)
        add_search_history(user_id, username, request_key, "dxb_error", False)
        send_telegram(chat_id, "❌ DXB search error. Try again later.")
        update_job(job_id, {"status": "error", "result": str(e)[:1000]})
        return

    if not is_found_result(raw):
        add_search_history(user_id, username, request_key, "not_found", False)
        send_telegram(chat_id, "No matching DXB property was found.")
        update_job(job_id, {"status": "not_found", "result": raw[:4000]})
        return

    charged = not is_duplicate
    if charged:
        increment_user_usage(row_number, requests_used)
        remaining_after_search = max(request_limit - requests_used - 1, 0)
    else:
        remaining_after_search = max(request_limit - requests_used, 0)

    add_search_history(user_id, username, request_key, "found", charged)

    reply = format_clean_premium(raw, is_admin=str(user_id) in {str(x) for x in ADMIN_IDS})
    if is_duplicate:
        reply += "\n\n♻️ Repeated object — no search was charged."
    reply += f"\n\n❗ You have {remaining_after_search} free searches left."

    send_telegram(chat_id, reply)
    update_job(job_id, {"status": "done", "result": raw[:4000]})


def main():
    print("DXB WORKER STARTED")
    while True:
        try:
            jobs = fetch_pending_jobs(limit=1)
            if not jobs:
                time.sleep(POLL_SECONDS)
                continue
            for job in jobs:
                process_job(job)
        except KeyboardInterrupt:
            print("DXB WORKER STOPPED")
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("WORKER LOOP ERROR:", e, flush=True)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
