/**
 * Pack email dialog — open/close for dashboard deliverable actions.
 */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var dlg = document.querySelector("[data-pack-mail]");
    if (!dlg || typeof dlg.showModal !== "function") return;

    var input = dlg.querySelector("#pack-mail-to");

    function openMail() {
      if (dlg.open) return;
      dlg.showModal();
      if (input && !input.disabled) {
        try {
          input.focus();
          input.select();
        } catch (_) {
          /* ignore */
        }
      }
    }

    function closeMail() {
      if (dlg.open) dlg.close();
    }

    document.querySelectorAll("[data-pack-mail-open]").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        if (btn.disabled) return;
        openMail();
      });
    });

    dlg.querySelectorAll("[data-pack-mail-close]").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        closeMail();
      });
    });

    dlg.addEventListener("click", function (ev) {
      if (ev.target === dlg) closeMail();
    });
  });
})();
