// The /search/ page: every matching passage, grouped by the text it is in,
// with filters by work and (for The Federalist) by author. The query and
// filters live in the URL (?q=…&work=…&author=…) so results can be shared.

import { group, jump, note, row, search, shortWork, type PageHit } from "./search";

const root = document.querySelector<HTMLElement>("[data-search-page]")!;
const form = root.querySelector<HTMLFormElement>("form")!;
const input = root.querySelector<HTMLInputElement>("[data-search-input]")!;
const workBar = root.querySelector<HTMLElement>("[data-work-filters]")!;
const authorBar = root.querySelector<HTMLElement>("[data-author-filters]")!;
const summary = root.querySelector<HTMLElement>("[data-summary]")!;
const jumps = root.querySelector<HTMLElement>("[data-jumps]")!;
const list = root.querySelector<HTMLElement>("[data-results]")!;
const more = root.querySelector<HTMLButtonElement>("[data-more]")!;

const WORKS: [string, string][] = [
  ["", "All texts"],
  ["The Constitution of the United States", "Constitution"],
  ["Amendments to the Constitution of the United States", "Amendments"],
  ["The Federalist", "The Federalist"],
];
const AUTHORS: [string, string][] = [["", "Any author"], ["Alexander Hamilton", "Hamilton"], ["James Madison", "Madison"], ["John Jay", "Jay"]];
const PAGE_STEP = 10;
const SHOWN_PER_TEXT = 3;

const params = new URLSearchParams(location.search);
let state = { q: params.get("q") || "", work: params.get("work") || "", author: params.get("author") || "" };
input.value = state.q;
let token = 0;

function chips(bar: HTMLElement, options: [string, string][], key: "work" | "author") {
  bar.replaceChildren(
    ...options.map(([value, label]) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.setAttribute("aria-pressed", String(state[key] === value));
      b.addEventListener("click", () => {
        state = { ...state, [key]: value, ...(key === "work" && value !== "The Federalist" ? { author: "" } : {}) };
        render();
        run();
      });
      return b;
    }),
  );
}

function render() {
  chips(workBar, WORKS, "work");
  authorBar.hidden = state.work !== "The Federalist";
  if (!authorBar.hidden) chips(authorBar, AUTHORS, "author");
}

function syncUrl() {
  const u = new URL(location.href);
  for (const k of ["q", "work", "author"] as const) state[k] ? u.searchParams.set(k, state[k]) : u.searchParams.delete(k);
  history.replaceState(null, "", u);
  document.title = state.q ? `“${state.q}” · Search · Res Publica` : "Search · Res Publica";
}

function textBlock(p: PageHit): HTMLElement {
  const sec = document.createElement("section");
  sec.className = "srp-text";
  const h = document.createElement("h2");
  const a = document.createElement("a");
  a.href = p.url;
  a.textContent = p.title;
  const w = document.createElement("span");
  w.className = "srp-work";
  w.textContent = `${shortWork(p.work)} · ${p.passages.length} passage${p.passages.length === 1 ? "" : "s"}`;
  h.append(a, w);
  const ol = document.createElement("div");
  ol.className = "srp-passages";
  p.passages.forEach((ps, i) => {
    const r = row(ps.url, ps.label, ps.ref || "", ps.excerpt);
    if (i >= SHOWN_PER_TEXT) r.hidden = true;
    ol.append(r);
  });
  sec.append(h, ol);
  if (p.passages.length > SHOWN_PER_TEXT) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "srp-expand";
    const rest = p.passages.length - SHOWN_PER_TEXT;
    b.textContent = `Show ${rest} more in this text`;
    b.addEventListener("click", () => {
      ol.querySelectorAll<HTMLElement>("[hidden]").forEach((el) => (el.hidden = false));
      b.remove();
    });
    sec.append(b);
  }
  return sec;
}

async function run() {
  const mine = ++token;
  syncUrl();
  more.hidden = true;
  const q = state.q.trim();
  if (!q) {
    summary.textContent = "";
    jumps.replaceChildren();
    list.replaceChildren();
    return;
  }
  const j = await jump(q);
  if (mine !== token) return;
  jumps.replaceChildren(...(j.length ? [group("Jump to"), ...j.map((x) => row(x.url, x.title, x.ref))] : []));
  summary.textContent = "Searching…";
  list.replaceChildren();
  const filters: Record<string, string> = { work: state.work, author: state.author };
  const s = await search(q, filters, 150);
  if (mine !== token || s === "stale") return;
  if (s === null) {
    summary.textContent = "";
    list.replaceChildren(note("Full-text search could not load in this browser. Jump-to still works."));
    return;
  }
  let loaded = 0;
  let passages = 0;
  let shown = 0;
  const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
  const loadMore = async () => {
    more.disabled = true;
    const pages = await s.load(loaded, loaded + PAGE_STEP);
    if (mine !== token) return;
    loaded += PAGE_STEP;
    passages += pages.reduce((n, p) => n + p.passages.length, 0);
    shown += pages.length;
    list.append(...pages.map(textBlock));
    const left = Math.max(0, s.total - loaded);
    summary.textContent = shown
      ? `${plural(passages, "matching passage")} in ${plural(shown, "text")}${left ? " so far" : ""}`
      : "";
    if (!shown && !left) list.replaceChildren(note(`No passages found for “${q}”. Try fewer or different words.`));
    more.textContent = `Show more (${plural(left, "more text")} to check)`;
    more.hidden = !left;
    more.disabled = false;
  };
  more.onclick = loadMore;
  await loadMore();
}

let timer: number | undefined;
input.addEventListener("input", () => {
  state.q = input.value;
  window.clearTimeout(timer);
  timer = window.setTimeout(run, 200);
});
form.addEventListener("submit", (e) => {
  e.preventDefault();
  state.q = input.value;
  run();
});

render();
run();
if (!state.q) input.focus();
