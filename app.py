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
