from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])

processed_event_ids = set()

@app.get("/")
def root():
    return {"status": "3Q貢丸 LINE Bot is running"}

@app.post("/line/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        background_tasks.add_task(handler.handle, body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    if hasattr(event, "webhook_event_id"):
        if event.webhook_event_id in processed_event_ids:
            return
        processed_event_ids.add(event.webhook_event_id)

    reply = route(event.message.text.strip())

    with ApiClient(configuration) as api:
        MessagingApi(api).reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)],
            )
        )

def route(text: str) -> str:
    # 服務諮詢
    if any(kw in text for kw in ["諮詢", "了解", "問問", "想知道", "報價", "方案", "服務"]):
        return (
            "感謝您對 3Q貢丸 有興趣\n\n"
            "我們提供兩條服務:\n\n"
            "一、500 元生圖\n"
            "用十題探尋表收需求,後台轉譯出圖交付\n"
            "適合:預算有限想試水的小店家\n\n"
            "二、客製化網路行銷\n"
            "目標承諾書 + 七步框架交付\n"
            "適合:認真想做品牌的老闆\n\n"
            "想了解哪一條?\n"
            "回覆「1」聽 500 生圖細節\n"
            "回覆「2」聽客製行銷細節\n"
            "回覆「3」直接約諮詢"
        )

    # 第一條產品線
    if "500" in text or "生圖" in text or text == "1":
        return (
            "500 元生圖方案\n\n"
            "流程:\n"
            "1. 填十題探尋表(5 分鐘)\n"
            "2. 我們後台轉譯為視覺需求\n"
            "3. 24-48 小時內交付 1 張主視覺\n"
            "4. 不限商品類別,從攤車到家庭工坊皆可\n\n"
            "適合:\n"
            "- 想試品牌視覺的小店\n"
            "- 預算還沒到客製等級\n"
            "- 想看我們手感再決定要不要深合作\n\n"
            "想開始?回覆「開始生圖」"
        )

    # 第二條產品線
    if any(kw in text for kw in ["行銷", "客製", "承諾書", "孵化"]) or text == "2":
        return (
            "客製化網路行銷方案\n\n"
            "我們做的:\n"
            "品牌命名 / 包裝設計\n"
            "電商上架 / 行銷投放\n"
            "社群經營 / 內容代產\n\n"
            "我們的不同:\n"
            "敲定方案時給你「目標承諾書」\n"
            "沒達到指標,全額退款\n\n"
            "我們要賺一塊錢\n"
            "就會付一塊錢的責任\n\n"
            "但我們挑客戶,不是什麼都接\n"
            "想了解我們合不合適,回覆「約諮詢」"
        )

    # 諮詢預約
    if any(kw in text for kw in ["約", "預約", "見面", "開始生圖"]) or text == "3":
        return (
            "好的 約一場 30 分鐘免費諮詢\n\n"
            "請告訴我:\n"
            "1. 你的店做什麼產品\n"
            "2. 目前最大的卡點\n"
            "3. 方便諮詢的時段(平日晚上 / 假日)\n\n"
            "看過後私訊給你具體時間"
        )

    # 客戶進度
    if any(kw in text for kw in ["進度", "上次", "做完", "等多久"]):
        return (
            "想查已合作案件進度\n"
            "請提供:\n"
            "1. 你的姓名或商號\n"
            "2. 案件大致開始日期\n\n"
            "立刻找專員回覆你"
        )

    # 預設主選單
    return (
        "你好 我是 3Q貢丸\n\n"
        "不管你的店多大多小\n"
        "只要你有產品、有技術、有口味\n"
        "我們就有平台、有舞台、有後台\n\n"
        "請問需要:\n"
        "回覆「諮詢」聊聊你的品牌\n"
        "回覆「500」聽生圖方案\n"
        "回覆「行銷」聽客製方案\n"
        "回覆「進度」查已合作案件"
    )
