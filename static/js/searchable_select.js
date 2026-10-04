/* Searchable selects. Every single-choice <select> becomes a text box with a filtered list. The real <select> stays in
   the page (hidden but still focusable for validation), so the form posts exactly what it posted before and every
   script that reads or sets select.value keeps working. Opt out with data-native on a select. */
(function () {
  var MAX_SHOWN = 200, uid = 0;
  var proto = HTMLSelectElement.prototype;
  var valueDesc = Object.getOwnPropertyDescriptor(proto, "value");
  var indexDesc = Object.getOwnPropertyDescriptor(proto, "selectedIndex");
  var panel = null, current = null;                     // the shared list and the widget that owns it

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) { n.className = cls; } if (text != null) { n.textContent = text; } return n; }
  function label(opt) { return (opt.textContent || "").replace(/\s+/g, " ").trim(); }

  function ensurePanel() {
    if (panel) { return panel; }
    panel = el("div", "ss-panel"); panel.id = "ss-panel"; panel.setAttribute("role", "listbox"); panel.hidden = true;
    panel.addEventListener("mousedown", function (e) { e.preventDefault(); });          // keep focus in the text box
    panel.addEventListener("click", function (e) {
      var li = e.target.closest("[data-i]");
      if (li && current) { current.pick(parseInt(li.getAttribute("data-i"), 10)); }
    });
    panel.addEventListener("mousemove", function (e) {
      var li = e.target.closest("[data-i]");
      if (li && current) { current.setActive(parseInt(li.getAttribute("data-i"), 10), false); }
    });
    document.body.appendChild(panel);
    return panel;
  }

  function cleanup(select) {                            // a cloned row carries a dead copy of the widget: unwrap it
    var wrap = select.parentNode;
    if (wrap && wrap.classList && wrap.classList.contains("ss")) { wrap.parentNode.insertBefore(select, wrap); wrap.remove(); }
    select.classList.remove("ss-native"); select.removeAttribute("aria-hidden"); select.removeAttribute("data-ss-tab");
    select.tabIndex = 0;
  }

  function enhance(select) {
    if (select.__ss || select.multiple || select.size > 1 || select.hasAttribute("data-native")) { return; }
    if (select.classList.contains("ss-native")) { cleanup(select); }

    var wrap = el("span", "ss"), input = el("input", "ss-input");
    input.type = "text"; input.autocomplete = "off"; input.spellcheck = false;
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false"); input.setAttribute("aria-haspopup", "listbox");
    select.classList.forEach(function (c) { if (c !== "ss-native") { input.classList.add(c); } });
    if (select.hasAttribute("aria-label")) { input.setAttribute("aria-label", select.getAttribute("aria-label")); }
    if (select.id) {
      var lab = document.querySelector('label[for="' + select.id + '"]');
      if (lab) { if (!lab.id) { lab.id = "ss-lab-" + (++uid); } input.setAttribute("aria-labelledby", lab.id); }
    }
    if (select.required) { input.setAttribute("aria-required", "true"); }

    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select); wrap.appendChild(input);
    select.classList.add("ss-native"); select.setAttribute("aria-hidden", "true"); select.tabIndex = -1;

    var w = { select: select, input: input, wrap: wrap, items: [], shown: [], at: -1, open: false, typed: false };
    select.__ss = w;

    function selectedText() { var o = select.options[select.selectedIndex]; return o && o.value !== "" ? label(o) : ""; }
    function placeholder() { var first = select.options[0]; return first && first.value === "" ? label(first) : "Select"; }
    function refresh() {
      input.value = selectedText(); input.placeholder = placeholder();
      input.disabled = select.disabled; input.title = input.value;
      wrap.style.visibility = select.style.visibility || "";
      input.tabIndex = select.hasAttribute("data-ss-tab") ? parseInt(select.getAttribute("data-ss-tab"), 10) : (select.style.visibility === "hidden" ? -1 : 0);
    }
    w.refresh = refresh;

    // anything that sets select.value or selectedIndex from a script updates the box too
    Object.defineProperty(select, "value", { configurable: true, get: function () { return valueDesc.get.call(this); }, set: function (v) { valueDesc.set.call(this, v); refresh(); } });
    Object.defineProperty(select, "selectedIndex", { configurable: true, get: function () { return indexDesc.get.call(this); }, set: function (v) { indexDesc.set.call(this, v); refresh(); } });

    function build() {                                    // read the options now: they can change (location filter, new rows)
      var items = [], groupLabel = "";
      Array.prototype.forEach.call(select.children, function (c) {
        if (c.tagName === "OPTGROUP") {
          groupLabel = c.label; var kids = [];
          Array.prototype.forEach.call(c.children, function (o) { if (!o.hidden && !o.disabled) { kids.push({ opt: o, text: label(o), group: groupLabel }); } });
          if (kids.length) { items.push({ head: groupLabel }); items = items.concat(kids); }
        } else if (c.tagName === "OPTION" && !c.hidden && !c.disabled) {
          items.push({ opt: c, text: label(c), group: "" });
        }
      });
      w.items = items;
    }

    function filtered() {
      var q = w.typed ? input.value.trim().toLowerCase() : "", words = q ? q.split(/\s+/) : [];
      var out = [], pendingHead = null;
      w.items.forEach(function (it) {
        if (it.head !== undefined) { pendingHead = it; return; }
        var hay = (it.text + " " + it.group).toLowerCase();
        if (words.every(function (x) { return hay.indexOf(x) !== -1; })) {
          if (pendingHead) { out.push(pendingHead); pendingHead = null; }
          out.push(it);
        }
      });
      return out;
    }

    function render() {
      var p = ensurePanel(); p.innerHTML = ""; var shown = filtered(), count = 0, n = 0;
      w.shown = [];
      shown.forEach(function (it) {
        if (it.head !== undefined) { p.appendChild(el("div", "ss-group", it.head)); return; }
        if (count >= MAX_SHOWN) { return; }
        count++;
        var li = el("div", "ss-opt" + (it.opt.value === "" ? " ss-none" : "") + (it.opt === select.options[select.selectedIndex] ? " ss-current" : ""), it.text || "\u2014");
        li.setAttribute("role", "option"); li.setAttribute("data-i", n); li.id = "ss-opt-" + n;
        w.shown.push(it); p.appendChild(li); n++;
      });
      if (!w.shown.length) { p.appendChild(el("div", "ss-empty", "Nothing matches \u201c" + input.value + "\u201d")); }
      else if (filtered().filter(function (x) { return x.head === undefined; }).length > MAX_SHOWN) { p.appendChild(el("div", "ss-empty", "Keep typing to narrow the list")); }
      var cur = w.shown.findIndex(function (it) { return it.opt === select.options[select.selectedIndex]; });
      w.setActive(w.typed || cur < 0 ? (w.shown.length ? 0 : -1) : cur, true);
    }

    function place() {
      var r = input.getBoundingClientRect(), p = ensurePanel();
      p.style.minWidth = Math.max(r.width, 200) + "px"; p.style.maxWidth = "min(32rem, 94vw)";
      p.style.left = Math.max(4, Math.min(r.left, window.innerWidth - p.offsetWidth - 4)) + "px";
      var below = window.innerHeight - r.bottom, h = Math.min(p.scrollHeight, 288);
      if (below < h + 12 && r.top > below) { p.style.top = "auto"; p.style.bottom = (window.innerHeight - r.top + 4) + "px"; p.style.maxHeight = Math.min(288, r.top - 12) + "px"; }
      else { p.style.bottom = "auto"; p.style.top = (r.bottom + 4) + "px"; p.style.maxHeight = Math.min(288, below - 12) + "px"; }
    }

    w.setActive = function (i, scroll) {
      w.at = i;
      var p = ensurePanel();
      p.querySelectorAll(".ss-opt").forEach(function (li) { li.setAttribute("aria-selected", "false"); });
      var li = i >= 0 ? p.querySelector('[data-i="' + i + '"]') : null;
      if (li) { li.setAttribute("aria-selected", "true"); input.setAttribute("aria-activedescendant", li.id); if (scroll !== false) { li.scrollIntoView({ block: "nearest" }); } }
    };
    w.show = function () {
      if (w.open || select.disabled) { return; }
      if (current && current !== w) { current.close(); }
      current = w; w.open = true; build(); render();
      var p = ensurePanel(); p.hidden = false; input.setAttribute("aria-expanded", "true"); input.setAttribute("aria-controls", "ss-panel");
      place(); w.setActive(w.at, true);
    };
    w.close = function (revert) {
      if (!w.open) { return; }
      w.open = false; w.typed = false; if (current === w) { current = null; ensurePanel().hidden = true; }
      input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant");
      if (revert !== false) { refresh(); }
    };
    w.pick = function (i) {
      var it = w.shown[i];
      if (!it) { return; }
      var changed = select.selectedIndex !== it.opt.index;
      indexDesc.set.call(select, it.opt.index);
      w.close(); refresh();
      if (changed) {
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    };

    input.addEventListener("focus", function () { input.select(); });
    input.addEventListener("click", function () { if (w.open) { w.close(); } else { input.select(); w.show(); } });
    input.addEventListener("input", function () { w.typed = true; if (!w.open) { w.show(); } else { render(); place(); } });
    input.addEventListener("keydown", function (e) {
      var k = e.key;
      if (k === "ArrowDown" || k === "ArrowUp") {
        e.preventDefault();
        if (!w.open) { w.show(); return; }
        var n = w.shown.length; if (!n) { return; }
        w.setActive(k === "ArrowDown" ? Math.min(w.at + 1, n - 1) : Math.max(w.at - 1, 0), true);
      } else if (k === "Enter") {
        if (w.open) { e.preventDefault(); e.stopPropagation(); if (w.at >= 0) { w.pick(w.at); } else { w.close(); } }
      } else if (k === "Escape") {
        if (w.open) { e.preventDefault(); e.stopPropagation(); w.close(); input.select(); }
      } else if (k === "Tab") {
        if (w.open && w.typed && w.at >= 0) { w.pick(w.at); } else { w.close(); }
      } else if (k === "Home" && w.open) { e.preventDefault(); w.setActive(0, true); }
      else if (k === "End" && w.open) { e.preventDefault(); w.setActive(w.shown.length - 1, true); }
    });
    input.addEventListener("blur", function () { setTimeout(function () { if (document.activeElement !== input) { w.close(); } }, 0); });

    select.addEventListener("focus", function () { input.focus(); });          // a label click, or a script calling select.focus()
    select.addEventListener("change", refresh);
    new MutationObserver(refresh).observe(select, { attributes: true, attributeFilter: ["disabled", "style", "data-ss-tab", "required"], childList: true, subtree: true });
    if (select.form) { select.form.addEventListener("reset", function () { setTimeout(refresh, 0); }); }
    refresh();
  }

  function scan(root) {
    if (root.nodeType !== 1) { return; }
    if (root.tagName === "SELECT") { enhance(root); }
    root.querySelectorAll && root.querySelectorAll("select").forEach(enhance);
  }

  window.SearchableSelect = { scan: scan, enhance: enhance };       // used by entry_table.js for the line it has just added

  window.addEventListener("resize", function () { if (current) { current.close(); } });
  window.addEventListener("scroll", function (e) {
    if (current && !(e.target.closest && e.target.closest("#ss-panel"))) { current.close(); }
  }, true);
  document.addEventListener("mousedown", function (e) {
    if (current && !e.target.closest(".ss") && !e.target.closest("#ss-panel")) { current.close(); }
  });

  document.addEventListener("DOMContentLoaded", function () {
    scan(document.body);
    new MutationObserver(function (list) {
      list.forEach(function (m) { m.addedNodes.forEach(scan); });
    }).observe(document.body, { childList: true, subtree: true });
  });
})();
