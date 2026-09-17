import os
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
TOKEN = os.environ SENTINEL_URL = os.environ async def handle_message(update, context):
msg = update.effective_message
if not msg:
return
text = msg.text or msg.caption or ""
photo_id = msg.photo[-1].file_id if msg.photo else None
payload = {
"text": text,
"photo_id": photo_id,
"from": msg.from_user.username if msg.from_user else None,
"date": msg.date.isoformat() if msg.date else None,
}
requests.post(SENTINEL_URL, json=payload)
def main():
app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, handle_message))
app.run_polling()
if name == "main":
main()
Commit, Railway relance.
