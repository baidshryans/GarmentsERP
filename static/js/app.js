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

  // CSRF header for HTMX requests.
  document.addEventListener("htmx:configRequest", function (e) {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    if (m) { e.detail.headers["X-CSRFToken"] = m[1]; }
  });
})();
