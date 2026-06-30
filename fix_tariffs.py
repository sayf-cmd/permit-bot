from pathlib import Path

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_tariffs")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

text = text.replace("🔹 50 Searches — 200 AED", "🔹 30 Searches — 150 AED")
text = text.replace("🔹 100 Searches — 300 AED", "🔹 50 Searches — 200 AED")
text = text.replace("🔹 300 Searches — 500 AED", "🔹 100 Searches — 400 AED")

# На случай если тире другое
text = text.replace("🔹 50 Searches - 200 AED", "🔹 30 Searches — 150 AED")
text = text.replace("🔹 100 Searches - 300 AED", "🔹 50 Searches — 200 AED")
text = text.replace("🔹 300 Searches - 500 AED", "🔹 100 Searches — 400 AED")

p.write_text(text, encoding="utf-8")
print("DONE: tariffs updated")
