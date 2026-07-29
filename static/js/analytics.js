/**
 * Centropic analytics: Consent Mode v2 + GA4 events + Ads conversions.
 * Loads after Consent Mode default is declared in <head>.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "centropic_consent_v1";
  var cfg = window.__CENTROPIC_ANALYTICS__ || {};
  var gaId = cfg.ga4Id || "";
  var adsId = cfg.adsId || "";
  var adsenseClient = cfg.adsenseClient || "";
  var queued = Array.isArray(cfg.events) ? cfg.events.slice() : [];

  window.dataLayer = window.dataLayer || [];
  window.gtag =
    window.gtag ||
    function () {
      window.dataLayer.push(arguments);
    };

  function readConsent() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_e) {
      return null;
    }
  }

  function writeConsent(choice) {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          analytics: !!choice.analytics,
          ads: !!choice.ads,
          ts: Date.now(),
        })
      );
    } catch (_e) {
      /* ignore quota / private mode */
    }
  }

  function applyConsent(choice) {
    var analytics = !!choice.analytics;
    var ads = !!choice.ads;
    window.gtag("consent", "update", {
      analytics_storage: analytics ? "granted" : "denied",
      ad_storage: ads ? "granted" : "denied",
      ad_user_data: ads ? "granted" : "denied",
      ad_personalization: ads ? "granted" : "denied",
    });
    if (ads && adsenseClient) {
      loadAdSense(adsenseClient);
    }
  }

  function loadAdSense(clientId) {
    if (document.getElementById("centropic-adsense")) return;
    var s = document.createElement("script");
    s.id = "centropic-adsense";
    s.async = true;
    s.src =
      "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" +
      encodeURIComponent(clientId);
    s.crossOrigin = "anonymous";
    document.head.appendChild(s);
  }

  function track(name, params) {
    if (!name) return;
    var payload = Object.assign({}, params || {});
    var sendTo = payload.send_to;
    if (sendTo) {
      delete payload.send_to;
    }
    window.gtag("event", name, payload);
    if (sendTo) {
      window.gtag("event", "conversion", { send_to: sendTo, currency: payload.currency || "EUR" });
    }
  }

  function flushQueue() {
    while (queued.length) {
      var item = queued.shift();
      if (!item || !item.name) continue;
      track(item.name, item.params || {});
    }
  }

  function hideBanner() {
    var el = document.getElementById("cookie-consent");
    if (el) el.setAttribute("hidden", "hidden");
  }

  function showBanner() {
    var el = document.getElementById("cookie-consent");
    if (el) el.removeAttribute("hidden");
  }

  function bindBanner() {
    var accept = document.getElementById("cookie-consent-accept");
    var reject = document.getElementById("cookie-consent-reject");
    if (accept) {
      accept.addEventListener("click", function () {
        var choice = { analytics: true, ads: true };
        writeConsent(choice);
        applyConsent(choice);
        hideBanner();
        flushQueue();
      });
    }
    if (reject) {
      reject.addEventListener("click", function () {
        var choice = { analytics: false, ads: false };
        writeConsent(choice);
        applyConsent(choice);
        hideBanner();
        // Still flush: Consent Mode sends cookieless pings when denied.
        flushQueue();
      });
    }
  }

  function bindAnalyzeForms() {
    document.addEventListener("submit", function (ev) {
      var form = ev.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (
        form.classList.contains("js-analyze-form") ||
        form.getAttribute("action") === "/dashboard/analyze/confirmed" ||
        (form.getAttribute("action") || "").indexOf("analyze/confirmed") !== -1
      ) {
        track("analyze_start", { event_category: "analysis" });
      }
    });
  }

  function init() {
    bindBanner();
    bindAnalyzeForms();
    var existing = readConsent();
    if (existing) {
      applyConsent(existing);
      hideBanner();
      flushQueue();
      return;
    }
    // No choice yet: keep Consent Mode default (denied), show banner.
    if (gaId || adsId || adsenseClient) {
      showBanner();
    }
    // Queue stays until user chooses; cookieless measurement still works after reject.
  }

  window.centropicTrack = track;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
