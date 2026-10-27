// Search: "jump to" ref parsing plus Pagefind full-text search.
// Loaded only when someone opens search. Pagefind's index lives at
// {base}/pagefind/ (built by `make build`); it compiles WebAssembly, which is
// why the CSP allows 'wasm-unsafe-eval' and nothing else beyond 'self'.
//
// Pagefind ranks pages. To show every matching passage, each page's matched
// word positions are grouped by passage (Pagefind records every element with
// an id, and a passage's id is its ref), and each passage gets its own excerpt.

import { loading } from "./loader";

type RefEntry = { label: string; url: string; refs?: string };
export type Passage = { ref: string | null; label: string; url: string; excerpt: string; score: number; phrase: boolean };
export type PageHit = { url: string; title: string; work: string; passages: Passage[] };

// Paths in site data are root-relative; the site may be served under a base path.
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const withBase = (p: string) => (p.startsWith("/") && !p.startsWith("//") ? BASE + p : BASE + "/");
export const resultsUrl = (q: string, params: Record<string, string> = {}) => {
  const u = new URLSearchParams({ q, ...Object.fromEntries(Object.entries(params).filter(([, v]) => v)) });
  return `${BASE}/search/?${u}`;
};

let refsPromise: Promise<Record<string, RefEntry>> | null = null;
let pagefindPromise: Promise<any> | null = null;

function loadRefs() {
  refsPromise ??= fetch(`${BASE}/data/refs.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  return refsPromise;
}

// The paragraphs of a debate in Congress are in their own file, named by the
// debate's entry (decision 63): loaded into the same map when first needed.
const partsLoaded = new Map<string, Promise<void>>();
async function withRefsOf(prefixes: Iterable<string>): Promise<Record<string, RefEntry>> {
  const refs = await loadRefs();
  const lower = new Map(Object.keys(refs).filter((k) => !k.includes(".")).map((k) => [k.toLowerCase(), k]));
  await Promise.all([...new Set(prefixes)].map((p) => {
    const key = lower.get(p.toLowerCase());
    const file = key ? refs[key].refs : undefined;
    if (!file || !file.startsWith("/") || file.startsWith("//")) return;
    if (!partsLoaded.has(file)) {
      partsLoaded.set(file, fetch(`${BASE}${file}`).then((r) => (r.ok ? r.json() : {})).then((part) => {
        Object.assign(refs, part);
      }).catch(() => {}));
    }
    return partsLoaded.get(file);
  }));
  return refs;
}

export function loadPagefind() {
  const path = `${BASE}/pagefind/pagefind.js`;
  pagefindPromise ??= import(/* @vite-ignore */ path)
    .then(async (pf) => {
      await pf.options({ excerptLength: 30, baseUrl: `${BASE}/` });
      pf.init();
      return pf;
    })
    .catch((err) => {
      console.error("Search index failed to load", err);
      return null;
    });
  return pagefindPromise;
}

// ---------------------------------------------------------------- jump

const ROMAN: Record<string, number> = { i: 1, v: 5, x: 10, l: 50, c: 100 };
function num(s: string): number | null {
  if (/^\d+$/.test(s)) return parseInt(s, 10);
  if (!/^[ivxlc]+$/.test(s)) return null;
  let total = 0;
  for (let i = 0; i < s.length; i++) {
    const v = ROMAN[s[i]], next = ROMAN[s[i + 1]] ?? 0;
    total += next > v ? -v : v;
  }
  return total;
}

/** Candidate refs for a typed query such as "fed 10.4", "art 1 sec 8 cl 3",
 *  "1.8.3", "14th amendment", "amendment xiv 1", or an exact ref. */
export function jumpCandidates(raw: string): string[] {
  const q = raw.trim().toLowerCase().replace(/[,;:§¶]/g, " ").replace(/\s+/g, " ");
  if (!q) return [];
  const out: string[] = [];
  const N = "(\\d+|[ivxlc]+)";
  let m: RegExpMatchArray | null;

  if ((m = q.match(new RegExp(`^(?:the )?(?:fed(?:eralist)?(?: papers?)?|no\\.?)(?: no\\.?)? ?${N}(?:[. ]+(?:p(?:ara(?:graph)?)? ?)?(\\d+|fn\\d+|note \\d+))?$`)))) {
    const p = num(m[1]);
    if (p) {
      const sub = m[2]?.replace(/^note /, "fn");
      out.push(sub ? `Federalist.${p}.${sub}` : `Federalist.${p}`);
    }
  }
  if ((m = q.match(new RegExp(`^(?:amend(?:ment)?|am\\.?) ?${N}(?:[. ]+(?:sec(?:tion)?\\.? ?|cl(?:ause)?\\.? ?)?(\\d+))?$`))) ||
      (m = q.match(/^(\d+)(?:st|nd|rd|th) amend(?:ment)?(?:[. ]+(?:sec(?:tion)?\.? ?)?(\d+))?$/))) {
    const n = num(m[1]);
    if (n) out.push(m[2] ? `Amendment.${n}.${m[2]}` : `Amendment.${n}`);
  }
  if ((m = q.match(new RegExp(`^(?:art(?:icle)?\\.?) ?${N}(?:[. ]+(?:sec(?:tion)?\\.? ?)?(\\d+))?(?:[. ]+(?:cl(?:ause)?\\.? ?)?(\\d+))?$`)))) {
    const a = num(m[1]);
    if (a) {
      out.push(`Constitution.${[a, m[2], m[3]].filter(Boolean).join(".")}`);
      if (m[2] && !m[3]) out.push(`Constitution.${a}.${m[2]}`);
    }
  }
  if ((m = q.match(/^(\d+)\.(\d+)(?:\.(\d+))?$/))) out.push(`Constitution.${q}`);
  if (/^(the )?preamble$/.test(q)) out.push("Constitution.Preamble");
  if (/^(signers|signatures)$/.test(q)) out.push("Constitution.Signers");
  out.push(raw.trim()); // an exact ref, any case
  return out;
}

export async function jump(q: string): Promise<{ url: string; title: string; ref: string }[]> {
  const refs = await withRefsOf(jumpCandidates(q).filter((c) => c.includes(".")).map((c) => c.split(".")[0]));
  const lower = new Map(Object.keys(refs).map((k) => [k.toLowerCase(), k]));
  const seen = new Set<string>();
  const items = [];
  for (const cand of jumpCandidates(q)) {
    const key = lower.get(cand.toLowerCase());
    if (key && !seen.has(key)) {
      seen.add(key);
      items.push({ url: withBase(refs[key].url), title: refs[key].label, ref: key });
    }
  }
  return items;
}

// ---------------------------------------------------------------- passages

const STOP = new Set("a an and are as at be but by for from has have he his i in is it its of on or that the their them they this to was were which will with".split(" "));
const norm = (w: string) => w.toLowerCase().replace(/[^a-z0-9]/g, "");
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Index of the query term a matched word belongs to (Pagefind stems words,
 *  so "ambitious" matches "ambition": compare by shared prefix). */
function termOf(word: string, terms: string[]): number {
  const w = norm(word);
  let best = -1, bestLen = 0;
  terms.forEach((t, i) => {
    let k = 0;
    while (k < t.length && k < w.length && t[k] === w[k]) k++;
    if ((k === t.length || k >= 4) && k > bestLen) { best = i; bestLen = k; }
  });
  return best;
}

/** Excerpt of ~32 words around `center`, within [lo, hi), with matches marked.
 *  Returns HTML built only from escaped text and <mark>. */
function excerpt(words: string[], lo: number, hi: number, center: number, marks: Set<number>): string {
  const start = Math.max(lo, center - 10);
  const end = Math.min(hi, start + 32);
  let out = start > lo ? "… " : "";
  for (let i = start; i < end; i++) {
    const w = esc(words[i]);
    out += (marks.has(i) ? `<mark>${w}</mark>` : w) + " ";
  }
  return out.trim() + (end < hi ? " …" : "");
}

/** Every passage on a result page that matches the query, best first. */
export function passagesOf(data: any, query: string, refs: Record<string, RefEntry>): Passage[] {
  const words: string[] = (data.content || "").split(/\s+/);
  const terms = query.split(/\s+/).map(norm).filter(Boolean);
  const significant = terms.map((t, i) => (!STOP.has(t) ? i : -1)).filter((i) => i >= 0);
  const need = significant.length ? significant : terms.map((_, i) => i);
  // Passage boundaries: elements with a ref id that are passages (divs), in order.
  const anchors = (data.anchors || [])
    .filter((a: any) => a.element === "div" && /\./.test(a.id || ""))
    .sort((a: any, b: any) => a.location - b.location);
  const bounds = [{ id: null as string | null, start: 0 }, ...anchors.map((a: any) => ({ id: a.id as string, start: a.location as number }))];
  const groups = new Map<number, number[]>();
  for (const loc of data.locations || []) {
    let i = bounds.length - 1;
    while (i > 0 && bounds[i].start > loc) i--;
    if (!groups.has(i)) groups.set(i, []);
    groups.get(i)!.push(loc);
  }
  const out: Passage[] = [];
  for (const [i, locs] of groups) {
    const lo = bounds[i].start;
    const hi = i + 1 < bounds.length ? bounds[i + 1].start : words.length;
    const byTerm = new Map<number, number[]>();
    for (const l of locs) {
      const t = termOf(words[l] || "", terms);
      if (t >= 0) (byTerm.get(t) ?? byTerm.set(t, []).get(t)!).push(l);
    }
    const covered = need.filter((t) => byTerm.has(t)).length;
    if (covered < need.length) continue; // every significant word must appear
    const marked = new Set<number>(need.flatMap((t) => byTerm.get(t) || []));
    // A phrase match: the query's words in order, consecutively.
    const set = new Set(locs);
    let phraseAt = -1;
    if (terms.length > 1) {
      for (const l of byTerm.get(0) || []) {
        if (terms.every((_, k) => set.has(l + k) && termOf(words[l + k], terms) === k)) { phraseAt = l; break; }
      }
      if (phraseAt >= 0) terms.forEach((_, k) => marked.add(phraseAt + k));
    }
    // Otherwise, the tightest window holding every significant word.
    let window = 0, windowAt = Math.min(...marked);
    if (phraseAt < 0 && need.length > 1) {
      window = Infinity;
      for (const l of byTerm.get(need[0]) || []) {
        let lo2 = l, hi2 = l;
        for (const t of need.slice(1)) {
          const near = (byTerm.get(t) || []).reduce((b, x) => (Math.abs(x - l) < Math.abs(b - l) ? x : b), Infinity);
          lo2 = Math.min(lo2, near);
          hi2 = Math.max(hi2, near);
        }
        if (hi2 - lo2 < window) { window = hi2 - lo2; windowAt = lo2; }
      }
    }
    const center = phraseAt >= 0 ? phraseAt : windowAt;
    const ref = bounds[i].id;
    const hit = ref ? refs[ref] : undefined;
    out.push({
      ref: hit ? ref : null,
      label: hit ? hit.label : data.meta?.label ? `${data.meta.label}: ${data.meta.title}` : data.meta?.title || "Title",
      url: hit ? withBase(hit.url) : data.url,
      excerpt: excerpt(words, lo, hi, center, marked),
      // Phrase first, then words close together, then how often they occur.
      score: (phraseAt >= 0 ? 1000 : 300 / (1 + window)) + Math.min(marked.size, 20),
      phrase: phraseAt >= 0,
    });
  }
  return out.sort((a, b) => b.score - a.score);
}

// ---------------------------------------------------------------- search

export type Search = { total: number; load: (from: number, to: number) => Promise<PageHit[]> };

const SINGLE_PAGE_WORKS = ["The Constitution of the United States", "Amendments to the Constitution of the United States"];

/** Run a full-text search. `total` is the number of matching pages; `load`
 *  fetches and analyses a slice of them. Null if search cannot run here. */
export async function search(q: string, filters: Record<string, string> = {}, debounce = 0): Promise<Search | null | "stale"> {
  const pf = await loadPagefind();
  if (!pf) return null;
  q = q.replace(/ſ/g, "s"); // the index reads the long s as s (tools/search_site.py, decision 74)
  const f = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
  const res = debounce ? await pf.debouncedSearch(q, { filters: f }, debounce) : await pf.search(q, { filters: f });
  if (!res) return "stale";
  // Pagefind scores whole pages, and the Constitution and the Amendments are
  // each one long page holding many passages, so they rank below short papers
  // that repeat a phrase. Look them up directly and put them first.
  const first: any[] = [];
  for (const work of SINGLE_PAGE_WORKS) {
    if (f.work && f.work !== work) continue;
    const own = await pf.search(q, { filters: { ...f, work } });
    first.push(...own.results);
  }
  const ids = new Set(first.map((r: any) => r.id));
  const results = [...first, ...res.results.filter((r: any) => !ids.has(r.id))];
  const refs = await loadRefs();
  return {
    total: results.length,
    load: async (from, to) => {
      const datas = await Promise.all(results.slice(from, to).map((r: any) => r.data()));
      await withRefsOf(datas.flatMap((d: any) => (d.anchors || []).map((a: any) => String(a.id || "").split(".")[0]).filter(Boolean)));
      return datas
        .map((d: any) => {
          const work = d.filters?.work?.[0] || "";
          const passages = passagesOf(d, q, refs);
          // On equal matches, the constitutional text itself comes before writing about it.
          if (SINGLE_PAGE_WORKS.includes(work)) passages.forEach((p) => (p.score += 25));
          return {
            url: d.url,
            title: d.meta?.label ? `${d.meta.label}: ${d.meta.title}` : d.meta?.title || d.url,
            work,
            passages,
          };
        })
        .filter((p: PageHit) => p.passages.length)
        .sort((a: PageHit, b: PageHit) => b.passages[0].score - a.passages[0].score);
    },
  };
}

// ---------------------------------------------------------------- palette

const SHORT: Record<string, string> = {
  "The Constitution of the United States": "Constitution",
  "Amendments to the Constitution of the United States": "Amendments",
  "The Federalist": "Federalist",
};
export const shortWork = (w: string) => SHORT[w] || w;

export function row(href: string, title: string, meta: string, excerptHtml?: string): HTMLAnchorElement {
  const a = document.createElement("a");
  a.className = "sr-item";
  a.href = href;
  a.setAttribute("role", "option");
  const t = document.createElement("div");
  t.className = "sr-title";
  t.append(document.createTextNode(title));
  if (meta) {
    const r = document.createElement("span");
    r.className = "ref";
    r.textContent = meta;
    t.append(r);
  }
  a.append(t);
  if (excerptHtml) {
    const p = document.createElement("p");
    p.className = "sr-excerpt";
    p.innerHTML = excerptHtml; // escaped text and <mark> only (see excerpt())
    a.append(p);
  }
  return a;
}

export function group(label: string) {
  const h = document.createElement("div");
  h.className = "sr-group";
  h.textContent = label;
  return h;
}

export function note(text: string, cls = "sr-empty") {
  const p = document.createElement("p");
  p.className = cls;
  p.textContent = text;
  return p;
}

const attached = new WeakSet<Element>();

/** The search dialog: quick results while typing; Enter opens the full
 *  results page unless a result has been picked with the arrow keys. */
export function attachPalette(dialog: HTMLDialogElement, initial = "") {
  const input = dialog.querySelector<HTMLInputElement>("[data-search-input]")!;
  const results = dialog.querySelector<HTMLElement>("[data-search-results]")!;
  const all = dialog.querySelector<HTMLAnchorElement>("[data-search-all]");
  if (initial) input.value = initial;
  input.focus();
  input.select();
  if (attached.has(dialog)) {
    run();
    return;
  }
  attached.add(dialog);
  let active = -1;
  let token = 0;

  async function run() {
    const q = input.value.trim();
    const mine = ++token;
    active = -1;
    if (!q) {
      results.replaceChildren();
      if (all) all.hidden = true;
      return;
    }
    const jumps = await jump(q);
    if (mine !== token) return;
    const head: Node[] = [];
    if (jumps.length) head.push(group("Jump to"), ...jumps.map((j) => row(j.url, j.title, j.ref)));
    if (all) {
      all.hidden = false;
      all.href = resultsUrl(q);
      all.querySelector("[data-q]")!.textContent = q;
    }
    results.replaceChildren(...head, loading("Searching…", "sr-loading"));
    const s = await search(q, {}, 150);
    if (mine !== token || s === "stale") return;
    if (s === null) {
      results.replaceChildren(...head, note("Full-text search could not load in this browser. Jump-to still works."));
      return;
    }
    const pages = await s.load(0, 8);
    if (mine !== token) return;
    // Best passages across texts, at most two from any one text.
    const best = pages
      .flatMap((p) => p.passages.slice(0, 2).map((ps) => ({ ps, work: p.work })))
      .sort((a, b) => b.ps.score - a.ps.score)
      .slice(0, 6);
    const rows = best.map(({ ps, work }) => row(ps.url, ps.label, shortWork(work), ps.excerpt));
    results.replaceChildren(...head, ...(rows.length ? [group("Passages"), ...rows] : [note(`No passages found for “${q}”.`)]));
  }

  function move(delta: number) {
    const items = Array.from(results.querySelectorAll<HTMLElement>(".sr-item"));
    if (!items.length) return;
    active = (active + delta + items.length) % items.length;
    items.forEach((el, i) => el.setAttribute("aria-selected", String(i === active)));
    items[active].scrollIntoView({ block: "nearest" });
  }

  input.addEventListener("input", run);
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    else if (e.key === "Enter") {
      e.preventDefault();
      const q = input.value.trim();
      const items = results.querySelectorAll<HTMLAnchorElement>(".sr-item");
      const target = active >= 0 ? items[active]?.href : q ? resultsUrl(q) : null;
      if (target) {
        dialog.close();
        location.href = target;
      }
    }
  });
  results.addEventListener("click", (e) => {
    const a = (e.target as HTMLElement).closest<HTMLAnchorElement>("a");
    if (!a) return;
    // A passage on this page: close the search first, then go to the passage,
    // so closing the dialog (which returns focus to the search button) does
    // not leave the page scrolled elsewhere.
    if (a.pathname === location.pathname && a.hash) {
      e.preventDefault();
      dialog.close();
      requestAnimationFrame(() => {
        if (location.hash === a.hash) window.dispatchEvent(new HashChangeEvent("hashchange"));
        else location.hash = a.hash;
      });
      return;
    }
    dialog.close();
  });
  dialog.querySelector("form")?.addEventListener("submit", (e) => e.preventDefault());
  loadPagefind();
  run();
}
