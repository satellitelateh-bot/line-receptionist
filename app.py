import time
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from receptionist import reply

app = FastAPI(title="Lumi Hair Studio receptionist")

SESSIONS = {}
RECENT = defaultdict(deque)
MAX_PER_HOUR = 30
MAX_HISTORY = 30
MAX_TEXT = 500


class ChatIn(BaseModel):
    session_id: str
    message: str


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or request.client.host


def trim(history):
    if len(history) <= MAX_HISTORY:
        return history
    cut = history[-MAX_HISTORY:]
    while cut and cut[0]["role"] != "user":
        cut.pop(0)
    return cut


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
def chat(body: ChatIn, request: Request):
    text = body.message.strip()[:MAX_TEXT]
    if not text:
        raise HTTPException(400, "Empty message")

    now = time.time()
    hits = RECENT[client_ip(request)]
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= MAX_PER_HOUR:
        raise HTTPException(429, "ข้อความเยอะเกินไป ลองใหม่ภายหลังนะคะ / Too many messages, please try later.")
    hits.append(now)

    history = SESSIONS.setdefault(body.session_id[:64], [])
    history.append({"role": "user", "content": text})
    answer = reply(history)
    SESSIONS[body.session_id[:64]] = trim(history)
    return {"reply": answer}


import base64
import hashlib
import hmac
import json
import os
import urllib.request
from starlette.concurrency import run_in_threadpool

LINE_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")


def line_send(reply_token, text):
    data = json.dumps({"replyToken": reply_token,
                       "messages": [{"type": "text", "text": text[:5000]}]}).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/reply", data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"})
    urllib.request.urlopen(req, timeout=10)


def line_handle(user_key, text):
    now = time.time()
    hits = RECENT[user_key]
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= MAX_PER_HOUR:
        return "ข้อความเยอะเกินไป ลองใหม่ภายหลังนะคะ / Too many messages, please try later."
    hits.append(now)
    history = SESSIONS.setdefault(user_key, [])
    history.append({"role": "user", "content": text[:MAX_TEXT]})
    answer = reply(history)
    SESSIONS[user_key] = trim(history)
    return answer


@app.post("/line/webhook")
async def line_webhook(request: Request):
    body = await request.body()
    expected = base64.b64encode(hmac.new(LINE_SECRET.encode(), body, hashlib.sha256).digest()).decode()
    if not LINE_SECRET or not hmac.compare_digest(request.headers.get("x-line-signature", ""), expected):
        raise HTTPException(403, "Bad signature")
    for event in json.loads(body).get("events", []):
        if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
            continue
        user_key = "line:" + event.get("source", {}).get("userId", "unknown")
        answer = await run_in_threadpool(line_handle, user_key, event["message"]["text"])
        await run_in_threadpool(line_send, event["replyToken"], answer)
    return {"ok": True}
