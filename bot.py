import os
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]
SENTINEL_URL = os.environ["SENTINEL_URL"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    text = msg.text or msg.caption or ""
    photo_id = None
    if msg.photo:
        photo_id = msg.photo[-1].file_id
    payload = {
        "text": text,
        "photo_id": photo_id,
        "from": msg.from_user.username if msg.from_user else None,
        "date": msg.date.isoformat() if msg.date else None,
    }
    try:
        requests.post(SENTINEL_URL, json=payload, timeout=10)
    except Exception as e:
        print(e)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
