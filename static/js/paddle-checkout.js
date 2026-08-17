/**
 * Centropic Paddle.js checkout (Plus + credit top-ups).
 *
 * Flow:
 *  1. Click [data-paddle-checkout] → waiver <dialog>
 *  2. Confirm → POST /billing/accept-immediate-service
 *  3. Paddle.Checkout.open (overlay) — works for new AND existing subscribers
 *     (card update / re-checkout; Paddle enforces product rules server-side)
 */
(function () {
  var pending = null;
  var _inited = false;

  function cfg() {
    return window.__CENTROPIC_PADDLE__ || {};
  }

  function dialogEl() {
    return document.querySelector("[data-digital-waiver-dialog]");
  }

  function csrfToken() {
    var dialog = dialogEl();
    var el =
      (dialog && dialog.querySelector("[data-digital-waiver-csrf]")) ||
      document.querySelector('input[name="csrf_token"]');
    return el ? el.value : "";
  }

  function setDialogBusy(busy, msg) {
    var dialog = dialogEl();
    if (!dialog) return;
    var confirmBtn = dialog.querySelector("[data-digital-waiver-confirm]");
    var status = dialog.querySelector("[data-digital-waiver-status]");
    if (confirmBtn) confirmBtn.disabled = !!busy;
    if (status) {
      if (msg) {
        status.hidden = false;
        status.textContent = msg;
      } else {
        status.hidden = true;
        status.textContent = "";
      }
    }
  }

  function showDialogError(msg) {
    var dialog = dialogEl();
    var err = dialog && dialog.querySelector("[data-digital-waiver-error]");
    if (err) {
      err.hidden = false;
      err.textContent = msg;
    } else {
      showCheckoutError(msg);
    }
  }

  function ready() {
    var c = cfg();
    return !!(c.enabled && c.overlay && c.clientToken && window.Paddle);
  }

  function init() {
    var c = cfg();
    if (!c.overlay || !c.clientToken || !window.Paddle) return false;
    try {
      if (c.environment === "sandbox") {
        window.Paddle.Environment.set("sandbox");
      }
      window.Paddle.Initialize({
        token: c.clientToken,
        eventCallback: function (ev) {
          if (!ev || !ev.name) return;
          if (ev.name === "checkout.completed") {
            var url =
              ev.data &&
              ev.data.custom_data &&
              ev.data.custom_data.product === "topup"
                ? c.successTopup
                : c.successPlus;
            if (url) window.location.href = url;
          }
        },
      });
      return true;
    } catch (e) {
      console.warn("Paddle init failed", e);
    }
    return false;
  }

  function ensureInit() {
    if (_inited) return ready();
    _inited = init();
    return _inited;
  }

  function showCheckoutError(msg) {
    try {
      console.error("Paddle checkout:", msg);
      if (window.alert) window.alert(msg);
    } catch (_e) {
      /* ignore */
    }
  }

  function recordWaiver() {
    var body = new URLSearchParams();
    body.set("csrf_token", csrfToken());
    body.set("accept_immediate_service", "y");
    return fetch("/billing/accept-immediate-service", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: body.toString(),
      credentials: "same-origin",
    }).then(function (res) {
      if (!res.ok) throw new Error("waiver_http_" + res.status);
      var ct = res.headers.get("content-type") || "";
      if (ct.indexOf("application/json") === -1) {
        throw new Error("waiver_rejected");
      }
      return res.json().then(function (data) {
        if (!data || !data.ok) throw new Error("waiver_rejected");
        return data;
      });
    });
  }

  function explainCheckoutFailure(err) {
    var detail =
      (err && (err.message || err.detail || err.code || err.error)) ||
      String(err || "");
    var text = String(detail);
    if (
      text.indexOf("default_checkout_url") !== -1 ||
      text.indexOf("payment link") !== -1 ||
      text.indexOf("transaction_default_checkout_url_not_set") !== -1
    ) {
      return (
        "Paddle: manca il Default payment link. In Paddle Dashboard → Checkout → " +
        "Checkout settings imposta https://centropic.ai poi riprova."
      );
    }
    if (!text || text === "undefined" || text === "null") {
      return "Checkout Paddle non disponibile. Riprova o contatta supporto.";
    }
    return "Checkout non disponibile: " + text;
  }

  function openItems(items, extra) {
    if (!ensureInit()) {
      showCheckoutError(
        "Checkout Paddle non pronto. Ricarica la pagina o contatta supporto."
      );
      return Promise.resolve(false);
    }
    var c = cfg();
    if (!c.userId) {
      showCheckoutError("Accedi per completare il pagamento.");
      return Promise.resolve(false);
    }
    var opts = {
      items: items,
      customData: Object.assign(
        { centropic_user_id: String(c.userId || "") },
        (extra && extra.customData) || {}
      ),
      settings: {
        successUrl:
          (extra && extra.successUrl) || c.successPlus || window.location.href,
        allowLogout: false,
        displayMode: "overlay",
        theme: "dark",
        locale: "it",
      },
    };
    if (c.email) {
      opts.customer = { email: c.email };
    }

    try {
      var opened = window.Paddle.Checkout.open(opts);
      if (opened && typeof opened.then === "function") {
        return opened
          .then(function () {
            return true;
          })
          .catch(function (err) {
            showCheckoutError(explainCheckoutFailure(err));
            return false;
          });
      }
      return Promise.resolve(true);
    } catch (e) {
      showCheckoutError(explainCheckoutFailure(e));
      return Promise.resolve(false);
    }
  }

  function openPlus() {
    var c = cfg();
    if (!c.pricePlus) {
      showCheckoutError("Prezzo Plus non configurato (PADDLE_PRICE_PLUS).");
      return Promise.resolve(false);
    }
    return openItems(
      [{ priceId: c.pricePlus, quantity: 1 }],
      { customData: { product: "plus" }, successUrl: c.successPlus }
    );
  }

  function openBusiness() {
    var c = cfg();
    if (!c.priceBusiness) {
      showCheckoutError("Business non in vendita self-serve.");
      return Promise.resolve(false);
    }
    return openItems(
      [{ priceId: c.priceBusiness, quantity: 1 }],
      { customData: { product: "business" }, successUrl: c.successPlus }
    );
  }

  function openTopup(cents) {
    var c = cfg();
    var priceId = (c.topupPrices || {})[String(cents)];
    if (!priceId) {
      showCheckoutError("Prezzo top-up non configurato.");
      return Promise.resolve(false);
    }
    return openItems(
      [{ priceId: priceId, quantity: 1 }],
      {
        customData: { product: "topup", topup_cents: String(cents) },
        successUrl: c.successTopup,
      }
    );
  }

  function runPendingCheckout() {
    if (!pending) return Promise.resolve(false);
    var kind = pending.kind;
    var cents = pending.cents;
    pending = null;
    if (kind === "plus") return openPlus();
    if (kind === "business") return openBusiness();
    if (kind === "topup") return openTopup(cents);
    return Promise.resolve(false);
  }

  function openWaiverDialog(kind, cents) {
    var dialog = dialogEl();
    pending = { kind: kind, cents: cents || 0 };

    if (!dialog || typeof dialog.showModal !== "function") {
      if (
        window.confirm(
          "Confermi l’erogazione immediata del servizio digitale e la perdita del recesso di 14 giorni?"
        )
      ) {
        setDialogBusy(true);
        recordWaiver()
          .then(runPendingCheckout)
          .catch(function () {
            showCheckoutError(
              "Conferma il consenso all’erogazione immediata e riprova."
            );
          })
          .finally(function () {
            setDialogBusy(false);
          });
      } else {
        pending = null;
      }
      return;
    }

    var input = dialog.querySelector("[data-digital-waiver-input]");
    var err = dialog.querySelector("[data-digital-waiver-error]");
    if (input) input.checked = false;
    if (err) {
      err.hidden = true;
      err.textContent = err.getAttribute("data-default-error") || err.textContent;
    }
    setDialogBusy(false);
    dialog.showModal();
    if (input && typeof input.focus === "function") input.focus();
  }

  function closeWaiverDialog() {
    var dialog = dialogEl();
    if (dialog && dialog.open) dialog.close();
  }

  function onConfirmWaiver() {
    var dialog = dialogEl();
    var input = dialog && dialog.querySelector("[data-digital-waiver-input]");
    var err = dialog && dialog.querySelector("[data-digital-waiver-error]");
    if (!input || !input.checked) {
      if (err) {
        err.hidden = false;
        err.textContent =
          err.getAttribute("data-default-error") ||
          "Spunta la casella per continuare.";
      }
      if (input && typeof input.focus === "function") input.focus();
      return;
    }
    if (err) err.hidden = true;
    if (!pending) {
      showDialogError("Sessione checkout scaduta. Chiudi e riprova.");
      return;
    }
    setDialogBusy(true, "Apertura checkout Paddle…");
    // Consent first (best-effort), then ALWAYS open Paddle if checkbox is on.
    // Previously a CSRF/referrer 400 on the waiver POST aborted Checkout.open.
    recordWaiver()
      .catch(function (e) {
        console.warn("waiver record failed; opening checkout anyway", e);
      })
      .then(function () {
        closeWaiverDialog();
        return runPendingCheckout();
      })
      .finally(function () {
        setDialogBusy(false);
      });
  }

  function bindClicks() {
    // Warm Paddle as soon as the page is interactive.
    ensureInit();

    document.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!(t instanceof Element)) return;

      if (t.closest("[data-digital-waiver-confirm]")) {
        ev.preventDefault();
        onConfirmWaiver();
        return;
      }
      if (t.closest("[data-digital-waiver-cancel]")) {
        ev.preventDefault();
        pending = null;
        closeWaiverDialog();
        return;
      }

      var btn = t.closest("[data-paddle-checkout]");
      if (!btn) return;
      var kind = btn.getAttribute("data-paddle-checkout");
      if (!kind) return;
      ev.preventDefault();
      var c = cfg();
      if (!c.userId) {
        window.location.href =
          "/login?next=" + encodeURIComponent("/prezzi#plus");
        return;
      }
      if (!ensureInit()) {
        showCheckoutError(
          "Checkout Paddle non pronto (script o client token). Ricarica o contatta supporto."
        );
        return;
      }
      var cents = parseInt(btn.getAttribute("data-paddle-cents") || "0", 10);
      openWaiverDialog(kind, cents);
    });

    document.addEventListener("submit", function (ev) {
      var form = ev.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (!form.hasAttribute("data-checkout-form")) return;
      var input = form.querySelector("[data-digital-waiver-input]");
      if (input && !input.checked) {
        ev.preventDefault();
        showCheckoutError(
          "Conferma l’erogazione immediata del servizio digitale prima di procedere."
        );
        if (typeof input.focus === "function") input.focus();
      }
    });
  }

  window.CentropicPaddle = {
    ready: ready,
    openPlus: openPlus,
    openBusiness: openBusiness,
    openTopup: openTopup,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindClicks);
  } else {
    bindClicks();
  }
})();
