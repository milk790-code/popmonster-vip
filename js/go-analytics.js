(function (global) {
  "use strict";

  var MEASUREMENT_ID = "G-WTKLHW33D7";
  var CONSENT_KEY = "ck_consent";
  var ALLOWED_SOURCES = new Set([
    "direct",
    "business-card",
    "package-insert",
    "social",
    "legacy-worker",
    "facebook-free-first",
    "facebook-dont-pay",
    "facebook-connect",
    "line-free-first",
    "line-dont-pay",
    "line-connect",
    "threads-free-first",
    "threads-dont-pay",
    "threads-connect",
  ]);
  var ALLOWED_SURFACES = new Set([
    "hero",
    "directory",
    "router_result",
    "pop_card",
  ]);
  var EVENT_PARAMETERS = Object.freeze({
    page_ready: [],
    hero_cta: ["target"],
    route_stage_1: ["category"],
    route_result: ["slug"],
    service_select: ["slug", "surface"],
    line_start: ["slug", "surface"],
    site_start: ["slug", "surface"],
    share_success: [],
  });

  global.dataLayer = global.dataLayer || [];
  global.gtag =
    global.gtag ||
    function () {
      global.dataLayer.push(arguments);
    };
  global.gtag("consent", "default", {
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    analytics_storage: "denied",
  });

  function privacySignalEnabled() {
    var dnt =
      global.navigator.doNotTrack ||
      global.doNotTrack ||
      global.navigator.msDoNotTrack ||
      "";
    return (
      global.navigator.globalPrivacyControl === true ||
      dnt === "1" ||
      String(dnt).toLowerCase() === "yes"
    );
  }

  function isPreviewMode() {
    try {
      return (
        new URLSearchParams(global.location.search).get("preview") === "1" ||
        document.body?.dataset.preview === "true" ||
        Boolean(document.getElementById("preview-form"))
      );
    } catch (_error) {
      return false;
    }
  }

  function consentValue() {
    try {
      return global.localStorage.getItem(CONSENT_KEY) || "";
    } catch (_error) {
      return "";
    }
  }

  var FB_MATRIX_PATTERN = /^fb-[0-9a-f]{6}$/;

  function sourceValue() {
    try {
      var source = new URLSearchParams(global.location.search).get("src");
      if (ALLOWED_SOURCES.has(source)) return source;
      if (FB_MATRIX_PATTERN.test(source)) return source;
      return "direct";
    } catch (_error) {
      return "direct";
    }
  }

  function cleanValue(value) {
    if (typeof value === "string") {
      var trimmed = value.trim();
      return trimmed ? trimmed.slice(0, 64) : undefined;
    }
    if (typeof value === "number" && isFinite(value)) return value;
    if (typeof value === "boolean") return value;
    return undefined;
  }

  function cleanParameter(key, value) {
    if (key === "surface") {
      return ALLOWED_SURFACES.has(value) ? value : undefined;
    }
    return cleanValue(value);
  }

  function allowedParameters(eventName, parameters) {
    var clean = { source: sourceValue() };
    var source = parameters || {};
    EVENT_PARAMETERS[eventName].forEach(function (key) {
      var value = cleanParameter(key, source[key]);
      if (value !== undefined) clean[key] = value;
    });
    return clean;
  }

  function loadAnalytics() {
    try {
      if (isPreviewMode() || privacySignalEnabled() || consentValue() !== "granted") {
        return false;
      }
      if (document.querySelector('script[data-pm-analytics]')) return true;
      var script = document.createElement("script");
      script.async = true;
      script.dataset.pmAnalytics = "true";
      script.src =
        "https://www.googletagmanager.com/gtag/js?id=" +
        encodeURIComponent(MEASUREMENT_ID);
      document.head.appendChild(script);
      global.gtag("js", new Date());
      global.gtag("config", MEASUREMENT_ID, {
        send_page_view: false,
      });
      return true;
    } catch (_error) {
      return false;
    }
  }

  function track(eventName, parameters) {
    if (!Object.prototype.hasOwnProperty.call(EVENT_PARAMETERS, eventName)) {
      return false;
    }
    if (isPreviewMode() || privacySignalEnabled() || consentValue() !== "granted") {
      return false;
    }
    if (!loadAnalytics() || typeof global.gtag !== "function") return false;
    try {
      global.gtag("event", eventName, allowedParameters(eventName, parameters));
      return true;
    } catch (_error) {
      return false;
    }
  }

  function setConsent(value) {
    if (isPreviewMode()) return false;
    var granted = value === "granted";
    try {
      global.localStorage.setItem(CONSENT_KEY, granted ? "granted" : "denied");
    } catch (_error) {
      return false;
    }
    global.gtag("consent", "update", {
      analytics_storage: granted ? "granted" : "denied",
    });
    if (granted && loadAnalytics()) track("page_ready", {});
    return true;
  }

  function initConsentControls() {
    var panel = document.getElementById("go-analytics-consent");
    if (!panel) return;
    if (isPreviewMode() || privacySignalEnabled()) {
      panel.hidden = true;
      return;
    }

    var current = consentValue();
    panel.hidden = current === "granted" || current === "denied";
    if (current === "granted") {
      global.gtag("consent", "update", {
        analytics_storage: "granted",
      });
      loadAnalytics();
    }

    panel.querySelectorAll("[data-analytics-consent]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (setConsent(button.dataset.analyticsConsent)) panel.hidden = true;
      });
    });
  }

  global.PopMonsterGoAnalytics = {
    setConsent: setConsent,
    track: track,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initConsentControls, { once: true });
  } else {
    initConsentControls();
  }
})(window);
