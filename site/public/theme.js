// Runs before first paint: applies saved theme, text size and line spacing,
// and marks that JavaScript is available. Stored only in this browser.
(function () {
  var d = document.documentElement;
  d.classList.add("js");
  try {
    var t = localStorage.getItem("rp-theme");
    if (t === "light" || t === "dark") d.setAttribute("data-theme", t);
    var s = localStorage.getItem("rp-size");
    if (s === "s" || s === "l" || s === "xl" || s === "xxl") d.setAttribute("data-size", s);
    if (localStorage.getItem("rp-leading") === "relaxed") d.setAttribute("data-leading", "relaxed");
  } catch (e) {}
})();
