/**
 * Centropic Paddle.js checkout (Plus + credit top-ups).
 *
 * Expects window.__CENTROPIC_PADDLE__ from the page:
 *   { enabled, overlay, environment, clientToken, pricePlus, topupPrices,
 *     userId, email, successPlus, successTopup }
 *
 * Digital-service waiver: checkout buttons require
 * [data-digital-waiver-input] checked inside [data-checkout-gate].
 */
(function () {
  function cfg() {
    return window.__CENTROPIC_PADDLE__ || {};
  }

  function csrfToken() {
    var el = document.querySelector('input[name="csrf_token"]');
    return el ? el.value : "";
  }

  function gateFor(el) {
    return el.closest("[data-checkout-gate]") || document;
  }

  function waiverChecked(el) {
    var gate = gateFor(el);
    var input = gate.querySelector("[data-digital-waiver-input]");
    return !!(input && input.checked);
  }

  function syncWaiverMirrors(gate) {
    var input = gate.querySelector("[data-digital-waiver-input]");
    var on = !!(input && input.checked);
    gate.querySelectorAll("[data-waiver-mirror]").forEach(function (hidden) {
      hidden.value = on ? "y" : "";
    });
  }

  function requireWaiver(el) {
    if (waiverChecked(el)) {
      syncWaiverMirrors(gateFor(el));
      return true;
    }
    showCheckoutError(
      "Conferma l’erogazione immediata del servizio digitale (perdi il recesso di 14 giorni) prima di procedere al checkout."
    );
    var input = gateFor(el).querySelector("[data-digital-waiver-input]");
    if (input && typeof input.focus === "function") input.focus();
    return false;
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

  var _inited = false;
  function ensureInit() {
    if (_inited) return ready();
    _inited = init();
    return _inited;
  }

  function showCheckoutError(msg) {
    try {
      console.error("Paddle checkout:", msg);
      if (window.alert) {
        window.alert(msg);
      }
    } catch (_e) {
      /* ignore */
    }
  }

  function recordWaiver(kind, extra) {
    var endpoint =
      kind === "topup" ? "/crediti/checkout" : "/billing/checkout";
    var body = new URLSearchParams();
    body.set("csrf_token", csrfToken());
    body.set("accept_immediate_service", "y");
    body.set("overlay", "1");
    if (kind === "topup") {
      body.set("amount_cents", String((extra && extra.cents) || 0));
    } else {
      body.set("product", kind === "business" ? "business" : "plus");
    }
    return fetch(endpoint, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: body.toString(),
      credentials: "same-origin",
    })
      .then(function (res) {
        if (!res.ok) throw new Error("waiver_http_" + res.status);
        var ct = res.headers.get("content-type") || "";
        if (ct.indexOf("application/json") === -1) {
          // Redirect HTML flash page — treat as blocked.
          throw new Error("waiver_rejected");
        }
        return res.json();
      })
      .then(function (data) {
        if (!data || !data.ok) throw new Error("waiver_rejected");
        return data;
      });
  }

  function openItems(items, extra) {
    if (!ensureInit()) {
      showCheckoutError(
        "Checkout Paddle non pronto. Ricarica la pagina o contatta supporto."
      );
      return false;
    }
    var c = cfg();
    var opts = {
      items: items,
      customData: Object.assign(
        { centropic_user_id: String(c.userId || "") },
        (extra && extra.customData) || {}
      ),
      settings: {
        successUrl: (extra && extra.successUrl) || c.successPlus || window.location.href,
        allowLogout: false,
        displayMode: "overlay",
        theme: "dark",
        locale: "it",
      },
    };
    if (c.email) {
      opts.customer = { email: c.email };
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
        showCheckoutError(
          "Paddle: manca il Default payment link. In dashboard Paddle → Checkout → Checkout settings imposta https://centropic.ai poi riprova."
        );
        return;
      }
      showCheckoutError("Checkout non disponibile: " + text);
    }

    try {
      var opened = window.Paddle.Checkout.open(opts);
      if (opened && typeof opened.then === "function") {
        opened.catch(explainCheckoutFailure);
      }
      return true;
    } catch (e) {
      explainCheckoutFailure(e);
      return false;
    }
  }

  function openPlus() {
    var c = cfg();
    if (!c.pricePlus) return false;
    return openItems(
      [{ priceId: c.pricePlus, quantity: 1 }],
      { customData: { product: "plus" }, successUrl: c.successPlus }
    );
  }

  function openBusiness() {
    var c = cfg();
    if (!c.priceBusiness) return false;
    return openItems(
      [{ priceId: c.priceBusiness, quantity: 1 }],
      { customData: { product: "business" }, successUrl: c.successPlus }
    );
  }

  function openTopup(cents) {
    var c = cfg();
    var priceId = (c.topupPrices || {})[String(cents)];
    if (!priceId) return false;
    return openItems(
      [{ priceId: priceId, quantity: 1 }],
      {
        customData: { product: "topup", topup_cents: String(cents) },
        successUrl: c.successTopup,
      }
    );
  }

  function bindClicks() {
    document.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!(t instanceof Element)) return;
      var btn = t.closest("[data-paddle-checkout]");
      if (!btn) return;
      var kind = btn.getAttribute("data-paddle-checkout");
      if (!kind) return;
      ev.preventDefault();
      if (!requireWaiver(btn)) return;

      var run = function () {
        if (kind === "plus") {
          if (!openPlus()) {
            var form = btn.closest("form");
            if (form) form.submit();
          }
          return;
        }
        if (kind === "business") {
          if (!openBusiness()) {
            var formBiz = btn.closest("form");
            if (formBiz) formBiz.submit();
          }
          return;
        }
        if (kind === "topup") {
          var cents = parseInt(btn.getAttribute("data-paddle-cents") || "0", 10);
          if (!openTopup(cents)) {
            var form2 = btn.closest("form");
            if (form2) form2.submit();
          }
        }
      };

      recordWaiver(kind, {
        cents: parseInt(btn.getAttribute("data-paddle-cents") || "0", 10),
      })
        .then(run)
        .catch(function () {
          showCheckoutError(
            "Conferma il consenso all’erogazione immediata e riprova."
          );
        });
    });

    document.addEventListener("submit", function (ev) {
      var form = ev.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (!form.hasAttribute("data-checkout-form")) return;
      if (!requireWaiver(form)) {
        ev.preventDefault();
      }
    });

    document.querySelectorAll("[data-checkout-gate]").forEach(function (gate) {
      var input = gate.querySelector("[data-digital-waiver-input]");
      if (!input) return;
      input.addEventListener("change", function () {
        syncWaiverMirrors(gate);
      });
      syncWaiverMirrors(gate);
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
