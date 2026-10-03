/* Theme toggle. The no-flash bootstrap lives inline in <head> (see partials/theme_boot.html). */
(function () {
  function current() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) { /* storage blocked */ }
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-theme-toggle]");
    if (btn) { apply(current() === "dark" ? "light" : "dark"); }
  });
  document.addEventListener("DOMContentLoaded", function () { apply(current()); });

  // ---- menu: collapsible groups, and a switch between the side menu and the top menu ----
  var OPEN_KEY = "navOpen";
  function navMode() { return document.documentElement.getAttribute("data-nav") === "top" ? "top" : "side"; }
  function topLike() { return navMode() === "top" || window.matchMedia("(max-width: 800px)").matches; }
  function readOpen() {
    try { return JSON.parse(localStorage.getItem(OPEN_KEY) || "{}"); } catch (e) { return {}; }
  }
  function saveOpen(map) {
    try { localStorage.setItem(OPEN_KEY, JSON.stringify(map)); } catch (e) { /* storage blocked */ }
  }
  function setNav(mode) {
    document.documentElement.setAttribute("data-nav", mode);
    try { localStorage.setItem("nav", mode); } catch (e) { /* storage blocked */ }
    document.querySelectorAll("[data-nav-toggle]").forEach(function (b) { b.setAttribute("aria-pressed", mode === "top" ? "true" : "false"); });
    initGroups();
  }
  function initGroups() {
    var saved = readOpen();
    document.querySelectorAll("#main-nav .nav-group").forEach(function (g) {
      var key = g.getAttribute("data-group");
      if (topLike()) { g.open = false; }                      // drop-downs start closed
      else { g.open = g.classList.contains("active") || saved[key] === true; }
    });
  }
  document.addEventListener("toggle", function (e) {
    var g = e.target;
    if (!g.classList || !g.classList.contains("nav-group")) { return; }
    if (topLike()) {
      if (g.open) {                                            // one drop-down at a time
        document.querySelectorAll("#main-nav .nav-group").forEach(function (o) { if (o !== g) { o.open = false; } });
      }
    } else {
      var map = readOpen();
      map[g.getAttribute("data-group")] = g.open;
      saveOpen(map);
    }
  }, true);
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-nav-toggle]");
    if (t) { setNav(navMode() === "top" ? "side" : "top"); return; }
    if (topLike() && !e.target.closest("#main-nav")) {
      document.querySelectorAll("#main-nav .nav-group").forEach(function (g) { g.open = false; });
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { document.querySelectorAll("#main-nav .nav-group").forEach(function (g) { if (topLike()) { g.open = false; } }); }
  });
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-nav-toggle]").forEach(function (b) { b.setAttribute("aria-pressed", navMode() === "top" ? "true" : "false"); });
    initGroups();
  });
  window.matchMedia("(max-width: 800px)").addEventListener("change", initGroups);

  // CSRF header for HTMX requests.
  document.addEventListener("htmx:configRequest", function (e) {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    if (m) { e.detail.headers["X-CSRFToken"] = m[1]; }
  });
})();
