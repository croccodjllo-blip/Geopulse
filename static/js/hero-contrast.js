/**
 * Landing hero contrast demo: Invisible-to-AI ↔ Centropic-Optimized.
 */
(function () {
  function init(root) {
    var tabs = root.querySelectorAll("[data-hero-state]");
    var panes = root.querySelectorAll("[data-pane]");
    if (!tabs.length || !panes.length) return;

    var reduce =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var autoTimer = null;
    var idx = 0;
    var states = ["before", "after"];

    function show(state) {
      idx = states.indexOf(state);
      if (idx < 0) idx = 0;
      tabs.forEach(function (btn) {
        var on = btn.getAttribute("data-hero-state") === state;
        btn.classList.toggle("is-active", on);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
      });
      panes.forEach(function (pane) {
        var on = pane.getAttribute("data-pane") === state;
        pane.classList.toggle("is-active", on);
        pane.hidden = !on;
      });
      root.setAttribute("data-active", state);
    }

    function armAuto() {
      if (reduce || autoTimer) return;
      autoTimer = window.setInterval(function () {
        show(states[(idx + 1) % states.length]);
      }, 4200);
    }

    function stopAuto() {
      if (!autoTimer) return;
      window.clearInterval(autoTimer);
      autoTimer = null;
    }

    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        stopAuto();
        show(btn.getAttribute("data-hero-state") || "before");
        armAuto();
      });
    });

    show("before");
    armAuto();
  }

  function boot() {
    document.querySelectorAll("[data-hero-contrast]").forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
