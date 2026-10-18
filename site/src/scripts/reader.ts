// Reader behavior: select a passage to show it in the panel (bottom sheet on
// phones), j/k to move between passages, contents drawer, scrollspy,
// copy link/text, text size. Without JavaScript the page is fully readable:
// anchors still work and connections show inline under each passage.

const toast = (m: string) => (window as any).rpToast?.(m);
const panel = document.querySelector<HTMLElement>("[data-panel]");
const scrim = document.querySelector<HTMLElement>("[data-scrim]");
const toc = document.querySelector<HTMLElement>("[data-toc-nav]");
const passages = Array.from(document.querySelectorAll<HTMLElement>(".passage"));
const narrow = window.matchMedia("(max-width: 63.99rem)");
const tocDrawer = window.matchMedia("(max-width: 79.99rem)");

let selected: HTMLElement | null = null;

// ---------------------------------------------------------------- panel

function q<T extends Element = HTMLElement>(sel: string) {
  return panel?.querySelector<T>(sel) ?? null;
}

function fillPanel(p: HTMLElement) {
  if (!panel) return;
  q("[data-panel-ref]")!.textContent = p.dataset.ref || "";
  q("[data-panel-label]")!.textContent = p.dataset.label || "";
  const changed = q("[data-panel-changed]")!;
  const chg = p.querySelector<HTMLTemplateElement>("template.chg-data");
  changed.replaceChildren(...(chg ? [chg.content.cloneNode(true)] : []));
  changed.hidden = !chg;
  const conns = q("[data-panel-conns]")!;
  const list = p.querySelector(".conns .conn-list");
  conns.replaceChildren(...(list ? [list.cloneNode(true)] : []));
  q("[data-panel-empty]")!.hidden = !!list;
  q(".panel-default")!.hidden = true;
  q(".panel-passage")!.hidden = false;
}

function openSheet() {
  if (!panel || !narrow.matches) return;
  panel.classList.add("open");
  scrim?.classList.add("show");
}

function closeSheet() {
  panel?.classList.remove("open");
  if (!toc?.classList.contains("open")) scrim?.classList.remove("show");
}

function select(p: HTMLElement, opts: { scroll?: boolean; sheet?: boolean; hash?: boolean } = {}) {
  if (selected === p && opts.sheet) {
    // Second tap on a phone toggles the sheet.
    if (panel?.classList.contains("open")) closeSheet(); else openSheet();
    return;
  }
  selected?.classList.remove("is-selected");
  selected = p;
  p.classList.add("is-selected");
  fillPanel(p);
  if (opts.hash !== false) history.replaceState(null, "", `#${p.id}`);
  if (opts.scroll) p.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  if (opts.sheet) openSheet();
}

function deselect() {
  selected?.classList.remove("is-selected");
  selected = null;
  closeSheet();
  if (q(".panel-default")) q(".panel-default")!.hidden = false;
  if (q(".panel-passage")) q(".panel-passage")!.hidden = true;
  history.replaceState(null, "", location.pathname + location.search);
}

for (const p of passages) {
  p.addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    if (t.closest("a") && !t.closest(".num")) return; // real links inside text
    if (t.closest(".num")) e.preventDefault();
    if (window.getSelection()?.toString()) return; // the reader is selecting text
    select(p, { sheet: true });
  });
}

q("[data-panel-close]")?.addEventListener("click", deselect);
scrim?.addEventListener("click", () => {
  closeSheet();
  closeToc();
});

// Copy actions
async function copy(text: string, done: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast(done);
  } catch {
    toast("Copy is not available here");
  }
}

panel?.addEventListener("click", (e) => {
  const action = (e.target as HTMLElement).closest<HTMLElement>("[data-action]")?.dataset.action;
  if (!action || !selected) return;
  const url = `${location.origin}${location.pathname}#${selected.id}`;
  if (action === "copy-link") copy(url, "Link copied");
  if (action === "copy-quote") {
    const text = Array.from(selected.querySelectorAll(".ptext p")).map((p) => (p as HTMLElement).innerText.trim()).join("\n\n");
    copy(`${text}\n\n— ${selected.dataset.label} (${selected.dataset.ref})\n${url}`, "Text copied");
  }
});

// ---------------------------------------------------------------- keyboard

function isTyping(t: EventTarget | null) {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
}

function firstVisible(): number {
  const top = (document.querySelector(".site-header") as HTMLElement)?.offsetHeight ?? 0;
  const i = passages.findIndex((p) => p.getBoundingClientRect().bottom > top + 8);
  return Math.max(0, i);
}

document.addEventListener("keydown", (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target) || document.querySelector("dialog[open]")) return;
  if (e.key === "j" || e.key === "k") {
    if (!passages.length) return;
    const cur = selected ? passages.indexOf(selected) : -1;
    const next = cur === -1 ? firstVisible() : Math.min(passages.length - 1, Math.max(0, cur + (e.key === "j" ? 1 : -1)));
    select(passages[next], { scroll: true });
  } else if (e.key === "Escape") {
    if (toc?.classList.contains("open")) closeToc();
    else if (selected) deselect();
  } else if (e.key === "[" || e.key === "]") {
    const a = document.querySelector<HTMLAnchorElement>(e.key === "[" ? "a[rel=prev]" : "a[rel=next]");
    if (a) location.href = a.href;
  }
});

// ---------------------------------------------------------------- contents

function openToc() {
  toc?.classList.add("open");
  scrim?.classList.add("show");
  centerInToc(toc?.querySelector<HTMLElement>("a.active, a[aria-current]"));
  toc?.querySelector<HTMLElement>("[data-toc-close]")?.focus();
}
function closeToc() {
  toc?.classList.remove("open");
  if (!panel?.classList.contains("open")) scrim?.classList.remove("show");
}
document.querySelector("[data-toc-open]")?.addEventListener("click", openToc);
document.querySelector("[data-toc-close]")?.addEventListener("click", closeToc);
toc?.addEventListener("click", (e) => {
  if ((e.target as HTMLElement).closest("a") && tocDrawer.matches) closeToc();
});
// Keep the current entry visible in a long list of contents, without
// scrolling the page itself.
function centerInToc(a: HTMLElement | null | undefined) {
  if (!toc || !a) return;
  toc.scrollTop = a.offsetTop - toc.clientHeight / 2 + a.offsetHeight / 2;
}
centerInToc(toc?.querySelector<HTMLElement>("a[aria-current]"));

// Scrollspy: highlight the contents entry for the division being read.
const tocLinks = new Map<string, HTMLAnchorElement>();
for (const a of toc?.querySelectorAll<HTMLAnchorElement>("a[data-toc-ref]") ?? []) tocLinks.set(a.dataset.tocRef!, a);
const headings = Array.from(document.querySelectorAll<HTMLElement>("[data-toc]")).filter((h) => tocLinks.has(h.dataset.toc!));
if (headings.length && "IntersectionObserver" in window) {
  let current: HTMLAnchorElement | undefined;
  const visible = new Set<HTMLElement>();
  const update = () => {
    const header = (document.querySelector(".site-header") as HTMLElement)?.offsetHeight ?? 0;
    let best: HTMLElement | undefined;
    for (const h of headings) if (h.getBoundingClientRect().top <= header + 120) best = h;
    best ??= headings[0];
    const link = tocLinks.get(best.dataset.toc!);
    if (link !== current) {
      current?.classList.remove("active");
      link?.classList.add("active");
      current = link;
    }
  };
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) en.isIntersecting ? visible.add(en.target as HTMLElement) : visible.delete(en.target as HTMLElement);
    update();
  }, { rootMargin: "0px 0px -60% 0px" });
  headings.forEach((h) => io.observe(h));
  window.addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
  update();
}

// ---------------------------------------------------------------- text size

const SIZES = ["s", "m", "l", "xl"];
document.querySelector("[data-size-toggle]")?.addEventListener("click", () => {
  const root = document.documentElement;
  const cur = root.getAttribute("data-size") || "m";
  const next = SIZES[(SIZES.indexOf(cur) + 1) % SIZES.length];
  if (next === "m") root.removeAttribute("data-size"); else root.setAttribute("data-size", next);
  try {
    if (next === "m") localStorage.removeItem("rp-size"); else localStorage.setItem("rp-size", next);
  } catch {
    /* preference lasts for this page only */
  }
  toast(`Text size: ${{ s: "small", m: "medium", l: "large", xl: "extra large" }[next]}`);
});

// ---------------------------------------------------------------- initial

const fromHash = decodeURIComponent(location.hash.slice(1));
const initial = fromHash ? document.getElementById(fromHash) : null;
if (initial?.classList.contains("passage")) select(initial, { hash: false });
window.addEventListener("hashchange", () => {
  const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (el?.classList.contains("passage") && el !== selected) select(el, { hash: false });
});
