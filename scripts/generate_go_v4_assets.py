#!/usr/bin/env python3
"""Generate deterministic raster assets for the XUEYI SWITCHBOARD release."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "go-v4"

COLORS = {
    "background": "#0A0A0A",
    "panel": "#161616",
    "text": "#F5F5F5",
    "muted": "#A8A8A8",
    "gold": "#D4AF37",
    "line": "#2A2A2A",
}

FONT_CJK = Path("/System/Library/Fonts/STHeiti Medium.ttc")
FONT_LATIN = Path("/System/Library/Fonts/HelveticaNeue.ttc")


def font(size: int, *, latin: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_LATIN if latin else FONT_CJK
    if not path.is_file():
        raise FileNotFoundError(f"required system font not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def draw_og_card() -> Path:
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, width, 8), fill=COLORS["gold"])
    draw.rounded_rectangle(
        (54, 45, 1146, 585),
        radius=30,
        fill=COLORS["panel"],
        outline=COLORS["line"],
        width=2,
    )

    draw.text((86, 76), "XUEYI SWITCHBOARD", font=font(22, latin=True), fill=COLORS["gold"])
    draw.text((86, 112), "學誼接線台", font=font(31), fill=COLORS["text"])

    draw.rounded_rectangle((86, 178, 344, 226), radius=24, fill=COLORS["gold"])
    draw.text((108, 187), "7 個第一次，免費", font=font(24), fill=COLORS["background"])

    draw.text((86, 258), "你卡住的那件事，", font=font(54), fill=COLORS["text"])
    draw.text((86, 334), "我先免費幫你解第一步。", font=font(54), fill=COLORS["text"])
    draw.text(
        (88, 426),
        "選一個情境，30 秒帶你到正確入口。",
        font=font(26),
        fill=COLORS["muted"],
    )

    draw.text((86, 514), "popmonster.vip/go", font=font(25, latin=True), fill=COLORS["gold"])
    draw.text((395, 515), "7 項免費服務  +  POP 汽美本業", font=font(23), fill=COLORS["muted"])

    track_x = 1072
    track_top = 144
    track_bottom = 480
    draw.line((track_x, track_top, track_x, track_bottom), fill=COLORS["line"], width=4)
    node_specs = (
        (track_top, "01"),
        ((track_top + track_bottom) // 2, "02"),
        (track_bottom, "03"),
    )
    for index, (y, label) in enumerate(node_specs):
        radius = 17 if index == 0 else 13
        fill = COLORS["gold"] if index == 0 else COLORS["background"]
        draw.ellipse(
            (track_x - radius, y - radius, track_x + radius, y + radius),
            fill=fill,
            outline=COLORS["gold"],
            width=3,
        )
        label_box = draw.textbbox((0, 0), label, font=font(12, latin=True))
        label_width = label_box[2] - label_box[0]
        draw.text(
            (track_x - label_width / 2, y - 7),
            label,
            font=font(12, latin=True),
            fill=COLORS["background"] if index == 0 else COLORS["gold"],
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "go-og-1200x630.png"
    image.save(target, format="PNG", optimize=True)
    return target


def main() -> None:
    target = draw_og_card()
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
