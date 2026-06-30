from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_repair_start_description")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# 1) Remove broken OWNER_LOOKUP_START_DESCRIPTION block from any place
text = re.sub(
    r'\n?OWNER_LOOKUP_START_DESCRIPTION\s*=\s*\(\n(?:.*?\n)*?\)\n?',
    '\n',
    text,
    flags=re.S,
)

# 2) Remove description from Tariffs if it was inserted there
text = re.sub(
    r'🔎 Owner Lookup\\n\\nUse /d with a permit number or a listing link to check owner details\.\\n\\nExamples:\\n/d 71495697794\\n/d https://propertyfinder\.ae/\.\.\.\\n\\nAfter the result, tap .*?\\n\\n(?=💳 Tariffs)',
    '',
    text,
    flags=re.S,
)

# 3) Insert constant AFTER all imports, not inside imports
constant = '''OWNER_LOOKUP_START_DESCRIPTION = (
    "🔎 Owner Lookup\\n\\n"
    "Use /d with a permit number or a listing link to check owner details.\\n\\n"
    "Examples:\\n"
    "/d 71495697794\\n"
    "/d https://propertyfinder.ae/...\\n\\n"
    "After the result, tap “Show more details” to view additional owner details."
)
'''

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

lines = lines[:last_import_end] + ["", constant, ""] + lines[last_import_end:]
text = "\n".join(lines) + "\n"

# 4) Find real /start handler from CommandHandler("start", handler_name)
m = re.search(r'CommandHandler\(\s*["\']start["\']\s*,\s*([A-Za-z_]\w+)', text)

if not m:
    print("WARNING: CommandHandler('start', ...) not found. Description constant added only.")
else:
    handler_name = m.group(1)
    print(f"Found start handler: {handler_name}")

    func_pattern = re.compile(
        rf'(async\s+def\s+{re.escape(handler_name)}\([^)]*\):\n)',
        re.S,
    )

    fm = func_pattern.search(text)

    if not fm:
        print(f"WARNING: async def {handler_name} not found.")
    else:
        body_start = fm.end()
        next_func = re.search(r'\nasync\s+def\s+\w+\(', text[body_start:])
        body_end = body_start + next_func.start() if next_func else len(text)

        block = text[body_start:body_end]

        if "OWNER_LOOKUP_START_DESCRIPTION" not in block:
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

            text = text[:body_start] + block + text[body_end:]

# 5) Rename buttons / public text
text = text.replace("📞 Показать все номера", "Show more details")
text = text.replace("🙈 Скрыть номера", "Hide details")
text = text.replace("📞 Все номера по объекту", "Details")
text = text.replace("Открываю номера...", "Opening details...")
text = text.replace("Loading numbers...", "Loading details...")
text = text.replace("❌ Proppy error:", "❌ Search error:")
text = text.replace("⏳ Searching Proppy...", "⏳ Searching...")
text = text.replace("👤 PROPPY OWNER INFORMATION", "👤 OWNER INFORMATION")
text = text.replace("🟢 Actual owner / Database 2.0", "🟢 Actual owner")
text = text.replace("No Proppy owner data found.", "No owner data found.")

p.write_text(text, encoding="utf-8")
print("DONE: bot.py repaired")
