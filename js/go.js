(function () {
  "use strict";

  const ALLOWED_SOURCES = new Set([
    "direct",
    "business-card",
    "package-insert",
    "social",
    "legacy-worker",
  ]);
  const ALLOWED_SURFACES = new Set([
    "hero",
    "directory",
    "router_result",
    "pop_card",
  ]);
  const EVENT_NAMES = new Set([
    "page_ready",
    "hero_cta",
    "route_stage_1",
    "route_result",
    "line_start",
    "site_start",
    "share_success",
  ]);
  const SESSION_STORAGE_KEY = "switchboard_v5_session_hash";
  const SESSION_HASH_PATTERN = /^[0-9a-f]{64}$/;
  const FB_MATRIX_PATTERN = /^fb-[0-9a-f]{6}$/;
  let memorySessionHash = "";

  const SERVICES = Object.freeze([
    Object.freeze({
      slug: "brand-content",
      category: "business",
      title: "品牌內容",
      hook: "先看改完，再決定要不要做。",
      freeDeliverable: "首屏重寫、單張主標改版、短片前 5 秒重剪，三選一免費樣張。",
      freeScope: "每人一次、一次聚焦一項。",
      outcome: "看一個首屏、單張或短片，指出第一個最該改善的地方。",
      requiredInput: "頁面、單張或短片＋目標。",
      boundary: "先提供一版可比較樣張，不含完整製作與無限修改。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "line",
          label: "把素材傳來，先看一版",
          value: "@121lkspe",
          prefill: "你好，我想領品牌內容免費樣張。我附上素材與目標，目前卡在：",
        }),
      ]),
      icon: "message",
    }),
    Object.freeze({
      slug: "creator-kit",
      category: "business",
      title: "CreatorKit",
      hook: "別再盯著空白頁，21 個 AI 工具直接免費用。",
      freeDeliverable: "文案、腳本或逐字稿第一版，不用先註冊。",
      freeScope: "不用先註冊；實際可用次數與服務狀態以工具當下頁面為準。",
      outcome: "直接使用 21 個文案、腳本與逐字稿工具。",
      requiredInput: "不用先註冊。",
      boundary: "工具成果仍需自行檢查與調整。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "site",
          label: "免費開工具，現在做第一版",
          value: "https://creatorkit.milk790.workers.dev/",
        }),
      ]),
      icon: "document",
    }),
    Object.freeze({
      slug: "rental-check",
      category: "risk",
      title: "租屋風險",
      hook: "簽約前先查一次，比入住後才後悔便宜。",
      freeDeliverable: "地址公開資訊摘要＋簽約前風險快篩卡。",
      freeScope: "每人一次、一個地址或物件。",
      outcome: "整理公開資訊與簽約前風險清單。",
      requiredInput: "地址、物件頁、遮蔽個資的合約。",
      boundary: "公開資訊整理，非權利認證。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "line",
          label: "傳地址，免費領快篩卡",
          value: "@207cpaps",
          prefill: "你好，我想領租屋地段與簽約風險快篩卡。地址／物件頁是：",
        }),
      ]),
      icon: "home",
    }),
    Object.freeze({
      slug: "legal-guidance",
      category: "risk",
      title: "合約事件",
      hook: "事情再亂，我先幫你排成一條看得懂的時間線。",
      freeDeliverable: "事件時間線＋證據缺口＋下一步清單。",
      freeScope: "每人一次、一件事件；先整理現有資料。",
      outcome: "整理事實、證據與下一步；非法律意見。",
      requiredInput: "時間線、遮蔽個資的文件或對話。",
      boundary: "不代替律師判斷或正式代理；需要資格時協助轉介。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "line",
          label: "把事件傳來，先整理局面",
          value: "@772iosnh",
          prefill: "你好，我想領事件時間線與證據缺口清單。我會先遮蔽個資，事情經過是：",
        }),
      ]),
      icon: "contract",
    }),
    Object.freeze({
      slug: "luxury-check",
      category: "risk",
      title: "精品初篩",
      hook: "先別急著匯款，照片裡可能已經有紅旗。",
      freeDeliverable: "款式、來源、價格、行情四項初篩卡。",
      freeScope: "每人一次、一件商品；以收到的照片與資料初篩。",
      outcome: "做款式、來源、價格與行情初篩；非正式鑑定。",
      requiredInput: "來源、價格與清楚照片。",
      boundary: "初步整理，不提供真偽保證。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "line",
          label: "傳照片與價格，先看紅旗",
          value: "@186vktox",
          prefill: "你好，我想領精品四項初篩卡。來源、價格與清楚照片如下：",
        }),
      ]),
      icon: "bag",
    }),
    Object.freeze({
      slug: "flight-plan",
      category: "travel",
      title: "機票比較",
      hook: "同一趟旅程，不要只看一個價格。",
      freeDeliverable: "偏省錢、偏省時間、偏少轉機三種取向比較。",
      freeScope: "每人一次、一組來回條件；依查詢當下資訊整理。",
      outcome: "整理一組路線與日期比較。",
      requiredInput: "出發地、目的地、日期彈性、人數。",
      boundary: "不保留票價、不代替平台出票。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "line",
          label: "傳日期，免費拿三種取向比較",
          value: "@129vsziy",
          prefill: "你好，我想領三種取向機票比較。出發地、目的地、日期彈性與人數是：",
        }),
      ]),
      icon: "plane",
    }),
    Object.freeze({
      slug: "travel-stay",
      category: "travel",
      title: "旅遊住宿",
      hook: "不用再看 100 間，先把本次查詢縮成較符合條件的 3 間。",
      freeDeliverable: "本次查詢中較符合預算、交通與偏好的三間住宿清單。",
      freeScope: "每人一次、一個地點與日期區間。",
      outcome: "整理一組住宿與行程比較。",
      requiredInput: "地點、日期、人數、預算、偏好。",
      boundary: "不保留房況、不代替平台訂房。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "line",
          label: "傳條件，幫我縮成 3 間",
          value: "@805udwla",
          prefill: "你好，我想領三間住宿精選清單。地點、日期、人數、預算與偏好是：",
        }),
      ]),
      icon: "stay",
    }),
    Object.freeze({
      slug: "auto-care",
      category: "auto",
      title: "POP 汽美",
      hook: "先別亂買藥劑，傳車況再決定買什麼。",
      freeDeliverable: "「該買／先不用買／怎麼搭配」車況選品清單。",
      freeScope: "每人一次、一台車或一項施工目標。",
      outcome: "依車況與施工目標導向商品或選品協助。",
      requiredInput: "車況、目標、手邊工具或藥劑。",
      boundary: "規格、庫存與適用方式以 POP 官網當下資訊為準。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "site",
          label: "看 32 款商品",
          value: "https://popmonster.vip/",
        }),
        Object.freeze({
          kind: "line",
          label: "傳車況，先避開買錯",
          value: "@150tiznd",
          prefill: "你好，我想領 POP 車況選品清單。車況、目標與手邊工具／藥劑是：",
        }),
      ]),
      icon: "car",
    }),
    Object.freeze({
      slug: "popcard-demo",
      category: "shop",
      title: "POP CARD 店家系統",
      hook: "讓客人自己想回來，先看公開展示再決定。",
      freeDeliverable: "服務菜單、會員履歷、透明帳本與預約流程的互動展示，打開就能看。",
      freeScope: "公開展示使用去識別示範資料；不用留任何資料。",
      outcome: "看懂汽美店的會員與回訪系統長什麼樣，再評估要不要導入。",
      requiredInput: "不用準備，直接看。",
      boundary: "展示系統獨立運作，不讀取你的官網會員、購物車或付款資料。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "site",
          label: "開啟 POP CARD 公開展示",
          value: "https://popcard-saas-preview.milk790.workers.dev/s/jilin#story",
        }),
      ]),
      icon: "car",
    }),
    Object.freeze({
      slug: "site-launch",
      category: "shop",
      title: "掘計畫 · 免費建官網",
      hook: "建置費 0 元，先用滿意再談月費。",
      freeDeliverable: "為你的店建一個正式官網，建置費 NT$0，先用滿意再付。",
      freeScope: "名額有限、每行業只收一名；席次與條件以掘計畫頁面當下公告為準。",
      outcome: "看完方案說明與剩餘席次，直接在頁上申請。",
      requiredInput: "店名、行業與想放上官網的內容方向。",
      boundary: "方案細節以掘計畫頁面為準，不在此頁另做承諾。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "site",
          label: "看掘計畫方案與剩餘席次",
          value: "https://3q-art-portfolio.milk790.workers.dev/launch-plan",
        }),
      ]),
      icon: "home",
    }),
    Object.freeze({
      slug: "grant-check",
      category: "shop",
      title: "政府補助快篩",
      hook: "3 分鐘看你的店符合哪些政府補助。",
      freeDeliverable: "選幾個條件，立即比對 10 個政府補助／貸款計畫的符合度。",
      freeScope: "免登入、不留個資；規則庫資料時點以頁面標示為準。",
      outcome: "拿到「符合／待確認／不符」排序清單，再決定要不要深入申請。",
      requiredInput: "公司所在地、成立年數與行業等基本條件。",
      boundary: "快篩是初步比對，不是政府核定結果；申請前以各計畫公告為準。",
      destinations: Object.freeze([
        Object.freeze({
          kind: "site",
          label: "開始 3 分鐘補助快篩",
          value: "https://3q-site.milk790.workers.dev/assess.html",
        }),
      ]),
      icon: "contract",
    }),
  ]);

  const EXTERNAL_TOOL_SLUGS = new Set(["creator-kit", "popcard-demo", "site-launch", "grant-check"]);

  const CATEGORY_TITLES = Object.freeze({
    business: "生意與內容",
    risk: "簽約與購買避雷",
    travel: "旅行規劃",
    auto: "汽美與耗材",
    shop: "店家與品牌",
  });

  const ICON_PATHS = Object.freeze({
    message: Object.freeze(["M8 11h32v22H22l-8 6v-6H8z", "M15 18h18", "M15 25h12"]),
    document: Object.freeze(["M9 10h30v28H9z", "M16 18h16", "M16 24h10", "M16 30h13"]),
    home: Object.freeze(["M7 23 24 9l17 14", "M12 21v18h24V21", "M20 39V28h8v11"]),
    contract: Object.freeze(["M14 7h16l7 7v27H14z", "M30 7v8h7", "M20 23h11", "M20 30h11"]),
    bag: Object.freeze(["M10 18h28l-5 21H15z", "M16 18a8 8 0 0 1 16 0", "M19 28l3 3 7-8"]),
    plane: Object.freeze(["m7 27 14-3 10-14 5 1-5 13 10 5-2 4-12-2-7 8-4-1 3-9-10 2z"]),
    stay: Object.freeze(["M7 37h34", "M10 37V18h28v19", "M15 26h18", "M16 18v-7h16v7"]),
    car: Object.freeze(["M8 29h32l-3-10H14z", "M11 29v8h4", "M37 29v8h-4", "M15 33h4", "M29 33h4", "M18 19l3-7h6l3 7"]),
  });

  const QUERY_CHOICES = Object.freeze({
    concept: new Set(["signal", "manual", "tickets"]),
    hook: new Set(["offer", "founder"]),
    flow: new Set(["hybrid", "guided", "all"]),
    motion: new Set(["full", "reduced"]),
  });
  const QUERY_DEFAULTS = Object.freeze({
    concept: "signal",
    hook: "offer",
    flow: "hybrid",
    motion: "full",
  });
  const HOOK_COPY = Object.freeze({
    offer: Object.freeze({
      eyebrow: "10 個免費第一步＋1 個 POP 汽美入口",
      title: "你先說卡在哪，我幫你把第一步分清楚。",
      lede: "品牌內容、CreatorKit、店家系統、免費官網、補助快篩、租屋、合約、精品、機票、住宿、汽美選品，都先交代我能幫你的成果、你要準備的資料與服務邊界。",
    }),
    founder: Object.freeze({
      eyebrow: "接線台的工作方式",
      title: "我不先推銷，先陪你找出最該做哪一步。",
      lede: "先看清全部入口；不確定時，我再幫你把問題接到正確第一步。",
    }),
  });

  function queryParams() {
    try {
      return new URLSearchParams(window.location.search);
    } catch (_error) {
      return new URLSearchParams();
    }
  }

  function parseSource(value) {
    const candidate = typeof value === "string" ? value : queryParams().get("src");
    if (ALLOWED_SOURCES.has(candidate)) return candidate;
    if (FB_MATRIX_PATTERN.test(candidate)) return candidate;
    return "direct";
  }

  function parseSurface(value) {
    return ALLOWED_SURFACES.has(value) ? value : "";
  }

  function serviceBySlug(slug) {
    return SERVICES.find((service) => service.slug === slug) || null;
  }

  function destinationByKind(service, kind) {
    return (
      service?.destinations.find((destination) => destination.kind === kind) ||
      service?.destinations[0] ||
      null
    );
  }

  function buildLineUrl(lineId, prefill, slug, source) {
    const safeSource = parseSource(source);
    const message = `${prefill}\n【GO:${slug}:${safeSource}】`;
    return `https://line.me/R/oaMessage/${encodeURIComponent(lineId)}/?${encodeURIComponent(message)}`;
  }

  function buildSiteUrl(destination, source) {
    try {
      const url = new URL(destination, window.location.href);
      url.searchParams.set("src", parseSource(source));
      return url.toString();
    } catch (_error) {
      return destination;
    }
  }

  function destinationFor(service, source, kind) {
    const destination = destinationByKind(service, kind);
    if (!destination) return "#";
    if (destination.kind === "line") {
      return buildLineUrl(
        destination.value,
        destination.prefill,
        service.slug,
        source,
      );
    }
    return buildSiteUrl(destination.value, source);
  }

  function isPreviewMode() {
    return (
      queryParams().get("preview") === "1" ||
      document.body?.dataset.preview === "true" ||
      Boolean(document.getElementById("preview-form"))
    );
  }

  function privacySignalEnabled() {
    const dnt =
      navigator.doNotTrack ||
      window.doNotTrack ||
      navigator.msDoNotTrack ||
      "";
    return (
      navigator.globalPrivacyControl === true ||
      dnt === "1" ||
      String(dnt).toLowerCase() === "yes"
    );
  }

  function analyticsConsentGranted() {
    try {
      return localStorage.getItem("ck_consent") === "granted";
    } catch (_error) {
      return false;
    }
  }

  function eventEndpoint() {
    const bodyEndpoint =
      document.body?.dataset.eventEndpoint ||
      document.body?.dataset.eventsEndpoint ||
      "";
    const metaEndpoint =
      document.querySelector('meta[name="switchboard-events"]')?.content ||
      document.querySelector('meta[name="event-endpoint"]')?.content ||
      "";
    return String(bodyEndpoint || metaEndpoint).trim();
  }

  function randomBytes(size) {
    if (
      typeof crypto === "undefined" ||
      typeof crypto.getRandomValues !== "function"
    ) {
      return null;
    }
    return crypto.getRandomValues(new Uint8Array(size));
  }

  function bytesToHex(bytes) {
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function eventId() {
    if (
      typeof crypto !== "undefined" &&
      typeof crypto.randomUUID === "function"
    ) {
      return crypto.randomUUID();
    }
    const bytes = randomBytes(16);
    if (!bytes) return "";
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = bytesToHex(bytes);
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function sessionHash() {
    try {
      const existing = sessionStorage.getItem(SESSION_STORAGE_KEY) || "";
      if (SESSION_HASH_PATTERN.test(existing)) {
        memorySessionHash = existing;
        return existing;
      }
      const bytes = SESSION_HASH_PATTERN.test(memorySessionHash)
        ? null
        : randomBytes(32);
      const generated = bytes ? bytesToHex(bytes) : memorySessionHash;
      if (!SESSION_HASH_PATTERN.test(generated)) return "";
      memorySessionHash = generated;
      sessionStorage.setItem(SESSION_STORAGE_KEY, generated);
      return generated;
    } catch (_error) {
      if (SESSION_HASH_PATTERN.test(memorySessionHash)) return memorySessionHash;
      const bytes = randomBytes(32);
      memorySessionHash = bytes ? bytesToHex(bytes) : "";
      return memorySessionHash;
    }
  }

  function sendEvent(eventName, detail, options = {}) {
    try {
      if (
        !EVENT_NAMES.has(eventName) ||
        isPreviewMode() ||
        privacySignalEnabled() ||
        !analyticsConsentGranted()
      ) {
        return false;
      }

      const safeDetail = {};
      const slug =
        typeof detail === "string"
          ? detail
          : detail && typeof detail.slug === "string"
            ? detail.slug
            : "";
      const surface = parseSurface(detail?.surface);
      if (serviceBySlug(slug)) safeDetail.slug = slug;
      if (
        surface &&
        (eventName === "line_start" || eventName === "site_start")
      ) {
        safeDetail.surface = surface;
      }
      if (eventName === "route_stage_1" && CATEGORY_TITLES[detail?.category]) {
        safeDetail.category = detail.category;
      }
      if (eventName === "hero_cta" && typeof detail?.target === "string") {
        safeDetail.target = detail.target.slice(0, 32);
      }

      const analyticsSent =
        options.analytics === false
          ? false
          : window.PopMonsterGoAnalytics?.track?.(eventName, safeDetail) === true;
      const endpoint = eventEndpoint();
      if (!endpoint || typeof navigator.sendBeacon !== "function") {
        return analyticsSent;
      }

      const eventIdentifier = eventId();
      const anonymousSession = sessionHash();
      if (!eventIdentifier || !anonymousSession) return false;
      const payload = {
        event_id: eventIdentifier,
        event: eventName,
        session_hash: anonymousSession,
        source: parseSource(),
        timestamp: new Date().toISOString(),
      };
      Object.assign(payload, safeDetail);

      const json = JSON.stringify(payload);
      const body =
        typeof Blob === "function"
          ? new Blob([json], { type: "text/plain;charset=UTF-8" })
          : json;
      return navigator.sendBeacon(endpoint, body) === true || analyticsSent;
    } catch (_error) {
      return false;
    }
  }

  function appendDetail(container, label, value) {
    const row = document.createElement("p");
    const strong = document.createElement("strong");
    strong.textContent = `${label}：`;
    row.append(strong, document.createTextNode(value));
    container.append(row);
  }

  function createServiceIcon(iconName) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("service-icon");
    svg.setAttribute("viewBox", "0 0 48 48");
    svg.setAttribute("aria-hidden", "true");
    (ICON_PATHS[iconName] || ICON_PATHS.message).forEach((pathData) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", pathData);
      svg.append(path);
    });
    return svg;
  }

  function createServiceTicket(service) {
    const ticket = document.createElement("div");
    ticket.className = "service-ticket";
    const top = document.createElement("div");
    top.className = "ticket-topline";
    const label = document.createElement("span");
    label.className = "ticket-label";
    label.textContent = "免費拿到";
    const stamp = document.createElement("span");
    stamp.className = "ticket-stamp";
    stamp.textContent = "FREE RESULT";
    const deliverable = document.createElement("p");
    deliverable.className = "ticket-deliverable";
    deliverable.textContent = service.freeDeliverable;
    top.append(label, stamp);
    ticket.append(top, deliverable);
    return ticket;
  }

  function createDestinationLink(service, destination, index, surface) {
    const link = document.createElement("a");
    link.className = index === 0
      ? "service-link"
      : "service-link service-link-secondary";
    link.href = destinationFor(service, parseSource(), destination.kind);
    link.dataset.serviceSlug = service.slug;
    link.dataset.destinationKind = destination.kind;
    link.dataset.channel = destination.kind;
    link.dataset.surface = surface;
    link.rel = "noopener";
    if (destination.kind === "line" || EXTERNAL_TOOL_SLUGS.has(service.slug)) {
      link.target = "_blank";
    }
    link.textContent = destination.label;
    return link;
  }

  function appendCardDetail(list, label, value) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value;
    row.append(term, detail);
    list.append(row);
    return detail;
  }

  function createServiceCard(service, index) {
    const card = document.createElement("article");
    card.className = service.slug === "auto-care"
      ? "service-card service-card-pop"
      : "service-card";
    card.dataset.cardSlug = service.slug;

    const header = document.createElement("header");
    header.className = "service-card-header";
    const heading = document.createElement("div");
    const serviceIndex = document.createElement("p");
    serviceIndex.className = "service-index";
    serviceIndex.textContent = `${String(index + 1).padStart(2, "0")} / CLAIM TICKET`;
    const title = document.createElement("h4");
    title.textContent = service.title;
    heading.append(serviceIndex, title);
    header.append(createServiceIcon(service.icon), heading);

    const hook = document.createElement("p");
    hook.className = "service-hook";
    hook.textContent = service.hook;

    const details = document.createElement("dl");
    appendCardDetail(details, "你準備", service.requiredInput);
    appendCardDetail(details, "免費範圍", service.freeScope);
    appendCardDetail(details, "服務邊界", service.boundary);
    const actionDetail = appendCardDetail(details, "前往方式", "");
    actionDetail.replaceChildren();
    const lineDestination = service.destinations.find((destination) => destination.kind === "line");
    if (lineDestination) {
      const lineId = document.createElement("span");
      lineId.className = "line-id";
      lineId.append("LINE ID：");
      const code = document.createElement("code");
      code.textContent = lineDestination.value;
      lineId.append(code);
      actionDetail.append(lineId);
    }
    const actions = document.createElement("span");
    actions.className = "service-actions";
    const surface = service.slug === "auto-care" ? "pop_card" : "directory";
    service.destinations.forEach((destination, destinationIndex) => {
      actions.append(createDestinationLink(service, destination, destinationIndex, surface));
    });
    actionDetail.append(actions);

    card.append(header, hook, createServiceTicket(service), details);
    return card;
  }

  function renderDirectory() {
    document.querySelectorAll("[data-service-grid]").forEach((grid) => {
      const category = grid.dataset.serviceGrid;
      const cards = SERVICES
        .map((service, index) => ({ service, index }))
        .filter((entry) => entry.service.category === category)
        .map((entry) => createServiceCard(entry.service, entry.index));
      grid.replaceChildren(...cards);
    });
  }

  function renderService(serviceOrSlug) {
    const service =
      typeof serviceOrSlug === "string"
        ? serviceBySlug(serviceOrSlug)
        : serviceBySlug(serviceOrSlug?.slug);
    const result = document.getElementById("route-result");
    if (!service || !result) return null;

    const card = document.createElement("article");
    card.className = "result-card";
    card.dataset.selectedService = service.slug;

    const summary = document.createElement("div");
    summary.className = "result-summary";
    const kicker = document.createElement("p");
    kicker.className = "result-kicker";
    kicker.textContent = "你的接線結果";
    const title = document.createElement("h2");
    title.className = "result-title";
    title.textContent = service.title;
    const hook = document.createElement("p");
    hook.className = "service-hook result-hook";
    hook.textContent = service.hook;
    const sourceCode = document.createElement("code");
    sourceCode.className = "result-source";
    sourceCode.textContent = `【GO:${service.slug}:${parseSource()}】`;
    summary.append(kicker, title, hook, sourceCode);

    const details = document.createElement("div");
    details.className = "result-details";
    details.append(createServiceTicket(service));
    appendDetail(details, "你準備", service.requiredInput);
    appendDetail(details, "免費範圍", service.freeScope);
    appendDetail(details, "服務邊界", service.boundary);

    const actions = document.createElement("div");
    actions.className = "result-actions";
    service.destinations.forEach((destination, index) => {
      const cta = document.createElement("a");
      cta.className = index === 0
        ? "button button-primary result-cta"
        : "button button-secondary result-cta";
      const sharedLink = createDestinationLink(
        service,
        destination,
        index,
        "router_result",
      );
      cta.href = sharedLink.href;
      Object.assign(cta.dataset, sharedLink.dataset);
      cta.rel = sharedLink.rel;
      cta.target = sharedLink.target;
      cta.textContent = sharedLink.textContent;
      actions.append(cta);
    });
    details.append(actions);

    card.append(summary, details);
    result.replaceChildren(card);
    result.hidden = false;
    result.dataset.selectedService = service.slug;

    document.querySelectorAll("[data-route-service]").forEach((button) => {
      const selected = button.dataset.routeService === service.slug;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    const reset = document.getElementById("router-reset");
    if (reset) reset.hidden = false;

    sendEvent("route_result", { slug: service.slug });
    result.focus({ preventScroll: true });
    result.scrollIntoView({ behavior: motionBehavior(), block: "start" });
    return service;
  }

  function applyHookCopy(hook) {
    const copy = HOOK_COPY[hook] || HOOK_COPY.offer;
    const eyebrow = document.querySelector(".hero-copy > .eyebrow");
    const title = document.getElementById("hero-title");
    const lede = document.querySelector(".hero-copy > .hero-lede");
    if (eyebrow) eyebrow.textContent = copy.eyebrow;
    if (title) title.textContent = copy.title;
    if (lede) lede.textContent = copy.lede;
  }

  function motionBehavior() {
    return document.documentElement.dataset.motion === "reduced" ? "auto" : "smooth";
  }

  function syncFlowControls(flow) {
    const primary = document.getElementById("hero-cta");
    const secondary = document.querySelector(
      '.hero-actions .button-secondary[data-target="router"]',
    );
    if (primary) {
      if (flow === "guided") {
        primary.href = "#problem-router";
        primary.dataset.target = "router";
        primary.textContent = "開始兩步分流";
      } else {
        primary.href = "#all-services";
        primary.dataset.target = "directory";
        primary.textContent = "直接看 11 個入口";
      }
    }
    if (secondary) {
      secondary.hidden = flow !== "hybrid";
    }
  }

  function applyExperience(params) {
    const settings = {};
    const allowVariants = isPreviewMode();
    Object.keys(QUERY_CHOICES).forEach((key) => {
      const value = params.get(key);
      settings[key] =
        allowVariants && QUERY_CHOICES[key].has(value)
          ? value
          : QUERY_DEFAULTS[key];
    });

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (reducedMotion?.matches) settings.motion = "reduced";
    applyHookCopy(settings.hook);

    const source = parseSource(params.get("src"));
    [document.documentElement, document.body].forEach((element) => {
      if (!element) return;
      element.dataset.concept = settings.concept;
      element.dataset.hook = settings.hook;
      element.dataset.flow = settings.flow;
      element.dataset.motion = settings.motion;
      element.dataset.source = source;
      element.dataset.preview = String(isPreviewMode());
    });

    const allServices = document.getElementById("all-services");
    const router = document.getElementById("problem-router");
    if (allServices) allServices.hidden = settings.flow === "guided";
    if (router) router.hidden = settings.flow === "all";
    syncFlowControls(settings.flow);

    const syncMotion = (event) => {
      const requested = allowVariants
        ? params.get("motion")
        : QUERY_DEFAULTS.motion;
      const motion = event.matches || requested === "reduced" ? "reduced" : "full";
      document.documentElement.dataset.motion = motion;
      if (document.body) document.body.dataset.motion = motion;
    };
    reducedMotion?.addEventListener?.("change", syncMotion);
    if (!reducedMotion?.addEventListener) reducedMotion?.addListener?.(syncMotion);
  }

  function updateSourceUI(source) {
    const nodes = new Set([
      ...document.querySelectorAll("[data-source-code]"),
      document.getElementById("source-code"),
    ]);
    nodes.forEach((node) => {
      if (node) node.textContent = source;
    });

    document.querySelectorAll("a[data-service-slug]").forEach((anchor) => {
      const service = serviceBySlug(anchor.dataset.serviceSlug);
      const kind = anchor.dataset.destinationKind || anchor.dataset.channel;
      const destination = destinationByKind(service, kind);
      if (!service || !destination) return;
      anchor.href = destinationFor(service, source, destination.kind);
      anchor.dataset.channel = destination.kind;
    });
  }

  function resetRouter(options) {
    const settings = options || {};
    const stageTwo = document.getElementById("router-stage-2");
    const optionsContainer = document.getElementById("service-options");
    const result = document.getElementById("route-result");
    const reset = document.getElementById("router-reset");
    document.querySelectorAll("button.category-button[data-category]").forEach((button) => {
      button.classList.remove("is-selected");
      button.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-expanded", "false");
    });
    if (stageTwo) stageTwo.hidden = true;
    if (optionsContainer) optionsContainer.replaceChildren();
    if (result) {
      result.hidden = true;
      result.replaceChildren();
      delete result.dataset.selectedService;
    }
    if (reset) reset.hidden = true;
    if (settings.focus !== false) {
      document.querySelector("button.category-button[data-category]")?.focus();
    }
  }

  function installRouter() {
    const stageTwo = document.getElementById("router-stage-2");
    const stageTitle = document.getElementById("stage-2-title");
    const options = document.getElementById("service-options");
    if (!stageTwo || !options) return;

    document.querySelectorAll("button.category-button[data-category]").forEach((button) => {
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => {
        const category = button.dataset.category;
        const matches = SERVICES.filter((service) => service.category === category);
        if (!matches.length) return;

        document.querySelectorAll("button.category-button[data-category]").forEach((item) => {
          const selected = item === button;
          item.classList.toggle("is-selected", selected);
          item.setAttribute("aria-pressed", String(selected));
          item.setAttribute("aria-expanded", String(selected));
        });

        options.replaceChildren();
        matches.forEach((service) => {
          const option = document.createElement("button");
          option.type = "button";
          option.className = "service-option";
          option.dataset.routeService = service.slug;
          option.setAttribute("aria-pressed", "false");
          const optionTitle = document.createElement("strong");
          optionTitle.textContent = service.title;
          const optionHook = document.createElement("small");
          optionHook.textContent = service.hook;
          option.append(optionTitle, optionHook);
          option.addEventListener("click", () => renderService(service.slug));
          options.append(option);
        });
        if (stageTitle) {
          stageTitle.textContent = `${CATEGORY_TITLES[category]}：選最貼近的一項`;
        }
        stageTwo.hidden = false;
        sendEvent("route_stage_1", { category: category });
        options.querySelector("button")?.focus();
      });
    });
    document.getElementById("router-reset")?.addEventListener("click", () => {
      resetRouter();
    });
  }

  function showPreviewNotice() {
    const notice = document.getElementById("preview-notice");
    if (notice) {
      notice.hidden = false;
      notice.textContent = "預覽模式：所有事件與外部跳轉都已停用。";
    }
  }

  function isNavigatingAnchor(anchor) {
    const href = anchor?.getAttribute("href") || "";
    return Boolean(href && !href.startsWith("#") && !href.startsWith("javascript:"));
  }

  function installClickHandling() {
    document.addEventListener(
      "click",
      (event) => {
        const anchor = event.target.closest?.("a");
        if (isPreviewMode() && isNavigatingAnchor(anchor)) {
          event.preventDefault();
          showPreviewNotice();
          return;
        }

        const destination = event.target.closest?.("a[data-service-slug]");
        if (!destination) return;
        const service = serviceBySlug(destination.dataset.serviceSlug);
        const channel = destination.dataset.channel;
        if (service && (channel === "line" || channel === "site")) {
          sendEvent(channel === "line" ? "line_start" : "site_start", {
            slug: service.slug,
            surface: parseSurface(destination.dataset.surface),
          });
          // 阻斷 GA4 Enhanced Measurement 傳送完整 LINE 預填網址。
          event.stopImmediatePropagation();
        }
      },
      true,
    );

    document.querySelectorAll('[data-event="hero_cta"]').forEach((cta) => {
      cta.addEventListener("click", () =>
        sendEvent("hero_cta", {
          target: cta.dataset.target || cta.dataset.action || cta.id || "router",
        }),
      );
    });
  }

  async function shareSwitchboard() {
    if (isPreviewMode()) {
      showPreviewNotice();
      return false;
    }
    const url = new URL("https://popmonster.vip/go");
    url.searchParams.set("v", "20260729");
    url.searchParams.set("src", "social");
    const shareData = {
      title: "POP 免費接線台",
      text: "你先說卡在哪，我幫你把第一步分清楚。10 個免費第一步＋1 個 POP 汽美入口。",
      url: url.toString(),
    };
    try {
      if (typeof navigator.share === "function") {
        await navigator.share(shareData);
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareData.url);
      } else {
        return false;
      }
      sendEvent("share_success");
      return true;
    } catch (error) {
      if (error?.name !== "AbortError") {
        console.warn("Switchboard share was not completed.");
      }
      return false;
    }
  }

  function installShare() {
    document.getElementById("share-button")?.addEventListener("click", shareSwitchboard);
  }

  function installConsentBridge() {
    document
      .querySelectorAll('[data-analytics-consent="granted"]')
      .forEach((button) => {
        button.addEventListener("click", () => {
          queueMicrotask(() => sendEvent("page_ready", null, { analytics: false }));
        });
      });
  }

  function installConsentPreferences() {
    const button = document.getElementById("analytics-preferences");
    const panel = document.getElementById("go-analytics-consent");
    if (!button || !panel) return;
    button.addEventListener("click", () => {
      if (isPreviewMode()) {
        showPreviewNotice();
        return;
      }
      panel.hidden = false;
      panel.setAttribute("tabindex", "-1");
      panel.focus();
    });
  }

  function installPreviewControls() {
    const form = document.getElementById("preview-form");
    const frame = document.getElementById("preview-frame");
    if (!form || !frame) return;
    const updateFrame = (event) => {
      event?.preventDefault();
      const values = new FormData(form);
      const params = new URLSearchParams();
      params.set("preview", "1");
      Object.keys(QUERY_CHOICES).forEach((key) => {
        const value = String(values.get(key) || QUERY_DEFAULTS[key]);
        params.set(key, QUERY_CHOICES[key].has(value) ? value : QUERY_DEFAULTS[key]);
      });
      frame.src = `go.html?${params.toString()}`;
    };
    form.addEventListener("change", updateFrame);
    form.addEventListener("submit", updateFrame);
  }

  function init() {
    const params = queryParams();
    applyExperience(params);
    renderDirectory();
    updateSourceUI(parseSource(params.get("src")));
    resetRouter({ focus: false });
    installRouter();
    installClickHandling();
    installShare();
    installConsentBridge();
    installConsentPreferences();
    installPreviewControls();
    if (isPreviewMode()) showPreviewNotice();
    sendEvent("page_ready");
  }

  window.Switchboard = {
    SERVICES,
    parseSource,
    parseSurface,
    buildLineUrl,
    sendEvent,
    renderService,
    resetRouter,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
