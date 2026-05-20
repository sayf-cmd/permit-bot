import os
import re
import uuid
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
IMPORT_SECRET = os.environ["IMPORT_SECRET"]


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def clean_phone(value):
    value = clean_text(value)
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) >= 7 else ""


def normalize_permit(value):
    return re.sub(r"\D", "", str(value or "").strip())


def insert_listing(row):
    url = f"{SUPABASE_URL}/rest/v1/listings?on_conflict=permit_number"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    response = requests.post(
        url,
        headers=headers,
        json=row,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "service": "crm-api",
    })


@app.route("/import-bayut", methods=["POST"])
def import_bayut():
    secret = request.headers.get("X-Import-Secret", "")

    if secret != IMPORT_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)

    permit_number = normalize_permit(data.get("permit_number"))

    if not permit_number:
        return jsonify({
            "error": "permit_number is required"
        }), 400

    listing_row = {
        "permit_number": permit_number,

        "listing_url": clean_text(data.get("listing_url")),

        "area_name": clean_text(data.get("area")),
        "building_name": clean_text(data.get("building_name")),

        "unit_number": clean_text(data.get("unit_number")),

        "room": clean_text(data.get("room")),
        "bedrooms": clean_text(data.get("room")),

        "price": clean_text(data.get("price")),

        "size": clean_text(data.get("size")),

        "rent_frequency": clean_text(data.get("rent_frequency")),
        "listing_type": clean_text(data.get("listing_type")),

        "added_date": clean_text(data.get("added_date")),
        "parse_status": clean_text(data.get("parse_status")),

        "matched_owner_name": clean_text(data.get("owner_name")),

        "matched_phone_1": clean_phone(data.get("phone_1")),
        "matched_phone_2": clean_phone(data.get("phone_2")),
        "matched_phone_3": clean_phone(data.get("phone_3")),
        "matched_phone_4": clean_phone(data.get("phone_4")),

        "listing_status": (
            "matched"
            if data.get("owner_name") or data.get("phone_1")
            else "not_matched"
        ),

        "source": "Bayut",

        "raw_data": data,
    }

    inserted = insert_listing(listing_row)

    return jsonify({
        "ok": True,
        "inserted": inserted,
    })
