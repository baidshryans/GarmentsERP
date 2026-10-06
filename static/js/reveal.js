/* Fields that apply to one choice only. An element marked data-show-when="<field name>=<value> <value> ..." shows
   while the named field of the same form holds one of those values, and hides otherwise. The server renders the
   first state; this keeps it in step as the choice changes. A hidden field is still sent with the form, exactly as
   if it had been left alone, unless the element also carries data-off-when-hidden: then its controls are switched
   off while hidden, so a value typed for another choice is never sent. The server decides everything. */
(function () {
  "use strict";

  function chosen(scope, name) {
    var found = "";
    Array.prototype.some.call(scope.querySelectorAll('[name="' + name + '"]'), function (c) {
      if ((c.type === "radio" || c.type === "checkbox") && !c.checked) { return false; }
      found = c.value; return true;
    });
    return found;
  }

  function sync() {
    document.querySelectorAll("[data-show-when]").forEach(function (el) {
      var spec = el.getAttribute("data-show-when"), cut = spec.indexOf("=");
      if (cut < 1) { return; }
      var show = spec.slice(cut + 1).split(/\s+/).indexOf(chosen(el.closest("form") || document, spec.slice(0, cut))) !== -1;
      el.hidden = !show;
      if (el.hasAttribute("data-off-when-hidden")) {
        el.querySelectorAll("input, select, textarea").forEach(function (c) { c.disabled = !show; });
      }
    });
  }

  document.addEventListener("change", function (e) { if (e.target && e.target.name) { sync(); } });
  sync();
})();
