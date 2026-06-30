from pathlib import Path

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_callback_indent")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

lines = text.splitlines()

# Удаляем все старые/кривые строки CallbackQueryHandler для proppy_numbers
clean_lines = []
for line in lines:
    if "CallbackQueryHandler(handle_proppy_numbers" in line:
        continue
    clean_lines.append(line)

# Ищем строку регистрации команды /d
insert_index = None
indent = ""

for i, line in enumerate(clean_lines):
    if 'CommandHandler("d", handle_proppy_d)' in line or "CommandHandler('d', handle_proppy_d)" in line:
        insert_index = i + 1
        indent = line[:len(line) - len(line.lstrip())]
        break

if insert_index is None:
    raise SystemExit('Не нашёл app.add_handler(CommandHandler("d", handle_proppy_d))')

handler_line = indent + 'app.add_handler(CallbackQueryHandler(handle_proppy_numbers, pattern=r"^proppy_numbers:"))'

clean_lines.insert(insert_index, handler_line)

p.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")

print("DONE: CallbackQueryHandler indentation fixed")
