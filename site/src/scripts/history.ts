// Where you've been, and continue reading. Kept in this browser only
// (localStorage); nothing is sent anywhere, and Clear empties it.
//
// The history is one list of places, oldest first, with the current place
// marked. A page or a jump within a page (a link, a search result, the
// contents) adds a place; revisiting a place by Back, Forward or the list
// moves to it without adding one, and going somewhere new from an earlier
// place moves that place to the end first, so Back always means "where I came
// from". The current place follows the reader: its address is updated to
// the passage at the top of the screen once scrolling stops, so returning
// lands where they left off. Continue reading keeps the same for each work.

const KEY = "rp-history";
const NAV = "rp-history-nav";
const WORKS = "rp-continue";
const MAX = 100;
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
// Pages that are tools, not reading: not recorded.
const SKIP = new Set(["/", "/search/", "/review/", "/errata/"].map((p) => BASE + p));

type Item = { id: string; u: string; t: string; w?: string; at: number };
type State = { items: Item[]; cur: string | null };
type Works = Record<string, { u: string; t: string; w?: string; at: number }>;

// Only paths on this site (never another scheme or host: CLAUDE.md rule 8).
const isPath = (u: unknown): u is string => typeof u === "string" && u.startsWith("/") && !u.startsWith("//");

function read<T>(key: string, fallback: T, store: Storage = localStorage): T {
  try {
    return (JSON.parse(store.getItem(key) || "null") as T) ?? fallback;
  } catch {
    return fallback;
  }
}
function write(key: string, value: unknown, store: Storage = localStorage) {
  try {
    if (value === null) store.removeItem(key);
    else store.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable or full: history lasts for this page only */
  }
}

function load(): State {
  const s = read<State>(KEY, { items: [], cur: null });
  const items = Array.isArray(s.items) ? s.items.filter((x) => x && typeof x.id === "string" && isPath(x.u)) : [];
  return { items, cur: items.some((x) => x.id === s.cur) ? s.cur : null };
}
const save = (s: State) => write(KEY, s);
const newId = () => Math.random().toString(36).slice(2, 10);
const pageTitle = () => document.title.replace(/ · Res Publica$/, "");
const pathOf = (u: string) => u.split("#")[0];
const here = () => location.pathname + location.search;
const recordable = () => !SKIP.has(location.pathname) && !document.querySelector("[data-not-found]");

// The passage being read: the selected one while it is on screen, else the
// first one mostly below the header (not one that has nearly scrolled away).
function topPassage(): HTMLElement | null {
  const line = (document.querySelector<HTMLElement>(".site-header")?.offsetHeight ?? 0) + 8;
  const sel = document.querySelector<HTMLElement>(".passage.is-selected[data-ref]");
  if (sel) {
    const r = sel.getBoundingClientRect();
    if (r.bottom > line && r.top < window.innerHeight) return sel;
  }
  if (window.scrollY < 40) return null;
  for (const el of document.querySelectorAll<HTMLElement>(".passage[data-ref]")) {
    const r = el.getBoundingClientRect();
    if (r.bottom > line + Math.min(80, r.height / 2)) return el;
  }
  return null;
}

// ---------------------------------------------------------------- recording

let curId: string | null = null;

function add(u: string): Item | null {
  const s = load();
  const at = s.items.findIndex((x) => x.id === s.cur);
  // Leaving an earlier place for somewhere new: that place moves to the end,
  // so Back from the new place returns to it.
  if (at >= 0 && at < s.items.length - 1) s.items.push(...s.items.splice(at, 1));
  const prev = s.items.at(-1) ?? null;
  if (prev && prev.u === u) {
    s.cur = curId = prev.id;
    save(s);
    return null;
  }
  const item: Item = { id: newId(), u, t: pageTitle(), at: Date.now() };
  const target = u.includes("#") ? document.getElementById(decodeURIComponent(u.split("#")[1])) : null;
  const label = target?.closest<HTMLElement>("[data-label]")?.dataset.label;
  if (label) item.w = label;
  s.items.push(item);
  if (s.items.length > MAX) s.items.splice(0, s.items.length - MAX);
  s.cur = curId = item.id;
  save(s);
  return prev;
}

// The current place follows the reader (once scrolling stops), and so does
// the work's continue-reading place.
function track() {
  if (!curId) return;
  const p = topPassage();
  const u = here() + (p ? `#${p.id}` : "");
  const s = load();
  const item = s.items.find((x) => x.id === curId);
  if (!item) return;
  item.u = u;
  item.at = Date.now();
  if (p?.dataset.label) item.w = p.dataset.label;
  else delete item.w;
  save(s);
  const work = location.pathname.slice(BASE.length).split("/")[1];
  if (work && document.querySelector(".passage[data-ref]")) {
    const works = read<Works>(WORKS, {});
    works[work] = { u, t: pageTitle(), ...(item.w ? { w: item.w } : {}), at: item.at };
    write(WORKS, works);
  }
}

// ---------------------------------------------------------------- moving

function go(id: string) {
  const s = load();
  const item = s.items.find((x) => x.id === id);
  if (!item) return;
  write(NAV, { id }, sessionStorage);
  const [path, hash] = item.u.split("#");
  if (path === here()) {
    s.cur = curId = id;
    save(s);
    closeHistory();
    if (hash) {
      // The hashchange handler below sees the marker and adds no place.
      const el = document.getElementById(decodeURIComponent(hash));
      history.pushState(null, "", `#${hash}`);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
      if (el && !el.closest(".passage")) el.scrollIntoView({ block: "start" });
    } else {
      write(NAV, null, sessionStorage);
      history.pushState(null, "", here());
      window.scrollTo({ top: 0 });
    }
    return;
  }
  location.href = item.u;
}

function neighbour(step: number): Item | null {
  const s = load();
  const at = s.items.findIndex((x) => x.id === s.cur);
  return at >= 0 ? s.items[at + step] ?? null : null;
}

// ---------------------------------------------------------------- back chip

const chip = document.querySelector<HTMLElement>("[data-back-chip]");
let chipTimer: number | undefined;
function showChip(prev: Item | null) {
  if (!chip || !prev || Date.now() - prev.at > 6 * 3600e3) return;
  const label = chip.querySelector("[data-back-chip-label]");
  if (label) label.textContent = prev.w ? `${prev.w}` : prev.t;
  const a = chip.querySelector<HTMLAnchorElement>("[data-back-chip-link]");
  if (a) {
    a.href = prev.u;
    a.onclick = (e) => {
      e.preventDefault();
      chip.hidden = true;
      go(prev.id);
    };
  }
  chip.hidden = false;
  window.clearTimeout(chipTimer);
  chipTimer = window.setTimeout(() => (chip.hidden = true), 20000);
}
chip?.querySelector("[data-back-chip-close]")?.addEventListener("click", () => (chip.hidden = true));

// ---------------------------------------------------------------- the list

// The list itself (history-list.ts) loads when first opened.
const dialog = document.querySelector<HTMLDialogElement>("[data-history-dialog]");
let listModule: Promise<typeof import("./history-list")> | null = null;
export const store = { load, save, read, write, go, neighbour, KEY, WORKS, clearCurrent: () => (curId = null) };

function closeHistory() {
  if (dialog?.open) dialog.close();
}

for (const b of document.querySelectorAll<HTMLButtonElement>("[data-history-open]")) {
  b.addEventListener("click", async () => {
    if (!dialog) return;
    track();
    if (chip) chip.hidden = true;
    listModule ??= import("./history-list");
    (await listModule).open(dialog, store);
  });
}

// ---------------------------------------------------------------- continue reading

// Rendered from what was stored before this page, so it does not point at
// the page being read now.
function renderContinue() {
  const works = read<Works>(WORKS, {});
  for (const el of document.querySelectorAll<HTMLElement>("[data-continue]")) {
    const scope = el.dataset.continue;
    const list = el.querySelector("[data-continue-list]");
    if (!list) continue;
    const entries = Object.entries(works)
      .filter(([k, v]) => v && isPath(v.u) && (!scope || k === scope))
      .sort((a, b) => b[1].at - a[1].at)
      .slice(0, scope ? 1 : 3);
    list.replaceChildren();
    for (const [, v] of entries) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = v.u;
      a.append(Object.assign(document.createElement("strong"), { textContent: v.w || v.t }));
      if (v.w) a.append(Object.assign(document.createElement("span"), { textContent: v.t }));
      li.append(a);
      list.append(li);
    }
    el.hidden = !entries.length;
  }
}

// ---------------------------------------------------------------- start

renderContinue();

if (recordable()) {
  const nav = read<{ id: string } | null>(NAV, null, sessionStorage);
  write(NAV, null, sessionStorage);
  const s = load();
  const byNav = nav && s.items.find((x) => x.id === nav.id && pathOf(x.u) === here());
  const kind = (performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined)?.type;
  const current = s.items.find((x) => x.id === s.cur);
  if (byNav) {
    s.cur = curId = byNav.id;
    save(s);
  } else if ((kind === "reload" || kind === "back_forward") && current && pathOf(current.u) === here()) {
    curId = current.id;
  } else if (kind === "back_forward") {
    // The browser's own Back or Forward: the nearest place with this page.
    const at = s.items.findIndex((x) => x.id === s.cur);
    const order = s.items.map((x, i) => ({ x, d: Math.abs(i - at) })).sort((a, b) => a.d - b.d);
    const found = order.find(({ x }) => pathOf(x.u) === here())?.x;
    if (found) {
      s.cur = curId = found.id;
      save(s);
    } else add(here() + location.hash);
  } else {
    const prev = add(here() + location.hash);
    // Arrived by following a link on this site: offer the way back.
    if (prev && document.referrer && new URL(document.referrer).origin === location.origin) showChip(prev);
  }

  let timer: number | undefined;
  window.addEventListener("scroll", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(track, 700);
  }, { passive: true });
  window.addEventListener("pagehide", track);
  // Every jump starts with a tap, click or key: note the place first, in case
  // scrolling has not yet stopped long enough for the timer.
  let last = 0;
  const now = () => {
    if (Date.now() - last < 300) return;
    last = Date.now();
    window.clearTimeout(timer);
    track();
  };
  document.addEventListener("pointerdown", now, { capture: true, passive: true });
  document.addEventListener("keydown", now, { capture: true, passive: true });
  document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" && track());

  // A jump within the page (a link, a search result, the contents).
  window.addEventListener("hashchange", () => {
    const nav2 = read<{ id: string } | null>(NAV, null, sessionStorage);
    write(NAV, null, sessionStorage);
    if (nav2) return;
    window.clearTimeout(timer);
    const prev = add(here() + location.hash);
    showChip(prev);
  });
}
