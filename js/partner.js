(function () {
  "use strict";

  const ALLOWED_SOURCES = new Set([
    "direct",
    "facebook",
    "instagram",
    "group",
    "referral",
    "distributor",
    "demo",
  ]);
  const EVENT_NAMES = new Set([
    "page_ready",
    "eligibility_check",
    "evidence_open",
    "apply_line_start",
    "audit_line_start",
    "share_success",
  ]);
  const EVENT_FIELDS = Object.freeze({
    page_ready: new Set([]),
    eligibility_check: new Set(["choice"]),
    evidence_open: new Set(["evidence_id"]),
    apply_line_start: new Set(["surface"]),
    audit_line_start: new Set(["surface"]),
    share_success: new Set(["surface"]),
  });
  const ALLOWED_CHOICES = new Set(["ready", "not-ready"]);
  const ALLOWED_SURFACES = new Set(["hero", "final", "demo"]);
  const ANALYTICS_STORAGE_KEY = "partner_analytics_consent";
  const lineId = "@150tiznd";
  let pageReadySent = false;

  function getSource() {
    let candidate = "direct";
    try {
      const params = new URLSearchParams(window.location.search || "");
      candidate = (params.get("src") || "direct").trim().toLowerCase();
      if (candidate === "direct" && document.body && document.body.dataset.demo === "true") {
        candidate = "demo";
      }
    } catch (_error) {
      candidate = "direct";
    }
    return ALLOWED_SOURCES.has(candidate) ? candidate : "direct";
  }

  const source = getSource();

  function lineMessage(action, selectedSource) {
    const safeAction = action === "audit" ? "audit" : "apply";
    const requestedSource = selectedSource || source;
    const safeSource = ALLOWED_SOURCES.has(requestedSource) ? requestedSource : "direct";
    return `【PARTNER:${safeAction}:${safeSource}】`;
  }

  function buildLineUrl(action, selectedSource) {
    const message = lineMessage(action, selectedSource);
    return `https://line.me/R/oaMessage/${encodeURIComponent(lineId)}/?${encodeURIComponent(message)}`;
  }

  function privacySignalEnabled() {
    try {
      return Boolean(
        navigator.globalPrivacyControl ||
        navigator.doNotTrack === "1" ||
        window.doNotTrack === "1"
      );
    } catch (_error) {
      return true;
    }
  }

  function isPreviewMode() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return Boolean(
        params.get("preview") === "1" ||
        (document.body && document.body.dataset.preview === "true") ||
        (document.documentElement && document.documentElement.dataset.preview === "true")
      );
    } catch (_error) {
      return true;
    }
  }

  function canNavigate() {
    return !isPreviewMode();
  }

  function eventEndpoint() {
    const meta = document.querySelector('meta[name="partner-events"]');
    return meta && typeof meta.content === "string" ? meta.content.trim() : "";
  }

  function storedConsent() {
    try {
      const value = localStorage.getItem(ANALYTICS_STORAGE_KEY);
      return value === "granted" || value === "denied" ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function writeConsent(value) {
    try {
      localStorage.setItem(ANALYTICS_STORAGE_KEY, value);
      return true;
    } catch (_error) {
      return false;
    }
  }

  function cleanEventData(eventName, data) {
    const clean = {};
    const allowed = EVENT_FIELDS[eventName] || new Set([]);
    const input = data && typeof data === "object" ? data : {};

    allowed.forEach((key) => {
      const value = input[key];
      if (typeof value !== "string") return;
      if (key === "choice" && !ALLOWED_CHOICES.has(value)) return;
      if (key === "surface" && !ALLOWED_SURFACES.has(value)) return;
      if (key === "evidence_id" && !/^[a-z0-9-]{1,48}$/.test(value)) return;
      clean[key] = value;
    });
    return clean;
  }

  function track(eventName, data) {
    if (!EVENT_NAMES.has(eventName)) return false;
    if (storedConsent() !== "granted") return false;
    if (privacySignalEnabled() || isPreviewMode()) return false;

    const endpoint = eventEndpoint();
    if (!endpoint || !navigator.sendBeacon) return false;

    const payload = Object.assign(
      { event: eventName, source: source },
      cleanEventData(eventName, data)
    );
    try {
      const body = new Blob([JSON.stringify(payload)], {
        type: "text/plain;charset=UTF-8",
      });
      return navigator.sendBeacon(endpoint, body);
    } catch (_error) {
      return false;
    }
  }

  function updateConsentStatus(value) {
    const status = document.getElementById("consent-status");
    if (!status) return;
    if (privacySignalEnabled()) {
      status.textContent = "瀏覽器已啟用隱私拒絕訊號；分析事件保持關閉。";
      return;
    }
    if (value === "granted") {
      status.textContent = "已同意匿名分析；可隨時改選拒絕。";
    } else if (value === "denied") {
      status.textContent = "已拒絕分析；不會送出分析事件。";
    } else {
      status.textContent = "目前尚未選擇。";
    }
  }

  function setConsent(value) {
    if (value !== "granted" && value !== "denied") return false;
    writeConsent(value);
    updateConsentStatus(value);
    if (value !== "granted" || privacySignalEnabled() || isPreviewMode()) return false;
    if (pageReadySent) return true;
    pageReadySent = track("page_ready");
    return pageReadySent;
  }

  function revealPreviewNotice() {
    const notice = document.getElementById("preview-notice");
    if (notice) notice.hidden = false;
  }

  function wireLineLinks() {
    document.querySelectorAll("[data-line-action]").forEach((link) => {
      const action = link.dataset.lineAction === "audit" ? "audit" : "apply";
      if (canNavigate()) link.href = buildLineUrl(action);
      link.addEventListener("click", (event) => {
        if (!canNavigate()) {
          event.preventDefault();
          revealPreviewNotice();
          return;
        }
        track(`${action}_line_start`, {
          surface: link.dataset.surface || "hero",
        });
      });
    });
  }

  function wireEligibilityCheck() {
    const output = document.getElementById("eligibility-result");
    document.querySelectorAll("[data-eligibility-choice]").forEach((button) => {
      button.addEventListener("click", () => {
        const choice = button.dataset.eligibilityChoice;
        document.querySelectorAll("[data-eligibility-choice]").forEach((item) => {
          item.setAttribute("aria-pressed", String(item === button));
        });
        if (output) {
          output.textContent = choice === "ready"
            ? "可以進入健檢：先整理四個去識別化數字，不需要顧客對話截圖。"
            : "先指定一位真人接手價格、退款與客訴，再評估試行。";
        }
        track("eligibility_check", { choice: choice });
      });
    });
  }

  function wireEvidenceLinks() {
    document.querySelectorAll("[data-evidence-id]").forEach((link) => {
      link.addEventListener("click", () => {
        track("evidence_open", { evidence_id: link.dataset.evidenceId || "" });
      });
    });
  }

  async function sharePage() {
    if (!canNavigate()) {
      revealPreviewNotice();
      return;
    }
    const shareData = {
      title: "POP MONSTER 城市共創試行夥伴",
      text: "把漏掉的詢問，變成預約、加購與回訪。",
      url: window.location.href,
    };
    try {
      if (navigator.share) {
        await navigator.share(shareData);
      } else if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(shareData.url);
      } else {
        return;
      }
      track("share_success", { surface: "final" });
    } catch (_error) {
      // User cancellation is not an error state and must not emit an event.
    }
  }

  function wireShare() {
    const button = document.querySelector("[data-share]");
    if (button) button.addEventListener("click", sharePage);
  }

  function wireConsent() {
    document.querySelectorAll("[data-consent]").forEach((button) => {
      button.addEventListener("click", () => setConsent(button.dataset.consent));
    });
    updateConsentStatus(storedConsent());
  }

  function renderDemo() {
    const config = window.PARTNER_DEMO_CONFIG;
    if (!document.body || document.body.dataset.demo !== "true" || !config) return;

    const scalarFields = new Set(["storeName", "city", "logo"]);
    document.querySelectorAll("[data-demo-field]").forEach((node) => {
      const field = node.dataset.demoField;
      if (!scalarFields.has(field) || typeof config[field] !== "string") return;
      node.textContent = config[field].slice(0, 80);
    });

    const list = document.getElementById("demo-service-list");
    const services = Array.isArray(config.services) ? config.services : [];
    const prices = Array.isArray(config.prices) ? config.prices : [];
    if (!list) return;
    services.slice(0, 6).forEach((service, index) => {
      const article = document.createElement("article");
      const number = document.createElement("span");
      const title = document.createElement("h3");
      const price = document.createElement("p");
      number.textContent = String(index + 1).padStart(2, "0");
      title.textContent = String(service).slice(0, 80);
      price.textContent = String(prices[index] || "現場評估").slice(0, 80);
      article.append(number, title, price);
      list.append(article);
    });
  }

  function init() {
    if (isPreviewMode()) revealPreviewNotice();
    wireLineLinks();
    wireEligibilityCheck();
    wireEvidenceLinks();
    wireShare();
    wireConsent();
    renderDemo();
    if (storedConsent() === "granted" && !privacySignalEnabled() && !isPreviewMode()) {
      setConsent("granted");
    }
  }

  window.PopPartner = Object.freeze({
    allowedEvents: EVENT_NAMES,
    allowedSources: ALLOWED_SOURCES,
    buildLineUrl: buildLineUrl,
    canNavigate: canNavigate,
    lineMessage: lineMessage,
    setConsent: setConsent,
    source: source,
    track: track,
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
