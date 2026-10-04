/* Help page: filter the contents by title or by text inside a section, and mark the section being read. */
(function () {
  var body = document.getElementById("help-body");
  var filter = document.getElementById("help-filter");
  if (!body || !filter) { return; }
  var links = Array.prototype.slice.call(document.querySelectorAll(".help-toc-list a"));
  var count = document.getElementById("help-count");

  /* The text of each section: its heading and everything up to the next heading. A level-3 part also counts
     toward the level-2 section that contains it, so searching finds the parent as well. */
  var text = {}, current = null, parent = null;
  Array.prototype.forEach.call(body.children, function (el) {
    if (/^H[1-3]$/.test(el.tagName) && el.id) {
      current = el.id;
      if (el.tagName !== "H3") { parent = el.tagName === "H2" ? el.id : null; }
      text[current] = el.textContent.toLowerCase();
      return;
    }
    if (!current) { return; }
    var t = " " + el.textContent.toLowerCase();
    text[current] += t;
    if (parent && parent !== current) { text[parent] += t; }
  });

  function apply() {
    var q = filter.value.trim().toLowerCase(), shown = 0;
    links.forEach(function (a) {
      var id = a.getAttribute("href").slice(1);
      var hit = !q || (text[id] || "").indexOf(q) !== -1;
      a.parentNode.hidden = !hit;
      if (hit) { shown += 1; }
    });
    count.hidden = !q;
    count.textContent = shown ? shown + (shown === 1 ? " section matches" : " sections match") : "Nothing matches. Try a shorter word.";
  }
  filter.addEventListener("input", apply);

  /* Mark the section in view. */
  if ("IntersectionObserver" in window) {
    var heads = Array.prototype.slice.call(body.querySelectorAll("h2, h3"));
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) { return; }
        links.forEach(function (a) { a.classList.toggle("current", a.getAttribute("href") === "#" + e.target.id); });
      });
    }, { rootMargin: "0px 0px -75% 0px" });
    heads.forEach(function (h) { io.observe(h); });
  }
})();
