from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_start_desc_button")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# 1) Remove Owner Lookup description if it was inserted before Tariffs
tariff_desc_variants = [
'''🔎 Owner Lookup\\n\\nUse /d with a permit number or a listing link to check owner details.\\n\\nExamples:\\n/d 71495697794\\n/d https://propertyfinder.ae/...\\n\\nAfter the result, tap “📞 Показать все номера” to view additional owner numbers.\\n\\n💳 Tariffs''',
'''🔎 Owner Lookup\\n\\nUse /d with a permit number or a listing link to check owner details.\\n\\nExamples:\\n/d 71495697794\\n/d https://propertyfinder.ae/...\\n\\nAfter the result, tap “Show more details” to view additional owner details.\\n\\n💳 Tariffs''',
]

for old in tariff_desc_variants:
    text = text.replace(old, "💳 Tariffs")

# More flexible cleanup if the block is split inside source
text = re.sub(
    r'🔎 Owner Lookup\\n\\nUse /d with a permit number or a listing link to check owner details\.\\n\\nExamples:\\n/d 71495697794\\n/d https://propertyfinder\.ae/\.\.\.\\n\\nAfter the result, tap .*?\\n\\n(?=💳 Tariffs)',
    '',
    text,
    flags=re.S,
)

# 2) Add /d description to /start
start_description = r'''
OWNER_LOOKUP_START_DESCRIPTION = (
    "🔎 Owner Lookup\n\n"
    "Use /d with a permit number or a listing link to check owner details.\n\n"
    "Examples:\n"
    "/d 71495697794\n"
    "/d https://propertyfinder.ae/...\n\n"
    "After the result, tap “Show more details” to view additional owner details."
)
'''

if "OWNER_LOOKUP_START_DESCRIPTION" not in text:
    # insert after imports
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1
    lines.insert(insert_at, start_description.strip())
    text = "\n".join(lines) + "\n"

# Put description into handle_start as a separate first message
m = re.search(r'async def handle_start\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n', text)
if m:
    start_pos = m.end()
    next_func = text.find("\nasync def ", start_pos)
    if next_func == -1:
        next_func = len(text)

    block = text[start_pos:next_func]

    if "OWNER_LOOKUP_START_DESCRIPTION" not in block:
        # insert after try: if exists, otherwise at beginning of function
        if "    try:\n" in block:
            block = block.replace(
                "    try:\n",
                "    try:\n"
                "        await update.message.reply_text(OWNER_LOOKUP_START_DESCRIPTION)\n",
                1,
            )
        else:
            block = (
                "    await update.message.reply_text(OWNER_LOOKUP_START_DESCRIPTION)\n"
                + block
            )

        text = text[:start_pos] + block + text[next_func:]
else:
    print("WARNING: handle_start not found. Description variable added, but not inserted into /start.")

# 3) Button text changes
text = text.replace("📞 Показать все номера", "Show more details")
text = text.replace("🙈 Скрыть номера", "Hide details")
text = text.replace("📞 Все номера по объекту", "Details")
text = text.replace("Открываю номера...", "Opening details...")
text = text.replace("Loading numbers...", "Loading details...")

# 4) Remove source names from user-facing text
user_text_replacements = {
    "👤 PROPPY OWNER INFORMATION": "👤 OWNER INFORMATION",
    "🟢 Actual owner / Database 2.0": "🟢 Actual owner",
    "No Proppy owner data found.": "No owner data found.",
    "❌ Proppy error:": "❌ Search error:",
    "⏳ Searching Proppy...": "⏳ Searching...",
    "Database 2.0": "Owner records",
    "Proppy": "Owner Lookup",
}

for old, new in user_text_replacements.items():
    text = text.replace(old, new)

p.write_text(text, encoding="utf-8")


# Also clean proppy_link_request_api.py
api = Path("proppy_link_request_api.py")
if api.exists():
    api_text = api.read_text(encoding="utf-8")
    api_backup = api.with_suffix(".py.backup_public_words")
    api_backup.write_text(api_text, encoding="utf-8")
    print(f"Backup saved: {api_backup}")

    api_replacements = {
        "👤 PROPPY OWNER INFORMATION": "👤 OWNER INFORMATION",
        "🟢 Actual owner / Database 2.0": "🟢 Actual owner",
        "No Proppy owner data found.": "No owner data found.",
        "Database 2.0": "Owner records",
        "Proppy": "Owner Lookup",
    }

    for old, new in api_replacements.items():
        api_text = api_text.replace(old, new)

    api.write_text(api_text, encoding="utf-8")

print("DONE: /start description moved, tariffs cleaned, button renamed")
