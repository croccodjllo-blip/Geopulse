/**
 * Dashboard shell: mobile sidebar drawer + report view rail (SoV / Score).
 */
(function () {
  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function setOpen(open) {
    var shell = document.body;
    var sidebar = qs("#app-topbar") || qs("#app-sidebar");
    var backdrop = qs("[data-sidebar-backdrop]");
    var toggle = qs("[data-sidebar-toggle]");
    if (!sidebar) return;
    shell.classList.toggle("sidebar-open", open);
    shell.classList.toggle("topbar-open", open);
    if (backdrop) {
      if (open) backdrop.removeAttribute("hidden");
      else backdrop.setAttribute("hidden", "");
    }
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute(
        "aria-label",
        open ? (toggle.getAttribute("data-label-close") || "Close menu") : (toggle.getAttribute("data-label-open") || "Open menu")
      );
    }
    document.documentElement.style.overflow = open ? "hidden" : "";
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

  function applyDock(mode) {
    var next = mode === "rail" ? "rail" : "open";
    document.documentElement.setAttribute("data-dock", next);
    try {
      localStorage.setItem("centropic.dock", next);
    } catch (e) {}
    var pin = qs("[data-dock-pin]");
    if (pin) {
      var rail = next === "rail";
      pin.setAttribute("aria-pressed", rail ? "true" : "false");
      var openLbl = qs("[data-dock-pin-open]", pin);
      var railLbl = qs("[data-dock-pin-rail]", pin);
      if (openLbl) openLbl.hidden = rail;
      if (railLbl) railLbl.hidden = !rail;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = qs("[data-sidebar-toggle]");
    var closeBtn = qs("[data-sidebar-close]");
    var backdrop = qs("[data-sidebar-backdrop]");
    var pin = qs("[data-dock-pin]");
    applyDock(document.documentElement.getAttribute("data-dock") || "open");
    if (pin) {
      pin.addEventListener("click", function () {
        var cur = document.documentElement.getAttribute("data-dock") || "open";
        applyDock(cur === "rail" ? "open" : "rail");
      });
    }

    if (toggle) {
      toggle.addEventListener("click", function () {
        setOpen(!document.body.classList.contains("sidebar-open"));
      });
    }
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        setOpen(false);
      });
    }
    if (backdrop) {
      backdrop.addEventListener("click", function () {
        setOpen(false);
      });
    }

    var navToggle = qs("[data-nav-toggle]");
    var siteNav = qs("#site-nav");
    function setNavOpen(open) {
      document.body.classList.toggle("nav-open", open);
      if (navToggle) navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    }
    if (navToggle) {
      navToggle.addEventListener("click", function () {
        setNavOpen(!document.body.classList.contains("nav-open"));
      });
    }
    if (siteNav) {
      qsa("a, button", siteNav).forEach(function (el) {
        el.addEventListener("click", function () {
          if (window.matchMedia("(max-width: 720px)").matches) setNavOpen(false);
        });
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        setOpen(false);
        setNavOpen(false);
      }
    });

    // Close drawer after navigating on small screens
    qsa(".app-topbar__link, .app-sidebar__link, .app-sidebar__sublink").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.matchMedia("(max-width: 960px)").matches) setOpen(false);
      });
    });

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
      if (panel && "open" in panel) panel.open = true;
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
        if (p && "open" in p) p.open = true;
        if (p && typeof p.scrollIntoView === "function") {
          p.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    });
  });
})();
