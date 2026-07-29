#!/usr/bin/env python3
"""Generate nine source-aware social cards and static OG redirect wrappers."""

from __future__ import annotations

import html
import json
from pathlib import Path

from PIL import Image, ImageDraw

from generate_go_v4_assets import font, save_png


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "go-v4" / "experiments"
SHARE_DIR = ROOT / "share"
WIDTH, HEIGHT = 1200, 630

VARIANTS = {
    "free-first": {
        "label": "A · 免費第一步",
        "headline": ("先拿一個", "免費第一步。"),
        "description": "先把問題分清楚，再決定要不要往下做。",
        "title": "先拿一個免費第一步，再決定要不要往下做。",
        "accent": "#2C67FF",
    },
    "dont-pay": {
        "label": "B · 別急著花錢",
        "headline": ("你卡住的那件事，", "第一步先別急著花錢。"),
        "description": "生意、網站、風險、出國、汽美，先接到正確入口。",
        "title": "你卡住的那件事，第一步先別急著花錢。",
        "accent": "#FF5A43",
    },
    "connect": {
        "label": "C · 我幫你接線",
        "headline": ("你先說卡在哪，", "我幫你接到正確第一步。"),
        "description": "不用先懂服務名稱，從你的問題開始。",
        "title": "你先說卡在哪，我幫你接到正確第一步。",
        "accent": "#F4C969",
    },
}

PLATFORMS = {
    "facebook": {
        "label": "FACEBOOK 版",
        "accent": "#1877F2",
        "description": "10 個免費入口＋POP 汽美選品，先看清楚能拿到什麼。",
    },
    "line": {
        "label": "LINE 版",
        "accent": "#06C755",
        "description": "回一句你卡在哪，我幫你找到免費第一步。",
    },
    "threads": {
        "label": "THREADS 版",
        "accent": "#F5F5F5",
        "description": "不急著推銷，先聊你現在卡住的那一步。",
    },
}

ROUTES = ("生意與內容", "網站與店家", "簽約與避雷", "旅行規劃", "汽美與耗材")


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, **kwargs) -> None:
    draw.rounded_rectangle(box, radius=radius, **kwargs)


def base_canvas(platform: str, variant: dict[str, str]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#071426")
    draw = ImageDraw.Draw(image)
    accent = variant["accent"]
    platform_accent = PLATFORMS[platform]["accent"]

    for y in range(HEIGHT):
        ratio = y / HEIGHT
        shade = (
            round(7 + 8 * ratio),
            round(20 + 14 * ratio),
            round(38 + 20 * ratio),
        )
        draw.line((0, y, WIDTH, y), fill=shade)
    for x in range(0, WIDTH, 52):
        draw.line((x, 0, x, HEIGHT), fill="#102A49", width=1)
    for y in range(0, HEIGHT, 52):
        draw.line((0, y, WIDTH, y), fill="#102A49", width=1)

    draw.ellipse((970, -170, 1320, 180), fill=platform_accent)
    draw.ellipse((-150, 500, 170, 820), fill=accent)
    rounded(draw, (44, 38, 1156, 592), 38, fill="#071426", outline="#294865", width=2)
    return image, draw


def draw_header(draw: ImageDraw.ImageDraw, platform: str, variant: dict[str, str]) -> None:
    platform_spec = PLATFORMS[platform]
    rounded(draw, (72, 66, 116, 110), 12, fill=variant["accent"])
    draw.text((84, 70), "P", font=font(24, latin=True), fill="#071426")
    draw.text((132, 68), "POP 免費接線台", font=font(25), fill="#F7F1E7")
    rounded(draw, (890, 66, 1128, 108), 21, fill="#102642", outline=platform_spec["accent"], width=2)
    draw.text((914, 76), platform_spec["label"], font=font(16), fill="#F7F1E7")
    rounded(draw, (72, 132, 310, 174), 21, fill="#102642", outline=variant["accent"], width=2)
    draw.text((94, 141), variant["label"], font=font(18), fill="#F7F1E7")


def draw_facebook(draw: ImageDraw.ImageDraw, variant: dict[str, str]) -> None:
    draw_header(draw, "facebook", variant)
    draw.text((72, 214), variant["headline"][0], font=font(48), fill="#F7F1E7")
    draw.text((72, 276), variant["headline"][1], font=font(48), fill="#F7F1E7")
    draw.text((72, 352), variant["description"], font=font(23), fill="#C7D2DF")
    rounded(draw, (72, 420, 348, 472), 26, fill=variant["accent"])
    draw.text((98, 431), "打開，先把問題分清楚", font=font(19), fill="#071426")
    draw.text((72, 516), "popmonster.vip/go", font=font(20, latin=True), fill="#F4C969")

    rounded(draw, (748, 142, 1128, 538), 28, fill="#F7F1E7")
    draw.text((782, 172), "5 條服務線", font=font(25), fill="#071426")
    draw.text((1002, 177), "11 入口", font=font(15), fill="#42556B")
    for index, route in enumerate(ROUTES, start=1):
        y = 232 + (index - 1) * 56
        rounded(draw, (780, y, 826, y + 40), 13, fill="#071426")
        draw.text((793, y + 8), f"{index:02}", font=font(14, latin=True), fill=variant["accent"])
        draw.text((848, y + 6), route, font=font(19), fill="#071426")
        draw.line((848, y + 39, 1094, y + 39), fill="#CDD5DE", width=2)


def draw_line(draw: ImageDraw.ImageDraw, variant: dict[str, str]) -> None:
    draw_header(draw, "line", variant)
    rounded(draw, (74, 205, 770, 438), 34, fill="#F7F1E7")
    draw.polygon(((114, 438), (154, 438), (104, 478)), fill="#F7F1E7")
    draw.text((112, 244), variant["headline"][0], font=font(49), fill="#071426")
    draw.text((112, 306), variant["headline"][1], font=font(49), fill="#071426")
    draw.text((112, 382), "回一句就好：我現在卡在＿＿＿", font=font(22), fill="#3D536B")

    rounded(draw, (824, 204, 1106, 438), 32, fill="#0E2A28", outline="#06C755", width=3)
    draw.text((858, 236), "不用先選服務", font=font(25), fill="#F7F1E7")
    draw.text((858, 286), "我幫你接線", font=font(34), fill="#06C755")
    draw.line((858, 344, 1072, 344), fill="#376A63", width=2)
    draw.text((858, 365), "資料先遮蔽", font=font(18), fill="#C7D2DF")
    draw.text((858, 398), "免費範圍先說", font=font(18), fill="#C7D2DF")
    draw.text((74, 522), "popmonster.vip/go", font=font(20, latin=True), fill="#F4C969")


def draw_threads(draw: ImageDraw.ImageDraw, variant: dict[str, str]) -> None:
    draw_header(draw, "threads", variant)
    draw.line((142, 214, 142, 482), fill="#6E7D90", width=4)
    for y, color in ((230, "#F5F5F5"), (354, variant["accent"]), (474, "#F5F5F5")):
        draw.ellipse((122, y - 20, 162, y + 20), fill="#071426", outline=color, width=4)
    draw.text((190, 204), "你：我卡住了，但不想先買錯。", font=font(29), fill="#F7F1E7")
    draw.text((190, 330), variant["headline"][0], font=font(42), fill="#F7F1E7")
    draw.text((190, 382), variant["headline"][1], font=font(42), fill=variant["accent"])
    draw.text((190, 464), "POP：先分清楚，再決定下一步。", font=font(27), fill="#C7D2DF")
    rounded(draw, (810, 504, 1128, 550), 23, fill="#F5F5F5")
    draw.text((842, 515), "同一入口，從問題開始 →", font=font(18), fill="#071426")
    draw.text((72, 524), "popmonster.vip/go", font=font(19, latin=True), fill="#F4C969")


def render_card(platform: str, variant_name: str, variant: dict[str, str]) -> Path:
    image, draw = base_canvas(platform, variant)
    {"facebook": draw_facebook, "line": draw_line, "threads": draw_threads}[platform](draw, variant)
    return save_png(image, ASSET_DIR / f"go-{platform}-{variant_name}-1200x630.png")


def wrapper_html(entry: dict[str, object]) -> str:
    title = html.escape(str(entry["title"]), quote=True)
    description = html.escape(str(entry["description"]), quote=True)
    url = html.escape(str(entry["url"]), quote=True)
    image_url = html.escape(f'https://popmonster.vip/{entry["image"]}', quote=True)
    destination = html.escape(str(entry["destination"]), quote=True)
    return f"""<!doctype html>
<html lang="zh-Hant-TW">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="noindex,follow">
  <link rel="canonical" href="https://popmonster.vip/go">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="zh_TW">
  <meta property="og:site_name" content="POP MONSTER">
  <meta property="og:url" content="{url}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="{image_url}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{image_url}">
</head>
<body>
  <p>正在前往 <a href="{destination}">POP 免費接線台</a>…</p>
  <script>location.replace({json.dumps(str(entry["destination"]), ensure_ascii=False)});</script>
</body>
</html>
"""


def build_campaign() -> list[dict[str, object]]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    for platform, platform_spec in PLATFORMS.items():
        for variant_name, variant in VARIANTS.items():
            source = f"{platform}-{variant_name}"
            image_path = render_card(platform, variant_name, variant)
            wrapper_name = f"go-{platform}-{variant_name}.html"
            entry: dict[str, object] = {
                "platform": platform,
                "variant": variant_name,
                "source": source,
                "title": variant["title"],
                "description": platform_spec["description"],
                "image": image_path.relative_to(ROOT).as_posix(),
                "wrapper": f"share/{wrapper_name}",
                "url": f"https://popmonster.vip/share/{wrapper_name}",
                "destination": f"https://popmonster.vip/go?src={source}",
                "width": WIDTH,
                "height": HEIGHT,
            }
            (SHARE_DIR / wrapper_name).write_text(wrapper_html(entry), encoding="utf-8")
            entries.append(entry)

    (ASSET_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "version": "2026-07-29",
                "canonical": "https://popmonster.vip/go",
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return entries


if __name__ == "__main__":
    generated = build_campaign()
    print(f"generated {len(generated)} share cards and wrappers")
