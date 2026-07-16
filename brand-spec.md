# POP MONSTER homepage brand spec

## Positioning

- Subject: 台灣汽車美容產品與施工選品。
- Audience: 手洗車主、DIY 玩家與專業汽美施工店。
- Homepage job: 讓訪客在 10 秒內先選「要解決的施工任務」，再進到正確商品或 LINE 選品協助。
- Narrative role: 首屏是選品入口，不是品牌自我介紹。
- Viewing distance: 390px 手機優先，並支援 768px 平板與 1440px 桌面。
- Visual temperature: 沉著、精準、帶實驗室與工坊質感；不做電競霓虹或通用 AI gradient。
- Capacity check: 首屏維持一個主張、兩個 CTA、一張真實產品圖；完整商品密度放到目錄區。

## Design decisions

- Anchor: custom —「台灣汽美配方實驗室 × 職人選品牆」。
- Signature: 「施工任務軌道」；以一條可掃讀的技術軌道把清潔、研磨、鍍膜、耗材、護理導向既有商品分類。
- Palette:
  - Carbon `#080908` — page background.
  - Furnace `#121310` — raised surface.
  - Warm ivory `#F2E9D7` — primary text.
  - Brass `#C8A96B` — sole homepage accent.
  - Muted sand `#A89E8E` — secondary text.
  - Hairline `rgba(200, 169, 107, .18)` — structure.
- Typography:
  - Display: Apple-local `Iowan Old Style` / `Songti TC` stack, restrained to hero and section theses.
  - Body: Apple system / `PingFang TC` stack.
  - Utility/SKU: `ui-monospace`, compact uppercase tracking.
  - Performance rule: homepage typography must not depend on a render-blocking remote font request.
- Spacing: 4px base; primary rhythm 12 / 16 / 24 / 32 / 48 / 72 / 96.
- Radius: 2px controls, 12px internal surfaces, 24px hero/product media; no uniform pill-card system.
- Shadow: one warm, low-opacity product shadow; hierarchy comes mainly from borders and spacing.
- Motion: 220–420ms, `cubic-bezier(.22,1,.36,1)`; no continuous shimmer; `prefers-reduced-motion` disables non-essential motion.

## Real assets

- Repository brand mark: `favicon.svg`.
- Hero / featured product: `img/a001-main.jpg` with responsive source `img/a001-main-480.jpg`.
- Product catalogue assets: existing `img/a*-main.jpg` files only; no hotlinks or synthetic silhouettes.
- Social preview: `og-image-1200x630.png`.

## Copy and trust rules

- Keep verified product/category facts from the repository.
- Do not publish absolute safety claims such as「零風險」「零不可逆傷害」「0 殘留風險」。
- Replace stale marketplace vanity numbers with site-verifiable facts unless re-verified live.
- CTA names describe the result:「依施工任務選」「直接看 32 款商品」「LINE 選品協助」。

## Release boundary

This specification authorizes a local deploy-ready preview only. Push, merge, Cloudflare/GitHub Pages deployment, and other customer-visible publication require owner review.
