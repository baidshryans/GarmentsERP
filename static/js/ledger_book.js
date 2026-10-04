/* Ledger book: filter the ledger tick-list, select what is shown, keep the count. */
(function () {
  var form = document.getElementById("ledger-book-form");
  if (!form) { return; }
  var search = document.getElementById("lp-search"), count = document.getElementById("lp-count");
  var items = Array.prototype.slice.call(form.querySelectorAll(".lp-item")), groups = form.querySelectorAll(".lp-group");

  function boxes(shownOnly) {
    return items.filter(function (el) { return !shownOnly || !el.hidden; }).map(function (el) { return el.querySelector("input"); });
  }
  function recount() {
    var n = boxes(false).filter(function (b) { return b.checked; }).length;
    count.textContent = n + " selected";
  }
  function filter() {
    var q = search.value.trim().toLowerCase();
    items.forEach(function (el) { el.hidden = q !== "" && el.textContent.toLowerCase().indexOf(q) === -1; });
    Array.prototype.forEach.call(groups, function (g) { g.hidden = !g.querySelector(".lp-item:not([hidden])"); });
  }
  search.addEventListener("input", filter);
  search.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); } });
  form.addEventListener("change", function (e) { if (e.target.name === "ledger") { recount(); } });
  document.getElementById("lp-all").addEventListener("click", function () { boxes(true).forEach(function (b) { b.checked = true; }); recount(); });
  document.getElementById("lp-none").addEventListener("click", function () { boxes(false).forEach(function (b) { b.checked = false; }); recount(); });
  recount();
})();
