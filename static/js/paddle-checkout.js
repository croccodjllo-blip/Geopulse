/**
 * Centropic Paddle.js checkout (Plus + credit top-ups).
 *
 * Expects window.__CENTROPIC_PADDLE__ from the page:
 *   { enabled, overlay, environment, clientToken, pricePlus, topupPrices,
 *     userId, email, successPlus, successTopup }
 */
(function () {
  function cfg() {
    return window.__CENTROPIC_PADDLE__ || {};
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
            var url = (ev.data && ev.data.custom_data && ev.data.custom_data.product === "topup")
              ? c.successTopup
              : c.successPlus;
            if (url) window.location.href = url;
          }
        },
      });
      return true;
    } catch (e) {
      console.warn("Paddle init failed", e);
      return false;
    }
  }

  var _inited = false;
  function ensureInit() {
    if (_inited) return ready();
    _inited = init();
    return _inited;
  }

  function openItems(items, extra) {
    if (!ensureInit()) return false;
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
      },
    };
    if (c.email) {
      opts.customer = { email: c.email };
    }
    window.Paddle.Checkout.open(opts);
    return true;
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
      if (kind === "plus") {
        ev.preventDefault();
        if (!openPlus()) {
          var form = btn.closest("form");
          if (form) form.submit();
        }
        return;
      }
      if (kind === "business") {
        ev.preventDefault();
        if (!openBusiness()) {
          var formBiz = btn.closest("form");
          if (formBiz) formBiz.submit();
        }
        return;
      }
      if (kind === "topup") {
        ev.preventDefault();
        var cents = parseInt(btn.getAttribute("data-paddle-cents") || "0", 10);
        if (!openTopup(cents)) {
          var form2 = btn.closest("form");
          if (form2) form2.submit();
        }
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
