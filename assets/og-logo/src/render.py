#!/usr/bin/env python3
"""首頁分享預覽圖（商標版）渲染。
用法：python3 render.py（在本目錄執行）
輸出：img/og/og-logo-1200x630.jpg（正本）＋ 根目錄 og-image-1200x630.png（舊網址改放同一張）"""
import io
import pathlib
from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

SRC = pathlib.Path(__file__).resolve().parent
ROOT = SRC.parents[2]

# 1) 商標底圖：500px 原檔去掉 1px 金褐邊框 → 放大到本體約 470px 高（1.237 倍）→ 輕微銳化補回放大的軟
src = Image.open(SRC / "logo-avatar-500-source.png").convert("RGB")
size = round(498 * 470 / 380)
mark = src.crop((1, 1, 499, 499)).resize((size, size), Image.LANCZOS)
mark = mark.filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
mark.save(SRC / f"logo-mark-{size}.png")

# 2) 排版：render.html（商標 screen 疊在 #0a0a0a 上＋左右下角小字）

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto((SRC / "render.html").as_uri())
    page.evaluate("document.fonts.ready.then(() => {})")
    page.wait_for_function("document.fonts.status === 'loaded'", timeout=30000)
    page.wait_for_timeout(800)
    png = page.locator("#capture").screenshot()
    browser.close()

im = Image.open(io.BytesIO(png)).convert("RGB")
assert im.size == (1200, 630), im.size
jpg = ROOT / "img" / "og" / "og-logo-1200x630.jpg"
jpg.parent.mkdir(parents=True, exist_ok=True)
im.save(jpg, "JPEG", quality=92, optimize=True, progressive=True, subsampling=0)
legacy = ROOT / "og-image-1200x630.png"
im.save(legacy, "PNG", optimize=True)
for f in (jpg, legacy):
    print(f"{f.relative_to(ROOT)}  {f.stat().st_size / 1024:.0f} KB")
