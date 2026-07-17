#!/usr/bin/env python3
"""品牌圖騰實體物渲染：海報／IG 限動模板／LINE 圖文選單背景。
用法：python3 render.py（在本目錄執行；輸出到上層 assets/brand-totem/）"""
import pathlib
from playwright.sync_api import sync_playwright

SRC = pathlib.Path(__file__).resolve().parent
OUT = SRC.parent

JOBS = [
    # (原始檔, 輸出名, 視窗寬, 視窗高, 縮放倍數列表)
    ("render-poster.html",   "totem-poster",        1080, 1920, [1, 2, 4]),
    ("render-story.html",    "ig-story-template",   1080, 1920, [1, 2]),
    ("render-richmenu.html", "line-rich-menu-bg",   2500, 1686, [1]),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for src, name, w, h, scales in JOBS:
        for scale in scales:
            ctx = browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=scale,
            )
            page = ctx.new_page()
            page.goto((SRC / src).as_uri())
            # 等 Google Fonts 全部到位再拍
            page.evaluate("document.fonts.ready.then(() => {})")
            page.wait_for_function("document.fonts.status === 'loaded'", timeout=30000)
            page.wait_for_timeout(1200)
            out = OUT / f"{name}-{w * scale}x{h * scale}.png"
            page.locator("#capture").screenshot(path=str(out))
            print(f"{out.name}  ({out.stat().st_size / 1024:.0f} KB)")
            ctx.close()
    browser.close()
print("done")
