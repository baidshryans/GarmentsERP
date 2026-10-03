/* Show only the locations that belong to the chosen factory. The server still checks everything. */
(function () {
  function filter(factorySelect) {
    var target = document.getElementById(factorySelect.getAttribute("data-factory-select"));
    if (!target) { return; }
    var chosen = factorySelect.value, firstVisible = null;
    Array.prototype.forEach.call(target.options, function (opt) {
      var show = opt.getAttribute("data-factory") === chosen;
      opt.hidden = !show;
      opt.disabled = !show;
      if (show && firstVisible === null) { firstVisible = opt; }
    });
    var current = target.options[target.selectedIndex];
    if (!current || current.disabled) { target.value = firstVisible ? firstVisible.value : ""; }
  }
  document.querySelectorAll("[data-factory-select]").forEach(function (sel) {
    sel.addEventListener("change", function () { filter(sel); });
    filter(sel);
  });
})();
