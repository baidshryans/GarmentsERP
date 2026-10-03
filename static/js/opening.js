/* Opening balances: add rows and show running debit / credit totals (display only; the server decides). */
(function () {
  var form = document.getElementById("opening-form");
  if (!form) { return; }
  var body = form.querySelector("#opening-rows tbody");

  function num(v) {
    var n = parseFloat((v || "").replace(/,/g, ""));
    return isNaN(n) ? 0 : n;
  }
  function totals() {
    var dr = 0, cr = 0;
    form.querySelectorAll("input[name=debit]").forEach(function (i) { dr += num(i.value); });
    form.querySelectorAll("input[name=credit]").forEach(function (i) { cr += num(i.value); });
    document.getElementById("tot-dr").textContent = dr.toFixed(2);
    document.getElementById("tot-cr").textContent = cr.toFixed(2);
    var diff = Math.abs(dr - cr);
    document.getElementById("diff").textContent =
      diff > 0.004 ? "· " + diff.toFixed(2) + " will go to Opening Balance Difference" : "";
  }
  form.addEventListener("input", totals);
  document.getElementById("add-row").addEventListener("click", function () {
    var last = body.querySelector("tr:last-child");
    var copy = last.cloneNode(true);
    copy.querySelectorAll("input").forEach(function (i) { i.value = ""; });
    copy.querySelectorAll("select").forEach(function (s) { s.selectedIndex = 0; });
    body.appendChild(copy);
    copy.querySelector("select").focus();
  });
  totals();
})();
