/* Ledger book: a type-to-find box that adds ledgers as removable chips (each chip carries a hidden "ledger" field). */
(function () {
  var form = document.getElementById("ledger-book-form");
  if (!form) { return; }
  var search = document.getElementById("lb-search"), menu = document.getElementById("lb-menu");
  var chips = document.getElementById("lb-chips"), hint = document.getElementById("lb-hint");
  var options = JSON.parse(document.getElementById("lb-options").textContent);
  var shown = [], active = -1;

  function chosen() {
    return Array.prototype.map.call(chips.querySelectorAll(".lb-chip"), function (c) { return c.getAttribute("data-id"); });
  }
  function syncHint() { hint.hidden = chips.children.length > 0; }
  function closeMenu() { menu.hidden = true; search.setAttribute("aria-expanded", "false"); active = -1; }

  function add(opt) {
    if (chosen().indexOf(String(opt.id)) !== -1) { return; }
    var chip = document.createElement("span");
    chip.className = "lb-chip";
    chip.setAttribute("data-id", opt.id);
    chip.appendChild(document.createTextNode(opt.name));
    var hidden = document.createElement("input");
    hidden.type = "hidden"; hidden.name = "ledger"; hidden.value = opt.id;
    var x = document.createElement("button");
    x.type = "button"; x.setAttribute("aria-label", "Remove " + opt.name); x.innerHTML = "&times;";
    chip.appendChild(hidden); chip.appendChild(x);
    chips.appendChild(chip);
    syncHint();
  }

  function highlight(i) {
    var items = menu.children;
    if (!items.length) { return; }
    active = (i + items.length) % items.length;
    Array.prototype.forEach.call(items, function (li, n) { li.classList.toggle("on", n === active); });
    items[active].scrollIntoView({ block: "nearest" });
  }

  function render() {
    var q = search.value.trim().toLowerCase();
    var taken = chosen();
    shown = options.filter(function (o) {
      return taken.indexOf(String(o.id)) === -1 && (q === "" || (o.name + " " + o.group).toLowerCase().indexOf(q) !== -1);
    }).slice(0, 50);
    menu.innerHTML = "";
    shown.forEach(function (o, n) {
      var li = document.createElement("li");
      li.setAttribute("role", "option");
      var name = document.createElement("span"); name.textContent = o.name;
      var grp = document.createElement("span"); grp.className = "muted"; grp.textContent = o.group;
      li.appendChild(name); li.appendChild(grp);
      li.addEventListener("mousedown", function (e) { e.preventDefault(); pick(n); });
      menu.appendChild(li);
    });
    if (!shown.length) {
      var none = document.createElement("li");
      none.className = "none"; none.textContent = q ? "No ledger matches" : "All ledgers are added";
      menu.appendChild(none);
    }
    menu.hidden = false;
    search.setAttribute("aria-expanded", "true");
    active = -1;
    if (shown.length && q) { highlight(0); }
  }

  function pick(n) {
    if (shown[n]) { add(shown[n]); }
    search.value = "";
    render();
    search.focus();
  }

  search.addEventListener("input", render);
  search.addEventListener("focus", render);
  search.addEventListener("blur", closeMenu);
  search.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); if (menu.hidden) { render(); } highlight(active + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); highlight(active - 1); }
    else if (e.key === "Enter") { e.preventDefault(); if (!menu.hidden && active >= 0) { pick(active); } else if (search.value === "") { form.requestSubmit(); } }
    else if (e.key === "Escape") { closeMenu(); }
    else if (e.key === "Backspace" && search.value === "" && chips.lastElementChild) { chips.removeChild(chips.lastElementChild); syncHint(); }
  });
  chips.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (b) { chips.removeChild(b.parentNode); syncHint(); search.focus(); }
  });
})();
