/**
 * Plus: auto-suggest competitor domains into the analyze form textarea.
 */
(function () {
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    var input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : "";
  }

  function initRoot(root) {
    var btn = root.querySelector("[data-competitor-suggest-btn]");
    var input = root.querySelector("[data-competitor-suggest-input], #competitors");
    var status = root.querySelector("[data-competitor-suggest-status]");
    var form = root.closest("form");
    var urlInput = form ? form.querySelector("#url, input[name='url']") : null;
    var endpoint = root.getAttribute("data-suggest-url");
    if (!btn || !input || !endpoint) return;

    var busy = false;
    var lastUrl = "";

    function setStatus(text, isError) {
      if (!status) return;
      if (!text) {
        status.hidden = true;
        status.textContent = "";
        return;
      }
      status.hidden = false;
      status.textContent = text;
      status.classList.toggle("is-error", !!isError);
    }

    async function suggest(force) {
      if (busy) return;
      var url = (urlInput && urlInput.value ? urlInput.value : "").trim();
      if (!url) {
        setStatus("Inserisci prima l’URL del sito.", true);
        return;
      }
      if (!force && (input.value || "").trim()) {
        return;
      }
      if (!force && url === lastUrl && (input.value || "").trim()) {
        return;
      }
      busy = true;
      btn.disabled = true;
      setStatus("Cerco competitor…");
      try {
        var res = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken(),
          },
          credentials: "same-origin",
          body: JSON.stringify({ url: url }),
        });
        var data = await res.json().catch(function () {
          return {};
        });
        if (!res.ok || !data.ok) {
          var err = (data && data.error) || "suggest_failed";
          setStatus("Suggerimento non disponibile (" + err + ").", true);
          return;
        }
        var list = data.competitors || [];
        if (!list.length) {
          setStatus("Nessun competitor affidabile trovato. Inseriscili a mano.", true);
          return;
        }
        input.value = list.join("\n");
        lastUrl = url;
        setStatus("Inseriti " + list.length + " competitor (" + (data.source || "auto") + ").");
        root.dispatchEvent(new CustomEvent("centropic:competitors", { bubbles: true }));
      } catch (e) {
        setStatus("Errore di rete nel suggerimento.", true);
      } finally {
        busy = false;
        btn.disabled = false;
      }
    }

    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      suggest(true);
    });

    if (urlInput) {
      urlInput.addEventListener("blur", function () {
        if ((input.value || "").trim()) return;
        if (!(urlInput.value || "").trim()) return;
        suggest(false);
      });
    }
  }

  function boot() {
    document.querySelectorAll("[data-competitor-suggest]").forEach(initRoot);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
