/* Sales, purchase and credit/debit note vouchers: show what the chosen customer or vendor already owes (or is owed). */
(function () {
  var select = document.getElementById("party"), note = document.getElementById("party-position");
  var script = document.currentScript;
  if (!select || !note || !script) { return; }
  var urlTemplate = script.getAttribute("data-url");
  function update() {
    if (!select.value) { LedgerPosition.clear(note); return; }
    fetch(urlTemplate.replace("/0/", "/" + select.value + "/"), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) { LedgerPosition.show(note, data, true); })
      .catch(function () { LedgerPosition.clear(note); });
  }
  select.addEventListener("change", update);
  window.addEventListener("load", update);
})();
