/**
 * Panoramica command: filter saved domains from the URL field,
 * and keep competitor tokens in sync with the hidden textarea.
 */
(function () {
  function parseList(raw) {
    return String(raw || "")
      .split(/\r?\n|,/)
      .map(function (item) {
        return item.trim();
      })
      .filter(Boolean)
      .slice(0, 3);
  }

  function writeStore(store, list) {
    if (!store) return;
    store.value = list.join("\n");
    store.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function hostOf(value) {
    var raw = String(value || "").trim().toLowerCase();
    raw = raw.replace(/^https?:\/\//, "").replace(/^www\./, "");
    return raw.split("/")[0];
  }

  function initSites(root) {
    var query = root.querySelector("[data-audit-query]");
    var chips = root.querySelectorAll("[data-site-switch] .dash-sites__chip");
    if (!query || !chips.length) return;

    function applyFilter() {
      var raw = String(query.value || "").trim();
      var active = root.querySelector("[data-site-switch] .dash-sites__chip.is-active");
      var currentUrl = active ? String(active.getAttribute("data-url") || "").trim() : "";
      if (!raw || raw === currentUrl) {
        chips.forEach(function (chip) {
          chip.hidden = false;
        });
        return;
      }
      var q = hostOf(raw);
      chips.forEach(function (chip) {
        var domain = String(chip.getAttribute("data-domain") || "").toLowerCase();
        var url = String(chip.getAttribute("data-url") || "").toLowerCase();
        chip.hidden = !(domain.indexOf(q) !== -1 || url.indexOf(q) !== -1);
      });
    }

    query.addEventListener("input", applyFilter);
    applyFilter();
  }

  function initRivals(root) {
    var box = root.querySelector("[data-competitor-suggest]");
    if (!box) return;
    var store = box.querySelector("[data-rival-store], #competitors");
    var listEl = box.querySelector("[data-rival-chips]");
    var add = box.querySelector("[data-rival-add]");
    if (!store || !listEl) return;

    function current() {
      return parseList(store.value);
    }

    function render() {
      var items = current();
      listEl.textContent = "";
      items.forEach(function (item) {
        var li = document.createElement("li");
        var mark = document.createElement("strong");
        mark.textContent = item.replace(/^https?:\/\//, "");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dash-rivals__x";
        btn.setAttribute("aria-label", "Rimuovi");
        btn.textContent = "×";
        btn.addEventListener("click", function () {
          writeStore(
            store,
            current().filter(function (row) {
              return row !== item;
            })
          );
          render();
        });
        li.appendChild(mark);
        li.appendChild(btn);
        listEl.appendChild(li);
      });
      if (add) add.hidden = items.length >= 3;
    }

    function addValue(raw) {
      var next = String(raw || "").trim();
      if (!next) return;
      var items = current();
      if (items.length >= 3) return;
      var key = hostOf(next);
      var exists = items.some(function (row) {
        return hostOf(row) === key;
      });
      if (exists) return;
      items.push(next);
      writeStore(store, items);
      render();
    }

    if (!(store.value || "").trim()) {
      var seed = box.getAttribute("data-rival-seed");
      if (seed) writeStore(store, parseList(seed));
    }

    if (add) {
      add.addEventListener("keydown", function (ev) {
        if (ev.key !== "Enter") return;
        ev.preventDefault();
        addValue(add.value);
        add.value = "";
      });
    }

    box.addEventListener("centropic:competitors", render);
    store.addEventListener("change", render);
    render();
  }

  function boot() {
    document.querySelectorAll("[data-audit-command]").forEach(function (root) {
      initSites(root);
      initRivals(root);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
