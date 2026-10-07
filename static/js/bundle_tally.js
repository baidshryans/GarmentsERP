/* Cutting screen: as the pieces of each bundle are typed for a size ("25 25 22 18"), show how many bundles that is
   and the pieces they hold. A row that carries data-cut (a cutting recorded earlier without its bundles) also shows
   how the pieces stand against the pieces cut. A guide only: the server checks the same thing on saving. */
(function () {
  "use strict";

  function whole(text) { return /^\d+$/.test(text) ? parseInt(text, 10) : NaN; }

  function tally(row) {
    var list = row.querySelector("[data-bundle-list]").value.replace(/,/g, " ").trim();
    var counts = list ? list.split(/\s+/).map(whole) : [];
    var total = counts.reduce(function (a, b) { return a + b; }, 0);
    var count = row.querySelector("[data-bundle-count]"), out = row.querySelector("[data-bundle-tally]");
    if (isNaN(total) || counts.indexOf(0) !== -1) {
      count.textContent = "";
      out.innerHTML = '<span class="pill danger">Whole numbers only</span>';
      return;
    }
    count.textContent = counts.length || "";
    if (!row.hasAttribute("data-cut")) { out.textContent = counts.length ? total : ""; return; }
    var cut = parseInt(row.getAttribute("data-cut"), 10), gap = cut - total, note = "";
    if (gap > 0) { note = ' <span class="pill warning">' + gap + " short</span>"; }
    if (gap < 0) { note = ' <span class="pill danger">' + (-gap) + " too many</span>"; }
    out.innerHTML = total + " of " + cut + note;
  }

  document.querySelectorAll("[data-bundle-row]").forEach(function (row) {
    row.addEventListener("input", function () { tally(row); });
    tally(row);
  });
})();
