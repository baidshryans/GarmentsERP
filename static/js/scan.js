/* Scanner input: a barcode scanner types the QR text and presses Enter. We tick the matching row. The server checks everything. */
(function () {
  var box = document.getElementById("scan");
  if (!box) { return; }
  function normalise(text) {
    text = (text || "").trim();
    return text.indexOf("GE1:") === 0 ? text.slice(4) : text;
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
      if (check) { check.checked = true; }
      found.style.outline = "2px solid var(--color-primary)";
      found.scrollIntoView({ block: "nearest" });
    } else {
      box.setCustomValidity("Not on this lot");
      box.reportValidity();
      box.setCustomValidity("");
    }
  });
})();
