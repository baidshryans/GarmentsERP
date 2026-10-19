// Drill-down rows (trial balance, profit and loss, balance sheet): a group opens into the level below it and
// closes everything beneath it. "Expand all" and "Collapse all" work on the whole table.
(function () {
  function children(table, key) {
    return table.querySelectorAll('[data-drill-parent="' + key + '"]');
  }
  function close(table, key) {
    children(table, key).forEach(function (row) {
      row.hidden = true;
      var btn = row.querySelector(".drill-toggle");
      if (btn) { btn.setAttribute("aria-expanded", "false"); btn.textContent = "▸"; close(table, row.dataset.drillKey); }
    });
  }
  function toggle(btn) {
    var row = btn.closest("tr"), table = btn.closest("table"), open = btn.getAttribute("aria-expanded") !== "true";
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.textContent = open ? "▾" : "▸";
    if (open) { children(table, row.dataset.drillKey).forEach(function (r) { r.hidden = false; }); }
    else { close(table, row.dataset.drillKey); }
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".drill-toggle");
    if (btn) { toggle(btn); return; }
    var all = e.target.closest("[data-drill-all]");
    if (!all) return;
    var expand = all.dataset.drillAll === "open";
    document.querySelectorAll("[data-drill-key]").forEach(function (row) {
      if (row.dataset.depth !== "0") row.hidden = !expand;
      var b = row.querySelector(".drill-toggle");
      if (b) { b.setAttribute("aria-expanded", expand ? "true" : "false"); b.textContent = expand ? "▾" : "▸"; }
    });
  });
})();
