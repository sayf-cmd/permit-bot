from pathlib import Path

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_numbers_toggle")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

start = text.find("async def handle_proppy_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):")
end = text.find("\n\nasync def handle_proppy_d", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл handle_proppy_numbers или handle_proppy_d")

new_func = r'''async def handle_proppy_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    permit = query.data.split(":", 1)[1].strip()
    chat_id = query.message.chat_id
    storage_key = f"{chat_id}:{permit}"

    messages_store = context.application.bot_data.setdefault("proppy_numbers_messages", {})

    show_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Показать все номера", callback_data=f"proppy_numbers:{permit}")]
    ])

    hide_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🙈 Скрыть номера", callback_data=f"proppy_numbers:{permit}")]
    ])

    # If numbers are already opened — delete them and switch button back.
    if storage_key in messages_store:
        await query.answer("Скрыто")

        message_ids = messages_store.pop(storage_key, [])

        for message_id in message_ids:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id,
                )
            except Exception as e:
                print("DELETE NUMBERS MESSAGE ERROR:", e, flush=True)

        try:
            await query.message.edit_reply_markup(reply_markup=show_keyboard)
        except Exception as e:
            print("EDIT BUTTON BACK ERROR:", e, flush=True)

        return

    # First click — show numbers.
    await query.answer("Открываю номера...")

    cache = context.application.bot_data.setdefault("proppy_cache", {})
    data = cache.get(permit)

    if not data:
        loading_msg = await query.message.reply_text("⏳ Loading numbers...")
        try:
            data = await search_proppy_link_request_data(permit)
            cache[permit] = data
        finally:
            try:
                await loading_msg.delete()
            except Exception:
                pass

    text = format_proppy_all_numbers(data)

    sent_ids = []

    if len(text) > 3900:
        chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]
        for chunk in chunks:
            sent = await query.message.reply_text(chunk)
            sent_ids.append(sent.message_id)
    else:
        sent = await query.message.reply_text(text)
        sent_ids.append(sent.message_id)

    messages_store[storage_key] = sent_ids

    try:
        await query.message.edit_reply_markup(reply_markup=hide_keyboard)
    except Exception as e:
        print("EDIT BUTTON HIDE ERROR:", e, flush=True)
'''

text = text[:start] + new_func + text[end:]
p.write_text(text, encoding="utf-8")

print("DONE: numbers button is now toggle open/close")
