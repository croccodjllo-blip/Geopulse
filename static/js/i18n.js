/**
 * Language switcher dropdown (header).
 */
(function () {
  function closeAll(except) {
    document.querySelectorAll("[data-lang-switch]").forEach(function (root) {
      if (except && root === except) return;
      var menu = root.querySelector("[data-lang-menu]");
      var btn = root.querySelector("[data-lang-toggle]");
      if (menu) menu.hidden = true;
      if (btn) btn.setAttribute("aria-expanded", "false");
    });
  }

  function init() {
    document.querySelectorAll("[data-lang-switch]").forEach(function (root) {
      var btn = root.querySelector("[data-lang-toggle]");
      var menu = root.querySelector("[data-lang-menu]");
      if (!btn || !menu) return;
      btn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var open = menu.hidden;
        closeAll();
        menu.hidden = !open;
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });
    document.addEventListener("click", function () {
      closeAll();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") closeAll();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
