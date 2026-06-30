PROPPY ONLY READY FILES

Files:
1. proppy_link_request_api.py
   - Proppy-only LinkCreate -> LinkDetails -> GetLinkProgress -> parse owner data.
   - Owner data is taken from Proppy LinkDetails / Database 2.0 table, not local Excel/CSV.

2. proppy_sheet_logger.py
   - Saves Proppy result to Google Sheet tab ProppyRequests.

3. proppy_bulk_to_sheet.py
   - Reads permits.txt and saves each result to Google Sheet.

4. apply_proppy_only_patch.py
   - Patches bot.py handle_proppy_d so /d uses only Proppy owner data.
   - Creates bot.py.backup_proppy_only before changing bot.py.

5. permits.txt
   - Sample file. Put your permits here, one permit per line.

Install:
cd /Users/sayf/Desktop/Playground/telegram_bot
source venv/bin/activate
pip install beautifulsoup4 playwright gspread

Copy these files into telegram_bot folder, then:
python3 apply_proppy_only_patch.py
python3 bot.py

Telegram test:
/d 7122516800

Bulk:
python3 proppy_bulk_to_sheet.py permits.txt --delay 15 --skip-existing
