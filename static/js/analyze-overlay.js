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
  var PHASES = ["queue", "crawl", "probe", "score", "pack"];
  var PHASE_INDEX = {
    pending: 0,
    queue: 0,
    in_coda: 0,
    running: 1,
    crawl: 1,
    in_esecuzione: 1,
    probe: 2,
    geo: 3,
    score: 3,
    pack: 4,
  };

  function el(root, sel) {
    return root.querySelector(sel);
  }

  function Overlay(root) {
    this.root = root;
    this.title = el(root, "[data-overlay-title]");
    this.desc = el(root, "[data-overlay-desc]");
    this.urlEl = el(root, "[data-overlay-url]");
    this.eta = el(root, "[data-overlay-eta]");
    this.hint = el(root, "[data-overlay-hint]");
    this.bar = el(root, "[data-overlay-bar]");
    this.steps = root.querySelectorAll("[data-overlay-steps] [data-step]");
    this.errorBox = el(root, "[data-overlay-error]");
    this.errorText = el(root, "[data-overlay-error-text]");
    this.closeBtn = el(root, "[data-overlay-close]");
    this._timer = null;
    this._poll = null;
    this._stepIdx = 0;
    this._progress = 8;
    this._etaSeconds = null;
    this._doneUrl = "/dashboard";
    var self = this;
    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", function () {
        self.hide();
      });
    }
    // Block Escape dismiss while running (dialog cancel)
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
      this.eta.textContent =
        label.indexOf("Stima") === 0 || label.indexOf("About") === 0 || label.indexOf("Complet") === 0
          ? label
          : "Stima: " + label;
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
    // Nudge progress bar toward phase target
    var target = 12 + this._stepIdx * 18;
    this._progress = Math.max(this._progress, Math.min(target, 88));
    this._paintBar();
  };

  Overlay.prototype._paintBar = function () {
    if (this.bar) this.bar.style.width = this._progress + "%";
  };

  Overlay.prototype._tickProgress = function () {
    // Slow asymptotic crawl toward 92% while waiting
    if (this._progress < 92) {
      this._progress += Math.max(0.15, (92 - this._progress) * 0.02);
      this._paintBar();
    }
    // Local countdown softens stale server ETA between polls
    if (typeof this._etaSeconds === "number" && this._etaSeconds > 5) {
      this._etaSeconds = Math.max(5, this._etaSeconds - 0.4);
    }
  };

  Overlay.prototype._cycleLocalSteps = function () {
    // While the job is still "running", never jump to Pack — that stage only
    // happens at the end and confused users when crawls/SoV took longer.
    // Cap visual progress at "score" until the server reports done.
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
      this.errorText.textContent = message || "Analisi non riuscita.";
    }
    if (this.title) this.title.textContent = "Analisi interrotta";
    if (this.eta) this.eta.textContent = "";
    if (this.bar) this.bar.style.width = "100%";
  };

  Overlay.prototype.show = function (opts) {
    opts = opts || {};
    this.root.classList.remove("is-error");
    if (this.errorBox) this.errorBox.hidden = true;
    this._doneUrl = opts.doneUrl || this.root.getAttribute("data-done-url") || "/dashboard";
    this.setUrl(opts.url || this.root.getAttribute("data-url") || "");
    if (this.title) {
      this.title.textContent =
        opts.title || this.root.getAttribute("data-title") || "Elaborazione in corso";
    }
    if (this.desc) {
      this.desc.textContent =
        opts.desc ||
        "Stiamo analizzando i segnali del dominio. Resta su questa pagina.";
    }
    this._stepIdx = 0;
    this._progress = 8;
    this._etaSeconds = null;
    this.setEta(opts.etaLabel || "Stima: 30–90 secondi");
    this.setPhase(opts.phase || "pending", opts.hint || "Di solito 30–90 secondi.");
    this.openDialog();
    this._stopTimers();
    var self = this;
    this._timer = setInterval(function () {
      self._tickProgress();
    }, 400);
    // Local step animation every ~18s while running (stops before Pack)
    this._stepClock = setInterval(function () {
      if (!self.root.classList.contains("is-error")) self._cycleLocalSteps();
    }, 18000);

    var statusUrl = opts.statusUrl || this.root.getAttribute("data-status-url");
    if (statusUrl) this._startPoll(statusUrl);
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
          if (data.progress && typeof data.progress.fraction === "number") {
            var pct = Math.round(8 + data.progress.fraction * 84);
            self._progress = Math.max(self._progress, Math.min(pct, 92));
            self._paintBar();
          }
          if (data.status === "running" && self._stepIdx < 1) self.setPhase("crawl", data.hint);
          if (data.status === "running") {
            // Keep pack step reserved for completion; nudge toward score only.
            if (self._stepIdx >= 4) self._stepIdx = 3;
            if (tries > 45 && self._stepIdx < 3) self.setPhase("score", data.hint);
          }
          if (data.status === "done") {
            self._stepIdx = 4;
            self.setPhase("pack", "Completamento pack…");
            self.setEta("Completato", 0);
            self._progress = 100;
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
            window.location.href = self._doneUrl;
            return;
          }
          if (data.status === "error") {
            var info = data.error_info;
            var msg = info
              ? [info.title, info.message, info.hint].filter(Boolean).join(". ")
              : data.error || "Errore durante l’analisi";
            self.fail(msg);
            return;
          }
        }
      } catch (e) {
        /* ignore transient */
      }
      // Keep polling until terminal status (long Plus crawls may exceed 4 minutes).
      // Back off slightly after 3 minutes to reduce load.
      var delay = tries < 90 ? 2000 : tries < 180 ? 4000 : 8000;
      if (tries === 90 && self.hint && !(typeof self._etaSeconds === "number")) {
        self.hint.textContent = "Analisi ancora in corso — puoi lasciare questa pagina aperta.";
      }
      self._poll = setTimeout(tick, delay);
    };
    self._poll = setTimeout(tick, 1200);
  };

  function init() {
    var root = document.querySelector("[data-analyze-overlay]");
    if (!root) return;
    var api = new Overlay(root);
    window.CentropicAnalyzeOverlay = api;

    if (root.getAttribute("data-auto-open") === "1") {
      api.show({
        url: root.getAttribute("data-url"),
        statusUrl: root.getAttribute("data-status-url"),
        doneUrl: root.getAttribute("data-done-url"),
        phase: root.getAttribute("data-phase") || "pending",
      });
    }

    // Interim overlay on submit (no statusUrl until redirect with ?job=).
    // Skip if another handler already opened with statusUrl.
    document.addEventListener("submit", function (ev) {
      var form = ev.target;
      if (!(form instanceof HTMLFormElement)) return;
      var trigger =
        form.classList.contains("js-analyze-form") ||
        form.classList.contains("js-analyze-confirm") ||
        form.getAttribute("data-analyze-overlay-trigger") === "1";
      if (!trigger) return;
      if (root.open) return;
      var urlInput = form.querySelector('[name="url"]');
      var url = urlInput && urlInput.value ? urlInput.value : "";
      api.show({
        url: url,
        phase: "pending",
        hint: "Invio richiesta… il worker partirà a breve.",
        etaLabel: "Stima in preparazione…",
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
