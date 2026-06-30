from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_drop_pending")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# Меняем app.run_polling() на app.run_polling(drop_pending_updates=True)
text = re.sub(
    r'\.run_polling\(\s*\)',
    '.run_polling(drop_pending_updates=True)',
    text
)

text = re.sub(
    r'\.run_polling\(\s*drop_pending_updates=True\s*,\s*drop_pending_updates=True\s*\)',
    '.run_polling(drop_pending_updates=True)',
    text
)

p.write_text(text, encoding="utf-8")
print("DONE: old pending Telegram messages will be ignored on startup")
