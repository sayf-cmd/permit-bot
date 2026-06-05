import os
import time
import asyncio
import requests
from supabase import create_client
from dxb_interact_api import search_dxb_unit_api

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def send_telegram(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text[:3900],
        },
        timeout=30,
    )


def get_pending_job():
    res = (
        supabase.table("dxb_jobs")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def mark_processing(job_id):
    supabase.table("dxb_jobs").update({
        "status": "processing"
    }).eq("id", job_id).execute()


def mark_done(job_id, result):
    supabase.table("dxb_jobs").update({
        "status": "done",
        "result": result,
    }).eq("id", job_id).execute()


def mark_error(job_id, error):
    supabase.table("dxb_jobs").update({
        "status": "error",
        "error": str(error),
    }).eq("id", job_id).execute()


print("DXB worker started...")

while True:
    job = get_pending_job()

    if not job:
        time.sleep(5)
        continue

    job_id = job["id"]
    chat_id = job["chat_id"]
    building = job["building"]
    unit = job["unit"]

    print(f"Processing DXB job {job_id}: {building} {unit}")

    try:
        mark_processing(job_id)

        result = asyncio.run(
            search_dxb_unit_api(building, unit)
        )

        mark_done(job_id, result)
        send_telegram(chat_id, result)

        print("DONE")

    except Exception as e:
        mark_error(job_id, e)
        send_telegram(chat_id, f"❌ DXB error: {e}")

        print("ERROR:", e)

    time.sleep(2)