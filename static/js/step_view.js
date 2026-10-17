/* Step by step on the lot page: each step's row opens the list of what was recorded there. Without script the lists stay open. */
(function () {
  document.querySelectorAll("table[data-step-view] .step-toggle").forEach(function (btn) {
    var row = document.getElementById(btn.getAttribute("aria-controls"));
    if (!row) { return; }
    row.hidden = true;
    btn.addEventListener("click", function () {
      var open = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", open ? "false" : "true");
      row.hidden = open;
    });
  });
})();
