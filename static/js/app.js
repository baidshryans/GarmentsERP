/* Theme toggle and menu behaviour. The no-flash bootstrap lives inline in <head> (see partials/theme_boot.html). */
(function () {
  var root = document.documentElement;
  var SMALL = window.matchMedia("(max-width: 960px)");
  var TOP_FITS = window.matchMedia("(min-width: 1181px)");   // below this the top menu is too crowded and becomes the drawer
  var MOBILE = { get matches() { return root.hasAttribute("data-drawer"); } };
  var W_MIN = 196, W_MAX = 440, W_DEFAULT = 248;

  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* storage blocked */ } }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }

  // ---- theme ----
  function current() { return root.getAttribute("data-theme") === "dark" ? "dark" : "light"; }
  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    store("theme", theme);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });
  }

  // ---- menu ----
  var OPEN_KEY = "navOpen";
  function computeDrawer() {
    var on = SMALL.matches || (root.getAttribute("data-nav") === "top" && !TOP_FITS.matches);
    if (on) { root.setAttribute("data-drawer", ""); } else { root.removeAttribute("data-drawer"); setDrawerState(false); }
  }
  function navMode() { return root.getAttribute("data-nav") === "top" ? "top" : "side"; }
  function collapsed() { return root.getAttribute("data-collapsed") === "1"; }
  // Drop-downs: the top menu, or the icon-only side menu. On small screens the menu is a drawer with plain accordions.
  function popover() { return !MOBILE.matches && (navMode() === "top" || collapsed()); }
  function groups() { return document.querySelectorAll("#main-nav .nav-group"); }
  function readOpen() { try { return JSON.parse(load(OPEN_KEY) || "{}"); } catch (e) { return {}; } }

  function closeAll(except) { groups().forEach(function (g) { if (g !== except) { g.open = false; } }); }

  function place(g) {                       // fixed-position a drop-down next to its trigger
    var sum = g.querySelector("summary"), items = g.querySelector(".nav-items");
    if (!sum || !items) { return; }
    var r = sum.getBoundingClientRect();
    items.style.left = (navMode() === "top" ? r.left : r.right + 8) + "px";
    items.style.top = (navMode() === "top" ? r.bottom + 4 : r.top) + "px";
    var over = items.getBoundingClientRect().right - window.innerWidth + 8;   // keep it on screen
    if (over > 0) { items.style.left = Math.max(8, parseFloat(items.style.left) - over) + "px"; }
  }

  function syncGroups() {
    var saved = readOpen();
    document.querySelectorAll("#main-nav .nav-sub").forEach(function (box) {      // remembered sections; the page in view always opens its own
      var key = box.getAttribute("data-sub");
      var on = !!box.querySelector("[aria-current]") || saved[key] === true || (box.classList.contains("open") && saved[key] !== false);
      box.classList.toggle("open", on);
      box.querySelector(".nav-sub-toggle").setAttribute("aria-expanded", on ? "true" : "false");
    });
    groups().forEach(function (g) {
      var key = g.getAttribute("data-group");
      if (popover()) { g.open = false; }
      else if (MOBILE.matches) { g.open = g.classList.contains("active"); }
      else { g.open = g.classList.contains("active") || saved[key] === true; }
      var items = g.querySelector(".nav-items");
      if (items && !popover()) { items.style.left = ""; items.style.top = ""; }
    });
  }

  function syncButtons() {
    document.querySelectorAll("[data-nav-toggle]").forEach(function (b) {
      b.setAttribute("aria-pressed", navMode() === "top" ? "true" : "false");
      var text = navMode() === "top" ? "Move the menu to the side" : "Move the menu to the top";
      var l = b.querySelector(".nav-label");
      if (l) { l.textContent = text; } else { b.setAttribute("aria-label", text); b.setAttribute("data-tip", text); }
    });
    document.querySelectorAll("[data-nav-collapse]").forEach(function (b) {
      b.setAttribute("aria-pressed", collapsed() ? "true" : "false");
      b.setAttribute("aria-label", collapsed() ? "Expand the menu" : "Collapse the menu");
      b.setAttribute("title", collapsed() ? "Expand the menu" : "Collapse the menu");
      var l = b.querySelector(".nav-label");
      if (l) { l.textContent = collapsed() ? "Expand menu" : "Collapse menu"; }
    });
  }

  function setNav(mode) {
    root.setAttribute("data-nav", mode);
    store("nav", mode);
    computeDrawer(); syncButtons(); syncGroups(); syncResizer();
  }
  function setCollapsed(on) {
    if (on) { root.setAttribute("data-collapsed", "1"); } else { root.removeAttribute("data-collapsed"); }
    store("navCollapsed", on ? "1" : "0");
    syncButtons(); syncGroups(); syncResizer();
  }
  function setDrawerState(open) { root.classList.toggle("nav-open", open); }
  function setDrawer(open) {
    root.classList.toggle("nav-open", open);
    document.querySelectorAll("[data-nav-open]").forEach(function (b) {
      b.setAttribute("aria-expanded", open ? "true" : "false");
      b.setAttribute("aria-label", open ? "Close the menu" : "Open the menu");
    });
  }

  document.addEventListener("toggle", function (e) {
    var g = e.target;
    if (!g.classList) { return; }
    if (g.classList.contains("nav-group")) {
      if (popover()) {
        if (g.open) { closeAll(g); place(g); }
      } else if (!MOBILE.matches) {
        var map = readOpen();
        map[g.getAttribute("data-group")] = g.open;
        store(OPEN_KEY, JSON.stringify(map));
      }
    } else if (g.classList.contains("user-menu") && g.open) {
      closeAll();
    }
  }, true);

  document.addEventListener("click", function (e) {
    var sub = e.target.closest(".nav-sub-toggle");
    if (sub && !popover()) {                     // fold or unfold a section inside a group
      var box = sub.closest(".nav-sub"), on = !box.classList.contains("open");
      box.classList.toggle("open", on); sub.setAttribute("aria-expanded", on ? "true" : "false");
      var m = readOpen(); m[box.getAttribute("data-sub")] = on; store(OPEN_KEY, JSON.stringify(m));
      return;
    }
    if (e.target.closest("[data-cmdk-open]")) { openJump(); return; }
    if (e.target.closest("[data-theme-toggle]")) { applyTheme(current() === "dark" ? "light" : "dark"); return; }
    if (e.target.closest("[data-nav-toggle]")) { setNav(navMode() === "top" ? "side" : "top"); return; }
    if (e.target.closest("[data-nav-collapse]")) { setCollapsed(!collapsed()); return; }
    if (e.target.closest("[data-nav-open]")) { setDrawer(!root.classList.contains("nav-open")); return; }
    if (e.target.closest("[data-nav-close]")) { setDrawer(false); return; }
    if (MOBILE.matches && e.target.closest("#main-nav a")) { setDrawer(false); }
    if (popover() && !e.target.closest("#main-nav")) { closeAll(); }
    var um = document.querySelector(".user-menu");
    if (um && um.open && !e.target.closest(".user-menu")) { um.open = false; }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") { return; }
    if (popover()) { closeAll(); }
    setDrawer(false);
    var um = document.querySelector(".user-menu");
    if (um && um.open) { um.open = false; um.querySelector("summary").focus(); }
  });

  window.addEventListener("resize", function () { groups().forEach(function (g) { if (popover() && g.open) { place(g); } }); });
  function onViewport() { setDrawer(false); computeDrawer(); syncGroups(); syncResizer(); }
  SMALL.addEventListener("change", onViewport);
  TOP_FITS.addEventListener("change", onViewport);

  // ---- resizing the side menu: drag the right edge, arrow keys, double-click to reset ----
  var resizer = null;
  function width() { return parseInt(getComputedStyle(root).getPropertyValue("--sidebar-w"), 10) || W_DEFAULT; }
  function setWidth(w, save) {
    w = Math.max(W_MIN, Math.min(W_MAX, Math.round(w)));
    root.style.setProperty("--rail-w-user", w + "px");
    if (save) { store("navWidth", String(w)); }
    syncResizer();
    return w;
  }
  function syncResizer() {
    if (!resizer) { return; }
    resizer.setAttribute("aria-valuemin", W_MIN);
    resizer.setAttribute("aria-valuemax", W_MAX);
    resizer.setAttribute("aria-valuenow", collapsed() ? "" : width());
  }
  function initResizer() {
    resizer = document.querySelector(".rail-resizer");
    if (!resizer) { return; }
    var startX = 0, startW = 0;
    function move(ev) { setWidth(startW + (ev.clientX - startX), false); }
    function stop(ev) {
      resizer.classList.remove("dragging"); root.classList.remove("resizing");
      resizer.removeEventListener("pointermove", move); resizer.removeEventListener("pointerup", stop); resizer.removeEventListener("pointercancel", stop);
      try { resizer.releasePointerCapture(ev.pointerId); } catch (e) { /* not captured */ }
      store("navWidth", String(width()));
    }
    resizer.addEventListener("pointerdown", function (ev) {
      if (ev.button !== 0) { return; }
      ev.preventDefault();
      startX = ev.clientX; startW = width();
      resizer.setPointerCapture(ev.pointerId);
      resizer.classList.add("dragging"); root.classList.add("resizing");
      resizer.addEventListener("pointermove", move); resizer.addEventListener("pointerup", stop); resizer.addEventListener("pointercancel", stop);
    });
    resizer.addEventListener("dblclick", function () { setWidth(W_DEFAULT, false); try { localStorage.removeItem("navWidth"); } catch (e) { /* ignore */ } });
    resizer.addEventListener("keydown", function (ev) {
      var step = ev.shiftKey ? 48 : 16;
      if (ev.key === "ArrowLeft") { setWidth(width() - step, true); ev.preventDefault(); }
      else if (ev.key === "ArrowRight") { setWidth(width() + step, true); ev.preventDefault(); }
      else if (ev.key === "Home") { setWidth(W_MIN, true); ev.preventDefault(); }
      else if (ev.key === "End") { setWidth(W_MAX, true); ev.preventDefault(); }
    });
    syncResizer();
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(current());
    computeDrawer();
    initResizer(); syncButtons(); syncGroups();
  });

  // ---- quick jump (Ctrl+K): type to find any screen the user may open ----
  var jump = { box: null, input: null, list: null, items: [], shown: [], at: 0, opener: null };
  function jumpIndex() {
    if (jump.items.length) { return jump.items; }
    var el = document.getElementById("nav-index");
    try { jump.items = JSON.parse(el ? el.textContent : "[]"); } catch (e) { jump.items = []; }
    jump.items.forEach(function (i) { i.hay = (i.label + " " + i.sub + " " + i.group).toLowerCase(); });
    return jump.items;
  }
  function recent() { try { return JSON.parse(load("navRecent") || "[]"); } catch (e) { return []; } }
  function rememberPage() {
    var here = jumpIndex().filter(function (i) { return i.url === location.pathname; })[0];
    if (!here) { return; }
    var r = recent().filter(function (u) { return u !== here.url; });
    r.unshift(here.url); store("navRecent", JSON.stringify(r.slice(0, 6)));
  }
  function crumb(i) { return i.sub ? i.group + " \u203a " + i.sub : i.group; }
  function renderJump() {
    var q = jump.input.value.trim().toLowerCase(), all = jumpIndex(), nRecent = 0;
    if (q) {
      var words = q.split(/\s+/);
      var rows = all.filter(function (i) { return words.every(function (w) { return i.hay.indexOf(w) !== -1; }); });
      rows.sort(function (a, b) {
        var sa = a.label.toLowerCase().indexOf(q) === 0 ? 0 : 1, sb = b.label.toLowerCase().indexOf(q) === 0 ? 0 : 1;
        return sa - sb || a.label.localeCompare(b.label);
      });
      jump.shown = rows.slice(0, 40);
    } else {
      var r = recent().map(function (u) { return all.filter(function (i) { return i.url === u; })[0]; }).filter(Boolean);
      nRecent = r.length;
      jump.shown = r.concat(all.filter(function (i) { return r.indexOf(i) === -1; }));
    }
    jump.list.innerHTML = "";
    if (!jump.shown.length) {
      var none = document.createElement("li"); none.className = "cmdk-empty";
      none.textContent = "No screen matches \u201c" + jump.input.value + "\u201d."; jump.list.appendChild(none); return;
    }
    var heading = null;
    jump.shown.forEach(function (i, n) {
      var h = q ? "" : (n < nRecent ? "Recent" : i.group);
      if (h && h !== heading) {
        var hd = document.createElement("li"); hd.className = "cmdk-head"; hd.setAttribute("role", "presentation"); hd.textContent = h; jump.list.appendChild(hd);
      }
      heading = h;
      var li = document.createElement("li");
      li.setAttribute("role", "option"); li.id = "cmdk-opt-" + n; li.setAttribute("data-i", n);
      var name = document.createElement("span"); name.textContent = i.label;
      var c = document.createElement("span"); c.className = "cmdk-crumb"; c.textContent = crumb(i);
      li.appendChild(name); li.appendChild(c); jump.list.appendChild(li);
    });
    pick(0);
  }
  function pick(n) {
    if (!jump.shown.length) { return; }
    jump.at = Math.max(0, Math.min(n, jump.shown.length - 1));
    jump.list.querySelectorAll("[role=option]").forEach(function (li) { li.setAttribute("aria-selected", "false"); });
    var cur = document.getElementById("cmdk-opt-" + jump.at);
    if (cur) { cur.setAttribute("aria-selected", "true"); cur.scrollIntoView({ block: "nearest" }); jump.input.setAttribute("aria-activedescendant", cur.id); }
  }
  function openJump() {
    jump.box = jump.box || document.getElementById("cmdk");
    if (!jump.box) { return; }
    jump.input = document.getElementById("cmdk-input"); jump.list = document.getElementById("cmdk-list");
    jump.opener = document.activeElement; jump.box.hidden = false; jump.input.value = ""; renderJump(); jump.input.focus();
  }
  function closeJump() {
    if (!jump.box || jump.box.hidden) { return; }
    jump.box.hidden = true;
    if (jump.opener && jump.opener.focus) { jump.opener.focus(); }
  }
  function goJump(n) { var i = jump.shown[n]; if (i) { window.location.href = i.url; } }
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      if (jump.box && !jump.box.hidden) { closeJump(); } else { openJump(); }
      return;
    }
    if (!jump.box || jump.box.hidden) { return; }
    if (e.key === "Escape") { e.preventDefault(); closeJump(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); pick(jump.at + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); pick(jump.at - 1); }
    else if (e.key === "Enter") { e.preventDefault(); goJump(jump.at); }
    else if (e.key === "Tab") { e.preventDefault(); }          // keep focus in the box
  });
  document.addEventListener("input", function (e) { if (e.target && e.target.id === "cmdk-input") { renderJump(); } });
  document.addEventListener("mousedown", function (e) {
    if (!jump.box || jump.box.hidden) { return; }
    var li = e.target.closest("#cmdk-list [role=option]");
    if (li) { e.preventDefault(); goJump(parseInt(li.getAttribute("data-i"), 10)); }
    else if (!e.target.closest(".cmdk-box")) { closeJump(); }
  });
  document.addEventListener("mousemove", function (e) {
    var li = e.target.closest && e.target.closest("#cmdk-list [role=option]");
    if (li && jump.box && !jump.box.hidden) { var n = parseInt(li.getAttribute("data-i"), 10); if (n !== jump.at) { pick(n); } }
  });
  document.addEventListener("DOMContentLoaded", rememberPage);

  // ---- forms: confirm destructive buttons, and lock the submit buttons once a form is sent (no double posting) ----
  document.addEventListener("submit", function (e) {
    var form = e.target, who = e.submitter;
    if (!form || form.tagName !== "FORM") { return; }
    if (who && (who.hasAttribute("data-confirm") || who.classList.contains("danger"))) {
      var msg = who.getAttribute("data-confirm") || "Are you sure? This cannot be undone.";
      if (!window.confirm(msg)) { e.preventDefault(); return; }
    }
    if ((form.getAttribute("method") || "get").toLowerCase() === "get" || form.hasAttribute("data-no-lock")) { return; }
    if (Array.prototype.some.call(form.attributes, function (a) { return a.name.indexOf("hx-") === 0; })) { return; }
    setTimeout(function () {          // after the browser has read the form values, including the clicked button
      form.querySelectorAll("button:not([type=button]), input[type=submit]").forEach(function (b) {
        b.disabled = true; b.setAttribute("aria-busy", "true");
      });
    }, 0);
  });
  window.addEventListener("pageshow", function (e) {   // back button restores the page from cache: unlock it
    if (!e.persisted) { return; }
    document.querySelectorAll("button[aria-busy]").forEach(function (b) { b.disabled = false; b.removeAttribute("aria-busy"); });
  });

  // CSRF header for HTMX requests.
  document.addEventListener("htmx:configRequest", function (e) {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    if (m) { e.detail.headers["X-CSRFToken"] = m[1]; }
  });
})();
