#!/usr/bin/env python3
"""Generate deterministic web, QR, social, and print assets for v4."""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import qrcode
from qrcode.constants import ERROR_CORRECT_Q


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

QR_PAYLOADS = {
    "business-card": "https://popmonster.vip/go?src=business-card",
    "package-insert": "https://popmonster.vip/go?src=package-insert",
    "social": "https://popmonster.vip/go?src=social",
}

DPI = 300


def font(size: int, *, latin: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_LATIN if latin else FONT_CJK
    if not path.is_file():
        raise FileNotFoundError(f"required system font not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def mm_to_px(value: float) -> int:
    return round(value / 25.4 * DPI)


def draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    *,
    canvas_width: int,
    font_value: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    box = draw.textbbox((0, 0), text, font=font_value)
    width = box[2] - box[0]
    draw.text(((canvas_width - width) / 2, y), text, font=font_value, fill=fill)


def save_png(image: Image.Image, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(target, format="PNG", optimize=True)
    return target


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    return save_png(image, OUTPUT / "go-og-1200x630.png")


def draw_qr_assets() -> dict[str, dict[str, str]]:
    qr_dir = OUTPUT / "qr"
    qr_dir.mkdir(parents=True, exist_ok=True)
    manifest_assets: dict[str, dict[str, str]] = {}

    for name, url in QR_PAYLOADS.items():
        code = qrcode.QRCode(
            version=4,
            error_correction=ERROR_CORRECT_Q,
            box_size=40,
            border=4,
        )
        code.add_data(url)
        code.make(fit=False)
        if code.modules_count != 33:
            raise AssertionError(f"unexpected QR data matrix: {code.modules_count}")

        matrix = code.get_matrix()
        if len(matrix) != 41 or any(len(row) != 41 for row in matrix):
            raise AssertionError("QR matrix must be 41 x 41 including quiet zone")

        prefix = f"go-{name}"
        png_name = f"{prefix}-1640.png"
        svg_name = f"{prefix}.svg"
        png_path = qr_dir / png_name
        svg_path = qr_dir / svg_name

        png = code.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGB")
        if png.size != (1640, 1640):
            raise AssertionError(f"unexpected QR PNG size: {png.size}")
        png.save(png_path, format="PNG", optimize=True)

        path_commands = []
        for y, row in enumerate(matrix):
            for x, dark in enumerate(row):
                if dark:
                    path_commands.append(f"M{x} {y}h1v1h-1z")
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 41 41" '
            'width="41mm" height="41mm" shape-rendering="crispEdges" '
            f'aria-label="QR code for {url}">\n'
            '  <rect width="41" height="41" fill="#fff"/>\n'
            f'  <path d="{"".join(path_commands)}" fill="#000"/>\n'
            '</svg>\n'
        )
        svg_path.write_text(svg, encoding="utf-8")

        manifest_assets[name] = {
            "url": url,
            "svg": svg_name,
            "png": png_name,
            "svg_sha256": sha256(svg_path),
            "png_sha256": sha256(png_path),
        }

    manifest = {
        "qr_version": 4,
        "error_correction": "Q",
        "data_modules": 33,
        "quiet_zone_modules": 4,
        "matrix_modules": 41,
        "png_pixels": 1640,
        "pixels_per_module": 40,
        "assets": manifest_assets,
    }
    (qr_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_assets


def load_qr(name: str, size: int) -> Image.Image:
    source = OUTPUT / "qr" / f"go-{name}-1640.png"
    return Image.open(source).convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def draw_story() -> Path:
    width, height = 1080, 1920
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 12), fill=COLORS["gold"])
    draw.rounded_rectangle((48, 52, 1032, 1868), radius=38, fill=COLORS["panel"], outline=COLORS["line"], width=3)
    draw.text((84, 92), "XUEYI SWITCHBOARD", font=font(26, latin=True), fill=COLORS["gold"])
    draw.text((84, 137), "學誼接線台", font=font(42), fill=COLORS["text"])
    draw.rounded_rectangle((84, 248, 390, 308), radius=30, fill=COLORS["gold"])
    draw.text((111, 258), "7 個第一次，免費", font=font(29), fill=COLORS["background"])
    draw.text((84, 390), "你卡住的那件事，", font=font(67), fill=COLORS["text"])
    draw.text((84, 492), "先免費幫你解第一步。", font=font(67), fill=COLORS["text"])
    draw.text((86, 620), "選一個情境，30 秒帶你到正確入口。", font=font(31), fill=COLORS["muted"])
    draw.text((86, 682), "每項免費範圍，先說清楚。", font=font(31), fill=COLORS["muted"])

    qr = load_qr("social", 520)
    image.paste(qr, ((width - 520) // 2, 870))
    draw_centered(draw, "掃碼 30 秒找到正確入口", 1430, canvas_width=width, font_value=font(38), fill=COLORS["text"])
    draw_centered(draw, "7 項免費服務  +  POP 汽美本業", 1502, canvas_width=width, font_value=font(28), fill=COLORS["muted"])
    draw_centered(draw, "popmonster.vip/go", 1735, canvas_width=width, font_value=font(29, latin=True), fill=COLORS["gold"])
    return save_png(image, OUTPUT / "social" / "go-qr-story-1080x1920.png")


def draw_share_card() -> Path:
    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 10), fill=COLORS["gold"])
    draw.rounded_rectangle((52, 52, 1028, 1298), radius=36, fill=COLORS["panel"], outline=COLORS["line"], width=3)
    draw.text((88, 92), "XUEYI SWITCHBOARD", font=font(24, latin=True), fill=COLORS["gold"])
    draw.text((88, 134), "學誼接線台", font=font(38), fill=COLORS["text"])
    draw.rounded_rectangle((88, 238, 372, 294), radius=28, fill=COLORS["gold"])
    draw.text((112, 247), "7 個第一次，免費", font=font(27), fill=COLORS["background"])
    draw.text((88, 370), "你卡住的那件事，", font=font(63), fill=COLORS["text"])
    draw.text((88, 466), "我先免費幫你解第一步。", font=font(63), fill=COLORS["text"])
    draw.text((90, 584), "選一個情境，30 秒帶你到正確入口。", font=font(29), fill=COLORS["muted"])

    qr = load_qr("social", 330)
    image.paste(qr, (650, 780))
    draw.text((88, 796), "掃碼，\n找到你的第一步。", font=font(43), fill=COLORS["text"], spacing=18)
    draw.text((90, 1015), "7 項免費服務\n+ POP 汽美本業", font=font(28), fill=COLORS["muted"], spacing=14)
    draw.text((88, 1196), "popmonster.vip/go", font=font(27, latin=True), fill=COLORS["gold"])
    return save_png(image, OUTPUT / "social" / "go-share-1080x1350.png")


def draw_crop_marks(draw: ImageDraw.ImageDraw, width: int, height: int, inset: int) -> None:
    color = "#777777"
    length = max(14, inset - 8)
    for x in (inset, width - inset):
        draw.line((x, 4, x, length), fill=color, width=1)
        draw.line((x, height - length, x, height - 4), fill=color, width=1)
    for y in (inset, height - inset):
        draw.line((4, y, length, y), fill=color, width=1)
        draw.line((width - length, y, width - 4, y), fill=color, width=1)


def draw_business_card() -> Path:
    width, height = mm_to_px(96), mm_to_px(60)
    inset = mm_to_px(3)
    safe = mm_to_px(5)
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw_crop_marks(draw, width, height, inset)
    draw.rectangle((inset, inset, width - inset, inset + 5), fill=COLORS["gold"])

    left = inset + safe
    draw.text((left, inset + safe), "XUEYI SWITCHBOARD", font=font(18, latin=True), fill=COLORS["gold"])
    draw.text((left, inset + safe + 30), "學誼接線台", font=font(28), fill=COLORS["text"])
    draw.text((left, 220), "你卡住的那件事，", font=font(42), fill=COLORS["text"])
    draw.text((left, 282), "先免費幫你解第一步。", font=font(42), fill=COLORS["text"])
    draw.text((left, 385), "掃碼 30 秒找到正確入口", font=font(24), fill=COLORS["muted"])
    draw.text((left, 512), "popmonster.vip/go", font=font(20, latin=True), fill=COLORS["gold"])

    qr_size = mm_to_px(22)
    qr = load_qr("business-card", qr_size)
    qr_x = width - inset - safe - qr_size
    qr_y = (height - qr_size) // 2
    image.paste(qr, (qr_x, qr_y))
    draw_centered(
        draw,
        "7 項免費 + POP 本業",
        qr_y + qr_size + 18,
        canvas_width=width + (qr_x - (width - qr_x)),
        font_value=font(16),
        fill=COLORS["muted"],
    )
    return save_png(image, OUTPUT / "print" / "go-business-card-back-96x60mm-bleed.png")


def draw_package_insert() -> Path:
    width, height = mm_to_px(106), mm_to_px(154)
    inset = mm_to_px(3)
    safe = mm_to_px(5)
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw_crop_marks(draw, width, height, inset)
    draw.rectangle((inset, inset, width - inset, inset + 7), fill=COLORS["gold"])

    left = inset + safe
    draw.text((left, 92), "XUEYI SWITCHBOARD", font=font(25, latin=True), fill=COLORS["gold"])
    draw.text((left, 136), "學誼接線台", font=font(40), fill=COLORS["text"])
    draw.rounded_rectangle((left, 238, left + 310, 298), radius=30, fill=COLORS["gold"])
    draw.text((left + 27, 248), "7 個第一次，免費", font=font(29), fill=COLORS["background"])
    draw.text((left, 370), "你卡住的那件事，", font=font(62), fill=COLORS["text"])
    draw.text((left, 462), "先免費幫你解第一步。", font=font(62), fill=COLORS["text"])
    draw.text((left, 580), "掃碼 30 秒找到正確入口", font=font(32), fill=COLORS["muted"])

    qr_size = mm_to_px(42)
    qr = load_qr("package-insert", qr_size)
    qr_x = (width - qr_size) // 2
    qr_y = 735
    image.paste(qr, (qr_x, qr_y))
    draw_centered(draw, "7 項免費服務 + POP 汽美本業", 1286, canvas_width=width, font_value=font(31), fill=COLORS["text"])
    draw_centered(draw, "敏感資料先遮蔽｜需要專業資格時協助轉介", 1360, canvas_width=width, font_value=font(23), fill=COLORS["muted"])
    draw_centered(draw, "popmonster.vip/go", 1640, canvas_width=width, font_value=font(25, latin=True), fill=COLORS["gold"])
    return save_png(image, OUTPUT / "print" / "go-package-insert-106x154mm-bleed.png")


def write_print_pdf(
    png_path: Path,
    pdf_path: Path,
    *,
    bleed_mm: tuple[float, float],
    trim_mm: tuple[float, float],
) -> Path:
    try:
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import RectangleObject
    except ImportError as exc:
        raise RuntimeError(
            "reportlab and pypdf are required; use the bundled Codex PDF runtime"
        ) from exc

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = pdf_path.with_suffix(".working.pdf")
    page_width = bleed_mm[0] * mm
    page_height = bleed_mm[1] * mm
    document = canvas.Canvas(
        str(temporary),
        pagesize=(page_width, page_height),
        pageCompression=1,
        invariant=1,
    )
    document.setTitle("XUEYI SWITCHBOARD print artwork")
    document.drawImage(
        str(png_path),
        0,
        0,
        width=page_width,
        height=page_height,
        preserveAspectRatio=False,
        mask="auto",
    )
    document.showPage()
    document.save()

    reader = PdfReader(str(temporary))
    page = reader.pages[0]
    full_box = RectangleObject([0, 0, page_width, page_height])
    trim_left = (bleed_mm[0] - trim_mm[0]) / 2 * mm
    trim_bottom = (bleed_mm[1] - trim_mm[1]) / 2 * mm
    trim_box = RectangleObject(
        [
            trim_left,
            trim_bottom,
            trim_left + trim_mm[0] * mm,
            trim_bottom + trim_mm[1] * mm,
        ]
    )
    page.mediabox = full_box
    page.cropbox = full_box
    page.bleedbox = full_box
    page.trimbox = trim_box

    writer = PdfWriter()
    writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": "XUEYI SWITCHBOARD print artwork",
            "/Subject": "300 DPI proof with 3 mm bleed and explicit TrimBox",
        }
    )
    with pdf_path.open("wb") as stream:
        writer.write(stream)
    temporary.unlink()
    return pdf_path


def draw_delivery_assets() -> list[Path]:
    draw_qr_assets()
    story = draw_story()
    share = draw_share_card()
    business_png = draw_business_card()
    insert_png = draw_package_insert()
    business_pdf = write_print_pdf(
        business_png,
        OUTPUT / "print" / "go-business-card-back-90x54mm.pdf",
        bleed_mm=(96, 60),
        trim_mm=(90, 54),
    )
    insert_pdf = write_print_pdf(
        insert_png,
        OUTPUT / "print" / "go-package-insert-100x148mm.pdf",
        bleed_mm=(106, 154),
        trim_mm=(100, 148),
    )
    return [story, share, business_png, insert_png, business_pdf, insert_pdf]


def main() -> None:
    targets = [draw_og_card(), *draw_delivery_assets()]
    for target in targets:
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
