from pathlib import Path

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_d_link_proppy")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

start = text.find("async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):")
end = text.find("\nasync def handle_dxb(", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл handle_proppy_d или handle_dxb")

new_handle = r'''async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_input = " ".join(context.args).strip()

        if not user_input:
            await update.message.reply_text(
                "Напиши так:\n/d 71495668339\nили:\n/d https://propertyfinder.ae/...",
                reply_markup=MENU_KEYBOARD,
            )
            return

        urls = re.findall(r"https?://\S+", user_input)
        listing_url = urls[0] if urls else ""

        if listing_url:
            msg = await update.message.reply_text("🔎 Extracting permit from listing link...")

            if "propertyfinder.ae" in listing_url.lower() or "bayut.com" in listing_url.lower():
                permit = await extract_permit_safe(listing_url)

                if not permit:
                    await msg.edit_text(
                        "❌ Could not find permit number in this listing link.",
                        reply_markup=MENU_KEYBOARD,
                    )
                    return
            else:
                candidates = re.findall(r"\d{8,20}", listing_url)
                permit = normalize_permit(candidates[0]) if candidates else ""

                if not permit:
                    await msg.edit_text(
                        "❌ Could not extract permit from this link.",
                        reply_markup=MENU_KEYBOARD,
                    )
                    return

            await msg.edit_text("⏳ Searching...")
        else:
            permit = normalize_permit(user_input)

            if not permit:
                candidates = re.findall(r"\d{8,20}", user_input)
                permit = normalize_permit(candidates[0]) if candidates else ""

            if not permit:
                await update.message.reply_text(
                    "Please send a valid permit number or listing link after /d.",
                    reply_markup=MENU_KEYBOARD,
                )
                return

            msg = await update.message.reply_text("⏳ Searching...")

        data = await search_proppy_link_request_data(permit)
        result_text = format_proppy_data(data)

        context.application.bot_data.setdefault("proppy_cache", {})[permit] = data

        rows = data.get("actual_owners", []) or []
        has_numbers_button = bool(
            rows
            or data.get("actual_mobile")
            or data.get("actual_phone")
            or data.get("records2_phones")
        )

        numbers_keyboard = None
        if has_numbers_button:
            numbers_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Показать все номера", callback_data=f"proppy_numbers:{permit}")]
            ])

        try:
            spreadsheet = get_spreadsheet()
            append_proppy_result(spreadsheet, permit, data)
        except Exception as e:
            print("PROPPY SHEET SAVE ERROR:", e, flush=True)

        if len(result_text) > 3900:
            await msg.delete()
            chunks = [result_text[i:i + 3900] for i in range(0, len(result_text), 3900)]
            for index, chunk in enumerate(chunks):
                markup = numbers_keyboard if index == len(chunks) - 1 else None
                await update.message.reply_text(chunk, reply_markup=markup)
        else:
            await msg.edit_text(result_text, reply_markup=numbers_keyboard)

    except Exception as e:
        import traceback

        traceback.print_exc()

        await update.message.reply_text(
            f"❌ Proppy error:\n{e}",
            reply_markup=MENU_KEYBOARD,
        )

'''

text = text[:start] + new_handle + text[end+1:]
p.write_text(text, encoding="utf-8")

print("DONE: /d now accepts permit or listing link for Proppy only")
