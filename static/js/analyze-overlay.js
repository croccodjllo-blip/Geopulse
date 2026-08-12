/**
 * Analysis processing overlay: show while crawl/scoring jobs run.
 *
 * API:
 *   window.CentropicAnalyzeOverlay.show({ url, statusUrl, doneUrl, phase })
 *   window.CentropicAnalyzeOverlay.hide()
 *   window.CentropicAnalyzeOverlay.setPhase(phase, hint)
 *   window.CentropicAnalyzeOverlay.fail(message)
 */
(function () {
  var PHASES = ["queue", "crawl", "sov", "score", "pack"];
  var PHASE_INDEX = {
    pending: 0,
    queue: 0,
    in_coda: 0,
    running: 1,
    crawl: 1,
    in_esecuzione: 1,
    probe: 2,
    geo: 2,
    sov: 2,
    score: 3,
    pack: 4,
    persist: 4,
  };

  function el(root, sel) {
    return root.querySelector(sel);
  }

  function t(root, key, fallback) {
    return (root && root.getAttribute("data-" + key)) || fallback;
  }

  function Overlay(root) {
    this.root = root;
    this.title = el(root, "[data-overlay-title]");
    this.desc = el(root, "[data-overlay-desc]");
    this.urlEl = el(root, "[data-overlay-url]");
    this.eta = el(root, "[data-overlay-eta]");
    this.hint = el(root, "[data-overlay-hint]");
    this.bar = el(root, "[data-overlay-bar]");
    this.barTrack = el(root, "[data-overlay-bar-track]");
    this.percentEl = el(root, "[data-overlay-percent]");
    this.percentValue = el(root, "[data-overlay-percent-value]");
    this.ringProgress = el(root, "[data-overlay-ring-progress]");
    this.steps = root.querySelectorAll("[data-overlay-steps] [data-step]");
    this.errorBox = el(root, "[data-overlay-error]");
    this.errorText = el(root, "[data-overlay-error-text]");
    this.closeBtn = el(root, "[data-overlay-close]");
    this._timer = null;
    this._poll = null;
    this._stepClock = null;
    this._stepIdx = 0;
    this._progress = 0;
    this._displayPct = 0;
    this._serverPct = null;
    this._etaSeconds = null;
    this._ringLen = 326.73;
    this._doneUrl = "/dashboard";
    var self = this;
    if (this.ringProgress) {
      var len = Number(this.ringProgress.getAttribute("stroke-dasharray") || 0);
      if (len > 0) this._ringLen = len;
    }
    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", function () {
        self.hide();
      });
    }
    root.addEventListener("cancel", function (ev) {
      if (!root.classList.contains("is-error")) ev.preventDefault();
    });
  }

  Overlay.prototype.openDialog = function () {
    if (typeof this.root.showModal === "function") {
      if (!this.root.open) this.root.showModal();
    } else {
      this.root.setAttribute("open", "");
    }
    document.documentElement.classList.add("analyze-busy");
  };

  Overlay.prototype.hide = function () {
    this._stopTimers();
    if (typeof this.root.close === "function" && this.root.open) {
      this.root.close();
    } else {
      this.root.removeAttribute("open");
    }
    document.documentElement.classList.remove("analyze-busy");
  };

  Overlay.prototype._stopTimers = function () {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._stepClock) {
      clearInterval(this._stepClock);
      this._stepClock = null;
    }
    if (this._poll) {
      clearTimeout(this._poll);
      this._poll = null;
    }
  };

  Overlay.prototype.setUrl = function (url) {
    if (!this.urlEl) return;
    if (url) {
      this.urlEl.hidden = false;
      this.urlEl.textContent = url;
    } else {
      this.urlEl.hidden = true;
      this.urlEl.textContent = "";
    }
  };

  Overlay.prototype.setEta = function (label, seconds) {
    if (typeof seconds === "number" && !isNaN(seconds)) {
      this._etaSeconds = seconds;
    }
    if (!this.eta) return;
    if (label) {
      this.eta.hidden = false;
      var prefix = t(this.root, "eta-prefix", "Stima:");
      this.eta.textContent =
        label.indexOf("Stima") === 0 ||
        label.indexOf("About") === 0 ||
        label.indexOf("Complet") === 0 ||
        label.indexOf("Quasi") === 0 ||
        label.indexOf("Circa") === 0 ||
        label.indexOf(prefix) === 0
          ? label
          : prefix + " " + label;
    }
  };

  Overlay.prototype.setPercent = function (pct, opts) {
    opts = opts || {};
    var n = Math.round(Number(pct) || 0);
    if (opts.fromServer) {
      this._serverPct = n;
      this._progress = Math.max(this._progress, Math.min(n, 99));
    } else {
      // Local tick never jumps ahead of a known server value by more than a bit.
      if (typeof this._serverPct === "number") {
        n = Math.min(n, Math.max(this._serverPct + 3, this._serverPct));
      }
      this._progress = Math.max(0, Math.min(n, 99));
    }
    this._paintBar();
  };

  Overlay.prototype._paintBar = function () {
    var target = Math.max(0, Math.min(100, Math.round(this._progress)));
    // Ease the displayed number toward target for a smoother popup.
    if (this._displayPct < target) {
      this._displayPct = Math.min(target, this._displayPct + Math.max(1, Math.ceil((target - this._displayPct) / 4)));
    } else if (this._displayPct > target) {
      this._displayPct = target;
    }
    var shown = this._displayPct;
    if (this.bar) this.bar.style.width = shown + "%";
    if (this.percentValue) this.percentValue.textContent = String(shown);
    if (this.barTrack) this.barTrack.setAttribute("aria-valuenow", String(shown));
    if (this.percentEl) {
      this.percentEl.setAttribute(
        "aria-label",
        shown + "% " + t(this.root, "percent-label", "completato")
      );
    }
    if (this.ringProgress) {
      var offset = this._ringLen * (1 - shown / 100);
      this.ringProgress.style.strokeDashoffset = String(offset);
    }
  };

  Overlay.prototype.setPhase = function (phase, hint) {
    var idx = PHASE_INDEX[phase];
    if (typeof idx !== "number") idx = this._stepIdx;
    this._stepIdx = Math.max(this._stepIdx, idx);
    var active = PHASES[Math.min(this._stepIdx, PHASES.length - 1)];
    this.steps.forEach(function (li) {
      var key = li.getAttribute("data-step");
      var i = PHASES.indexOf(key);
      li.classList.toggle("is-done", i < PHASES.indexOf(active));
      li.classList.toggle("is-active", key === active);
    });
    if (hint && this.hint) this.hint.textContent = hint;
    // Nudge progress bar toward phase target when server percent is absent.
    if (typeof this._serverPct !== "number") {
      var target = 8 + this._stepIdx * 18;
      this.setPercent(Math.max(this._progress, Math.min(target, 88)));
    }
  };

  Overlay.prototype._tickProgress = function () {
    if (typeof this._serverPct === "number") {
      // Keep display easing toward server value; tiny local creep if stalled.
      if (this._progress < Math.min(96, this._serverPct + 2) && this._progress < 96) {
        this._progress += 0.08;
      }
      this._paintBar();
    } else if (this._progress < 92) {
      this._progress += Math.max(0.12, (92 - this._progress) * 0.018);
      this._paintBar();
    } else {
      this._paintBar();
    }
    if (typeof this._etaSeconds === "number" && this._etaSeconds > 5) {
      this._etaSeconds = Math.max(5, this._etaSeconds - 0.4);
    }
  };

  Overlay.prototype._cycleLocalSteps = function () {
    if (this._stepIdx < 3) {
      this._stepIdx += 1;
      this.setPhase(PHASES[this._stepIdx]);
    }
  };

  Overlay.prototype.fail = function (message) {
    this._stopTimers();
    this.root.classList.add("is-error");
    if (this.errorBox) this.errorBox.hidden = false;
    if (this.errorText) {
      this.errorText.textContent =
        message || t(this.root, "fail-fallback", "Analisi non riuscita.");
    }
    if (this.title) this.title.textContent = t(this.root, "fail-title", "Analisi interrotta");
    if (this.eta) this.eta.textContent = "";
    this._progress = this._displayPct;
    this._paintBar();
  };

  Overlay.prototype.show = function (opts) {
    opts = opts || {};
    this.root.classList.remove("is-error");
    if (this.errorBox) this.errorBox.hidden = true;
    this._doneUrl = opts.doneUrl || this.root.getAttribute("data-done-url") || "/dashboard";
    this.setUrl(opts.url || this.root.getAttribute("data-url") || "");
    if (this.title) {
      this.title.textContent =
        opts.title || t(this.root, "title", "Analisi in corso");
    }
    if (this.desc) {
      this.desc.textContent =
        opts.desc ||
        t(
          this.root,
          "desc",
          "Crawl, score e (se Plus) SoV measured sugli engine. Resta su questa pagina."
        );
    }
    this._stepIdx = 0;
    this._progress = 0;
    this._displayPct = 0;
    this._serverPct = null;
    this._etaSeconds = null;
    this.setPercent(0);
    this.setEta(
      opts.etaLabel || t(this.root, "eta-default", "Stima: 1–3 minuti con SoV measured")
    );
    this.setPhase(
      opts.phase || "pending",
      opts.hint ||
        t(
          this.root,
          "hint-default",
          "Di solito 30–90 s; con SoV measured fino a qualche minuto."
        )
    );
    this.openDialog();
    this._stopTimers();
    var self = this;
    this._timer = setInterval(function () {
      self._tickProgress();
    }, 280);
    this._stepClock = setInterval(function () {
      if (!self.root.classList.contains("is-error")) self._cycleLocalSteps();
    }, 18000);

    var statusUrl = opts.statusUrl || this.root.getAttribute("data-status-url");
    if (statusUrl) this._startPoll(statusUrl);
  };

  Overlay.prototype._applyServerProgress = function (data) {
    var pct = null;
    if (typeof data.percent === "number") pct = data.percent;
    else if (data.progress && typeof data.progress.percent === "number") pct = data.progress.percent;
    else if (data.progress && typeof data.progress.fraction === "number") {
      pct = Math.round(data.progress.fraction * 100);
    }
    if (pct !== null) {
      if (data.status === "done") pct = 100;
      else pct = Math.max(0, Math.min(99, pct));
      this.setPercent(pct, { fromServer: true });
    }
  };

  Overlay.prototype._startPoll = function (statusUrl) {
    var self = this;
    var tries = 0;
    var tick = async function () {
      tries += 1;
      try {
        var res = await fetch(statusUrl, { headers: { Accept: "application/json" } });
        var data = await res.json();
        if (data && data.ok) {
          if (data.url) self.setUrl(data.url);
          var phase = data.phase || data.status;
          if (data.progress && data.progress.phase) phase = data.progress.phase;
          self.setPhase(
            data.status === "pending"
              ? "pending"
              : data.status === "running"
                ? phase || "running"
                : phase,
            data.hint
          );
          if (data.eta_label) self.setEta(data.eta_label, data.eta_seconds);
          self._applyServerProgress(data);
          if (data.status === "running" && self._stepIdx < 1) self.setPhase("crawl", data.hint);
          if (data.status === "done") {
            self._stepIdx = 4;
            self.setPhase("pack", t(self.root, "hint-pack", "Completamento pack…"));
            self.setEta(t(self.root, "eta-done", "Completato"), 0);
            self._serverPct = 100;
            self._progress = 100;
            self._displayPct = 100;
            self._paintBar();
            self._stopTimers();
            if (data.emit_analyze_complete && typeof window.gtag === "function") {
              try {
                window.gtag("event", "analyze_complete", {
                  event_category: "analyze",
                  job_id: data.id || undefined,
                });
              } catch (e) { /* ignore */ }
            }
            var doneUrl = self._doneUrl || "/dashboard";
            var sep = doneUrl.indexOf("?") >= 0 ? "&" : "?";
            if (data.site_id) {
              doneUrl += sep + "site=" + encodeURIComponent(String(data.site_id));
              sep = "&";
            }
            // Prefer the completed job so dashboard can pin that site even if
            // site_id was late; bust bfcache/proxy with a nonce.
            if (data.id) {
              doneUrl += sep + "job=" + encodeURIComponent(String(data.id));
              sep = "&";
            }
            doneUrl += sep + "_r=" + encodeURIComponent(String(Date.now()));
            window.location.replace(doneUrl);
            return;
          }
          if (data.status === "error") {
            var info = data.error_info;
            var msg = info
              ? [info.title, info.message, info.hint].filter(Boolean).join(". ")
              : data.error || t(self.root, "error-fallback", "Errore durante l’analisi");
            self.fail(msg);
            return;
          }
        }
      } catch (e) {
        /* ignore transient */
      }
      var delay = tries < 20 ? 900 : tries < 90 ? 1600 : tries < 180 ? 4000 : 8000;
      if (tries === 90 && self.hint && !(typeof self._etaSeconds === "number")) {
        self.hint.textContent = t(
          self.root,
          "hint-long",
          "Analisi ancora in corso — puoi lasciare questa pagina aperta."
        );
      }
      self._poll = setTimeout(tick, delay);
    };
    // Poll faster early so the % feels live.
    self._poll = setTimeout(tick, 400);
  };

  function rememberPending(url) {
    try {
      sessionStorage.setItem(
        "centropic_analyze_overlay",
        JSON.stringify({ url: url || "", t: Date.now() })
      );
    } catch (e) {
      /* ignore */
    }
  }

  function consumePending() {
    try {
      var raw = sessionStorage.getItem("centropic_analyze_overlay");
      if (!raw) return null;
      sessionStorage.removeItem("centropic_analyze_overlay");
      var data = JSON.parse(raw);
      if (!data || !data.t || Date.now() - data.t > 120000) return null;
      return data;
    } catch (e) {
      return null;
    }
  }

  function init() {
    var root = document.querySelector("[data-analyze-overlay]");
    if (!root) return;
    var api = new Overlay(root);
    window.CentropicAnalyzeOverlay = api;

    if (root.getAttribute("data-auto-open") === "1") {
      consumePending();
      api.show({
        url: root.getAttribute("data-url"),
        statusUrl: root.getAttribute("data-status-url"),
        doneUrl: root.getAttribute("data-done-url"),
        phase: root.getAttribute("data-phase") || "pending",
        hint: t(root, "hint-live", "Aggiornamento avanzamento in tempo reale…"),
      });
    } else {
      // Dashboard landed without attrs but confirm just fired — open if job strip exists.
      var pending = consumePending();
      var jobStatus = document.getElementById("job-status");
      var statusUrl =
        (jobStatus && jobStatus.getAttribute("data-status-url")) ||
        (pending && root.getAttribute("data-status-url"));
      if (pending && statusUrl) {
        api.show({
          url: pending.url || (jobStatus && jobStatus.querySelector("code")
            ? jobStatus.querySelector("code").textContent
            : ""),
          statusUrl: statusUrl,
          doneUrl: root.getAttribute("data-done-url") || "/dashboard",
          phase: "pending",
          hint: t(root, "hint-started", "Analisi avviata — calcolo avanzamento…"),
        });
      }
    }

    document.addEventListener("submit", function (ev) {
      var form = ev.target;
      if (!(form instanceof HTMLFormElement)) return;
      var trigger =
        form.classList.contains("js-analyze-form") ||
        form.classList.contains("js-analyze-confirm") ||
        form.getAttribute("data-analyze-overlay-trigger") === "1";
      if (!trigger) return;
      var urlInput = form.querySelector('[name="url"]');
      var url = urlInput && urlInput.value ? urlInput.value : "";
      rememberPending(url);
      if (root.open) return;
      api.show({
        url: url,
        phase: "pending",
        hint: form.classList.contains("js-analyze-confirm")
          ? t(root, "hint-confirm", "Avvio analisi… a breve vedrai l’avanzamento in %.")
          : t(root, "hint-prepare", "Preparazione stima…"),
        etaLabel: t(root, "eta-prepare", "Stima in preparazione…"),
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
