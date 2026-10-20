// The /errata/ page: read uncertain words off the page images, then send the
// corrections as a GitHub issue (`correct REF INDEX "was" "now"`, one per
// line, the words as JSON strings). The review workflow records them under
// the issue author's GitHub login and the importers apply them
// (tools/errata.py; docs/decisions.md 48). Corrections are kept in this
// browser (localStorage) until sent; nothing else is stored.

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const KEY = "rp-errata";
const PER_ISSUE = 100; // GitHub limits how long a new-issue link can be
const PAGE = 20; // passages shown at a time
const SCANS: Record<string, string> = {
  primary: "main scan", brittle: "second scan", google: "Google scan", pitt: "Pittsburgh scan",
  microfilm: "microfilm scan", tesseract: "second OCR", lincoln: "Lincoln Foundation scan",
  michigan: "Michigan scan", cornell: "Cornell scan", harvard: "Harvard scan", uc: "UC scan",
  nypl: "NYPL scan", "nypl-ocr": "second OCR of the NYPL scan",
  tcp: "TCP transcription", jcb: "John Carter Brown Library scan", illinois: "Illinois scan",
  scan: "scan of the same printing", upload: "uploaded scan", acpl: "Allen County scan", ucgoogle: "UC Google scan",
};
// Page images only from the hosts the page's Content Security Policy allows.
const IMAGE_HOSTS = /^https:\/\/(archive\.org|[a-z0-9-]+\.us\.archive\.org|digital\.library\.unt\.edu|tile\.loc\.gov)\//;

// `suggestion`: the Anti-Federalist Library's reading, where no scan reads the
// word so: to check against the page image, never to take on trust.
type Word = {
  index: number; was: string; before: string; after: string; readings: Record<string, string>; suggestion?: string;
  // The text has the Library's reading, accepted by the owner without a check against the page (decision 56).
  accepted?: boolean;
};
type Passage = { ref: string; label: string; url: string | null; pages: { image: string; url: string }[]; words: Word[] };
type Fix = { ref: string; index: number; was: string; now: string; sent?: boolean };

const root = document.querySelector<HTMLElement>("[data-errata]")!;
const repo = root.dataset.repo || "";
const bar = document.querySelector<HTMLElement>("[data-review-bar]")!;
const tally = bar.querySelector<HTMLElement>("[data-tally]")!;
const send = bar.querySelector<HTMLAnchorElement>("[data-send]")!;
const clear = bar.querySelector<HTMLButtonElement>("[data-clear]")!;

const key = (ref: string, index: number) => `${ref}#${index}`;

// ---------------------------------------------------------------- state

let fixes: Record<string, Fix> = {};
try {
  fixes = JSON.parse(localStorage.getItem(KEY) || "{}");
} catch {
  fixes = {};
}

function save() {
  try {
    if (Object.keys(fixes).length) localStorage.setItem(KEY, JSON.stringify(fixes));
    else localStorage.removeItem(KEY);
  } catch {
    /* kept for this visit only */
  }
  update();
}

const pending = () => Object.values(fixes).filter((f) => !f.sent);

// ---------------------------------------------------------------- sending

function issueUrl(items: Fix[]): string {
  const lines = items.map((f) => `correct ${f.ref} ${f.index} ${JSON.stringify(f.was)} ${JSON.stringify(f.now)}`);
  const title = `Errata review: ${items.length} ${items.length === 1 ? "word" : "words"}`;
  const body = [
    "Corrections from the Res Publica errata page, read from the page images. Submit this issue to record them;",
    "the review workflow applies them under your GitHub login and redeploys the site.",
    "",
    ...lines,
    "",
  ].join("\n");
  return `https://github.com/${repo}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

function update() {
  const todo = pending();
  const sent = Object.values(fixes).length - todo.length;
  bar.hidden = !todo.length && !sent;
  let text = todo.length ? `${todo.length} ${todo.length === 1 ? "word" : "words"} to send` : "Nothing left to send";
  if (sent) text += ` · ${sent} sent, waiting for the site to update`;
  tally.textContent = text;
  send.hidden = !todo.length;
  send.textContent = todo.length > PER_ISSUE ? `Send ${PER_ISSUE} of ${todo.length} to GitHub` : "Send to GitHub";
  if (/^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/.test(repo) && todo.length) send.href = issueUrl(todo.slice(0, PER_ISSUE));
}

send.addEventListener("click", () => {
  // The issue opens in a new tab; mark what it carries as sent.
  for (const f of pending().slice(0, PER_ISSUE)) f.sent = true;
  window.setTimeout(() => {
    save();
    root.querySelectorAll<HTMLElement>(".er-passage").forEach(paintPassage);
  }, 0);
});

clear.addEventListener("click", () => {
  if (!window.confirm("Clear every correction kept on this page?")) return;
  fixes = {};
  save();
  root.querySelectorAll<HTMLElement>(".er-word").forEach(paintWord);
  root.querySelectorAll<HTMLElement>(".er-passage").forEach(paintPassage);
});

// ---------------------------------------------------------------- cards

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const local = (url: string | null) => (url && url.startsWith("/") && !url.startsWith("//") ? BASE + url : null);
const external = (url: string) => (/^https:\/\//.test(url) ? url : null);

function paintWord(row: HTMLElement) {
  const f = fixes[row.dataset.key!];
  row.dataset.state = f ? "chosen" : "";
  const typed = row.querySelector<HTMLInputElement>("[data-typed]")!;
  let matched = false;
  row.querySelectorAll<HTMLButtonElement>("[data-reading]").forEach((b) => {
    const on = !!f && f.now === b.dataset.reading && !matched;
    if (on) matched = true;
    b.setAttribute("aria-pressed", String(on));
  });
  if (document.activeElement !== typed) typed.value = f && !matched ? f.now : "";
  const mark = row.querySelector("mark")!;
  mark.textContent = f ? f.now : row.dataset.was!;
  mark.title = f ? `The scans read “${row.dataset.was}”` : "";
}

function paintPassage(card: HTMLElement) {
  const keys = [...card.querySelectorAll<HTMLElement>(".er-word")].map((r) => r.dataset.key!);
  const chosen = keys.filter((k) => fixes[k]);
  card.dataset.state = !chosen.length ? "" : chosen.every((k) => fixes[k].sent) ? "sent" : chosen.length === keys.length ? "done" : "";
}

function wordRow(p: Passage, w: Word, card: HTMLElement): HTMLElement {
  const row = el("li", "er-word");
  row.dataset.key = key(p.ref, w.index);
  row.dataset.was = w.was;
  const ctx = el("p", "er-context");
  ctx.append(w.before, el("mark", undefined, w.was), w.after);
  row.append(ctx);

  const choose = (now: string | null) => {
    const k = key(p.ref, w.index);
    if (now === null || !now.trim()) delete fixes[k];
    else fixes[k] = { ref: p.ref, index: w.index, was: w.was, now };
    save();
    paintWord(row);
    paintPassage(card);
  };

  const readings = el("div", "er-readings");
  readings.setAttribute("role", "group");
  readings.setAttribute("aria-label", `Readings of “${w.was}”`);
  // The same word read by several scans is one choice.
  const seen = new Map<string, string[]>();
  for (const [scan, text] of Object.entries(w.readings)) seen.set(text, [...(seen.get(text) || []), SCANS[scan] || scan]);
  for (const [text, scans] of seen) {
    const b = el("button", "rv-choice");
    b.type = "button";
    b.dataset.reading = text;
    b.append(text, el("small", undefined, scans.join(", ")));
    b.addEventListener("click", () => choose(fixes[row.dataset.key!]?.now === text ? null : text));
    readings.append(b);
  }
  if (w.accepted && !seen.has(w.was)) {
    const b = el("button", "rv-choice er-suggestion");
    b.type = "button";
    b.dataset.reading = w.was;
    b.title = "The text has this reading now. Choose it only if the page image shows it.";
    b.append(w.was, el("small", undefined, "Anti-Federalist Library, in the text now: check the page"));
    b.addEventListener("click", () => choose(fixes[row.dataset.key!]?.now === w.was ? null : w.was));
    readings.append(b);
  }
  const suggestion = w.suggestion;
  if (suggestion && !seen.has(suggestion)) {
    const b = el("button", "rv-choice er-suggestion");
    b.type = "button";
    b.dataset.reading = suggestion;
    b.title = "No scan reads this. Choose it only if the page image shows it.";
    b.append(suggestion, el("small", undefined, "Anti-Federalist Library: check the page"));
    b.addEventListener("click", () => choose(fixes[row.dataset.key!]?.now === suggestion ? null : suggestion));
    readings.append(b);
  }
  const typed = el("input", "rv-note");
  typed.type = "text";
  typed.maxLength = 200;
  typed.placeholder = "Or type what is printed";
  typed.setAttribute("aria-label", `What the page shows for “${w.was}”`);
  typed.dataset.typed = "";
  typed.addEventListener("change", () => choose(typed.value.replace(/\s+/g, " ").trim() || null));
  readings.append(typed);
  row.append(readings);
  paintWord(row);
  return row;
}

function passageCard(p: Passage): HTMLElement {
  const c = el("article", "rv-link er-passage");
  const head = el("header", "rv-head");
  const url = local(p.url);
  const name = url ? el("a", "rv-ref") : el("span", "rv-ref");
  name.textContent = p.label;
  if (url) Object.assign(name as HTMLAnchorElement, { href: url, target: "_blank", rel: "noopener" });
  head.append(name, el("code", "rv-id", p.ref));
  c.append(head);

  const pages = el("div", "er-pages");
  const box = el("div", "er-image-box");
  box.hidden = true;
  p.pages.forEach((pg, i) => {
    const label = p.pages.length > 1 ? `Page image ${i + 1}` : "Page image";
    const b = el("button", "rv-choice", label);
    b.type = "button";
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", () => {
      const open = b.getAttribute("aria-pressed") === "true";
      pages.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", "false"));
      box.replaceChildren();
      box.hidden = open;
      if (open || !IMAGE_HOSTS.test(pg.image)) return;
      b.setAttribute("aria-pressed", "true");
      const img = el("img", "er-image");
      img.alt = `${label} of ${p.label}`;
      img.src = pg.image;
      img.title = "Select to zoom in or out";
      img.addEventListener("click", () => img.classList.toggle("zoomed"));
      img.addEventListener("error", () => box.replaceChildren(el("p", "review-empty", "The image did not load; open the scan instead.")));
      box.append(img);
    });
    pages.append(b);
  });
  const scan = external(p.pages[0]?.url || "");
  if (scan) {
    const a = el("a", undefined, "Open the scan ↗");
    Object.assign(a, { href: scan, target: "_blank", rel: "noopener" });
    pages.append(a);
  }
  c.append(pages, box);

  const words = el("ol", "er-words");
  for (const w of p.words) words.append(wordRow(p, w, c));
  c.append(words);
  paintPassage(c);
  return c;
}

// ---------------------------------------------------------------- works

async function load(details: HTMLDetailsElement) {
  const body = details.querySelector<HTMLElement>("[data-work-body]")!;
  if (details.dataset.loaded) return;
  details.dataset.loaded = "1";
  try {
    const res = await fetch(`${BASE}/data/errata/${encodeURIComponent(details.dataset.work!)}.json`);
    if (!res.ok) throw new Error(String(res.status));
    const data: { passages: Passage[] } = await res.json();
    body.replaceChildren();
    let shown = 0;
    const more = el("button", "btn btn-ghost er-more");
    more.type = "button";
    const next = () => {
      const batch = data.passages.slice(shown, shown + PAGE);
      shown += batch.length;
      more.before(...batch.map(passageCard));
      const left = data.passages.length - shown;
      more.hidden = left <= 0;
      more.textContent = `Show ${Math.min(PAGE, left)} more of ${left} passages`;
    };
    more.addEventListener("click", next);
    body.append(more);
    next();
  } catch {
    delete details.dataset.loaded;
    body.replaceChildren(el("p", "review-empty", "Could not load this work. Close it and open it again to retry."));
  }
}

root.querySelectorAll<HTMLDetailsElement>("details[data-work]").forEach((d) => {
  d.addEventListener("toggle", () => {
    if (d.open) load(d);
  });
});

update();
