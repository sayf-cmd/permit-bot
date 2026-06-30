from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_repair_ownername_import")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# 1) Remove broken standalone import line wherever it was inserted
lines = text.splitlines()
lines = [
    line for line in lines
    if line.strip() != "from proppy_link_request_api import search_owner_records2_by_owner_name"
]
text = "\n".join(lines) + "\n"

target = "search_owner_records2_by_owner_name"

# 2) Add target into existing multiline import from proppy_link_request_api
pattern = re.compile(
    r"from proppy_link_request_api import \(\n(?P<body>.*?)\n\)",
    re.S,
)

m = pattern.search(text)

if m:
    body = m.group("body")

    if target not in body:
        new_body = body.rstrip() + f"\n    {target},"
        text = text[:m.start("body")] + new_body + text[m.end("body"):]
        print("Added into multiline proppy_link_request_api import.")
else:
    # 3) If import is single-line, extend it
    single_pattern = re.compile(r"from proppy_link_request_api import ([^\n]+)")
    m2 = single_pattern.search(text)

    if m2:
        imported = m2.group(1)

        if target not in imported:
            new_imported = imported.rstrip() + f", {target}"
            text = text[:m2.start(1)] + new_imported + text[m2.end(1):]
            print("Added into single-line proppy_link_request_api import.")
    else:
        # 4) Last fallback: insert after all imports using parentheses-aware logic
        lines = text.splitlines()
        i = 0
        last_import_end = 0

        while i < len(lines):
            s = lines[i].strip()

            if not s or s.startswith("#"):
                i += 1
                continue

            if s.startswith("import ") or s.startswith("from "):
                depth = lines[i].count("(") - lines[i].count(")")
                i += 1

                while i < len(lines) and (depth > 0 or lines[i - 1].rstrip().endswith("\\")):
                    depth += lines[i].count("(") - lines[i].count(")")
                    i += 1

                last_import_end = i
                continue

            break

        lines.insert(
            last_import_end,
            f"from proppy_link_request_api import {target}"
        )

        text = "\n".join(lines) + "\n"
        print("Added standalone import after import block.")

p.write_text(text, encoding="utf-8")
print("DONE: import repaired")
