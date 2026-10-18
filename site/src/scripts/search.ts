// Search: "jump to" ref parsing plus Pagefind full-text search.
// Loaded only when someone opens search. Pagefind's index lives at
// /pagefind/ (built by `make build`); it compiles WebAssembly, which is why
// the CSP allows 'wasm-unsafe-eval' and nothing else beyond 'self'.

type RefEntry = { label: string; url: string };
type Item = { url: string; title: string; ref?: string; excerpt?: string };

let refsPromise: Promise<Record<string, RefEntry>> | null = null;
let pagefindPromise: Promise<any> | null = null;

function loadRefs() {
  refsPromise ??= fetch("/data/refs.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  return refsPromise;
}

function loadPagefind() {
  const path = "/pagefind/pagefind.js";
  pagefindPromise ??= import(/* @vite-ignore */ path)
    .then(async (pf) => {
      await pf.options({ excerptLength: 26 });
      pf.init();
      return pf;
    })
    .catch(() => null);
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
      const parts = [a, m[2], m[3]].filter(Boolean).join(".");
      out.push(`Constitution.${parts}`);
      if (m[2] && !m[3]) out.push(`Constitution.${a}.${m[2]}`);
    }
  }
  if ((m = q.match(/^(\d+)\.(\d+)(?:\.(\d+))?$/))) out.push(`Constitution.${q}`);
  if (/^(the )?preamble$/.test(q)) out.push("Constitution.Preamble");
  if (/^(signers|signatures)$/.test(q)) out.push("Constitution.Signers");
  // An exact ref, any case.
  out.push(raw.trim());
  return out;
}

async function jump(q: string): Promise<Item[]> {
  const refs = await loadRefs();
  const lower = new Map(Object.keys(refs).map((k) => [k.toLowerCase(), k]));
  const seen = new Set<string>();
  const items: Item[] = [];
  for (const cand of jumpCandidates(q)) {
    const key = lower.get(cand.toLowerCase());
    if (key && !seen.has(key)) {
      seen.add(key);
      items.push({ url: refs[key].url, title: refs[key].label, ref: key });
    }
  }
  return items;
}

// ---------------------------------------------------------------- full text

/** Pagefind excerpts are HTML with <mark>. Keep only the text and <mark>. */
function safeExcerpt(html: string): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
  let out = "";
  const walk = (n: Node) => {
    for (const c of Array.from(n.childNodes)) {
      if (c.nodeType === Node.TEXT_NODE) out += esc(c.textContent || "");
      else if (c.nodeName === "MARK") { out += "<mark>"; walk(c); out += "</mark>"; }
      else walk(c);
    }
  };
  walk(doc.body);
  return out;
}

/** The passage (an element whose id is a ref) holding the first match.
 *  Pagefind records every element with an id as an anchor with its word
 *  position, so the nearest anchor before the match is its passage. */
function passageFor(anchors: any[], locations: number[]): string | null {
  const first = locations[0];
  if (first === undefined) return null;
  let best: string | null = null;
  for (const a of anchors) if (/\./.test(a.id || "") && a.location <= first) best = a.id;
  return best;
}

async function fullText(q: string, filters: Record<string, string>): Promise<Item[] | null> {
  const pf = await loadPagefind();
  if (!pf) return null;
  const search = await pf.debouncedSearch(q, { filters }, 120);
  if (!search) return [];
  const refs = await loadRefs();
  const datas = await Promise.all(search.results.slice(0, 12).map((r: any) => r.data()));
  const items: Item[] = [];
  const seen = new Set<string>();
  const add = (anchors: any[], locations: number[], excerpt: string, fallbackUrl: string, fallbackTitle: string) => {
    const ref = passageFor(anchors, locations);
    const key = ref || fallbackUrl;
    if (seen.has(key)) return;
    seen.add(key);
    const hit = ref ? refs[ref] : undefined;
    items.push({ url: hit ? hit.url : fallbackUrl, title: hit ? hit.label : fallbackTitle, ref: hit ? ref! : undefined, excerpt: safeExcerpt(excerpt) });
  };
  for (const d of datas) {
    const anchors = d.anchors || [];
    // One-page works (the Constitution) split into sections; show the best few.
    const subs = (d.sub_results || []).filter((s: any) => s.locations?.length)
      .sort((a: any, b: any) => b.locations.length - a.locations.length).slice(0, 4);
    if (subs.length > 1) for (const s of subs) add(anchors, s.locations, s.excerpt || "", s.url, s.title);
    else add(anchors, d.locations || [], d.excerpt || "", d.url, d.meta?.title || d.url);
    if (items.length >= 24) break;
  }
  return items;
}

// ---------------------------------------------------------------- UI

const WORK_FILTERS = ["The Constitution of the United States", "Amendments to the Constitution of the United States", "The Federalist"];
const SHORT: Record<string, string> = {
  "The Constitution of the United States": "Constitution",
  "Amendments to the Constitution of the United States": "Amendments",
  "The Federalist": "Federalist",
};

const attached = new WeakSet<Element>();

export function attach(container: HTMLElement, opts: { initial?: string; syncUrl?: boolean } = {}) {
  const input = container.querySelector<HTMLInputElement>("[data-search-input]")!;
  const results = container.querySelector<HTMLElement>("[data-search-results]")!;
  const filterBar = container.querySelector<HTMLElement>("[data-search-filters]");
  if (opts.initial !== undefined && opts.initial !== "") input.value = opts.initial;
  input.focus();
  input.select();
  if (attached.has(container)) {
    run();
    return;
  }
  attached.add(container);

  let work = "";
  let active = -1;
  let token = 0;

  if (filterBar) {
    filterBar.hidden = false;
    const mk = (label: string, value: string) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.setAttribute("aria-pressed", String(value === work));
      b.addEventListener("click", () => {
        work = value;
        for (const x of filterBar.querySelectorAll("button")) x.setAttribute("aria-pressed", "false");
        b.setAttribute("aria-pressed", "true");
        run();
        input.focus();
      });
      return b;
    };
    filterBar.replaceChildren(mk("All", ""), ...WORK_FILTERS.map((w) => mk(SHORT[w], w)));
  }

  function render(groups: { label: string; items: Item[] }[], message?: string) {
    results.replaceChildren();
    active = -1;
    for (const g of groups) {
      if (!g.items.length) continue;
      const h = document.createElement("div");
      h.className = "sr-group";
      h.textContent = g.label;
      results.append(h);
      for (const it of g.items) {
        const a = document.createElement("a");
        a.className = "sr-item";
        a.href = it.url.startsWith("/") ? it.url : "/";
        a.setAttribute("role", "option");
        const t = document.createElement("div");
        t.className = "sr-title";
        t.append(document.createTextNode(it.title));
        if (it.ref) {
          const r = document.createElement("span");
          r.className = "ref";
          r.textContent = it.ref;
          t.append(r);
        }
        a.append(t);
        if (it.excerpt) {
          const p = document.createElement("p");
          p.className = "sr-excerpt";
          p.innerHTML = it.excerpt; // sanitized by safeExcerpt: text + <mark> only
          a.append(p);
        }
        a.addEventListener("click", () => (container as HTMLDialogElement).close?.());
        results.append(a);
      }
    }
    if (message && !results.children.length) {
      const p = document.createElement("p");
      p.className = "sr-empty";
      p.textContent = message;
      results.append(p);
    }
  }

  async function run() {
    const q = input.value.trim();
    const mine = ++token;
    if (opts.syncUrl) {
      const u = new URL(location.href);
      if (q) u.searchParams.set("q", q); else u.searchParams.delete("q");
      history.replaceState(null, "", u);
    }
    if (!q) {
      render([]);
      return;
    }
    const jumps = await jump(q);
    if (mine !== token) return;
    render([{ label: "Jump to", items: jumps }]);
    const text = await fullText(q, work ? { work } : {});
    if (mine !== token) return;
    if (text === null) {
      render([{ label: "Jump to", items: jumps }], "Full-text search is available on the published site.");
      return;
    }
    render([{ label: "Jump to", items: jumps }, { label: "Passages", items: text }], `No results for “${q}”.`);
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
      const items = results.querySelectorAll<HTMLAnchorElement>(".sr-item");
      const target = items[Math.max(active, 0)];
      if (target) {
        (container as HTMLDialogElement).close?.();
        location.href = target.href;
      }
    }
  });
  container.querySelector("form")?.addEventListener("submit", (e) => e.preventDefault());
  loadPagefind();
  run();
}
