#!/usr/bin/env python3
"""渲染 /go 通用分享卡（1200×630）。

用法：python3 assets/go-v4/src/render-og-universal.py [--out 目錄]

除了輸出 PNG，還會把「機器量到的」版面數字印出來——截圖可能是過期或凍結的，
getBoundingClientRect 與 getComputedStyle 是第二個證據源，兩者對不上時信後者。
同時輸出 340px 縮圖：FB 手機動態消息的預覽卡大約就是這個寬度，
主標在那個尺寸讀不到的話，這張卡等於沒有鉤子。
"""

import argparse
import json
import pathlib
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright

SRC = pathlib.Path(__file__).resolve().parent
DEFAULT_OUT = SRC.parent
WIDTH, HEIGHT = 1200, 630

MEASURE = """() => {
  const px = (el) => {
    const r = el.getBoundingClientRect();
    return {top: Math.round(r.top), left: Math.round(r.left),
            right: Math.round(r.right), bottom: Math.round(r.bottom),
            w: Math.round(r.width), h: Math.round(r.height)};
  };
  const cs = (el, props) => Object.fromEntries(
    props.map((p) => [p, getComputedStyle(el)[p]]));
  const card = document.getElementById('capture');
  const head = document.getElementById('headline');
  const dek  = document.getElementById('dek');
  const sheet0 = document.querySelector('.sheet');
  const sheet = sheet0;
  const last = sheet0.lastElementChild;

  // 逐行量主標，確認中文沒有撞行
  const lines = [];
  const range = document.createRange();
  for (const node of head.childNodes) {
    if (node.nodeType === 3 && node.textContent.trim()) {
      range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        lines.push({top: Math.round(r.top), bottom: Math.round(r.bottom),
                    h: Math.round(r.height), text: node.textContent.trim()});
      }
    }
  }
  // 中文撞行不能用 client rect 的框重疊來判——CJK 字的 em box 常比 line-height 高，
  // 框重疊了字未必真的撞到。改量「相鄰行基線距離 ÷ 字級」，低於 1.02 才算真的會撞。
  const tops = [...new Set(lines.map((l) => l.top))].sort((a, b) => a - b);
  const fs = parseFloat(getComputedStyle(head).fontSize);
  let tightest = Infinity;
  for (let i = 1; i < tops.length; i++) {
    tightest = Math.min(tightest, (tops[i] - tops[i - 1]) / fs);
  }
  const overlap = (tops.length > 1 && tightest < 1.02) ? 1 : 0;

  return {
    card: px(card),
    overflowX: card.scrollWidth - card.clientWidth,
    overflowY: card.scrollHeight - card.clientHeight,
    headline: {...px(head), ...cs(head, ['fontFamily', 'fontSize', 'lineHeight', 'letterSpacing', 'color'])},
    headlineLines: lines.map((l) => l.text),
    headlineLineRatio: Number.isFinite(tightest) ? Number(tightest.toFixed(3)) : null,
    headlineLineOverlaps: overlap,
    dek: {...px(dek), ...cs(dek, ['fontFamily', 'fontSize', 'lineHeight'])},
    last: {tag: last.className || last.tagName, ...px(last)},
    sheetOverflowY: sheet.scrollHeight - sheet.clientHeight,
    // 被 flex-shrink 壓扁的元素：CSS 寫了高度、實際卻更矮
    squashed: [...sheet.children].filter((el) => {
      const want = parseFloat(getComputedStyle(el).height);
      return want > 0 && el.getBoundingClientRect().height < want - 0.5;
    }).map((el) => el.className || el.tagName),
    sheetBottomGap: Math.round(
      sheet.getBoundingClientRect().bottom
      - parseFloat(getComputedStyle(sheet).paddingBottom)
      - last.getBoundingClientRect().bottom),
  };
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--name", default="go-og-universal-1200x630")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    src = SRC / "render-og-universal.html"

    # 本 repo 位在 ~/Documents（iCloud）底下，瀏覽器沒有該目錄的 TCC 授權，
    # 直接 file:// 進去會整個掛住到逾時（不是報錯，是靜默卡死）。先複製到系統暫存再讀。
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="og-render-"))
    staged = tmp / src.name
    shutil.copy2(src, staged)
    src = staged

    with sync_playwright() as p:
        # 用 playwright 自帶的 chromium（跑 `python3 -m playwright install chromium` 裝一次）。
        # 不用系統 Chrome：它會跟本機瀏覽器搶 profile 而整個掛住，實測會卡到逾時。
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="chrome")
        ctx = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        page = ctx.new_page()
        page.goto(src.as_uri())
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=30000)
        page.wait_for_timeout(600)

        measured = page.evaluate(MEASURE)
        print(json.dumps(measured, ensure_ascii=False, indent=2))

        png = out_dir / f"{args.name}.png"
        page.locator("#capture").screenshot(path=str(png))
        print(f"\n→ {png}  ({png.stat().st_size / 1024:.0f} KB)")

        # 交付檔走 JPEG：滿版顆粒讓每個像素都不一樣，PNG 壓不動（實測 967 KB）。
        # q92 + subsampling=0（4:4:4）＝ 141 KB，且中文與金色字邊緣不糊——
        # 色度抽樣一開，細筆畫的中文字馬上出現彩邊，這個參數不能省。
        from PIL import Image
        jpg = out_dir / f"{args.name}.jpg"
        Image.open(png).convert("RGB").save(
            jpg, "JPEG", quality=92, optimize=True, progressive=True, subsampling=0)
        print(f"→ {jpg}  ({jpg.stat().st_size / 1024:.0f} KB)  ← 這個才是要上線的")

        # FB 手機動態消息的預覽卡大約 340px 寬：主標在這個尺寸讀不到就等於沒有鉤子
        small = out_dir / f"{args.name}-340.jpg"
        im = Image.open(png).convert("RGB")
        im.resize((340, round(340 * HEIGHT / WIDTH)), Image.LANCZOS).save(
            small, "JPEG", quality=90, optimize=True)
        print(f"→ {small}  （動態消息尺寸自檢用）")

        ctx.close()
        browser.close()
    shutil.rmtree(tmp, ignore_errors=True)

    # 機械閘：字撞行、破版、底部溢出，任一中了就非零離開，不讓壞圖悄悄過關
    problems = []
    if measured["headlineLineOverlaps"]:
        problems.append(f"主標撞行 {measured['headlineLineOverlaps']} 處")
    if measured["overflowX"] or measured["overflowY"]:
        problems.append(f"版面溢出 x={measured['overflowX']} y={measured['overflowY']}")
    if measured["sheetBottomGap"] < 0:
        problems.append(f"最後一層（{measured['last']['tag']}）撐出版心 {-measured['sheetBottomGap']}px")
    if measured["sheetOverflowY"] > 0:
        problems.append(f"版心內容溢出 {measured['sheetOverflowY']}px")
    if measured["squashed"]:
        problems.append("被 flex 壓扁的元素：" + "、".join(measured["squashed"]))
    if measured["card"]["w"] != WIDTH or measured["card"]["h"] != HEIGHT:
        problems.append(f"畫布尺寸不是 {WIDTH}x{HEIGHT}")
    if problems:
        print("\n❌ " + "；".join(problems), file=sys.stderr)
        return 1
    print("\n✅ 機械閘全過：無撞行、無溢出、尺寸正確")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
