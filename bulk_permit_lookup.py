import os
import re
import uuid
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

SHEET_CSV_URL = os.getenv("SHEET_CSV_URL", "").strip()
CRM_SPREADSHEET_ID = os.getenv("CRM_SPREADSHEET_ID", "").strip()
CRM_SHEET_NAME = os.getenv("CRM_SHEET_NAME", "CRM_INBOX").strip()
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "").strip()

OUTPUT_DIR = Path("bulk_reports")
OUTPUT_DIR.mkdir(exist_ok=True)

_DF = None
_INDEX = None


def clean_digits(value):
    return re.sub(r"\D+", "", str(value or ""))


def extract_permits(text):
    nums = re.findall(r"\b\d{8,15}\b", text or "")
    seen = set()
    result = []

    for n in nums:
        d = clean_digits(n)
        if not d:
            continue
        if d.startswith("971"):
            continue
        if d not in seen:
            seen.add(d)
            result.append(d)

    return result


def permit_variants(value):
    d = clean_digits(value)
    variants = []

    def add(x):
        x = clean_digits(x)
        if x and x not in variants:
            variants.append(x)

    add(d)

    if len(d) > 2:
        add(d[2:])
        add(d[:-2])

    if len(d) > 4:
        add(d[2:-2])

    base_list = list(variants)

    for base in base_list:
        if not base.startswith("71"):
            add("71" + base)
        if not base.startswith("65"):
            add("65" + base)
        if not base.endswith("00"):
            add(base + "00")
            add("71" + base + "00")
            add("65" + base + "00")

    return variants


def load_database():
    global _DF, _INDEX

    if _DF is not None and _INDEX is not None:
        return _DF, _INDEX

    if not SHEET_CSV_URL:
        raise RuntimeError("SHEET_CSV_URL is empty. Add it to .env")

    df = pd.read_csv(SHEET_CSV_URL, dtype=str, keep_default_na=False)
    if "Permit" not in df.columns:
        raise RuntimeError("Column 'Permit' not found in database")

    df["_permit_clean"] = df["Permit"].map(clean_digits)

    index = {}
    for i, p in enumerate(df["_permit_clean"].tolist()):
        if p and p not in index:
            index[p] = i

    _DF = df
    _INDEX = index
    return df, index


def pick_first(row, cols):
    for c in cols:
        if c in row and str(row.get(c, "")).strip():
            return str(row.get(c, "")).strip()
    return ""


def lookup_one(permit):
    df, index = load_database()

    for variant in permit_variants(permit):
        if variant in index:
            row = df.iloc[index[variant]].to_dict()

            return {
                "found": True,
                "requested_permit": permit,
                "matched_permit": row.get("Permit", ""),
                "matched_variant": variant,
                "area": row.get("Area", ""),
                "building": row.get("Building No", ""),
                "unit": row.get("Unit No", ""),
                "owner": pick_first(row, ["Latest_Owner", "Owner 2024", "Owner 2023", "Owner 2022"]),
                "phone_1": pick_first(row, ["Latest_Phone_1", "Mobile_2024_1", "Mobile_2023_1", "Mobile_2022_1"]),
                "phone_2": pick_first(row, ["Latest_Phone_2", "Mobile_2024_2", "Mobile_2023_2", "Mobile_2022_2"]),
                "phone_3": pick_first(row, ["Latest_Phone_3", "Mobile_2024_3", "Mobile_2023_3", "Mobile_2022_3"]),
                "phone_4": pick_first(row, ["Latest_Phone_4", "Mobile_2024_4", "Mobile_2023_4", "Mobile_2022_4"]),
                "raw": row,
            }

    return {
        "found": False,
        "requested_permit": permit,
        "matched_permit": "",
        "matched_variant": "",
        "area": "",
        "building": "",
        "unit": "",
        "owner": "",
        "phone_1": "",
        "phone_2": "",
        "phone_3": "",
        "phone_4": "",
        "raw": {},
    }


def create_excel(results, batch_id):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = OUTPUT_DIR / f"bulk_permits_{now}.xlsx"

    matched_rows = []
    not_found_rows = []

    for r in results:
        if r["found"]:
            base = {
                "Requested Permit": r["requested_permit"],
                "Matched Permit": r["matched_permit"],
                "Matched Variant": r["matched_variant"],
                "Area": r["area"],
                "Building": r["building"],
                "Unit": r["unit"],
                "Owner": r["owner"],
                "Phone 1": r["phone_1"],
                "Phone 2": r["phone_2"],
                "Phone 3": r["phone_3"],
                "Phone 4": r["phone_4"],
            }

            raw = {
                f"Raw - {k}": v
                for k, v in r["raw"].items()
                if k != "_permit_clean"
            }

            matched_rows.append({**base, **raw})
        else:
            not_found_rows.append({
                "Requested Permit": r["requested_permit"],
                "Status": "Not Found",
            })

    summary_rows = [
        {"Metric": "Batch ID", "Value": batch_id},
        {"Metric": "Checked", "Value": len(results)},
        {"Metric": "Matched", "Value": sum(1 for r in results if r["found"])},
        {"Metric": "Not Found", "Value": sum(1 for r in results if not r["found"])},
        {"Metric": "Created At", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    ]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(matched_rows).to_excel(writer, sheet_name="Matched", index=False)
        pd.DataFrame(not_found_rows).to_excel(writer, sheet_name="Not Found", index=False)

        for sheet_name in writer.book.sheetnames:
            ws = writer.book[sheet_name]
            ws.freeze_panes = "A2"

            for cell in ws[1]:
                cell.font = cell.font.copy(bold=True)

            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter

                for cell in col:
                    value = str(cell.value or "")
                    max_len = max(max_len, len(value))

                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 35)

    return str(path)


def get_credentials_file():
    if GOOGLE_CREDENTIALS_FILE and Path(GOOGLE_CREDENTIALS_FILE).exists():
        return GOOGLE_CREDENTIALS_FILE

    for name in [
        "service_account.json",
        "credentials.json",
        "google_credentials.json",
        "client_secret.json",
    ]:
        if Path(name).exists():
            return name

    return ""


def send_matched_to_crm(results, batch_id):
    matched = [r for r in results if r["found"]]

    if not matched:
        return 0, "no matched rows"

    if not CRM_SPREADSHEET_ID:
        return 0, "CRM_SPREADSHEET_ID is empty"

    cred_file = get_credentials_file()
    if not cred_file:
        return 0, "Google credentials file not found"

    import gspread

    gc = gspread.service_account(filename=cred_file)
    sh = gc.open_by_key(CRM_SPREADSHEET_ID)

    try:
        ws = sh.worksheet(CRM_SHEET_NAME)
    except Exception:
        ws = sh.add_worksheet(title=CRM_SHEET_NAME, rows=1000, cols=30)

    headers = [
        "created_at",
        "source",
        "batch_id",
        "requested_permit",
        "matched_permit",
        "matched_variant",
        "area",
        "building",
        "unit",
        "owner",
        "phone_1",
        "phone_2",
        "phone_3",
        "phone_4",
        "status",
    ]

    existing = ws.row_values(1)
    if existing != headers:
        ws.clear()
        ws.append_row(headers)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for r in matched:
        rows.append([
            now,
            "telegram_bulk",
            batch_id,
            r["requested_permit"],
            r["matched_permit"],
            r["matched_variant"],
            r["area"],
            r["building"],
            r["unit"],
            r["owner"],
            r["phone_1"],
            r["phone_2"],
            r["phone_3"],
            r["phone_4"],
            "new",
        ])

    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows), "ok"


def run_bulk(text, send_to_crm=True):
    permits = extract_permits(text)

    if not permits:
        raise RuntimeError("No permits found in message")

    batch_id = str(uuid.uuid4())[:8]
    results = [lookup_one(p) for p in permits]

    excel_path = create_excel(results, batch_id)

    crm_sent = 0
    crm_status = "skipped"

    if send_to_crm:
        try:
            crm_sent, crm_status = send_matched_to_crm(results, batch_id)
        except Exception as e:
            crm_sent = 0
            crm_status = f"crm_error: {type(e).__name__}: {e}"

    return {
        "batch_id": batch_id,
        "checked": len(results),
        "matched": sum(1 for r in results if r["found"]),
        "not_found": sum(1 for r in results if not r["found"]),
        "excel_path": excel_path,
        "crm_sent": crm_sent,
        "crm_status": crm_status,
    }
