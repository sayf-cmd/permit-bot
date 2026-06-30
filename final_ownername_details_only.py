from pathlib import Path
import re

# ==================================================
# 1) Add owner-name Records2 search to proppy_link_request_api.py
# ==================================================

api = Path("proppy_link_request_api.py")
api_text = api.read_text(encoding="utf-8")

api_backup = api.with_suffix(".py.backup_ownername_details")
api_backup.write_text(api_text, encoding="utf-8")
print(f"Backup saved: {api_backup}")

# Make sure quote_plus is imported
api_text = api_text.replace(
    "from urllib.parse import unquote, urljoin",
    "from urllib.parse import unquote, urljoin, quote_plus"
)

if "async def search_owner_records2_by_owner_name" not in api_text:
    insert_before = "\n\nasync def main()"
    if insert_before not in api_text:
        insert_before = "\n\nif __name__"

    owner_search_code = r'''

def parse_records2_ownername_html(html: str, owner_name: str = "") -> List[Dict[str, Any]]:
    """
    Parses Records2 OwnerName search result table.
    Returns rows like Area / Building / Unit / Owner / Phone / Size.
    """
    soup = BeautifulSoup(html, "html.parser")
    owner_upper = _clean(owner_name).upper()

    rows_out: List[Dict[str, Any]] = []

    for table in soup.find_all("table"):
        headers = [_clean(th.get_text(" ", strip=True)) for th in table.find_all("th")]

        if not headers:
            continue

        for tr in table.find_all("tr")[1:]:
            cells = [_clean(td.get_text(" ", strip=True)) for td in tr.find_all("td")]

            if not cells:
                continue

            row: Dict[str, Any] = {}

            for idx, cell in enumerate(cells):
                if idx < len(headers):
                    row[headers[idx]] = cell

            row_text = " ".join(cells).upper()

            if owner_upper and owner_upper not in row_text:
                continue

            rows_out.append(row)

    return rows_out


async def search_owner_records2_by_owner_name(owner_name: str, page_size: int = 50) -> List[Dict[str, Any]]:
    """
    Searches owner records by OwnerName in Records2.
    This is used for the 'Show more details' button.
    """
    owner_name = _clean(owner_name)

    if not owner_name:
        return []

    url = (
        f"{BASE_URL}/App/Properties/Records2"
        f"?OwnerName={quote_plus(owner_name)}"
        f"&Page=1&PageSize={int(page_size)}"
    )

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=90000)
            html = await page.content()
            return parse_records2_ownername_html(html, owner_name=owner_name)

        finally:
            await context.close()
'''

    api_text = api_text.replace(insert_before, owner_search_code + insert_before)

api.write_text(api_text, encoding="utf-8")


# ==================================================
# 2) Patch bot.py: Show more details uses only OwnerName Records2
# ==================================================

bot = Path("bot.py")
text = bot.read_text(encoding="utf-8")

bot_backup = bot.with_suffix(".py.backup_ownername_details")
bot_backup.write_text(text, encoding="utf-8")
print(f"Backup saved: {bot_backup}")

# import owner search function
if "search_owner_records2_by_owner_name" not in text:
    # simple safe standalone import
    lines = text.splitlines()
    insert_at = 0

    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1

    lines.insert(insert_at, "from proppy_link_request_api import search_owner_records2_by_owner_name")
    text = "\n".join(lines) + "\n"

# Replace formatter
start = text.find("def format_proppy_all_numbers(data):")
end = text.find("\n\nasync def handle_proppy_numbers", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл format_proppy_all_numbers или handle_proppy_numbers")

new_formatter = r'''def format_proppy_all_numbers(data):
    """
    Show more details:
    Uses owner_records_rows loaded from owner records by OwnerName.
    Does NOT use local database.
    """
    permit = str(data.get("permit") or data.get("link") or "").strip()

    rows = data.get("owner_records_rows", []) or []

    def clean(value):
        return " ".join(str(value or "").strip().split())

    def norm(value):
        return clean(value).upper()

    def get(row, *keys):
        for key in keys:
            value = row.get(key)
            if value not in [None, ""]:
                return clean(value)
        return ""

    cards = {}

    def add_card(area, building, unit, owner, phone="", price="", size=""):
        area = clean(area)
        building = clean(building)
        unit = clean(unit)
        owner = clean(owner)
        phone = clean(phone)
        price = clean(price)
        size = clean(size)

        key = (norm(building), norm(unit), norm(owner))

        if not any(key):
            return

        if key not in cards:
            cards[key] = {
                "area": area,
                "building": building,
                "unit": unit,
                "owner": owner,
                "phones": [],
                "price": price,
                "size": size,
                "has_phone": False,
            }

        if phone:
            for part in phone.replace(";", ",").split(","):
                part = clean(part)
                if part and part not in cards[key]["phones"]:
                    cards[key]["phones"].append(part)
                    cards[key]["has_phone"] = True

        if not cards[key].get("price") and price:
            cards[key]["price"] = price

        if not cards[key].get("size") and size:
            cards[key]["size"] = size

        if not cards[key].get("area") and area:
            cards[key]["area"] = area

    for row in rows:
        add_card(
            area=get(row, "Area", "area"),
            building=get(row, "Building", "building"),
            unit=get(row, "Unit", "unit", "Unit Number", "unit_number"),
            owner=get(row, "Owner", "owner", "Name", "name"),
            phone=get(row, "Phone", "phone", "Mobile", "mobile"),
            price=get(row, "Price", "price"),
            size=get(row, "Size (sqft)", "Size", "size"),
        )

    if not cards:
        return "No additional details found."

    all_cards = list(cards.values())

    # Priority: rows with phone first
    all_cards.sort(
        key=lambda x: (
            not x.get("has_phone", False),
            norm(x.get("building")),
            norm(x.get("unit")),
            norm(x.get("owner")),
        )
    )

    total_unique = len(all_cards)
    shown_cards = all_cards[:10]

    lines = ["Details"]

    if permit:
        lines.append(f"🔗 Permit: {permit}")

    for card in shown_cards:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━")

        if card.get("area"):
            lines.append(f"📍 {card['area']}")
        if card.get("building"):
            lines.append(f"🏢 {card['building']}")
        if card.get("unit"):
            lines.append(f"🏠 Unit: {card['unit']}")
        if card.get("owner"):
            lines.append(f"👤 Owner: {card['owner']}")
        if card.get("phones"):
            phone_label = "Phones" if len(card["phones"]) > 1 else "Phone"
            lines.append(f"📞 {phone_label}: {', '.join(card['phones'])}")
        if card.get("size"):
            lines.append(f"📐 Size: {card['size']}")
        if card.get("price"):
            lines.append(f"💰 Price: {card['price']}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append(f"Shown: {len(shown_cards)} of {total_unique} unique records")

    hidden = total_unique - len(shown_cards)
    if hidden > 0:
        lines.append(f"Hidden: {hidden}")

    return "\n".join(lines)
'''

text = text[:start] + new_formatter + text[end:]


# Replace handle_proppy_numbers
start = text.find("async def handle_proppy_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):")
end = text.find("\n\nasync def handle_proppy_d", start)

if start == -1 or end == -1:
    raise SystemExit("Не нашёл handle_proppy_numbers или handle_proppy_d")

new_handler = r'''async def handle_proppy_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    permit = query.data.split(":", 1)[1].strip()
    chat_id = query.message.chat_id
    storage_key = f"{chat_id}:{permit}"

    messages_store = context.application.bot_data.setdefault("proppy_numbers_messages", {})

    show_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Show more details", callback_data=f"proppy_numbers:{permit}")]
    ])

    hide_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Hide details", callback_data=f"proppy_numbers:{permit}")]
    ])

    # Toggle close
    if storage_key in messages_store:
        await query.answer("Hidden")

        message_ids = messages_store.pop(storage_key, [])

        for message_id in message_ids:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id,
                )
            except Exception as e:
                print("DELETE DETAILS MESSAGE ERROR:", e, flush=True)

        try:
            await query.message.edit_reply_markup(reply_markup=show_keyboard)
        except Exception as e:
            print("EDIT BUTTON BACK ERROR:", e, flush=True)

        return

    await query.answer("Opening details...")

    cache = context.application.bot_data.setdefault("proppy_cache", {})
    data = cache.get(permit)

    if not data:
        loading_msg = await query.message.reply_text("⏳ Loading details...")
        try:
            data = await search_proppy_link_request_data(permit)
            cache[permit] = data
        finally:
            try:
                await loading_msg.delete()
            except Exception:
                pass

    def clean(value):
        return " ".join(str(value or "").strip().split())

    def split_names(value):
        result = []
        for part in str(value or "").replace(";", ",").split(","):
            part = clean(part)
            if part and part.upper() not in ["N/A", "NONE", "NULL", "NOT AVAILABLE"]:
                result.append(part)
        return result

    owner_names = []
    owner_names += split_names(data.get("records2_owners"))
    owner_names += split_names(data.get("actual_owner"))
    owner_names += split_names(data.get("dld_owner"))

    for row in data.get("actual_owners", []) or []:
        for key in ["Owner", "owner", "Name", "name"]:
            if row.get(key):
                owner_names.append(clean(row.get(key)))

    unique_owner_names = []
    seen = set()

    for owner in owner_names:
        key = owner.upper()
        if key and key not in seen:
            seen.add(key)
            unique_owner_names.append(owner)

    owner_records_rows = []

    loading_msg = None

    try:
        loading_msg = await query.message.reply_text("⏳ Loading details...")

        for owner_name in unique_owner_names[:5]:
            try:
                rows = await search_owner_records2_by_owner_name(owner_name, page_size=50)
                owner_records_rows.extend(rows)
            except Exception as e:
                print("OWNER NAME RECORDS SEARCH ERROR:", e, flush=True)

    finally:
        if loading_msg:
            try:
                await loading_msg.delete()
            except Exception:
                pass

    data["owner_records_rows"] = owner_records_rows
    cache[permit] = data

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

text = text[:start] + new_handler + text[end:]

# Button text safety
text = text.replace("📞 Показать все номера", "Show more details")
text = text.replace("🙈 Скрыть номера", "Hide details")

bot.write_text(text, encoding="utf-8")

print("DONE: Show more details now uses OwnerName records only")
