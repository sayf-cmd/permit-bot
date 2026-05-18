import os
import re
import uuid
import pandas as pd
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

MASTER_CSV_URL = os.environ["MASTER_CSV_URL"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
IMPORT_SECRET = os.environ["IMPORT_SECRET"]


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def clean_phone(value):
    value = clean_text(value)
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) >= 7 else ""


def normalize_permit(value):
    return re.sub(r"\D", "", str(value or "").strip())


def load_master():
    df = pd.read_csv(MASTER_CSV_URL, low_memory=False)
    df.columns = [str(col).strip() for col in df.columns]
    df["Permit_number_clean"] = df["Permit_number"].apply(normalize_permit)
    return df


def find_master_match(permit_number):
    permit = normalize_permit(permit_number)
    if not permit:
        return None

    df = load_master()
    result = df[df["Permit_number_clean"] == permit]

    if result.empty:
        return None

    return result.iloc[0]


def insert_owner(row):
    url = f"{SUPABASE_URL}/rest/v1/owners"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    response = requests.post(url, headers=headers, json=row, timeout=30)
    response.raise_for_status()
    return response.json()


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "service": "crm-api"})


@app.route("/import-bayut", methods=["POST"])
def import_bayut():
    secret = request.headers.get("X-Import-Secret", "")

    if secret != IMPORT_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)

    permit_number = normalize_permit(data.get("permit_number"))

    if not permit_number:
        return jsonify({"error": "permit_number is required"}), 400

    match = find_master_match(permit_number)

    if match is None:
        owner_row = {
            "permit_number": permit_number,
            "area_name": clean_text(data.get("area")),
            "building_name": clean_text(data.get("building_name")),
            "room": clean_text(data.get("room")),
            "price": clean_text(data.get("price")),
            "added_date": clean_text(data.get("added_date")),
            "listing_url": clean_text(data.get("listing_url")),
            "source": "Bayut",
            "parser_id": str(uuid.uuid4()),
            "contact_status": "new",
            "listing_status": "not_matched",
        }
    else:
        owner_row = {
            "permit_number": permit_number,
            "area_name": clean_text(match.get("Area_name")) or clean_text(data.get("area")),
            "building_name": clean_text(match.get("Building_name")) or clean_text(data.get("building_name")),
            "unit_number": clean_text(match.get("Unit_number")),
            "owner_name": clean_text(match.get("Latest_owner")),
            "phone_1": clean_phone(match.get("Latest_phone_1")),
            "phone_2": clean_phone(match.get("Latest_phone_2")),
            "phone_3": clean_phone(match.get("Latest_phone_3")),
            "phone_4": clean_phone(match.get("Latest_phone_4")),
            "room": clean_text(data.get("room")),
            "price": clean_text(data.get("price")),
            "added_date": clean_text(data.get("added_date")),
            "listing_url": clean_text(data.get("listing_url")),
            "source": "Bayut",
            "parser_id": str(uuid.uuid4()),
            "contact_status": "new",
            "listing_status": "matched",
        }

    inserted = insert_owner(owner_row)

    return jsonify({
        "ok": True,
        "matched": match is not None,
        "inserted": inserted,
    })
