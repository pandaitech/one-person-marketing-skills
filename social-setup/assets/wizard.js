(function () {
  "use strict";

  var config = JSON.parse(document.getElementById("wizard-config").textContent);
  var storageKey = "pandaitech-social-setup:" + config.platform;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function loadDraft() {
    try {
      return JSON.parse(sessionStorage.getItem(storageKey) || "{}");
    } catch (e) {
      return {};
    }
  }

  function saveDraft(fields) {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(fields));
    } catch (e) { /* ignore, e.g. private mode */ }
  }

  function currentFields() {
    var fields = {};
    config.fields.forEach(function (f) {
      var input = document.getElementById("field-" + f.key);
      if (input) fields[f.key] = input.value.trim();
    });
    return fields;
  }

  function render() {
    document.getElementById("title").textContent = config.title;
    document.getElementById("subtitle").textContent = config.subtitle;

    var stepsEl = document.getElementById("steps");
    config.steps.forEach(function (step, i) {
      var card = el("div", { class: "step-card" });
      card.appendChild(el("h3", { text: step.heading }));
      card.appendChild(el("p", { text: step.body }));
      if (step.url) {
        var link = el("a", {
          class: "btn-link", href: step.url, target: "_blank", rel: "noopener",
          text: "Buka page ini" + (step.button_label ? " (" + step.button_label + ")" : ""),
        });
        card.appendChild(link);
      }
      stepsEl.appendChild(card);
    });

    var form = document.getElementById("fields-form");
    var draft = loadDraft();
    config.fields.forEach(function (f) {
      var field = el("div", { class: "field" });
      field.appendChild(el("label", { for: "field-" + f.key, text: f.label }));
      var input = el("input", {
        id: "field-" + f.key,
        type: f.type === "password" ? "password" : "text",
        placeholder: f.placeholder || "",
        autocomplete: "off",
      });
      if (draft[f.key]) input.value = draft[f.key];
      input.addEventListener("input", function () {
        var d = loadDraft();
        d[f.key] = input.value;
        saveDraft(d);
      });
      field.appendChild(input);
      form.appendChild(field);
    });

    document.getElementById("verify-btn").addEventListener("click", function () {
      runCheck("/api/verify", false);
    });
    document.getElementById("save-btn").addEventListener("click", function () {
      runCheck("/api/save", true);
    });
  }

  function runCheck(endpoint, isSave) {
    var fields = currentFields();
    saveDraft(fields);
    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: fields }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { showResults(data, isSave); })
      .catch(function () {
        showResults({ checks: [{ name: "Sambungan ke wizard", ok: false, hint: "Tak dapat hubungi wizard tempatan." }] }, false);
      });
  }

  function showResults(data, isSave) {
    var results = document.getElementById("results");
    var list = document.getElementById("checks-list");
    list.innerHTML = "";
    (data.checks || []).forEach(function (c) {
      var li = el("li", {});
      li.appendChild(el("span", { class: "dot " + (c.ok ? "ok" : "fail") }));
      var text = el("div", { class: "check-text" });
      text.appendChild(el("div", { class: "name", text: c.name }));
      if (!c.ok && c.hint) text.appendChild(el("div", { class: "fix", text: c.hint }));
      li.appendChild(text);
      list.appendChild(li);
    });
    results.hidden = false;

    var note = document.getElementById("result-note");
    if (isSave && data.saved) {
      note.textContent = "";
      document.getElementById("done-banner").hidden = false;
      try { sessionStorage.removeItem(storageKey); } catch (e) {}
    } else if (isSave && data.all_ok === false) {
      note.textContent = "Betulkan yang merah dulu sebelum simpan.";
    } else {
      note.textContent = "";
    }
  }

  render();
})();
