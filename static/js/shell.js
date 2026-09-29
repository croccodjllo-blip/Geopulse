/**
 * Dashboard shell: collapsible sidebar (desktop) + mobile drawer + report views.
 */
(function () {
  var SIDEBAR_KEY = "centropic.sidebar";
  var MOBILE_MQ = "(max-width: 960px)";

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }
  function isMobile() {
    return window.matchMedia(MOBILE_MQ).matches;
  }
  function isHidden() {
    return document.documentElement.getAttribute("data-sidebar") === "hidden";
  }

  function persistDesktop(hidden) {
    document.documentElement.setAttribute("data-sidebar", hidden ? "hidden" : "open");
    try {
      localStorage.setItem(SIDEBAR_KEY, hidden ? "hidden" : "open");
    } catch (e) {}
  }

  function setMobileOpen(open) {
    var shell = document.body;
    var sidebar = qs("#app-sidebar");
    var backdrop = qs("[data-sidebar-backdrop]");
    if (!sidebar) return;
    shell.classList.toggle("sidebar-open", open);
    if (backdrop) {
      if (open) backdrop.removeAttribute("hidden");
      else backdrop.setAttribute("hidden", "");
    }
    document.documentElement.style.overflow = open ? "hidden" : "";
    syncToggle();
  }

  function syncToggle() {
    var toggle = qs("[data-sidebar-toggle]");
    if (!toggle) return;
    var expanded = isMobile()
      ? document.body.classList.contains("sidebar-open")
      : !isHidden();
    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    var openLabel = toggle.getAttribute("data-label-open") || "Open menu";
    var closeLabel = toggle.getAttribute("data-label-close") || "Hide menu";
    toggle.setAttribute("aria-label", expanded ? closeLabel : openLabel);
  }

  function onToggle() {
    if (isMobile()) {
      setMobileOpen(!document.body.classList.contains("sidebar-open"));
      return;
    }
    persistDesktop(!isHidden());
    syncToggle();
  }

  function onClose() {
    if (isMobile()) {
      setMobileOpen(false);
      return;
    }
    persistDesktop(true);
    syncToggle();
  }

  function animateSovBars() {
    qsa(".engine-bar").forEach(function (row) {
      row.classList.remove("is-animated");
      void row.offsetWidth;
      row.classList.add("is-animated");
    });
    qsa(".sov-columns").forEach(function (chart) {
      chart.classList.remove("is-animated");
      void chart.offsetWidth;
      chart.classList.add("is-animated");
    });
  }

  function activateReportView(id) {
    if (!id) return;
    qsa(".report-nav__view").forEach(function (link) {
      var on = link.getAttribute("data-tab") === id;
      link.classList.toggle("is-active", on);
      if (on) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
    qsa(".report-panel").forEach(function (panel) {
      var on = panel.getAttribute("data-panel") === id;
      panel.classList.toggle("is-active", on);
      panel.hidden = !on;
    });
    if (id === "sov") animateSovBars();
  }

  function activateDashTab(id, opts) {
    if (!id) return;
    activateReportView(id);
    var scroll = !opts || opts.scroll !== false;
    var panel = qs("#panel-" + id) || qs("#" + id);
    if (scroll && panel && typeof panel.scrollIntoView === "function") {
      setTimeout(function () {
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 60);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = qs("[data-sidebar-toggle]");
    var closeBtn = qs("[data-sidebar-close]");
    var backdrop = qs("[data-sidebar-backdrop]");

    if (toggle) {
      toggle.addEventListener("click", onToggle);
    }
    if (closeBtn) {
      closeBtn.addEventListener("click", onClose);
    }
    if (backdrop) {
      backdrop.addEventListener("click", function () {
        if (isMobile()) setMobileOpen(false);
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (isMobile()) setMobileOpen(false);
      else if (!isHidden()) {
        persistDesktop(true);
        syncToggle();
      }
    });

    qsa(".app-sidebar__link, .app-sidebar__sublink").forEach(function (link) {
      link.addEventListener("click", function () {
        if (isMobile()) setMobileOpen(false);
      });
    });

    window.addEventListener("resize", function () {
      if (!isMobile()) {
        document.body.classList.remove("sidebar-open");
        document.documentElement.style.overflow = "";
        var bd = qs("[data-sidebar-backdrop]");
        if (bd) bd.setAttribute("hidden", "");
      }
      syncToggle();
    });

    syncToggle();

    qsa(".report-nav__view[data-tab]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        var id = link.getAttribute("data-tab");
        activateReportView(id);
        if (id && history.replaceState) {
          history.replaceState(null, "", "#" + (id === "sov" ? "panel-sov" : "panel-score"));
        }
      });
    });

    // Hash → SoV / Score / Edge / analyze sections
    var hash = (location.hash || "").replace(/^#/, "");
    if (hash === "panel-score" || hash === "score") activateDashTab("score");
    else if (hash === "panel-sov" || hash === "sov") activateDashTab("sov");
    else if (hash === "edge-signals") {
      var edge = qs("#edge-signals");
      if (edge) edge.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (hash === "analyze") {
      var panel = qs("#analyze-panel");
      if (panel) panel.open = true;
      var form = qs("#analyze");
      if (form && typeof form.scrollIntoView === "function") {
        form.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } else if (qs("#panel-sov.is-active")) {
      animateSovBars();
    }

    window.addEventListener("hashchange", function () {
      var h = (location.hash || "").replace(/^#/, "");
      if (h === "panel-score" || h === "score") activateDashTab("score");
      else if (h === "panel-sov" || h === "sov") activateDashTab("sov");
      else if (h === "analyze") {
        var p = qs("#analyze-panel");
        if (p) p.open = true;
      }
    });
  });
})();
