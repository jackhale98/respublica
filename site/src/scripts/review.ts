// The /review/ page: approve or reject suggested links, then send the
// decisions as a GitHub issue ("approve lnk_…" / "reject lnk_… — note", one
// per line). The review workflow records them under the issue author's
// GitHub login (.github/workflows/review.yml). Decisions are kept in this
// browser (localStorage) until sent; nothing else is stored.

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const KEY = "rp-review";
const CONF_KEY = "rp-review-confidence"; // the confidence level shown, remembered in this browser
const PER_ISSUE = 150; // GitHub limits how long a new-issue link can be
const TYPE_LABELS: Record<string, string> = {
  quotes: "quotes", cites: "cites", responds_to: "responds to", rebuts: "rebuts",
  shared_theme: "shares a theme with", interprets: "interprets", overrules: "overrules", implements: "implements",
};

type End = { ref: string; label: string; url: string | null; text?: string; parts?: number };
type Link = { id: string; type: string; confidence: string; rationale?: string; from_quote?: string; to_quote?: string; from: End; to: End };
type Decision = { d: "approve" | "reject"; note?: string; sent?: boolean };

const root = document.querySelector<HTMLElement>("[data-review]")!;
const repo = root.dataset.repo || "";
const bar = document.querySelector<HTMLElement>("[data-review-bar]")!;
const tally = bar.querySelector<HTMLElement>("[data-tally]")!;
const send = bar.querySelector<HTMLAnchorElement>("[data-send]")!;
const clear = bar.querySelector<HTMLButtonElement>("[data-clear]")!;

// ---------------------------------------------------------------- state

const live = new Set<string>();
root.querySelectorAll<HTMLElement>("[data-ids]").forEach((el) => el.dataset.ids!.split(" ").filter(Boolean).forEach((id) => live.add(id)));

let decisions: Record<string, Decision> = {};
try {
  decisions = JSON.parse(localStorage.getItem(KEY) || "{}");
} catch {
  decisions = {};
}
// Links no longer suggested (recorded since) drop out.
for (const id of Object.keys(decisions)) if (!live.has(id)) delete decisions[id];

function save() {
  try {
    if (Object.keys(decisions).length) localStorage.setItem(KEY, JSON.stringify(decisions));
    else localStorage.removeItem(KEY);
  } catch {
    /* kept for this visit only */
  }
  applyFilter();
update();
}

function pending(): [string, Decision][] {
  return Object.entries(decisions).filter(([, v]) => !v.sent);
}

// ---------------------------------------------------------------- confidence filter

const filterBox = root.querySelector<HTMLElement>("[data-conf-filter]")!;
let level = "all";
try {
  level = localStorage.getItem(CONF_KEY) || "all";
} catch {
  /* default */
}
if (!filterBox.querySelector(`[data-conf="${level}"]`)) level = "all";

const shown = (conf: string) => level === "all" || conf === level;

function applyFilter() {
  filterBox.querySelectorAll<HTMLButtonElement>("[data-conf]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.conf === level)));
  root.querySelectorAll<HTMLElement>("[data-batch]").forEach((b) => {
    b.hidden = level !== "all" && !(b.dataset[level] || "").trim();
    b.querySelectorAll<HTMLElement>(".rv-link").forEach((c) => (c.hidden = !shown(c.dataset.conf || "")));
    const all = b.querySelector<HTMLButtonElement>(".rb-all");
    if (all) all.textContent = level === "all" ? "Approve the undecided" : `Approve the undecided ${level}-confidence links`;
  });
  root.querySelectorAll<HTMLElement>(".review-group").forEach((g) => {
    g.hidden = ![...g.querySelectorAll<HTMLElement>("[data-batch]")].some((b) => !b.hidden);
  });
}

filterBox.hidden = false;
filterBox.querySelectorAll<HTMLButtonElement>("[data-conf]").forEach((b) =>
  b.addEventListener("click", () => {
    level = b.dataset.conf || "all";
    try {
      if (level === "all") localStorage.removeItem(CONF_KEY);
      else localStorage.setItem(CONF_KEY, level);
    } catch {
      /* kept for this visit only */
    }
    applyFilter();
  }),
);

// ---------------------------------------------------------------- sending

function issueUrl(items: [string, Decision][]): string {
  const lines = items.map(([id, v]) => `${v.d} ${id}${v.note ? ` — ${v.note.replace(/\s+/g, " ").slice(0, 200)}` : ""}`);
  const approved = items.filter(([, v]) => v.d === "approve").length;
  const title = `Link review: ${approved} approved, ${items.length - approved} rejected`;
  const body = [
    "Decisions from the Res Publica review page. Submit this issue to record them;",
    "the review workflow applies them under your GitHub login and redeploys the site.",
    "",
    ...lines,
    "",
  ].join("\n");
  return `https://github.com/${repo}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

function update() {
  const todo = pending();
  const sent = Object.values(decisions).filter((v) => v.sent).length;
  const approved = todo.filter(([, v]) => v.d === "approve").length;
  bar.hidden = !todo.length && !sent;
  const parts = [`${approved} approved`, `${todo.length - approved} rejected`];
  let text = todo.length ? `${parts.join(" · ")} to send` : "Nothing left to send";
  if (sent) text += ` · ${sent} sent, waiting for the site to update`;
  tally.textContent = text;
  const batch = todo.slice(0, PER_ISSUE);
  send.hidden = !todo.length;
  send.textContent = todo.length > PER_ISSUE ? `Send ${PER_ISSUE} of ${todo.length} to GitHub` : "Send to GitHub";
  if (/^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/.test(repo) && batch.length) send.href = issueUrl(batch);
  root.querySelectorAll<HTMLElement>("[data-batch]").forEach((el) => {
    const ids = el.dataset.ids!.split(" ");
    const done = ids.filter((id) => decisions[id]).length;
    const count = el.querySelector<HTMLElement>("[data-batch-count]")!;
    count.textContent = `${done ? `${done} of ` : ""}${ids.length} ${ids.length === 1 ? "link" : "links"}${done ? " decided" : ""}`;
    el.classList.toggle("done", done === ids.length);
  });
}

send.addEventListener("click", () => {
  // The issue opens in a new tab; mark what it carries as sent.
  for (const [id, v] of pending().slice(0, PER_ISSUE)) v.sent = true;
  window.setTimeout(save, 0);
});

clear.addEventListener("click", () => {
  if (!window.confirm("Clear every decision kept on this page?")) return;
  decisions = {};
  save();
  root.querySelectorAll<HTMLElement>(".rv-link").forEach(paint);
});

// ---------------------------------------------------------------- cards

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const local = (url: string | null) => (url && url.startsWith("/") && !url.startsWith("//") ? BASE + url : null);

// The passage, with the quoted words marked.
function passage(end: End, quote: string | undefined, side: string): HTMLElement {
  const box = el("div", "rv-end");
  const head = el("div", "rv-end-head");
  head.append(el("span", "rv-side", side));
  const url = local(end.url);
  const name = url ? el("a", "rv-ref") : el("span", "rv-ref");
  name.textContent = end.label;
  if (url) Object.assign(name as HTMLAnchorElement, { href: url, target: "_blank", rel: "noopener" });
  head.append(name, el("code", "rv-code", end.ref));
  box.append(head);
  if (end.text) {
    const p = el("p", "rv-text");
    const at = quote ? end.text.indexOf(quote) : -1;
    if (at >= 0) {
      p.append(end.text.slice(0, at), el("mark", undefined, quote), end.text.slice(at + quote!.length));
    } else {
      p.textContent = end.text;
    }
    box.append(p);
    if (end.text.length > 420) {
      p.classList.add("clamped");
      const more = el("button", "rv-more", "Show all");
      more.type = "button";
      more.addEventListener("click", () => {
        const open = p.classList.toggle("clamped");
        more.textContent = open ? "Show all" : "Show less";
      });
      box.append(more);
    }
  } else {
    box.append(el("p", "rv-whole", `The whole ${end.parts && end.parts > 1 ? `piece (${end.parts} passages)` : "piece"}: open it to check.`));
    if (quote) box.append(el("blockquote", "rv-quote", quote));
  }
  return box;
}

function paint(card: HTMLElement) {
  const v = decisions[card.dataset.id!];
  card.dataset.state = v ? (v.sent ? "sent" : v.d) : "";
  card.querySelectorAll<HTMLButtonElement>("[data-choice]").forEach((b) => b.setAttribute("aria-pressed", String(v?.d === b.dataset.choice)));
  const note = card.querySelector<HTMLInputElement>("[data-note]")!;
  note.hidden = !v;
  if (v && document.activeElement !== note) note.value = v.note || "";
}

function card(link: Link): HTMLElement {
  const c = el("article", "rv-link");
  c.dataset.id = link.id;
  c.dataset.conf = link.confidence;
  const head = el("header", "rv-head");
  const conf = el("span", `rv-conf ${link.confidence}`, `${link.confidence} confidence`);
  head.append(el("span", "rv-type", TYPE_LABELS[link.type] || link.type), conf, el("code", "rv-id", link.id));
  c.append(head);
  const ends = el("div", "rv-ends");
  ends.append(passage(link.from, link.from_quote, "From"), passage(link.to, link.to_quote, "To"));
  c.append(ends);
  if (link.rationale) {
    const why = el("p", "rv-why");
    why.append(el("strong", undefined, "Why: "), link.rationale);
    c.append(why);
  }
  const actions = el("div", "rv-actions");
  for (const [choice, label] of [["approve", "Approve"], ["reject", "Reject"]] as const) {
    const b = el("button", `rv-choice ${choice}`, label);
    b.type = "button";
    b.dataset.choice = choice;
    b.addEventListener("click", () => {
      const cur = decisions[link.id];
      if (cur?.d === choice && !cur.sent) delete decisions[link.id];
      else decisions[link.id] = { d: choice, note: cur?.note };
      save();
      paint(c);
      if (decisions[link.id]?.d === "reject") c.querySelector<HTMLInputElement>("[data-note]")!.focus();
    });
    actions.append(b);
  }
  const note = el("input", "rv-note");
  note.type = "text";
  note.maxLength = 200;
  note.placeholder = "Note (optional): why, or what to change";
  note.setAttribute("aria-label", `Note on ${link.id}`);
  note.dataset.note = "";
  note.addEventListener("input", () => {
    const cur = decisions[link.id];
    if (cur) {
      cur.note = note.value.trim() || undefined;
      cur.sent = false;
      save();
    }
  });
  actions.append(note);
  c.append(actions);
  paint(c);
  return c;
}

// ---------------------------------------------------------------- batches

async function load(details: HTMLDetailsElement) {
  const body = details.querySelector<HTMLElement>("[data-batch-body]")!;
  if (details.dataset.loaded) return;
  details.dataset.loaded = "1";
  try {
    const res = await fetch(`${BASE}/data/review/${encodeURIComponent(details.dataset.batch!)}.json`);
    if (!res.ok) throw new Error(String(res.status));
    const data: { links: Link[] } = await res.json();
    body.replaceChildren();
    const tools = el("div", "rb-tools");
    const all = el("button", "btn btn-ghost rb-all", "Approve the undecided");
    all.type = "button";
    all.addEventListener("click", () => {
      // Only the links shown: with a confidence level chosen, the others are left undecided.
      for (const l of data.links) if (!decisions[l.id] && shown(l.confidence)) decisions[l.id] = { d: "approve" };
      save();
      body.querySelectorAll<HTMLElement>(".rv-link").forEach(paint);
    });
    tools.append(all);
    body.append(tools, ...data.links.map(card));
    applyFilter();
  } catch {
    delete details.dataset.loaded;
    body.replaceChildren(el("p", "review-empty", "Could not load this batch. Close it and open it again to retry."));
  }
}

root.querySelectorAll<HTMLDetailsElement>("details[data-batch]").forEach((d) => {
  d.addEventListener("toggle", () => {
    if (d.open) load(d);
  });
});

applyFilter();
update();
