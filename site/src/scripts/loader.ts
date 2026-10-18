// The nib loader (public/loader.svg): the logo writes a ring of connected
// nodes and drinks the ink back in. Readers who prefer reduced motion get the
// still logo instead; SMIL in an <img> can't be paused by CSS.

const base = import.meta.env.BASE_URL.replace(/\/$/, "");

export function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** A status line with the animated nib, e.g. loading("Searching…"). */
export function loading(text: string, cls = "") {
  const p = document.createElement("p");
  p.className = `loading ${cls}`.trim();
  p.setAttribute("role", "status");
  const img = document.createElement("img");
  img.src = `${base}/${prefersReducedMotion() ? "loader-still" : "loader"}.svg`;
  img.alt = "";
  img.width = img.height = 40;
  const span = document.createElement("span");
  span.textContent = text;
  p.append(img, span);
  return p;
}
