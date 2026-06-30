from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_edit_text_keyboard")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

# Убираем обычную MENU_KEYBOARD из edit_text, потому что edit_text принимает только InlineKeyboardMarkup
text = re.sub(
    r'await ([a-zA-Z0-9_\.]+)\.edit_text\(\n(\s+)(.*?)\n\s*,\n\s*reply_markup=MENU_KEYBOARD,\n\s*\)',
    r'await \1.edit_text(\n\2\3\n\2)',
    text,
    flags=re.S,
)

# Дополнительный точечный фикс для случаев, где формат отличается
text = text.replace(
    'reply_markup=MENU_KEYBOARD,\n                    )',
    ')'
)

text = text.replace(
    'reply_markup=MENU_KEYBOARD,\n                )',
    ')'
)

p.write_text(text, encoding="utf-8")
print("DONE: removed MENU_KEYBOARD from edit_text calls")
