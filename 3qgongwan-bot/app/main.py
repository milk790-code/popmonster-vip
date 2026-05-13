from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    FollowEvent,
    UnfollowEvent,
)
from app.config import LINE_CHANNEL_SECRET
from app import handlers

app = FastAPI(title="3Q 公館 LINE Bot")
parser = WebhookParser(LINE_CHANNEL_SECRET)


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request) -> dict:
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()

    try:
        events = parser.parse(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent):
            handlers.handle_message(event)
        elif isinstance(event, FollowEvent):
            handlers.handle_follow(event)
        elif isinstance(event, UnfollowEvent):
            handlers.handle_unfollow(event)

    return {"ok": True}
