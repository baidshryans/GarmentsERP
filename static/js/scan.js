/* Scanner input: a barcode scanner types the QR text and presses Enter. We tick the matching row. The server checks everything. */
(function () {
  var box = document.getElementById("scan");
  if (!box) { return; }
  function normalise(text) {
    text = (text || "").trim();
    return text.indexOf("GE1:") === 0 ? text.slice(4) : text;
  }
  /* The tick box in the table heading ticks or clears every row, and follows the rows when they are ticked one by one. */
  var all = document.querySelector("input[data-select-all]");
  function rowChecks() {
    return Array.prototype.slice.call(document.querySelectorAll("tr[data-token] input[type=checkbox]"));
  }
  function syncAll() {
    if (!all) { return; }
    var checks = rowChecks();
    var ticked = checks.filter(function (c) { return c.checked; }).length;
    all.checked = checks.length > 0 && ticked === checks.length;
    all.indeterminate = ticked > 0 && ticked < checks.length;
  }
  if (all) {
    all.addEventListener("change", function () {
      rowChecks().forEach(function (c) { c.checked = all.checked; });
      all.indeterminate = false;
    });
    rowChecks().forEach(function (c) { c.addEventListener("change", syncAll); });
    syncAll();
  }
  box.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") { return; }
    e.preventDefault();
    var wanted = normalise(box.value).toLowerCase();
    box.value = "";
    if (!wanted) { return; }
    var found = null;
    document.querySelectorAll("tr[data-token]").forEach(function (row) {
      if (row.getAttribute("data-token").toLowerCase() === wanted || row.getAttribute("data-no").toLowerCase() === wanted) { found = row; }
    });
    if (found) {
      var check = found.querySelector("input[type=checkbox]");
      if (check) { check.checked = true; syncAll(); }
      found.style.outline = "2px solid var(--color-primary)";
      found.scrollIntoView({ block: "nearest" });
    } else {
      box.setCustomValidity("Not on this lot");
      box.reportValidity();
      box.setCustomValidity("");
    }
  });
})();
