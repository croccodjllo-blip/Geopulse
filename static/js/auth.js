/**
 * Password visibility toggles + Accedi login popup.
 * Buttons: [data-password-toggle] with aria-controls pointing at the input id.
 * Popup: [data-login-open] opens #login-modal; [data-login-close] / backdrop / Escape close.
 */
(function () {
  function bindToggle(btn) {
    if (btn.dataset.bound === "1") return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("aria-controls");
      var input = id ? document.getElementById(id) : null;
      if (!input) {
        var wrap = btn.closest(".password-field");
        input = wrap ? wrap.querySelector("input") : null;
      }
      if (!input) return;
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Nascondi password" : "Mostra password");
      btn.textContent = show ? "Nascondi" : "Mostra";
    });
  }

  function getModal() {
    return document.querySelector("[data-login-modal]");
  }

  function loginAction(next) {
    var base = "/login";
    if (!next) return base;
    return base + "?next=" + encodeURIComponent(next);
  }

  function openLogin(opts) {
    var dialog = getModal();
    if (!dialog || typeof dialog.showModal !== "function") {
      window.location.href = loginAction(opts && opts.next);
      return;
    }
    var form = dialog.querySelector("[data-login-form]");
    if (form && opts && opts.next) {
      form.setAttribute("action", loginAction(opts.next));
    }
    if (!dialog.open) {
      dialog.showModal();
    }
    var email = document.getElementById("login-modal-email");
    if (email) {
      try {
        email.focus();
      } catch (e) {}
    }
  }

  function closeLogin() {
    var dialog = getModal();
    if (dialog && dialog.open) {
      dialog.close();
    }
  }

  function bindLoginUi() {
    document.querySelectorAll("[data-login-open]").forEach(function (el) {
      if (el.dataset.loginBound === "1") return;
      el.dataset.loginBound = "1";
      el.addEventListener("click", function (ev) {
        // Keep native navigation if the modal is missing (no-JS / old browsers).
        var dialog = getModal();
        if (!dialog || typeof dialog.showModal !== "function") return;
        ev.preventDefault();
        var next =
          el.getAttribute("data-login-next") ||
          (function () {
            try {
              var u = new URL(el.href, window.location.origin);
              return u.searchParams.get("next") || "";
            } catch (err) {
              return "";
            }
          })();
        openLogin({ next: next });
      });
    });

    document.querySelectorAll("[data-login-close]").forEach(function (el) {
      if (el.dataset.loginBound === "1") return;
      el.dataset.loginBound = "1";
      el.addEventListener("click", function () {
        closeLogin();
      });
    });

    var dialog = getModal();
    if (dialog && dialog.dataset.loginBound !== "1") {
      dialog.dataset.loginBound = "1";
      dialog.addEventListener("click", function (ev) {
        if (ev.target === dialog) closeLogin();
      });
      dialog.addEventListener("cancel", function () {
        // native Escape already closes; keep body scroll unlock via close event
      });
    }
  }

  function init() {
    document.querySelectorAll("[data-password-toggle]").forEach(bindToggle);
    bindLoginUi();
    var dialog = getModal();
    if (dialog && dialog.getAttribute("data-auto-open") === "1") {
      openLogin({});
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
