"""
3Q貢丸 Rich Menu 設定腳本 v2

修正:
  1. 「設為預設」POST 帶 data=b"",避免某些 Python 版本誤判為 GET
  2. 找不到圖片時 sys.exit(1) 中止,避免上線空白選單
  3. 開頭自動清理舊 Rich Menu,避免堆積到 1000 上限

使用方式:
  python setup_richmenu.py

前置條件:
  1. .env 已填好 LINE_CHANNEL_ACCESS_TOKEN
  2. assets/rich-menu-2500x1686.png 存在
"""

import os, sys, json, urllib.request
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
if not TOKEN:
    print("❌ 找不到 LINE_CHANNEL_ACCESS_TOKEN,請確認 .env 已填好")
    sys.exit(1)

BASE = "https://api.line.me/v2/bot"
DATA_BASE = "https://api-data.line.me/v2/bot"
IMG_PATH = os.path.join(os.path.dirname(__file__), "assets", "rich-menu-2500x1686.png")
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


# ── 通用工具 ──────────────────────────────────

def _request(url, method, headers=None, data=None):
    """統一 request 處理"""
    h = dict(AUTH_HEADERS)
    if headers:
        h.update(headers)
    # 確保 POST 一律帶 body(即使是空的)
    body = data if data is not None else (b"" if method == "POST" else None)
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(req)
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"❌ API {method} {url} 失敗 {e.code}: {err_body}")
        sys.exit(1)


def api_get(path):
    _, body = _request(f"{BASE}{path}", "GET")
    return body


def api_post_json(path, data):
    body = json.dumps(data).encode()
    _, ret = _request(
        f"{BASE}{path}", "POST",
        headers={"Content-Type": "application/json"},
        data=body,
    )
    return ret


def api_post_empty(path):
    """設定類 POST(無 body),修正版帶 data=b''"""
    status, _ = _request(f"{BASE}{path}", "POST")
    return status


def api_delete(path):
    status, _ = _request(f"{BASE}{path}", "DELETE")
    return status


def api_upload_image(menu_id, img_data):
    url = f"{DATA_BASE}/richmenu/{menu_id}/content"
    status, _ = _request(
        url, "POST",
        headers={"Content-Type": "image/png"},
        data=img_data,
    )
    return status


# ── 主流程 ──────────────────────────────────

def main():
    print("🔨 3Q貢丸 Rich Menu 設定 v2\n")

    # 0. 前置檢查 — 圖片必須存在
    if not os.path.exists(IMG_PATH):
        print(f"❌ 找不到 {IMG_PATH}")
        print("  請先確認 assets/rich-menu-2500x1686.png 存在再執行")
        print("  避免上線一個沒有圖片的空白選單")
        sys.exit(1)
    print(f"[0/4] 圖片檢查 ✅ {IMG_PATH}")

    # 1. 清理舊 Rich Menu(避免堆積到 1000 上限)
    print("[1/4] 清理舊 Rich Menu...")
    existing = api_get("/richmenu/list")
    menus = existing.get("richmenus", [])
    if menus:
        for m in menus:
            mid = m.get("richMenuId")
            name = m.get("name", "(unnamed)")
            api_delete(f"/richmenu/{mid}")
            print(f"  ✅ 已刪除舊選單: {name} ({mid[:12]}...)")
    else:
        print("  (無舊選單需清理)")

    # 2. 建立 Rich Menu 結構
    print("[2/4] 建立新 Rich Menu 結構...")
    W, H = 2500, 1686
    cw, ch = W // 3, H // 2
    keywords = ["諮詢", "500", "行銷", "進度", "客服", "約諮詢"]

    areas = []
    # NOTE: 若未來改欄數(例如改成 4 欄),同步改 col == 2 為 col == (cols - 1)
    cols = 3
    for idx, kw in enumerate(keywords):
        col = idx % cols
        row = idx // cols
        # 最右欄補餘數,避免 width 加總不等於 W
        width = (W - col * cw) if col == (cols - 1) else cw
        areas.append({
            "bounds": {"x": col * cw, "y": row * ch, "width": width, "height": ch},
            "action": {"type": "message", "text": kw},
        })

    menu_body = {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": "3Q貢丸主選單v2",
        "chatBarText": "📋 選單",
        "areas": areas,
    }

    result = api_post_json("/richmenu", menu_body)
    menu_id = result.get("richMenuId")
    print(f"  ✅ Rich Menu ID: {menu_id}")

    # 3. 上傳圖片
    print("[3/4] 上傳 Rich Menu 圖片...")
    with open(IMG_PATH, "rb") as f:
        img_data = f.read()
    api_upload_image(menu_id, img_data)
    print(f"  ✅ 圖片上傳完成({len(img_data)//1024} KB)")

    # 4. 設為預設(POST 帶 data=b"" 避免被誤判為 GET)
    print("[4/4] 設為所有使用者的預設 Rich Menu...")
    api_post_empty(f"/user/all/richmenu/{menu_id}")
    print("  ✅ 已設為預設 Rich Menu")

    print(f"\n✅ 全部完成!")
    print(f"Rich Menu ID: {menu_id}")
    print(f"LINE 使用者打開對話即可看到底部六格選單")


if __name__ == "__main__":
    main()
