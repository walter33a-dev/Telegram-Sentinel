import io
import os
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, send_file
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

TOKEN = os.environ["BOT_TOKEN"]
SENTINEL_URL = os.environ.get("SENTINEL_URL", "").strip()
PORT = int(os.environ.get("PORT", "8080"))
PUBLIC = os.environ.get("RAILWAY_PUBLIC_DOMAIN") or os.environ.get("PUBLIC_URL") or ""
BASE = ("https://" + PUBLIC.replace("https://", "").replace("http://", "")).rstrip("/") if PUBLIC else ""

INCIDENTS: list[dict] = []
PHOTOS: dict[str, bytes] = {}

http = Flask(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@http.get("/")
@http.get("/health")
def health():
    return jsonify({"ok": True, "name": "Telegram-Sentinel", "n": len(INCIDENTS), "protocol": "imagepush"})


@http.get("/incidents")
def incidents():
    return jsonify({"ok": True, "n": len(INCIDENTS), "rows": INCIDENTS[:200]})


@http.get("/media/<name>")
def media(name: str):
    data = PHOTOS.get(name)
    if not data:
        return ("", 404)
    return send_file(io.BytesIO(data), mimetype="image/jpeg", download_name=name)


def remember(row: dict):
    INCIDENTS.insert(0, row)
    del INCIDENTS[200:]
    if SENTINEL_URL:
        try:
            requests.post(SENTINEL_URL, json=row, timeout=10)
        except Exception as exc:
            print("SENTINEL_URL", exc)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    text = msg.text or msg.caption or ""
    user = msg.from_user
    chat = msg.chat
    photo_id = msg.photo[-1].file_id if msg.photo else None
    photo_url = ""
    if photo_id:
        try:
            f = await context.bot.get_file(photo_id)
            data = bytes(await f.download_as_bytearray())
            name = f"tg{msg.message_id}.jpg"
            PHOTOS[name] = data
            if BASE:
                photo_url = f"{BASE}/media/{name}"
            print("ImagePush", name, len(data))
        except Exception as exc:
            print("photo", exc)
    from_name = (f"@{user.username}" if user and user.username else "") or (
        " ".join(p for p in [user.first_name if user else "", user.last_name if user else ""] if p)
    ) or "Telegram"
    title = chat.title if chat else ""
    row = {
        "text": text,
        "photo_id": photo_id,
        "photo_url": photo_url,
        "from": f"{from_name} · {title}".strip(" ·") if title else from_name,
        "date": msg.date.isoformat() if msg.date else now_iso(),
        "chat_id": chat.id if chat else None,
        "message_id": msg.message_id,
        "chat_title": title,
    }
    remember(row)


def main():
    threading.Thread(target=lambda: http.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False), daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
