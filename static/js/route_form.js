/* Route form: "Add step" adds a blank step below the last one, and the step numbers follow the rows. A step has a
   factory when it is in-house and a fabricator when it is subcontracted, so the other one is cleared and hidden.
   The select stays in the form (blank) because the server reads the rows by position. */
(function () {
  var table = document.getElementById("route-steps");
  if (!table) { return; }
  var body = table.querySelector("tbody");

  function fitWhere(tr) {
    var sub = tr.querySelector("select[name=assignment]").value === "subcontract";
    var factory = tr.querySelector("select[name=factory]"), party = tr.querySelector("select[name=party]");
    if (sub) { factory.value = ""; } else { party.value = ""; }
    factory.style.visibility = sub ? "hidden" : "";          // the searchable box follows the select's visibility
    party.style.visibility = sub ? "" : "hidden";
  }

  function renumber() {                              // the server reads "mandatory_<row index>"
    body.querySelectorAll("tr").forEach(function (tr, i) {
      tr.querySelector(".step-no").textContent = i + 1;
      tr.querySelector("input[type=checkbox]").name = "mandatory_" + i;
    });
  }

  document.getElementById("add-step").addEventListener("click", function () {
    var last = body.querySelector("tr:last-child");
    var copy = last.cloneNode(true);
    copy.querySelector("select[name=process]").selectedIndex = 0;
    copy.querySelector("select[name=assignment]").value = "in_house";
    copy.querySelector("select[name=party]").selectedIndex = 0;
    copy.querySelector("input[name=rate]").value = "";
    copy.querySelector("input[type=checkbox]").checked = true;
    var factory = copy.querySelector("select[name=factory]");   // keep the only factory chosen; otherwise start blank
    factory.selectedIndex = factory.options.length === 2 ? 1 : 0;
    body.appendChild(copy);
    fitWhere(copy);
    renumber();
    copy.querySelector("select[name=process]").focus();
  });
  body.addEventListener("change", function (e) {
    if (e.target.name === "assignment") { fitWhere(e.target.closest("tr")); }
  });
  body.querySelectorAll("tr").forEach(fitWhere);
  table.closest("form").addEventListener("submit", renumber);
})();
