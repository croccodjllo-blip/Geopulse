/**
 * Password visibility toggles on auth forms.
 * Buttons: [data-password-toggle] with aria-controls pointing at the input id.
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

  function init() {
    document.querySelectorAll("[data-password-toggle]").forEach(bindToggle);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
