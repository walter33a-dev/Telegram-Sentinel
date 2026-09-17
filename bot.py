import io
import json
import os
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, send_file

TOKEN = os.environ["BOT_TOKEN"]
SENTINEL_URL = os.environ.get("SENTINEL_URL", "").strip()
PORT = int(os.environ.get("PORT", "8080"))
PUBLIC = (
    os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    or os.environ.get("PUBLIC_URL")
    or "telegram-sentinel-production.up.railway.app"
)
BASE = "https://" + PUBLIC.replace("https://", "").replace("http://", "").rstrip("/")
STORE = "/tmp/incidents.json"

INCIDENTS: list[dict] = []
PHOTOS: dict[str, bytes] = {}

http = Flask(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load():
    global INCIDENTS
    try:
        INCIDENTS = json.load(open(STORE, encoding="utf-8"))
        if not isinstance(INCIDENTS, list):
            INCIDENTS = []
    except Exception:
        INCIDENTS = []


def persist():
    try:
        json.dump(INCIDENTS[:300], open(STORE, "w", encoding="utf-8"))
    except Exception as exc:
        print("persist", exc)


def remember(row: dict):
    INCIDENTS.insert(0, row)
    del INCIDENTS[300:]
    persist()
    if SENTINEL_URL:
        try:
            requests.post(SENTINEL_URL, json=row, timeout=10)
        except Exception as exc:
            print("SENTINEL_URL", exc)


def download_photo(file_id: str) -> bytes:
    meta = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=20,
    ).json()
    path = ((meta.get("result") or {}).get("file_path")) or ""
    if not path:
        print("getFile", meta)
        return b""
    r = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{path}", timeout=30)
    r.raise_for_status()
    print("ImagePush", path, len(r.content))
    return r.content


def ingest_msg(msg: dict):
    if not msg:
        return
    text = msg.get("text") or msg.get("caption") or ""
    photos = msg.get("photo") or []
    photo_id = photos[-1]["file_id"] if photos else None
    doc = msg.get("document") or {}
    if not photo_id and str(doc.get("mime_type") or "").startswith("image/"):
        photo_id = doc.get("file_id")
    user = msg.get("from") or {}
    chat = msg.get("chat") or {}
    photo_url = ""
    if photo_id:
        try:
            data = download_photo(str(photo_id))
            name = f"tg{msg.get('message_id')}.jpg"
            PHOTOS[name] = data
            photo_url = f"{BASE}/media/{name}"
        except Exception as exc:
            print("photo", exc)
    from_name = (
        (f"@{user['username']}" if user.get("username") else "")
        or " ".join(p for p in [user.get("first_name"), user.get("last_name")] if p)
        or "Telegram"
    )
    title = chat.get("title") or ""
    row = {
        "text": text,
        "photo_id": photo_id,
        "photo_url": photo_url,
        "from": f"{from_name} · {title}".strip(" ·") if title else from_name,
        "date": now_iso(),
        "chat_id": chat.get("id"),
        "message_id": msg.get("message_id"),
        "chat_title": title,
    }
    remember(row)


@http.get("/")
@http.get("/health")
def health():
    return jsonify({"ok": True, "name": "Telegram-Sentinel", "n": len(INCIDENTS), "protocol": "imagepush", "webhook": f"{BASE}/telegram"})


@http.get("/incidents")
def incidents():
    return jsonify({"ok": True, "n": len(INCIDENTS), "rows": INCIDENTS[:200]})


@http.get("/media/<name>")
def media(name: str):
    data = PHOTOS.get(name)
    if not data:
        return ("", 404)
    return send_file(io.BytesIO(data), mimetype="image/jpeg", download_name=name)


@http.post("/telegram")
def telegram():
    body = request.get_json(force=True, silent=True) or {}
    msg = body.get("message") or body.get("channel_post") or body.get("edited_message") or body.get("edited_channel_post") or {}
    ingest_msg(msg if isinstance(msg, dict) else {})
    return jsonify({"ok": True})


def set_webhook():
    url = f"{BASE}/telegram"
    r = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook",
        params={
            "url": url,
            "drop_pending_updates": "false",
            "allowed_updates": json.dumps(["message", "edited_message", "channel_post", "edited_channel_post"]),
        },
        timeout=20,
    )
    print("setWebhook", url, r.text)


if __name__ == "__main__":
    load()
    set_webhook()
    http.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
