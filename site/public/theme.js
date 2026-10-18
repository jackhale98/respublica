// Runs before first paint: applies saved theme and text size, and marks
// that JavaScript is available. Preferences are the only things stored.
(function () {
  var d = document.documentElement;
  d.classList.add("js");
  try {
    var t = localStorage.getItem("rp-theme");
    if (t === "light" || t === "dark") d.setAttribute("data-theme", t);
    var s = localStorage.getItem("rp-size");
    if (s === "s" || s === "l" || s === "xl") d.setAttribute("data-size", s);
  } catch (e) {}
})();
