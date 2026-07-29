(function (global) {
  "use strict";

  var SOURCE = "th3";
  var CONSENT_KEY = "ck_consent";
  var VARIANT_KEY = "systems_creator_cta_variant";
  var SESSION_KEY = "switchboard_v5_session_hash";
  var SESSION_PATTERN = /^[0-9a-f]{64}$/;
  var EVENT_FIELDS = Object.freeze({
    creator_impression: ["target"],
    creator_entry_click: ["surface", "target"],
    creator_tool_start: ["slug", "surface"],
  });
  var SURFACES = new Set([
    "systems_header",
    "systems_hero",
    "systems_section",
  ]);
  var TOOLS = new Set(["viral-breakdown", "ai-script", "rewrite"]);
  var TARGETS = new Set(["cta_a", "cta_b"]);
  var impressionSent = false;

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

  function consentGranted() {
    try {
      return global.localStorage.getItem(CONSENT_KEY) === "granted";
    } catch (_error) {
      return false;
    }
  }

  function endpoint() {
    return (
      document.querySelector('meta[name="systems-events"]')?.content || ""
    ).trim();
  }

  function bytesToHex(bytes) {
    return Array.from(bytes, function (byte) {
      return byte.toString(16).padStart(2, "0");
    }).join("");
  }

  function randomBytes(size) {
    try {
      var bytes = new Uint8Array(size);
      global.crypto.getRandomValues(bytes);
      return bytes;
    } catch (_error) {
      return null;
    }
  }

  function eventId() {
    try {
      if (typeof global.crypto.randomUUID === "function") {
        return global.crypto.randomUUID();
      }
    } catch (_error) {
      return "";
    }
    var bytes = randomBytes(16);
    if (!bytes) return "";
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    var hex = bytesToHex(bytes);
    return [
      hex.slice(0, 8),
      hex.slice(8, 12),
      hex.slice(12, 16),
      hex.slice(16, 20),
      hex.slice(20),
    ].join("-");
  }

  function sessionHash() {
    try {
      var current = global.sessionStorage.getItem(SESSION_KEY) || "";
      if (SESSION_PATTERN.test(current)) return current;
      var bytes = randomBytes(32);
      if (!bytes) return "";
      current = bytesToHex(bytes);
      global.sessionStorage.setItem(SESSION_KEY, current);
      return current;
    } catch (_error) {
      return "";
    }
  }

  function variant() {
    try {
      var current = global.sessionStorage.getItem(VARIANT_KEY);
      if (current === "a" || current === "b") return current;
      var bytes = randomBytes(1);
      current = bytes && bytes[0] % 2 === 1 ? "b" : "a";
      global.sessionStorage.setItem(VARIANT_KEY, current);
      return current;
    } catch (_error) {
      return "a";
    }
  }

  function cleanField(name, value) {
    if (typeof value !== "string") return null;
    if (name === "surface") return SURFACES.has(value) ? value : null;
    if (name === "slug") return TOOLS.has(value) ? value : null;
    if (name === "target") return TARGETS.has(value) ? value : null;
    return null;
  }

  function track(eventName, detail) {
    if (!Object.prototype.hasOwnProperty.call(EVENT_FIELDS, eventName)) {
      return false;
    }
    if (privacySignalEnabled() || !consentGranted()) return false;
    if (typeof global.navigator.sendBeacon !== "function") return false;

    var eventIdentifier = eventId();
    var anonymousSession = sessionHash();
    var eventEndpoint = endpoint();
    if (!eventIdentifier || !anonymousSession || !eventEndpoint) return false;

    var payload = {
      event_id: eventIdentifier,
      event: eventName,
      session_hash: anonymousSession,
      source: SOURCE,
      timestamp: new Date().toISOString(),
    };
    var values = detail || {};
    for (var field of EVENT_FIELDS[eventName]) {
      var clean = cleanField(field, values[field]);
      if (!clean) return false;
      payload[field] = clean;
    }

    try {
      return global.navigator.sendBeacon(
        eventEndpoint,
        JSON.stringify(payload),
      ) === true;
    } catch (_error) {
      return false;
    }
  }

  function sendImpression() {
    if (impressionSent) return false;
    var sent = track("creator_impression", {
      target: "cta_" + variant(),
    });
    if (sent) impressionSent = true;
    return sent;
  }

  function applyVariant() {
    var current = variant();
    document.querySelectorAll("[data-creator-cta]").forEach(function (cta) {
      var copy = current === "a" ? cta.dataset.ctaA : cta.dataset.ctaB;
      if (copy) cta.textContent = copy;
      cta.setAttribute("data-cta-variant", current);
    });
    if (document.documentElement) {
      document.documentElement.dataset.creatorCtaVariant = current;
    }
  }

  function installClicks() {
    document
      .querySelectorAll("[data-creator-entry], [data-creator-tool]")
      .forEach(function (link) {
        link.addEventListener("click", function () {
          if (Object.prototype.hasOwnProperty.call(link.dataset, "creatorTool")) {
            track("creator_tool_start", {
              slug: link.dataset.toolSlug,
              surface: link.dataset.surface,
            });
            return;
          }
          track("creator_entry_click", {
            surface: link.dataset.surface,
            target: "cta_" + variant(),
          });
        });
      });
  }

  function installConsent() {
    var panel = document.getElementById("systems-analytics-consent");
    if (!panel) return;
    if (privacySignalEnabled()) {
      panel.hidden = true;
      return;
    }
    var current = "";
    try {
      current = global.localStorage.getItem(CONSENT_KEY) || "";
    } catch (_error) {
      current = "";
    }
    panel.hidden = current === "granted" || current === "denied";
    document
      .querySelectorAll("[data-systems-consent]")
      .forEach(function (button) {
        button.addEventListener("click", function () {
          try {
            global.localStorage.setItem(
              CONSENT_KEY,
              button.dataset.systemsConsent === "granted"
                ? "granted"
                : "denied",
            );
            panel.hidden = true;
            sendImpression();
          } catch (_error) {
            panel.hidden = false;
          }
        });
      });
  }

  function init() {
    applyVariant();
    installClicks();
    installConsent();
    sendImpression();
  }

  global.PopMonsterSystemsFunnel = {
    init: init,
    track: track,
    variant: variant,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})(window);
