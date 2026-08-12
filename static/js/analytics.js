/**
 * Centropic analytics: Consent Mode v2 + GA4 events + Ads conversions.
 * Granular consent (analytics vs ads) + always-reachable "Gestisci consenso".
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
      window.gtag("event", "conversion", {
        send_to: sendTo,
        currency: payload.currency || "EUR",
      });
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

  function showBanner(opts) {
    var el = document.getElementById("cookie-consent");
    if (!el) return;
    el.removeAttribute("hidden");
    var panel = document.getElementById("cookie-consent-customize");
    var saveBtn = document.getElementById("cookie-consent-save");
    var customizeBtn = document.getElementById("cookie-consent-customize-btn");
    var showCustom = opts && opts.customize;
    if (panel) {
      if (showCustom) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "hidden");
    }
    if (saveBtn) {
      if (showCustom) saveBtn.removeAttribute("hidden");
      else saveBtn.setAttribute("hidden", "hidden");
    }
    if (customizeBtn) {
      if (showCustom) customizeBtn.setAttribute("hidden", "hidden");
      else customizeBtn.removeAttribute("hidden");
    }
    if (showCustom) {
      syncTogglesFromStored();
    }
  }

  function syncTogglesFromStored() {
    var existing = readConsent() || { analytics: false, ads: false };
    var a = document.getElementById("cookie-consent-analytics");
    var d = document.getElementById("cookie-consent-ads");
    if (a) a.checked = !!existing.analytics;
    if (d) d.checked = !!existing.ads;
  }

  function saveChoice(choice) {
    writeConsent(choice);
    applyConsent(choice);
    hideBanner();
    flushQueue();
  }

  function bindBanner() {
    var accept = document.getElementById("cookie-consent-accept");
    var reject = document.getElementById("cookie-consent-reject");
    var customizeBtn = document.getElementById("cookie-consent-customize-btn");
    var saveCustom = document.getElementById("cookie-consent-save");

    if (accept) {
      accept.addEventListener("click", function () {
        saveChoice({ analytics: true, ads: true });
      });
    }
    if (reject) {
      reject.addEventListener("click", function () {
        saveChoice({ analytics: false, ads: false });
      });
    }
    if (customizeBtn) {
      customizeBtn.addEventListener("click", function () {
        showBanner({ customize: true });
      });
    }
    if (saveCustom) {
      saveCustom.addEventListener("click", function () {
        var a = document.getElementById("cookie-consent-analytics");
        var d = document.getElementById("cookie-consent-ads");
        saveChoice({
          analytics: !!(a && a.checked),
          ads: !!(d && d.checked),
        });
      });
    }

    document.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!(t instanceof Element)) return;
      var btn = t.closest("[data-cookie-manage]");
      if (!btn) return;
      ev.preventDefault();
      showBanner({ customize: true });
    });
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
    // No choice yet: keep Consent Mode default (denied), show banner if trackers configured.
    if (gaId || adsId || adsenseClient) {
      showBanner({ customize: false });
    }
  }

  window.centropicTrack = track;
  window.centropicOpenCookiePrefs = function () {
    showBanner({ customize: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
