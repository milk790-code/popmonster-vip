#!/usr/bin/env python3
"""首頁分享預覽圖（商標版）渲染。規格見 ../PROMPT.md
用法：python3 render.py（在哪裡執行都可以）
輸出：img/og/og-badge-1200x630.jpg（正本）
　　　img/og/og-logo-1200x630.jpg、根目錄 og-image-1200x630.png（舊網址，內容換成同一張，平台快取回抓也是徽章）"""
import pathlib
from PIL import Image, ImageDraw

SRC = pathlib.Path(__file__).resolve().parent
ROOT = SRC.parents[2]

W, H = 1200, 630
BG = (10, 10, 10)                       # #0a0a0a 品牌手冊 PURE BLACK
D = 540                                 # 徽章直徑
CX, CY = W / 2, H / 2                   # 圓心放畫面正中

# 原圖（1008×992 黑底）上擬合出的外圈正圓
SRC_CX, SRC_CY, SRC_R = 497.99, 499.02, 476.32
PAD = 4                                 # 圓外多取幾 px，給遮罩抗鋸齒用
MASK_INSET = 0.4                        # 遮罩內縮，避開 JPEG 在灰圈外緣的暗邊
SS = 4                                  # 遮罩超取樣倍數

src = Image.open(SRC / "brand-logo-circle-1008x992.jpg").convert("RGB")

# 1) 等比縮小：取「圓＋PAD」的正方形區域，LANCZOS 一次縮到位（box 用浮點座標，圓心不會偏半格）
n = D + 2 * PAD
half = (n / 2) * SRC_R / (D / 2)
box = (SRC_CX - half, SRC_CY - half, SRC_CX + half, SRC_CY + half)
assert box[0] >= 0 and box[1] >= 0 and box[2] <= src.width and box[3] <= src.height, box
badge = src.resize((n, n), Image.LANCZOS, box=box)

# 2) 圓形遮罩：4 倍大畫實心圓再縮回來 = 抗鋸齒邊
r = D / 2 - MASK_INSET
big = Image.new("L", (n * SS, n * SS), 0)
c = n * SS / 2
ImageDraw.Draw(big).ellipse((c - r * SS, c - r * SS, c + r * SS, c + r * SS), fill=255)
mask = big.resize((n, n), Image.LANCZOS)

# 3) 貼到底色上
canvas = Image.new("RGB", (W, H), BG)
canvas.paste(badge, (round(CX - n / 2), round(CY - n / 2)), mask)

jpg = ROOT / "img" / "og" / "og-badge-1200x630.jpg"
jpg.parent.mkdir(parents=True, exist_ok=True)
# q97：q92 在灰圈外緣會有 12/255 的壓縮振鈴（黑底上看得到一圈髒邊），q97 壓到 5 以內、178 KB
canvas.save(jpg, "JPEG", quality=97, optimize=True, progressive=True, subsampling=0)
old_jpg = ROOT / "img" / "og" / "og-logo-1200x630.jpg"   # 09-28 金羽毛版上線過的網址
old_jpg.write_bytes(jpg.read_bytes())
legacy = ROOT / "og-image-1200x630.png"                  # 3Q貢丸 時期的網址
canvas.save(legacy, "PNG", optimize=True)
for f in (jpg, old_jpg, legacy):
    print(f"{f.relative_to(ROOT)}  {f.stat().st_size / 1024:.0f} KB")
