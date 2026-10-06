/* Sales screens: live totals in the size-colour grid (E4.1) and barcode scanning at billing (E4.2).
   The server does all the checking; this only saves keystrokes and gives feedback. */
(function () {
  "use strict";

  function num(v) { var n = parseFloat(String(v || "").replace(/,/g, "")); return isNaN(n) ? 0 : n; }
  function fmt(n) { return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

  // ---- size-colour grid: row and column totals update as you type; Tab moves cell to cell in reading order
  function recalcGrid(grid) {
    var rows = grid.querySelectorAll("tbody tr[data-row]");
    var colTotals = [], grand = 0;
    rows.forEach(function (tr) {
      var rowTotal = 0;
      tr.querySelectorAll("input.cell").forEach(function (inp, i) {
        var v = Math.floor(num(inp.value));
        rowTotal += v; colTotals[i] = (colTotals[i] || 0) + v;
      });
      var cell = tr.querySelector(".row-total"); if (cell) { cell.textContent = rowTotal; }
      grand += rowTotal;
    });
    grid.querySelectorAll("tfoot .col-total").forEach(function (td, i) { td.textContent = colTotals[i] || 0; });
    var g = grid.querySelector(".grand-total"); if (g) { g.textContent = grand; }
    var all = 0;
    document.querySelectorAll(".order-grid .grand-total").forEach(function (el) { all += num(el.textContent); });
    var sum = document.getElementById("order-pieces"); if (sum) { sum.textContent = all; }
  }
  document.addEventListener("input", function (e) {
    var grid = e.target.closest && e.target.closest(".order-grid");
    if (grid && e.target.classList.contains("cell")) { recalcGrid(grid); }
  });
  document.addEventListener("htmx:afterSwap", function () {
    document.querySelectorAll(".order-grid").forEach(recalcGrid);
  });
  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest(".remove-grid");
    if (btn) { btn.closest(".order-grid").remove(); document.querySelectorAll(".order-grid").forEach(recalcGrid); var s = document.getElementById("order-pieces"); if (s && !document.querySelector(".order-grid")) { s.textContent = 0; } }
  });
  document.querySelectorAll(".order-grid").forEach(recalcGrid);

  // (the GST template and note fields that show for one choice only are handled by reveal.js)

  // ---- barcode billing
  var box = document.getElementById("scan");
  var body = document.querySelector("#bill-lines tbody");
  if (!box || !body) { return; }
  var msg = document.getElementById("scan-msg");
  var audio;
  function beep(freq, secs) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      var osc = audio.createOscillator(), gain = audio.createGain();
      osc.frequency.value = freq; gain.gain.value = 0.1;
      osc.connect(gain); gain.connect(audio.destination); osc.start(); osc.stop(audio.currentTime + secs);
    } catch (err) { /* no sound available: the message still shows */ }
  }
  function say(text, bad) { msg.textContent = text; msg.className = bad ? "scan-msg bad" : "scan-msg"; }
  function recalcBill() {
    var total = 0, pieces = 0;
    body.querySelectorAll("tr[data-sku]").forEach(function (tr) {
      var q = num(tr.querySelector("[name=qty]").value), r = num(tr.querySelector("[name=rate]").value), d = num(tr.querySelector("[name=disc]").value);
      var amt = q * r * (100 - d) / 100; tr.querySelector(".amount").textContent = fmt(amt); total += amt; pieces += q;
    });
    document.getElementById("bill-total").textContent = fmt(total);
    document.getElementById("bill-pieces").textContent = pieces;
  }
  function addItem(it) {
    var row = body.querySelector('tr[data-sku="' + it.sku + '"]');
    if (row) {
      var q = row.querySelector("[name=qty]"); q.value = num(q.value) + it.qty;
      var rate = row.querySelector("[name=rate]"); if (!rate.value && it.rate) { rate.value = it.rate; }
    } else {
      row = document.getElementById("row-tpl").content.firstElementChild.cloneNode(true);
      row.setAttribute("data-sku", it.sku);
      row.querySelector("[name=sku]").value = it.sku;
      row.querySelector(".label").textContent = it.label;
      row.querySelector("[name=qty]").value = it.qty;
      row.querySelector("[name=rate]").value = it.rate;
      row.querySelector("[name=disc]").value = it.disc;
      row.querySelector(".src").textContent = it.source;
      body.insertBefore(row, body.firstChild);
    }
    row.classList.add("flash"); setTimeout(function () { row.classList.remove("flash"); }, 600);
    recalcBill();
  }
  box.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") { return; }
    e.preventDefault();
    var code = box.value.trim(); box.value = "";
    if (!code) { return; }
    var url = box.getAttribute("data-url") + "?code=" + encodeURIComponent(code) +
      "&customer=" + encodeURIComponent(document.getElementById("customer").value) +
      "&date=" + encodeURIComponent(document.getElementById("date").value);
    fetch(url, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (data) {
      if (!data.ok) { say(data.error, true); beep(200, 0.35); return; }
      data.items.forEach(addItem);
      say(data.items.length === 1 ? "Added " + data.items[0].label : "Added " + data.items.length + " items from the carton", false);
      beep(1000, 0.07);
    }).catch(function () { say("Could not reach the server.", true); beep(200, 0.35); });
  });
  body.addEventListener("input", recalcBill);
  body.addEventListener("click", function (e) {
    if (e.target.closest(".remove-row")) { e.target.closest("tr").remove(); recalcBill(); box.focus(); }
  });
  recalcBill();
  box.focus();
})();
