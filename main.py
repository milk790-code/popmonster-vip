"""
3Q貢丸 LINE 客服機器人
台灣在地品牌孵化所

v2.1 — 修正 + 常數抽取
  v2.0:
    1. TTL 去重防記憶體洩漏
    2. Webhook 簽名錯誤捕捉
    3. 路由優先級修正(「約諮詢」不被「諮詢」攔截)
    4. 新增「送出」路由 + 十題回答偵測
    5. 空訊息 / 超長訊息防護
    6. 加好友改 reply 省 push 額度
    7. 全形/半形容錯
    8. 擴充「合作」「案例」「作品」等入口詞
  v2.1:
    9. _normalize 加 .lower() — 英文大小寫不敏感
   10. 關鍵字 + 回覆文字抽成頂層常數,單一來源
   11. 新增 _has_any() 輔助函式減少重複
"""

from fastapi import FastAPI, Request, HTTPException
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, FollowEvent,
)
from dotenv import load_dotenv
import os, time, logging

load_dotenv()

# ══════════════════════════════════════════════
# 共用常數(改一處全生效)
# ══════════════════════════════════════════════

KW_START_IMAGE = ["開始生圖", "開始畫"]
KW_CUSTOMER_SERVICE = ["客服", "人工", "真人", "找你", "找人"]
KW_BOOKING = ["約諮詢", "預約", "約一下", "見面", "聊聊"]
KW_PRODUCT_2 = ["行銷", "客製", "承諾書", "孵化", "推廣", "代操", "經營", "投放"]
KW_INQUIRY = [
    "諮詢", "了解", "問問", "想知道", "報價", "方案", "服務",
    "多少", "價格", "費用", "項目", "業務", "做什麼",
    "合作", "案例", "作品", "介紹", "品牌",
    "怎麼收", "收費", "幾塊", "價目",
]
KW_PROGRESS = ["進度", "上次", "做完", "等多久", "完成沒"]
KW_THANKS = ["謝謝", "感謝", "讚", "厲害", "棒", "太好了"]

REPLY_RECEIVED_FORM = (
    "收到你的十題表了!\n\n"
    "我們會在 24-48 小時內\n"
    "整理好需求並開始製作\n\n"
    "過程中有問題會主動聯繫你\n"
    "想查進度隨時回覆「進度」"
)

REPLY_TEN_QUESTIONS = (
    "好的 開始你的 500 元生圖\n\n"
    "請依序回答十題,全部答完後傳「送出」\n"
    "24-48 小時內交付:\n\n"
    "1. 你的店家或品牌名稱\n"
    "2. 主要產品或服務\n"
    "3. 主要客群\n"
    "4. 喜歡的風格(可貼參考圖)\n"
    "5. 主色系偏好\n"
    "6. 想用在哪(招牌/包裝/IG/官網)\n"
    "7. 想傳達的核心訊息一句話\n"
    "8. 不喜歡的元素\n"
    "9. 截稿時間\n"
    "10. 含一次免費修,是否需要\n\n"
    "可一題一題回,也可一次貼齊"
)

# ══════════════════════════════════════════════
# 基礎設定
# ══════════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("3qbot")

app = FastAPI(title="3Q貢丸 LINE Bot", version="2.1")
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])

_seen: dict[str, float] = {}
_TTL = 600


def _dedup(event_id: str) -> bool:
    now = time.time()
    expired = [k for k, t in _seen.items() if now - t > _TTL]
    for k in expired:
        del _seen[k]
    if event_id in _seen:
        return True
    _seen[event_id] = now
    return False


# ══════════════════════════════════════════════
# 端點
# ══════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "3Q貢丸 LINE Bot is running", "version": "2.1"}


@app.post("/line/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature — 可能是 Channel Secret 不對")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")
    return "OK"


# ══════════════════════════════════════════════
# 事件處理
# ══════════════════════════════════════════════

@handler.add(FollowEvent)
def handle_follow(event):
    _reply(event, (
        "你好 我是 3Q貢丸\n"
        "台灣在地品牌孵化所\n\n"
        "不管你的店多大多小\n"
        "只要你有產品、有技術、有口味\n"
        "我們就有平台、有舞台、有後台\n\n"
        "兩條服務任選:\n"
        "回覆「500」聽 500 元生圖方案\n"
        "回覆「行銷」聽客製化網路行銷\n\n"
        "或直接回覆「諮詢」聊聊你的品牌\n"
        "找真人回覆「客服」"
    ))


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    eid = getattr(event, "webhook_event_id", None)
    if eid and _dedup(eid):
        return

    text = _normalize(event.message.text or "")

    if not text:
        _reply(event, _menu())
        return

    if len(text) > 500:
        _reply(event, "訊息有點長 我可能看不完\n\n請用簡短關鍵字:\n回覆「諮詢」「500」「行銷」「客服」")
        return

    _reply(event, route(text))


# ══════════════════════════════════════════════
# 工具
# ══════════════════════════════════════════════

def _reply(event, text: str):
    try:
        with ApiClient(configuration) as api:
            MessagingApi(api).reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)],
                )
            )
    except Exception as e:
        logger.error(f"Reply failed: {e}")


def _normalize(text: str) -> str:
    """全形→半形 + 去前後空白 + 小寫"""
    out = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            out.append(chr(cp - 0xFEE0))
        elif ch == '\u3000':
            out.append(' ')
        else:
            out.append(ch)
    return "".join(out).strip().lower()


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _menu() -> str:
    return (
        "你好 我是 3Q貢丸\n\n"
        "不管你的店多大多小\n"
        "只要你有產品、有技術、有口味\n"
        "我們就有平台、有舞台、有後台\n\n"
        "請問需要:\n"
        "回覆「諮詢」聊聊你的品牌\n"
        "回覆「500」聽生圖方案\n"
        "回覆「行銷」聽客製方案\n"
        "回覆「進度」查已合作案件\n"
        "回覆「客服」找人工小編"
    )


# ══════════════════════════════════════════════
# 路由(優先級從上到下)
# ══════════════════════════════════════════════

def route(text: str) -> str:

    # 0-A. 十題回答偵測(最高優先)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    numbered = sum(1 for l in lines if l[0].isdigit()) if lines else 0
    if len(lines) >= 5 and numbered >= 3:
        return REPLY_RECEIVED_FORM

    # 0-B. 開始生圖
    if _has_any(text, KW_START_IMAGE):
        return REPLY_TEN_QUESTIONS

    # 1. 送出
    if text == "送出":
        return REPLY_RECEIVED_FORM

    # 2. 客服
    if _has_any(text, KW_CUSTOMER_SERVICE):
        return (
            "客服小編在這\n\n"
            "請直接告訴我你的問題\n"
            "上班時段 09:00-21:00 內會回覆\n\n"
            "若想快速分流:\n"
            "回覆「諮詢」聊新合作\n"
            "回覆「進度」查已合作案件"
        )

    # 3. 預約(在「諮詢」之前)
    if _has_any(text, KW_BOOKING) or text == "3":
        return (
            "好的 約一場 30 分鐘免費諮詢\n\n"
            "請告訴我:\n"
            "1. 你的店做什麼產品\n"
            "2. 目前最大的卡點\n"
            "3. 方便諮詢的時段(平日晚上 / 假日)\n\n"
            "看過後私訊給你具體時間"
        )

    # 4. 500 生圖
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

    # 5. 客製行銷
    if _has_any(text, KW_PRODUCT_2) or text == "2":
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

    # 6. 服務諮詢
    if _has_any(text, KW_INQUIRY):
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

    # 7. 進度
    if _has_any(text, KW_PROGRESS):
        return (
            "想查已合作案件進度\n"
            "請提供:\n"
            "1. 你的姓名或商號\n"
            "2. 案件大致開始日期\n\n"
            "立刻找專員回覆你"
        )

    # 8. 感謝
    if _has_any(text, KW_THANKS):
        return (
            "不客氣 有任何問題隨時問\n\n"
            "回覆「諮詢」聊品牌\n"
            "回覆「客服」找人工小編"
        )

    # 9. 預設
    return _menu()
