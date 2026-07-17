(function () {
  "use strict";

  const ALLOWED_SOURCES = new Set([
    "direct",
    "business-card",
    "package-insert",
    "social",
    "legacy-worker",
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

  const SESSION_STORAGE_KEY = "switchboard_v4_session_hash";
  const SESSION_HASH_PATTERN = /^[0-9a-f]{64}$/;
  let memorySessionHash = "";

  const SERVICES = Object.freeze([
    Object.freeze({
      slug: "brand-content",
      category: "business",
      title: "品牌內容",
      freeScope: "一個首屏、單張或短片段的診斷與一項優先改善。",
      requiredInput: "目前頁面、單張或短片段，以及你最想改善的目標。",
      boundary: "一次聚焦一項優先改善，不含完整成品製作。",
      channel: "line",
      destination: "@121lkspe",
      prefill: "你好，我想先做品牌內容免費第一步。我目前卡在：",
    }),
    Object.freeze({
      slug: "rental-check",
      category: "risk",
      title: "租屋風險",
      freeScope: "公開資訊與簽約風險清單，不保證屋主身分或權利狀態。",
      requiredInput: "地址、物件頁與遮蔽個資後的合約草稿。",
      boundary: "僅整理公開資訊與風險，不作權利認證。",
      channel: "line",
      destination: "@207cpaps",
      prefill: "你好，我想先做租屋風險免費第一步。我目前卡在：",
    }),
    Object.freeze({
      slug: "legal-guidance",
      category: "risk",
      title: "合約事件",
      freeScope: "事實、證據與下一步整理；非法律意見。",
      requiredInput: "事件時間線，以及遮蔽個資後的合約或對話。",
      boundary: "不代替律師判斷或正式代理；需要資格時協助轉介。",
      channel: "line",
      destination: "@772iosnh",
      prefill: "你好，我想先做合約事件免費第一步。我目前卡在：",
    }),
    Object.freeze({
      slug: "flight-plan",
      category: "travel",
      title: "機票比較",
      freeScope: "一組路線／日期區間比較，價格以平台當下為準。",
      requiredInput: "出發地、目的地、日期彈性與人數。",
      boundary: "不保留票價，也不代替售票平台出票。",
      channel: "line",
      destination: "@129vsziy",
      prefill: "你好，我想先做機票比較免費第一步。我目前卡在：",
    }),
    Object.freeze({
      slug: "luxury-check",
      category: "risk",
      title: "精品初篩",
      freeScope: "款式、來源與行情初篩；不等同真偽證書。",
      requiredInput: "款式、來源、價格與清楚照片，敏感資料請先遮蔽。",
      boundary: "只做初步整理，不作正式鑑定或真偽保證。",
      channel: "line",
      destination: "@186vktox",
      prefill: "你好，我想先做精品初篩免費第一步。我目前卡在：",
    }),
    Object.freeze({
      slug: "travel-stay",
      category: "travel",
      title: "旅遊住宿",
      freeScope: "一組行程／住宿比較，實際條件由訂房平台決定。",
      requiredInput: "地點、日期、人數、預算與住宿偏好。",
      boundary: "不保留房況，也不代替訂房平台完成交易。",
      channel: "line",
      destination: "@805udwla",
      prefill: "你好，我想先做旅遊住宿免費第一步。我目前卡在：",
    }),
    Object.freeze({
      slug: "creator-kit",
      category: "business",
      title: "CreatorKit",
      freeScope: "16 個自媒體工具免費使用，不用先註冊。",
      requiredInput: "準備要處理的文案、腳本、圖片、音訊或影片。",
      boundary: "工具成果仍需自行檢查與調整；代工服務另行確認。",
      channel: "site",
      destination: "https://creatorkit.milk790.workers.dev/",
      prefill: "",
    }),
    Object.freeze({
      slug: "auto-care",
      category: "auto",
      title: "POP 汽美本業",
      freeScope: "查看現有汽美用品、選品資訊與使用路線。",
      requiredInput: "車況、施工目標，以及目前使用的工具或藥劑。",
      boundary: "商品規格、庫存與適用方式以 POP 官網當下資訊為準。",
      channel: "site",
      destination: "https://popmonster.vip/",
      prefill: "",
    }),
  ]);

  const CATEGORY_TITLES = Object.freeze({
    business: "生意／內容",
    risk: "怕踩雷／有糾紛",
    travel: "準備出國",
    auto: "汽美／耗材",
  });

  const QUERY_CHOICES = Object.freeze({
    concept: new Set(["signal", "manual", "tickets"]),
    hook: new Set(["offer", "founder"]),
    flow: new Set(["guided", "all"]),
    motion: new Set(["full", "reduced"]),
  });

  const QUERY_DEFAULTS = Object.freeze({
    concept: "signal",
    hook: "offer",
    flow: "guided",
    motion: "full",
  });

  const HOOK_COPY = Object.freeze({
    offer: Object.freeze({
      eyebrow: "花錢前，先避開最貴的錯",
      title: "有些坑，等踩到才看到就太晚。",
      lede: "租屋、合約、機票、精品、內容、汽美——先用免費第一步把風險說清楚，再決定要不要花錢。",
    }),
    founder: Object.freeze({
      eyebrow: "接線台的工作方式",
      title: "我不先推銷，先陪你找出最該做哪一步。",
      lede: "先把問題說清楚，再決定要不要花錢。",
    }),
  });

  function queryParams() {
    try {
      return new URLSearchParams(window.location.search);
    } catch (_error) {
      return new URLSearchParams();
    }
  }

  // FB 60 專矩陣來源：fb- + 6 碼小寫十六進位。嚴格 pattern，不可能注入。
  const FB_MATRIX_PATTERN = /^fb-[0-9a-f]{6}$/;

  function parseSource(value) {
    const candidate = typeof value === "string" ? value : queryParams().get("src");
    if (ALLOWED_SOURCES.has(candidate)) return candidate;
    if (FB_MATRIX_PATTERN.test(candidate)) return candidate;
    return "direct";
  }

  function serviceBySlug(slug) {
    return SERVICES.find((service) => service.slug === slug) || null;
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

  function destinationFor(service, source) {
    if (service.channel === "line") {
      return buildLineUrl(
        service.destination,
        service.prefill,
        service.slug,
        source,
      );
    }
    return buildSiteUrl(service.destination, source);
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
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
      "",
    );
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
      if (SESSION_HASH_PATTERN.test(memorySessionHash)) {
        return memorySessionHash;
      }
      const bytes = randomBytes(32);
      memorySessionHash = bytes ? bytesToHex(bytes) : "";
      return memorySessionHash;
    }
  }

  function sendEvent(eventName, detail) {
    try {
      if (
        !EVENT_NAMES.has(eventName) ||
        isPreviewMode() ||
        privacySignalEnabled()
      ) {
        return false;
      }

      const analyticsSent =
        window.PopMonsterGoAnalytics?.track?.(eventName, detail || {}) === true;
      const endpoint = eventEndpoint();
      if (!endpoint || typeof navigator.sendBeacon !== "function") {
        return analyticsSent;
      }

      const slug =
        typeof detail === "string"
          ? detail
          : detail && typeof detail.slug === "string"
            ? detail.slug
            : "";
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
      if (serviceBySlug(slug)) {
        payload.slug = slug;
      }

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

  function renderService(serviceOrSlug) {
    const service =
      typeof serviceOrSlug === "string"
        ? serviceBySlug(serviceOrSlug)
        : serviceBySlug(serviceOrSlug?.slug);
    const result = document.getElementById("route-result");
    if (!service || !result) {
      return null;
    }

    const card = document.createElement("article");
    card.className = "result-card";
    card.dataset.selectedService = service.slug;

    const summary = document.createElement("div");
    summary.className = "result-summary";

    const kicker = document.createElement("p");
    kicker.className = "result-kicker";
    kicker.textContent = "你的第一步";

    const title = document.createElement("h2");
    title.className = "result-title";
    title.textContent = service.title;

    const sourceCode = document.createElement("code");
    sourceCode.className = "result-source";
    sourceCode.textContent = `【GO:${service.slug}:${parseSource()}】`;
    summary.append(kicker, title, sourceCode);

    const details = document.createElement("div");
    details.className = "result-details";
    appendDetail(details, "免費先做", service.freeScope);
    appendDetail(details, "請準備", service.requiredInput);
    appendDetail(details, "服務邊界", service.boundary);
    if (service.channel === "line") {
      appendDetail(details, "LINE ID", service.destination);
    }

    const cta = document.createElement("a");
    cta.className = "button button-primary result-cta";
    cta.href = destinationFor(service, parseSource());
    cta.dataset.serviceSlug = service.slug;
    cta.dataset.channel = service.channel;
    cta.rel = "noopener";
    if (service.channel === "line" || service.slug === "creator-kit") {
      cta.target = "_blank";
    }
    cta.textContent =
      service.channel === "line"
        ? "開啟 LINE，帶入第一則訊息"
        : service.slug === "creator-kit"
          ? "開啟 CreatorKit 16 工具"
          : "前往 POP 汽美本業";
    details.append(cta);

    card.append(summary, details);
    result.replaceChildren(card);
    result.hidden = false;
    result.dataset.selectedService = service.slug;

    document.querySelectorAll("[data-route-service]").forEach((button) => {
      const selected = button.dataset.routeService === service.slug;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });

    sendEvent("route_result", { slug: service.slug });
    result.focus({ preventScroll: true });
    result.scrollIntoView({ behavior: "smooth", block: "start" });
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
    if (reducedMotion?.matches) {
      settings.motion = "reduced";
    }

    applyHookCopy(settings.hook);

    const source = parseSource(params.get("src"));
    [document.documentElement, document.body].forEach((element) => {
      if (!element) return;
      element.dataset.concept = settings.concept;
      element.dataset.hook = settings.hook;
      element.dataset.flow = settings.flow;
      element.dataset.motion = settings.motion;
      element.dataset.source = source;
    });

    const allServices = document.getElementById("all-services");
    const router = document.getElementById("problem-router");
    if (allServices) allServices.hidden = settings.flow !== "all";
    if (router) router.hidden = settings.flow === "all";

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
      if (service) {
        anchor.href = destinationFor(service, source);
        anchor.dataset.channel = service.channel;
      }
    });
  }

  function installRouter() {
    const stageTwo = document.getElementById("router-stage-2");
    const stageTitle = document.getElementById("stage-2-title");
    const options = document.getElementById("service-options");
    if (!stageTwo || !options) return;

    document.querySelectorAll("button.category-button[data-category]").forEach((button) => {
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
          option.textContent = service.title;
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
        if (service) {
          sendEvent(service.channel === "line" ? "line_start" : "site_start", {
            slug: service.slug,
          });
          // GA4 enhanced measurement otherwise sends the full prefilled LINE URL.
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

    const showAll = document.getElementById("show-all");
    showAll?.addEventListener("click", (event) => {
      const allServices = document.getElementById("all-services");
      if (!allServices) return;
      event.preventDefault();
      allServices.hidden = false;
      allServices.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    document.querySelectorAll("[data-target]").forEach((cta) => {
      cta.addEventListener("click", (event) => {
        const service = serviceBySlug(cta.dataset.target);
        if (!service) return;
        event.preventDefault();
        renderService(service.slug);
      });
    });
  }

  async function shareSwitchboard() {
    if (isPreviewMode()) {
      showPreviewNotice();
      return false;
    }

    const url = new URL("https://popmonster.vip/go");
    url.searchParams.set("v", "20260716");
    url.searchParams.set("src", "social");
    const shareData = {
      title: "免費避雷接線台",
      text: "有些坑，等踩到才看到就太晚。花錢前先免費問第一步。",
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
    updateSourceUI(parseSource(params.get("src")));
    installRouter();
    installClickHandling();
    installShare();
    installPreviewControls();
    if (isPreviewMode()) showPreviewNotice();
    sendEvent("page_ready");
  }

  window.Switchboard = {
    SERVICES,
    parseSource,
    buildLineUrl,
    sendEvent,
    renderService,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
