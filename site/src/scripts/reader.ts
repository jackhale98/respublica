// Reader behavior: select a passage to show it in the panel (bottom sheet on
// phones), j/k to move between passages, contents drawer, scrollspy,
// copy link/text, text size. Without JavaScript the page is fully readable:
// anchors still work and connections show inline under each passage.

import { loading } from "./loader";

const toast = (m: string) => (window as any).rpToast?.(m);
const panel = document.querySelector<HTMLElement>("[data-panel]");
const scrim = document.querySelector<HTMLElement>("[data-scrim]");
const toc = document.querySelector<HTMLElement>("[data-toc-nav]");
const passages = Array.from(document.querySelectorAll<HTMLElement>(".passage"));
const narrow = window.matchMedia("(max-width: 63.99rem)");
const tocDrawer = window.matchMedia("(max-width: 79.99rem)");

let selected: HTMLElement | null = null;

// ---------------------------------------------------------------- connections

type Conn = {
  verb: string; status: string; other: string; other_label: string; other_url: string | null;
  other_overruled?: boolean; other_quote?: string; rationale?: string; source?: string;
  other_excerpt?: { before: string; quote: string; after: string }; other_whole?: boolean;
};
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const connUrl = document.querySelector<HTMLElement>("[data-reader]")?.dataset.connUrl;
let connData: Promise<Record<string, Conn[]>> | null = null;
const loadConns = () =>
  (connData ??= connUrl ? fetch(connUrl).then((r) => (r.ok ? r.json() : {})).catch(() => ({})) : Promise.resolve({}));

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}

// ---------------------------------------------------------------- previews
// A connection's far end, read in the panel: one small file per passage
// (/data/preview/{ref}.json), fetched the first time a preview is opened.

type Preview = {
  label: string; url: string | null; text?: string; clipped?: boolean; more?: number; note?: string;
  case?: { date?: string; us_cite?: string; docket?: string };
};
const previewData = new Map<string, Promise<Record<string, Preview>>>();
const loadPreviews = (ref: string) => {
  if (!previewData.has(ref)) {
    previewData.set(ref, fetch(`${BASE}/data/preview/${encodeURIComponent(ref)}.json`)
      .then((r) => (r.ok ? r.json() : {})).catch(() => ({})));
  }
  return previewData.get(ref)!;
};
const localHref = (url: string | null) => (url && url.startsWith("/") && !url.startsWith("//") ? BASE + url : null);

function caseLine(c: NonNullable<Preview["case"]>): string {
  const parts = [c.us_cite || (c.docket ? `No. ${c.docket}` : "")];
  if (c.date) {
    const d = c.date.length === 4 ? c.date
      : new Date(`${c.date}T12:00:00Z`).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
    parts.push(`decided ${d}`);
  }
  return parts.filter(Boolean).join(", ");
}

function renderPreview(pv: Preview, quote?: string): HTMLElement {
  const box = el("div", "conn-preview");
  if (pv.case) box.append(el("p", "pv-meta", caseLine(pv.case)));
  if (pv.text) {
    const text = el("div", "pv-text");
    for (const para of pv.text.split("\n\n")) {
      const p = el("p");
      const at = quote ? para.indexOf(quote) : -1;
      if (at >= 0) p.append(para.slice(0, at), el("mark", undefined, quote), para.slice(at + quote!.length));
      else p.textContent = para;
      text.append(p);
    }
    box.append(text);
  }
  const notes = [pv.note, pv.more ? `${pv.more} more ${pv.more === 1 ? "paragraph" : "paragraphs"}` : ""].filter(Boolean);
  if (notes.length) box.append(el("p", "pv-note", notes.join(" · ")));
  const go = localHref(pv.url);
  if (go) {
    const a = el("a", "pv-go", pv.case ? "Open the case" : pv.clipped || pv.more ? "Read it all" : "Go to passage");
    a.href = go;
    a.append(el("span", undefined, " →"));
    box.append(a);
  }
  return box;
}

function previewToggle(c: Conn, here: string, li: HTMLLIElement): HTMLButtonElement {
  const b = el("button", "conn-pv", "Preview");
  b.type = "button";
  b.setAttribute("aria-expanded", "false");
  b.setAttribute("aria-label", `Preview ${c.other_label}`);
  b.addEventListener("click", async (e) => {
    e.stopPropagation();
    const open = b.getAttribute("aria-expanded") === "true";
    // One preview open at a time.
    panel?.querySelectorAll<HTMLButtonElement>(".conn-pv[aria-expanded=true]").forEach((x) => {
      x.setAttribute("aria-expanded", "false");
      x.textContent = "Preview";
      x.closest(".conn")?.querySelector(".conn-preview")?.remove();
    });
    if (open) return;
    b.setAttribute("aria-expanded", "true");
    b.textContent = "Close";
    const wait = loading("Loading…", "muted");
    li.append(wait);
    const pv = (await loadPreviews(here))[c.other];
    wait.remove();
    if (b.getAttribute("aria-expanded") !== "true") return;
    li.append(pv ? renderPreview(pv, c.other_quote) : el("p", "pv-note", "No preview for this connection."));
  });
  return b;
}

function renderConn(c: Conn, here: string): HTMLLIElement {
  const li = el("li", `conn ${c.status}`);
  const top = el("div", "conn-top");
  top.append(el("span", "conn-verb", c.verb));
  if (c.status === "suggested") {
    const b = el("span", "badge suggested", "Suggested");
    b.title = "Proposed by a machine; not yet reviewed by a person";
    top.append(b);
  }
  if (c.status === "reviewed") top.append(el("span", "badge reviewed", "Reviewed"));
  if (c.other_overruled) top.append(el("span", "badge overruled", "Overruled"));
  if (!c.other_whole) top.append(previewToggle(c, here, li));
  li.append(top);
  const url = c.other_url;
  if (url && url.startsWith("/") && !url.startsWith("//")) {
    const a = el("a", "conn-target", c.other_label);
    a.href = BASE + url;
    li.append(a);
  } else li.append(el("span", "conn-target", c.other_label));
  // The linked passage's own words around the quote, the quoted words marked.
  const ex = c.other_excerpt;
  if (ex && (ex.before || ex.quote || ex.after)) {
    const bq = el("blockquote");
    if (ex.before) bq.append(ex.before);
    if (ex.quote) bq.append(el("mark", undefined, ex.quote));
    if (ex.after) bq.append(ex.after);
    li.append(bq);
  } else if (c.other_quote) li.append(el("blockquote", undefined, c.other_quote));
  if (c.rationale) li.append(el("p", "why", c.rationale));
  if (c.source) li.append(el("p", "src", `Source: ${c.source}`));
  return li;
}

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
  const source = q("[data-panel-source]");
  const src = p.querySelector<HTMLTemplateElement>("template.src-data");
  if (source) {
    source.replaceChildren(...(src ? [src.content.cloneNode(true)] : []));
    source.hidden = !src;
  }
  const conns = q("[data-panel-conns]")!;
  const empty = q("[data-panel-empty]")!;
  const has = !!p.querySelector(".conns");
  empty.hidden = has;
  q("[data-action=show-graph]")!.hidden = !has;
  conns.replaceChildren(...(has ? [loading("Loading connections…", "muted")] : []));
  if (has) {
    loadConns().then((data) => {
      if (selected !== p) return;
      const list = el("ul", "conn-list");
      list.append(...(data[p.id] || []).map((c) => renderConn(c, p.id)));
      conns.replaceChildren(list);
    });
  }
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

// ---------------------------------------------------------------- graph

const graphDialog = document.querySelector<HTMLDialogElement>("[data-graph-dialog]");
const graphUrl = document.querySelector<HTMLElement>("[data-reader]")?.dataset.graphUrl;
graphDialog?.querySelector("[data-graph-close]")?.addEventListener("click", () => graphDialog.close());
graphDialog?.addEventListener("click", (e) => {
  if (e.target === graphDialog) graphDialog.close();
});

async function showGraph(ref: string) {
  if (!graphDialog || !graphUrl) return;
  const { openGraph } = await import("./graph");
  await openGraph(graphDialog, graphUrl, ref, (target) => {
    const p = document.getElementById(target);
    if (p?.classList.contains("passage")) select(p, { scroll: true });
  });
}

panel?.addEventListener("click", (e) => {
  const action = (e.target as HTMLElement).closest<HTMLElement>("[data-action]")?.dataset.action;
  if (!action || !selected) return;
  if (action === "show-graph") showGraph(selected.id);
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

// Scrollspy: highlight the contents entries for the division and the
// passage being read (a passage is in the contents when it is a clause or
// section of a division, or stands outside any division).
const tocLinks = new Map<string, HTMLAnchorElement>();
for (const a of toc?.querySelectorAll<HTMLAnchorElement>("a[data-toc-ref]") ?? []) tocLinks.set(a.dataset.tocRef!, a);
const headings = Array.from(document.querySelectorAll<HTMLElement>("[data-toc]")).filter((h) => tocLinks.has(h.dataset.toc!));
const spied = Array.from(document.querySelectorAll<HTMLElement>(".passage[data-ref]")).filter((p) => tocLinks.has(p.dataset.ref!));
if ((headings.length || spied.length) && "IntersectionObserver" in window) {
  const current: (HTMLAnchorElement | undefined)[] = [undefined, undefined];
  const mark = (i: number, link: HTMLAnchorElement | undefined) => {
    if (link === current[i]) return;
    current[i]?.classList.remove("active");
    link?.classList.add("active");
    current[i] = link;
  };
  const above = (els: HTMLElement[], line: number) => {
    let best: HTMLElement | undefined;
    for (const el of els) if (el.getBoundingClientRect().top <= line) best = el;
    return best;
  };
  const update = () => {
    const line = ((document.querySelector(".site-header") as HTMLElement)?.offsetHeight ?? 0) + 120;
    const h = above(headings, line) ?? (spied.length ? undefined : headings[0]);
    mark(0, h && tocLinks.get(h.dataset.toc!));
    const p = above(spied, line) ?? (headings.length ? undefined : spied[0]);
    mark(1, p && tocLinks.get(p.dataset.ref!));
  };
  const io = new IntersectionObserver(update, { rootMargin: "0px 0px -60% 0px" });
  [...headings, ...spied].forEach((el) => io.observe(el));
  window.addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
  update();
}

// ---------------------------------------------------------------- swipe

// On screens where the contents are a drawer, a left-to-right swipe across
// the page opens them and a right-to-left swipe closes them. Swipes that
// start at the very left edge are left to the browser (back), and swipes
// inside the passage panel, dialogs or wide content are ignored.
let swipe: { x: number; y: number; t: number } | null = null;
document.addEventListener("touchstart", (e) => {
  swipe = null;
  if (!tocDrawer.matches || e.touches.length !== 1) return;
  const t = e.touches[0];
  const target = e.target as HTMLElement;
  if (t.clientX < 24 || target.closest("dialog, [data-panel], pre, table, input, textarea, .graph-canvas")) return;
  swipe = { x: t.clientX, y: t.clientY, t: performance.now() };
}, { passive: true });
document.addEventListener("touchend", (e) => {
  if (!swipe) return;
  const t = e.changedTouches[0];
  const dx = t.clientX - swipe.x, dy = t.clientY - swipe.y, dt = performance.now() - swipe.t;
  swipe = null;
  if (dt > 800 || Math.abs(dy) > Math.abs(dx) * 0.5 || window.getSelection()?.toString()) return;
  const open = toc?.classList.contains("open");
  if (!open && dx > 70 && !panel?.classList.contains("open")) openToc();
  else if (open && dx < -60) closeToc();
}, { passive: true });

// ---------------------------------------------------------------- place bar

// Scrolling back up a little shows a slim bar under the header naming the
// page and the division being read; scrolling down, or reaching the top,
// hides it. The bar opens the contents (a drawer on narrow screens; on wide
// ones, where the contents are always shown, it scrolls to the division).
const placebar = document.querySelector<HTMLElement>("[data-placebar]");
const placeHeadings = Array.from(document.querySelectorAll<HTMLElement>("[data-place]"));
const docHead = document.querySelector<HTMLElement>(".doc-head");
if (placebar) {
  const here = placebar.querySelector<HTMLElement>("[data-placebar-here]")!;
  let lastY = window.scrollY, turnY = lastY, shown = false, current: HTMLElement | undefined;
  const show = (on: boolean) => {
    if (on === shown) return;
    shown = on;
    // Sit just under the site header, whatever its height on this screen.
    const header = document.querySelector<HTMLElement>(".site-header");
    if (on && header) placebar.style.top = `${Math.max(0, header.getBoundingClientRect().bottom)}px`;
    placebar.classList.toggle("show", on);
    placebar.toggleAttribute("inert", !on);
  };
  const place = () => {
    const top = ((document.querySelector(".site-header") as HTMLElement)?.offsetHeight ?? 0) + 72;
    let best: HTMLElement | undefined;
    for (const h of placeHeadings) if (h.getBoundingClientRect().top <= top) best = h;
    current = best;
    // "Article I, Section 8": a section heading's label already names its article.
    here.textContent = best?.dataset.place ?? "";
  };
  const onScroll = () => {
    const y = window.scrollY;
    const pastHead = docHead ? docHead.getBoundingClientRect().bottom < 0 : y > 300;
    if ((y > lastY) !== (lastY > turnY)) turnY = lastY; // direction changed
    if (!pastHead) show(false);
    else if (y < turnY - 24) { place(); show(true); }
    else if (y > turnY + 12) show(false);
    lastY = y;
  };
  window.addEventListener("scroll", () => requestAnimationFrame(onScroll), { passive: true });
  placebar.querySelector("[data-placebar-open]")?.addEventListener("click", () => {
    if (tocDrawer.matches) { show(false); openToc(); }
    else (current ?? docHead)?.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
  placebar.querySelector("[data-placebar-top]")?.addEventListener("click", () => {
    show(false);
    window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
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

// A retired ref's anchor sits inside the passage it was merged into.
const passageFor = (id: string) => (id ? document.getElementById(id)?.closest<HTMLElement>(".passage") : null) ?? null;
const initial = passageFor(decodeURIComponent(location.hash.slice(1)));
if (initial) select(initial, { hash: false });
window.addEventListener("hashchange", () => {
  const el = passageFor(decodeURIComponent(location.hash.slice(1)));
  if (el && el !== selected) select(el, { hash: false });
});
