/* Entry tables (<table data-entry>): one entry line at the bottom. Press Tab on its last field (or Enter) and the
   line drops into the table above and a fresh entry line opens. Every line in the table, and a line still being
   typed, is submitted when the form is saved; the server ignores a blank line. */
(function () {
  var CONTROLS = "select:not(.ss-native), input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea";   // a searchable select shows as its text box

  function controls(row) { return Array.prototype.slice.call(row.querySelectorAll(CONTROLS)); }

  function usable(el) {                              // visible, enabled and reachable by Tab
    if (el.disabled || el.tabIndex < 0 || el.type === "hidden") { return false; }
    var cs = window.getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.display !== "none" && el.offsetParent !== null;
  }

  function hasData(row) {
    return Array.prototype.slice.call(row.querySelectorAll("select, input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not(.ss-input), textarea")).some(function (c) {
      if (c.tagName === "SELECT") { return c.selectedIndex > 0 && c.value !== ""; }
      return c.value.trim() !== "";
    });
  }

  function blankCopy(row) {
    var copy = row.cloneNode(true);
    copy.classList.remove("entry-row");
    copy.querySelectorAll("input, textarea").forEach(function (i) { if (i.type !== "checkbox" && i.type !== "radio") { i.value = ""; } i.removeAttribute("list"); });
    copy.querySelectorAll("select").forEach(function (s) { s.selectedIndex = 0; });
    copy.querySelectorAll("datalist").forEach(function (d) { d.remove(); });
    return copy;
  }

  function addTools(table) {                         // a remove button on every line, and an empty cell where the totals sit
    var head = table.querySelector("thead tr");
    if (head && !head.querySelector(".row-tools")) {
      var th = document.createElement("th"); th.scope = "col"; th.className = "row-tools";
      th.innerHTML = '<span class="sr-only">Remove line</span>'; head.appendChild(th);
    }
    table.querySelectorAll("tfoot tr").forEach(function (tr) { if (!tr.querySelector(".row-tools")) { var td = document.createElement("td"); td.className = "row-tools"; tr.appendChild(td); } });
    table.querySelectorAll("tbody tr").forEach(function (tr) {
      if (tr.querySelector(".row-tools")) { return; }
      var td = document.createElement("td"); td.className = "row-tools";
      td.innerHTML = '<button type="button" class="btn icon ghost row-remove" aria-label="Remove this line" data-tip="Remove this line">&times;</button>';
      tr.appendChild(td);
    });
  }

  function mark(table) {                             // the last line is the entry line
    var rows = table.querySelectorAll("tbody tr");
    rows.forEach(function (r, i) { r.classList.toggle("entry-row", i === rows.length - 1); });
  }

  function announce(table, row) {
    table.dispatchEvent(new CustomEvent("entry:added", { bubbles: true, detail: { row: row } }));
  }

  function commit(table, row) {
    var fresh = blankCopy(row);
    row.parentNode.appendChild(fresh);
    if (window.SearchableSelect) { window.SearchableSelect.scan(fresh); }           // make the new line's selects searchable now, so focus lands on them
    addTools(table); mark(table); announce(table, fresh);
    var first = controls(fresh).filter(usable)[0];
    if (first) { first.focus(); }
    table.closest("form").dispatchEvent(new Event("input", { bubbles: true }));    // refresh any running totals
  }

  function init(table) {
    var body = table.querySelector("tbody");
    var rows = Array.prototype.slice.call(body.querySelectorAll("tr"));
    if (!rows.length) { return; }
    var filled = rows.filter(hasData), blanks = rows.filter(function (r) { return filled.indexOf(r) === -1; });
    var keep = blanks.length ? blanks[blanks.length - 1] : blankCopy(rows[rows.length - 1]);
    blanks.forEach(function (r) { if (r !== keep) { r.remove(); } });
    if (!keep.parentNode) { body.appendChild(keep); }
    body.appendChild(keep);                          // the entry line goes last, below the lines already entered
    addTools(table); mark(table);

    var form = table.closest("form");
    var add = form && form.querySelector("#add-row");                 // the entry line replaces the old "Add row" button
    if (add) { add.hidden = true; }
    var hint = document.createElement("p");
    hint.className = "muted small entry-hint";
    hint.textContent = "Fill the highlighted line and press Tab on its last field to add it to the table. Save keeps every line, including one you are still typing.";
    (table.closest(".table-wrap, .table-scroll") || table).insertAdjacentElement("afterend", hint);

    body.addEventListener("keydown", function (e) {
      var row = e.target.closest("tr");
      if (!row || !row.parentNode || e.target.closest("button")) { return; }
      var isEntry = row.classList.contains("entry-row");
      if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") {
        e.preventDefault();                          // Enter never saves the whole form by accident
        if (isEntry && hasData(row)) { commit(table, row); }
        return;
      }
      if (e.key === "Tab" && !e.shiftKey && isEntry && hasData(row)) {
        var last = controls(row).filter(usable).pop();
        if (e.target === last) { e.preventDefault(); commit(table, row); }
      }
    });
    body.addEventListener("click", function (e) {
      var btn = e.target.closest(".row-remove");
      if (!btn) { return; }
      var row = btn.closest("tr");
      if (body.querySelectorAll("tr").length > 1) { row.remove(); } else { row.replaceWith(blankCopy(row)); }
      mark(table);
      var entry = body.querySelector(".entry-row"), first = entry && controls(entry).filter(usable)[0];
      if (first) { first.focus(); }
      form.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  document.addEventListener("DOMContentLoaded", function () { document.querySelectorAll("table[data-entry]").forEach(init); });
})();
