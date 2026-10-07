/* Cutting screen: as the pieces of each bundle are typed for a size ("25 25 22 18"), show how many bundles that is
   and how the pieces stand against what is to be bundled (cut less lost in cutting). A guide only: the server
   checks the same thing when the bundles are made. */
(function () {
  "use strict";

  function whole(text) { return /^\d+$/.test(text) ? parseInt(text, 10) : NaN; }

  function tally(row) {
    var list = row.querySelector("[data-bundle-list]").value.replace(/,/g, " ").trim();
    var lost = row.querySelector("[data-bundle-loss]").value.trim();
    var good = parseInt(row.getAttribute("data-cut"), 10) - (lost ? whole(lost) : 0);
    var counts = list ? list.split(/\s+/).map(whole) : [];
    var total = counts.reduce(function (a, b) { return a + b; }, 0);
    var count = row.querySelector("[data-bundle-count]"), out = row.querySelector("[data-bundle-tally]");
    if (isNaN(total) || isNaN(good) || counts.indexOf(0) !== -1) {
      count.textContent = "";
      out.innerHTML = '<span class="pill danger">Whole numbers only</span>';
      return;
    }
    count.textContent = counts.length || "";
    var gap = good - total, note = "";
    if (gap > 0) { note = ' <span class="pill warning">' + gap + " short</span>"; }
    if (gap < 0) { note = ' <span class="pill danger">' + (-gap) + " too many</span>"; }
    out.innerHTML = total + " of " + good + note;
  }

  document.querySelectorAll("[data-bundle-row]").forEach(function (row) {
    row.addEventListener("input", function () { tally(row); });
    tally(row);
  });
})();
