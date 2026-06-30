from pathlib import Path
import re

p = Path("bot.py")
text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".py.backup_d_free_limit")
backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {backup}")

helper = r'''
PROPPY_D_FREE_LIMIT = 5
PROPPY_D_USAGE_SHEET = "ProppyDUsage"

# Если хочешь, чтобы твой Telegram ID был без лимита,
# добавь его сюда строкой, например: {"123456789"}
PROPPY_D_UNLIMITED_USER_IDS = set()


def _proppy_d_is_unlimited_user(update):
    user = getattr(update, "effective_user", None)
    user_id = str(getattr(user, "id", "") or "")

    if user_id in {str(x) for x in PROPPY_D_UNLIMITED_USER_IDS}:
        return True

    # Автоматически проверяем возможные старые списки админов/доступа в bot.py
    for name in [
        "ADMIN_IDS",
        "ADMIN_USER_IDS",
        "OWNER_IDS",
        "SPECIAL_USER_IDS",
        "SPECIAL_ACCESS_USER_IDS",
        "ALLOWED_USERS",
        "ALLOWED_USER_IDS",
    ]:
        values = globals().get(name)

        if not values:
            continue

        if isinstance(values, str):
            values = [x.strip() for x in values.split(",") if x.strip()]

        try:
            if user_id in {str(x) for x in values}:
                return True
        except Exception:
            pass

    return False


def _get_or_create_proppy_d_usage_ws():
    spreadsheet = get_spreadsheet()

    try:
        ws = spreadsheet.worksheet(PROPPY_D_USAGE_SHEET)
    except Exception:
        ws = spreadsheet.add_worksheet(
            title=PROPPY_D_USAGE_SHEET,
            rows=1000,
            cols=6,
        )

    headers = [
        "User ID",
        "Username",
        "Used",
        "Last Permit",
        "Last Time",
        "Limit",
    ]

    current = ws.row_values(1)
    if current != headers:
        ws.update("A1", [headers])

    return ws


def _proppy_d_get_user_info(update):
    user = getattr(update, "effective_user", None)

    user_id = str(getattr(user, "id", "") or "")
    username = str(getattr(user, "username", "") or "")

    if not username:
        first_name = str(getattr(user, "first_name", "") or "")
        last_name = str(getattr(user, "last_name", "") or "")
        username = (first_name + " " + last_name).strip()

    return user_id, username


def get_proppy_d_free_limit_status(update):
    """
    Returns: ok, used, limit
    """
    if _proppy_d_is_unlimited_user(update):
        return True, 0, PROPPY_D_FREE_LIMIT

    try:
        ws = _get_or_create_proppy_d_usage_ws()
        user_id, _ = _proppy_d_get_user_info(update)

        rows = ws.get_all_values()

        for row in rows[1:]:
            if len(row) >= 1 and str(row[0]).strip() == user_id:
                try:
                    used = int(str(row[2]).strip() or "0")
                except Exception:
                    used = 0

                if used >= PROPPY_D_FREE_LIMIT:
                    return False, used, PROPPY_D_FREE_LIMIT

                return True, used, PROPPY_D_FREE_LIMIT

        return True, 0, PROPPY_D_FREE_LIMIT

    except Exception as e:
        print("PROPPY D LIMIT CHECK ERROR:", e, flush=True)
        # Если Google Sheet временно дал ошибку — не блокируем пользователя
        return True, 0, PROPPY_D_FREE_LIMIT


def add_proppy_d_free_usage(update, permit):
    """
    Adds +1 usage after successful Proppy search.
    Returns new used count.
    """
    if _proppy_d_is_unlimited_user(update):
        return 0

    try:
        from datetime import datetime

        ws = _get_or_create_proppy_d_usage_ws()
        user_id, username = _proppy_d_get_user_info(update)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rows = ws.get_all_values()

        for index, row in enumerate(rows[1:], start=2):
            if len(row) >= 1 and str(row[0]).strip() == user_id:
                try:
                    used = int(str(row[2]).strip() or "0")
                except Exception:
                    used = 0

                used += 1

                ws.update(
                    f"A{index}:F{index}",
                    [[user_id, username, used, str(permit), now, PROPPY_D_FREE_LIMIT]],
                )

                return used

        ws.append_row(
            [user_id, username, 1, str(permit), now, PROPPY_D_FREE_LIMIT],
            value_input_option="USER_ENTERED",
        )

        return 1

    except Exception as e:
        print("PROPPY D LIMIT ADD ERROR:", e, flush=True)
        return 0
'''

if "PROPPY_D_FREE_LIMIT" not in text:
    marker = "async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):"
    if marker not in text:
        raise SystemExit("Не нашёл handle_proppy_d")
    text = text.replace(marker, helper + "\n\n" + marker, 1)

start = text.find("async def handle_proppy_d(update: Update, context: ContextTypes.DEFAULT_TYPE):")
end = text.find("\nasync def handle_dxb(", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл блок handle_proppy_d / handle_dxb")

block = text[start:end]

old = '''        data = await search_proppy_link_request_data(permit)
        result_text = format_proppy_data(data)
'''

new = '''        limit_ok, used_count, limit_total = get_proppy_d_free_limit_status(update)

        if not limit_ok:
            await msg.edit_text(
                f"❌ Бесплатный лимит /d закончился: {used_count}/{limit_total}.\\n"
                "Для продолжения нужен доступ.",
                reply_markup=MENU_KEYBOARD,
            )
            return

        data = await search_proppy_link_request_data(permit)
        add_proppy_d_free_usage(update, permit)

        result_text = format_proppy_data(data)
'''

if old not in block:
    raise SystemExit("Не нашёл место перед search_proppy_link_request_data в handle_proppy_d")

block = block.replace(old, new, 1)
text = text[:start] + block + text[end:]

p.write_text(text, encoding="utf-8")
print("DONE: /d free limit added")
