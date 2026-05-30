import json
import requests

url = "https://dxbinteract.com/wwv_flow.ajax?p_context=litedxb/property-history/17221699377089"

payload = {
    "p_flow_id": "242",
    "p_flow_step_id": "142",
    "p_instance": "17221699377089",
    "p_debug": "",
    "p_request": "PLUGIN=REEgVFlQRX5-ODUwNDQ5NzU3MzkxNjUwMTY1NQ/8jhEjFi34mv72if2DynlejDWDACp2hvpj36FVAZnhR0",
    "p_json": json.dumps({
        "pageItems": {
            "itemsToSubmit": [
                {"n": "P142_TYPE", "v": "P"},
                {"n": "P142_PROP_NO", "v": "607"},
                {
                    "n": "P142_LOCATION_ID",
                    "v": "35668",
                    "ck": "7HEUshkLnmI3aV0j5cCi0HT-FMiwNkn4lIF9r6EVPko"
                },
            ],
            "protected": "UDBfQ1VSUkVOVF9ZRUFSOlAwX1lURF9ZRUFSOlAwX1lURF9DT01QQVJFOlAwX0xP.,R0lOX1VSTDpQMF9DSEFOTkVMOlAwX0NVUlJFTkNZX1ZBTFVFOlAxNDJfUEFUSF9O.,QU1FOlAxNDJfTE9DQVRJT05fSUQ6UDBfTUVUUklDX1NZTUJPTDpHX1VTRJfTkFNRTpHX1VTRJfSU1BR0U6R19VU0VSX0VNQUlMOkdfVVNFUl9U.,SVRMRTpHX1VTRJfTU9CSUxFOkdfVVNFUl9DT01QQU5ZOkdfQ09NUEFOWV9MT0dP.,OkdfVVNFUl9ST0xFOl9HTDpQMF9TT1VSQ0U6UDBfU0lHTlVQX01PQklMRV9DT0RF/t7N3-xEmUVm-rFAI0KoPXH64_XJM4AFHU9TX6_q9Ess",
            "rowVersion": "",
            "formRegionChecksums": [],
        },
        "salt": "98059264775643367109347651372109080611",
    }),
}

r = requests.post(url, data=payload, timeout=30)

print("STATUS:", r.status_code)
print(r.text)