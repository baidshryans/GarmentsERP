/* Route form: "Add step" adds a blank step below the last one, and the step numbers follow the rows. */
(function () {
  var table = document.getElementById("route-steps");
  if (!table) { return; }
  var body = table.querySelector("tbody");

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
    if (factory.options.length !== 2) { factory.selectedIndex = 0; }
    body.appendChild(copy);
    renumber();
    copy.querySelector("select[name=process]").focus();
  });
  table.closest("form").addEventListener("submit", renumber);
})();
