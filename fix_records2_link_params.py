from pathlib import Path
import re

p = Path("proppy_link_request_api.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_records2_link_params")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

old = '''    records2_link = ""
    records2_a = soup.find("a", href=re.compile(r"/App/Properties/Records2", re.I))
    if records2_a:
        records2_link = _absolute_url(unquote(records2_a.get("href", "")))
'''

new = '''    records2_link = ""

    # Prefer the real "Search more in Database" link with query params.
    records2_candidates = soup.find_all("a", href=re.compile(r"/App/Properties/Records2", re.I))

    best_href = ""

    for a in records2_candidates:
        href = _clean(a.get("href", ""))
        text_value = _clean(a.get_text(" ", strip=True)).lower()

        if not href:
            continue

        # This is the useful button under LinkDetails:
        # /App/Properties/Records2?Building=...&UnitNumber=...&link=...
        if (
            "building=" in href.lower()
            or "unitnumber=" in href.lower()
            or "link=" in href.lower()
            or "search more in database" in text_value
        ):
            best_href = href
            break

    # Fallback: avoid generic /Records2 when possible
    if not best_href:
        for a in records2_candidates:
            href = _clean(a.get("href", ""))
            if "?" in href:
                best_href = href
                break

    if best_href:
        records2_link = _absolute_url(unquote(best_href))
'''

if old not in text:
    raise SystemExit("Не нашёл старый блок records2_link. Скинь sed -n '150,180p' proppy_link_request_api.py")

text = text.replace(old, new)

p.write_text(text, encoding="utf-8")
print("DONE: Records2 link now prefers Building/UnitNumber/link params")
