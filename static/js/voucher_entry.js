/* Manual voucher entry: running totals, add-row, and bill options that follow the chosen ledger. The server decides. */
(function () {
  var form = document.getElementById("voucher-form");
  var table = document.getElementById("voucher-rows");
  if (!form || !table) { return; }
  var body = table.querySelector("tbody");
  var journal = form.getAttribute("data-vtype") === "journal";
  var urlTemplate = form.getAttribute("data-bills-url");
  var listCount = 0;

  function num(v) { var n = parseFloat((v || "").replace(/,/g, "")); return isNaN(n) ? 0 : n; }

  function totals() {
    var dr = 0, cr = 0, tot = 0;
    form.querySelectorAll("input[name=row_debit]").forEach(function (i) { dr += num(i.value); });
    form.querySelectorAll("input[name=row_credit]").forEach(function (i) { cr += num(i.value); });
    form.querySelectorAll("input[name=row_amount]").forEach(function (i) { tot += num(i.value); });
    if (journal) {
      document.getElementById("tot-dr").textContent = dr.toFixed(2);
      document.getElementById("tot-cr").textContent = cr.toFixed(2);
      var diff = Math.abs(dr - cr);
      document.getElementById("diff").textContent = diff > 0.004 ? "· out by " + diff.toFixed(2) : (dr ? "· balanced" : "");
    } else {
      document.getElementById("tot").textContent = tot.toFixed(2);
    }
  }

  function billWise(row) {
    var sel = row.querySelector("select[name=row_ledger]");
    var opt = sel.options[sel.selectedIndex];
    return !!(opt && opt.getAttribute("data-billwise"));
  }

  function loadBills(row) {                       // offer this ledger's open bills for "Against bill"
    var sel = row.querySelector("select[name=row_ledger]"), ref = row.querySelector("input[name=row_reference]");
    if (!sel.value || !billWise(row)) { return; }
    var url = urlTemplate.replace("/0/", "/" + sel.value + "/") + "?factory=" + encodeURIComponent(document.getElementById("factory").value);
    fetch(url, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (data) {
      var id = ref.getAttribute("list");
      if (!id) { id = "bills-" + (++listCount); ref.setAttribute("list", id); }
      var dl = document.getElementById(id);
      if (!dl) { dl = document.createElement("datalist"); dl.id = id; row.appendChild(dl); }
      dl.innerHTML = "";
      row._bills = {};
      data.bills.forEach(function (b) {
        row._bills[b.reference] = b;
        var o = document.createElement("option");
        o.value = b.reference; o.label = b.amount + " " + b.side; dl.appendChild(o);
      });
    }).catch(function () { /* the field still accepts typed references */ });
  }

  function syncRow(row) {                         // bill cells only matter for bill-wise ledgers
    var on = billWise(row);
    row.querySelectorAll(".bill-cell").forEach(function (c) {
      c.style.visibility = on ? "visible" : "hidden";
      c.tabIndex = on ? 0 : -1;
    });
    if (on) { loadBills(row); }
  }

  function pickBill(row) {                        // choosing an open invoice settles it: fill the outstanding amount
    var ref = row.querySelector("input[name=row_reference]");
    var bill = row._bills && ref ? row._bills[ref.value.trim()] : null;
    if (!bill) { return; }
    row.querySelector("select[name=row_ref_type]").value = "against";
    var amt = row.querySelector("input[name=row_amount]"), dr = row.querySelector("input[name=row_debit]"), cr = row.querySelector("input[name=row_credit]");
    if (journal) {                                // a payable (Cr) bill is settled by a debit, a receivable (Dr) by a credit
        var target = bill.side === "Cr" ? dr : cr, other = bill.side === "Cr" ? cr : dr;
        if (!num(target.value)) { target.value = bill.amount; other.value = ""; }
    } else if (amt && !num(amt.value)) { amt.value = bill.amount; }
    totals();
  }

  body.addEventListener("change", function (e) {
    if (e.target.name === "row_ledger") { syncRow(e.target.closest("tr")); }
    if (e.target.name === "row_reference") { pickBill(e.target.closest("tr")); }
  });
  body.addEventListener("click", function (e) {
    var btn = e.target.closest(".remove-row");
    if (!btn) { return; }
    var row = btn.closest("tr");
    if (body.querySelectorAll("tr").length > 1) { row.remove(); }
    else { row.querySelectorAll("input[type=text],input[type=date]").forEach(function (i) { i.value = ""; }); row.querySelectorAll("select").forEach(function (x) { x.selectedIndex = 0; }); }
    totals();
  });
  form.addEventListener("input", totals);
  document.getElementById("factory").addEventListener("change", function () { body.querySelectorAll("tr").forEach(syncRow); });
  document.getElementById("add-row").addEventListener("click", function () {
    var copy = body.querySelector("tr:last-child").cloneNode(true);
    copy._bills = {};
    copy.querySelectorAll("input[type=text],input[type=date]").forEach(function (i) { i.value = ""; i.removeAttribute("list"); });
    copy.querySelectorAll("select").forEach(function (s) { s.selectedIndex = 0; });
    var dl = copy.querySelector("datalist"); if (dl) { dl.remove(); }
    body.appendChild(copy); syncRow(copy);
    copy.querySelector("select").focus();
  });
  table.addEventListener("entry:added", function (e) { syncRow(e.detail.row); });   // a new entry line from entry_table.js
  body.querySelectorAll("tr").forEach(syncRow);
  totals();
})();
