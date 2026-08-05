/**
 * Dashboard shell: mobile sidebar drawer + deep-link to report tabs.
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
    var sidebar = qs("#app-sidebar");
    var backdrop = qs("[data-sidebar-backdrop]");
    var toggle = qs("[data-sidebar-toggle]");
    if (!sidebar) return;
    shell.classList.toggle("sidebar-open", open);
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

  function activateDashTab(id) {
    if (!id) return;
    var btn = qs('.report-tabs__btn[data-tab="' + id + '"]');
    if (btn) btn.click();
    var panel = qs("#panel-" + id) || qs("#" + id);
    if (panel && typeof panel.scrollIntoView === "function") {
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

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setOpen(false);
    });

    // Close drawer after navigating on small screens
    qsa(".app-sidebar__link, .app-sidebar__sublink").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.matchMedia("(max-width: 960px)").matches) setOpen(false);
      });
    });

    // Hash → SoV / Edge / analyze sections
    var hash = (location.hash || "").replace(/^#/, "");
    if (hash === "panel-sov" || hash === "sov") activateDashTab("sov");
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
    }

    window.addEventListener("hashchange", function () {
      var h = (location.hash || "").replace(/^#/, "");
      if (h === "panel-sov" || h === "sov") activateDashTab("sov");
      else if (h === "analyze") {
        var p = qs("#analyze-panel");
        if (p) p.open = true;
      }
    });
  });
})();
