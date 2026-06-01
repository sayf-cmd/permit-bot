import os
import sys
import socket
import traceback
from io import StringIO

print("=== PYTHON ===")
print(sys.version)
print("Executable:", sys.executable)

print("\n=== ENV CHECK ===")
for key in ["CSV_URL", "PROPERTY_CSV_URL", "DATABASE_URL", "CSV_LINK", "BOT_TOKEN", "TELEGRAM_BOT_TOKEN"]:
    value = os.getenv(key)
    print(f"{key} =", repr(value)[:300])

csv_url = (
    os.getenv("CSV_URL")
    or os.getenv("PROPERTY_CSV_URL")
    or os.getenv("CSV_LINK")
)

print("\n=== SELECTED CSV URL ===")
print(repr(csv_url))

print("\n=== DNS CHECK ===")
for host in ["docs.google.com", "api.telegram.org"]:
    try:
        print(host, "=>", socket.gethostbyname(host))
    except Exception as e:
        print(host, "ERROR:", repr(e))

print("\n=== REQUESTS CSV CHECK ===")
try:
    import requests
    r = requests.get(csv_url, timeout=30, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    print("status:", r.status_code)
    print("content-type:", r.headers.get("content-type"))
    print("final-url:", r.url)
    print("preview:", r.text[:300])
except Exception:
    traceback.print_exc()

print("\n=== PANDAS CSV CHECK ===")
try:
    import pandas as pd
    import requests
    r = requests.get(csv_url, timeout=30, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    df = pd.read_csv(StringIO(r.text), dtype=str, low_memory=False)
    print("loaded rows:", len(df))
    print("columns:", list(df.columns))
    print(df.head(3).to_string())
except Exception:
    traceback.print_exc()

print("\n=== TELEGRAM TOKEN CHECK ===")
token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
print("token exists:", bool(token))
if token:
    print("token prefix:", token[:8] + "..." if len(token) > 8 else token)
    try:
        import httpx
        url = f"https://api.telegram.org/bot{token}/getMe"
        resp = httpx.get(url, timeout=20)
        print("telegram status:", resp.status_code)
        print("telegram response:", resp.text[:500])
    except Exception:
        traceback.print_exc()
