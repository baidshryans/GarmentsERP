/* Shows what is outstanding against a ledger beside the choice, on voucher screens. Information only: it never blocks. */
(function () {
  function money(v) {
    var n = parseFloat(v);
    return "₹" + (isNaN(n) ? v : n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  }

  /* data is the "position" object from the ledger_bills endpoint */
  function describe(data, billWise) {
    var p = data.position, parts = [];
    if (!p) { return ""; }
    if (billWise) {
      if (p.outstanding_side) {
        parts.push("Outstanding " + money(p.outstanding) + " " + p.outstanding_side +
                   (p.outstanding_side === "Dr" ? " (owes you)" : " (you owe)") +
                   " in " + p.open_bills + (p.open_bills === 1 ? " open bill" : " open bills"));
      } else {
        parts.push("Nothing outstanding");
      }
      if (p.advance_side) { parts.push("advance " + money(p.advance) + " " + p.advance_side); }
      if (p.on_account_side) { parts.push("on account " + money(p.on_account) + " " + p.on_account_side); }
    } else {
      parts.push("Balance " + (p.balance_side ? money(p.balance) + " " + p.balance_side : "nil"));
    }
    return parts.join(" · ");
  }

  function show(el, data, billWise) {
    if (!el) { return; }
    var text = describe(data, billWise);
    el.textContent = text;
    el.hidden = !text;
    var p = data.position;
    el.classList.toggle("owes", !!(billWise && p && p.outstanding_side));
  }

  function clear(el) { if (el) { el.textContent = ""; el.hidden = true; } }

  window.LedgerPosition = { show: show, clear: clear, describe: describe };
})();
