from pathlib import Path
import re

p = Path("bot.py")
s = p.read_text(encoding="utf-8")

original = s

# 1) Add missing OWNER_LOOKUP_START_DESCRIPTION
if "OWNER_LOOKUP_START_DESCRIPTION" in s and not re.search(r"^\s*OWNER_LOOKUP_START_DESCRIPTION\s*=", s, re.M):
    lines = s.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1

    block = [
        "",
        "# FIX: missing start description",
        "OWNER_LOOKUP_START_DESCRIPTION = '''👋 Welcome.",
        "",
        "Send me a permit number, building + unit, owner name, or use the menu below.",
        "'''",
        "",
    ]

    lines[insert_at:insert_at] = block
    s = "\n".join(lines) + "\n"

# 2) Disable Proppy import block
s = re.sub(
    r"from\s+proppy_link_request_api\s+import\s+\([\s\S]*?\)\n",
    "# PROPPY DISABLED\n# from proppy_link_request_api import (...)\n",
    s
)

# 3) Disable /d Proppy command handler
s = re.sub(
    r"^(\s*(?:app|application)\.add_handler\s*\(\s*CommandHandler\s*\(\s*['\"]d['\"].*handle_proppy_d.*\)\s*\).*)$",
    r"# PROPPY DISABLED: \1",
    s,
    flags=re.M
)

# 4) Disable external listing links inside handle_message
guard = '''
    # FIX: external websites disabled to avoid CloudFront / 401 errors
    if update.message and update.message.text:
        _external_text = update.message.text.lower()
        if any(x in _external_text for x in ["bayut.com", "propertyfinder.ae", "proppy.ae"]):
            await update.message.reply_text(
                "External listing lookup is temporarily disabled. Send permit number, building + unit, or owner name instead."
            )
            return
'''

if "external websites disabled to avoid CloudFront" not in s:
    s = re.sub(
        r"(async\s+def\s+handle_message\s*\([^\)]*\):\n)",
        r"\1" + guard,
        s,
        count=1
    )

# 5) Fix Google Sheets update deprecation if exact old format exists
s = s.replace(
    'sheet.update(f"A{next_row}:F{next_row}", [new_row])',
    'sheet.update(values=[new_row], range_name=f"A{next_row}:F{next_row}")'
)

# 6) Add global error handler
error_handler_code = '''
async def global_error_handler(update, context):
    try:
        print("GLOBAL ERROR:", context.error, flush=True)
    except Exception as e:
        print("GLOBAL ERROR HANDLER FAILED:", e, flush=True)

'''

if "async def global_error_handler" not in s:
    run_match = re.search(r"^(.*(?:app|application)\.run_polling\s*\()", s, re.M)
    if run_match:
        s = s[:run_match.start()] + error_handler_code + s[run_match.start():]

# 7) Register error handler before run_polling
if ".add_error_handler(global_error_handler)" not in s:
    s = re.sub(
        r"^(\s*)((app|application)\.run_polling\s*\()",
        r"\1\3.add_error_handler(global_error_handler)\n\1\2",
        s,
        count=1,
        flags=re.M
    )

if s != original:
    p.write_text(s, encoding="utf-8")
    print("✅ bot.py fixed")
else:
    print("ℹ️ No changes needed")
