// Graph view: a passage at the center, its connections one and two hops out.
// Drawn as plain SVG (no third-party library; docs/decisions.md 19). Data is
// /data/graph/{page}.json, built by tools/site_data.py.

type Node = { label: string; short: string; url: string | null; work: string };
type Edge = { id: string; from: string; to: string; type: string; status: string; confidence: string };
type Graph = { nodes: Record<string, Node>; edges: Edge[] };

const SVG = "http://www.w3.org/2000/svg";
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const SIZE = 800;
const C = SIZE / 2;
const MAX_HOP1 = 28;
const MAX_HOP2 = 48;

const WORK_ORDER = ["constitution", "amendments", "federalist"];
const WORK_NAMES: Record<string, string> = { constitution: "Constitution", amendments: "Amendments", federalist: "The Federalist" };
const TYPE_NAMES: Record<string, string> = {
  quotes: "quotes", cites: "cites", responds_to: "responds to", rebuts: "rebuts",
  shared_theme: "shared theme", interprets: "interprets", overrules: "overrules", implements: "implements",
};

const cache = new Map<string, Promise<Graph>>();
function load(url: string) {
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => (r.ok ? r.json() : { nodes: {}, edges: [] })).catch(() => ({ nodes: {}, edges: [] })));
  return cache.get(url)!;
}

function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}, text?: string) {
  const e = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (text !== undefined) e.textContent = text;
  return e;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Natural order for refs ("Federalist.9.2" before "Federalist.10.1"). */
function refOrder(a: string, b: string) {
  return a.localeCompare(b, "en", { numeric: true });
}
function byWork(g: Graph) {
  return (a: string, b: string) => {
    const wa = WORK_ORDER.indexOf(g.nodes[a]?.work), wb = WORK_ORDER.indexOf(g.nodes[b]?.work);
    return (wa === -1 ? 99 : wa) - (wb === -1 ? 99 : wb) || refOrder(a, b);
  };
}

type State = { center: string; selected: string; types: Set<string>; works: Set<string>; reviewedOnly: boolean };

export async function openGraph(dialog: HTMLDialogElement, dataUrl: string, center: string, onOpenPassage: (ref: string) => void) {
  const g = await load(dataUrl);
  const types = [...new Set(g.edges.map((e) => e.type))].sort();
  const works = [...new Set(Object.values(g.nodes).map((n) => n.work))].sort((a, b) => WORK_ORDER.indexOf(a) - WORK_ORDER.indexOf(b));
  const state: State = { center, selected: center, types: new Set(types), works: new Set(works), reviewedOnly: false };

  const title = dialog.querySelector<HTMLElement>("[data-graph-title]")!;
  const canvas = dialog.querySelector<SVGSVGElement>("[data-graph-svg]")!;
  const info = dialog.querySelector<HTMLElement>("[data-graph-info]")!;
  const filters = dialog.querySelector<HTMLElement>("[data-graph-filters]")!;
  const legend = dialog.querySelector<HTMLElement>("[data-graph-legend]")!;

  function visibleEdges() {
    return g.edges.filter((e) =>
      state.types.has(e.type) &&
      (!state.reviewedOnly || e.status === "reviewed") &&
      state.works.has(g.nodes[e.from]?.work) && state.works.has(g.nodes[e.to]?.work));
  }

  function chip(label: string, pressed: boolean, onClick: () => void, cls = "") {
    const b = el("button", cls, label);
    b.type = "button";
    b.setAttribute("aria-pressed", String(pressed));
    b.addEventListener("click", onClick);
    return b;
  }

  function renderFilters() {
    const toggle = (set: Set<string>, v: string) => () => {
      if (set.has(v) && set.size > 1) set.delete(v); else set.add(v);
      render();
    };
    filters.replaceChildren(
      el("span", "gf-label", "Links"),
      ...types.map((t) => chip(TYPE_NAMES[t] || t, state.types.has(t), toggle(state.types, t), `t-${t}`)),
      el("span", "gf-label", "Works"),
      ...works.map((w) => chip(WORK_NAMES[w] || w, state.works.has(w), toggle(state.works, w), `w-${w}`)),
      chip("Reviewed only", state.reviewedOnly, () => { state.reviewedOnly = !state.reviewedOnly; render(); }, "reviewed"),
    );
  }

  function render() {
    renderFilters();
    const edges = visibleEdges();
    const adj = new Map<string, Edge[]>();
    for (const e of edges) {
      (adj.get(e.from) ?? adj.set(e.from, []).get(e.from)!).push(e);
      (adj.get(e.to) ?? adj.set(e.to, []).get(e.to)!).push(e);
    }
    const other = (e: Edge, r: string) => (e.from === r ? e.to : e.from);
    const order = byWork(g);
    const hop1All = [...new Set((adj.get(state.center) || []).map((e) => other(e, state.center)))].sort(order);
    const hop1 = hop1All.slice(0, MAX_HOP1);
    const parentOf = new Map<string, string>();
    for (const p of hop1) {
      for (const e of (adj.get(p) || []).sort((a, b) => refOrder(other(a, p), other(b, p)))) {
        const n = other(e, p);
        if (n !== state.center && !hop1.includes(n) && !parentOf.has(n)) parentOf.set(n, p);
      }
    }
    const hop2All = [...parentOf.keys()];
    const hop2 = hop2All.slice(0, MAX_HOP2);
    const hidden = hop1All.length - hop1.length + hop2All.length - hop2.length;

    // Radial layout: hop 1 evenly around the center; hop 2 fanned out
    // behind its parent within the parent's slice of the circle.
    const pos = new Map<string, { x: number; y: number; a: number }>();
    pos.set(state.center, { x: C, y: C, a: 0 });
    const r1 = hop2.length ? 170 : 230;
    const r2 = 320;
    const slot = (2 * Math.PI) / Math.max(hop1.length, 1);
    hop1.forEach((n, i) => {
      const a = -Math.PI / 2 + i * slot;
      pos.set(n, { x: C + r1 * Math.cos(a), y: C + r1 * Math.sin(a), a });
    });
    for (const p of hop1) {
      const kids = hop2.filter((n) => parentOf.get(n) === p);
      const pa = pos.get(p)!.a;
      // Spread a parent's children over most of its slice, but not wider than ~28° apart.
      const step = Math.min((slot * 0.85) / Math.max(kids.length, 1), 0.5);
      kids.forEach((n, j) => {
        const a = pa + (j - (kids.length - 1) / 2) * step;
        pos.set(n, { x: C + r2 * Math.cos(a), y: C + r2 * Math.sin(a), a });
      });
    }

    const shown = new Set(pos.keys());
    const drawn = edges.filter((e) => shown.has(e.from) && shown.has(e.to));
    const radius = (r: string) => (r === state.center ? 16 : hop1.includes(r) ? 9 : 6.5);

    const edgeLayer = svg("g", { class: "edges" });
    for (const e of drawn) {
      const a = pos.get(e.from)!, b = pos.get(e.to)!;
      const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
      const ra = radius(e.from) + 2, rb = radius(e.to) + 5;
      const line = svg("line", {
        x1: a.x + (dx / len) * ra, y1: a.y + (dy / len) * ra,
        x2: b.x - (dx / len) * rb, y2: b.y - (dy / len) * rb,
        class: `edge t-${e.type} s-${e.status}`,
        "marker-end": "url(#graph-arrow)",
        "data-from": e.from, "data-to": e.to,
      });
      line.append(svg("title", {}, `${g.nodes[e.from]?.short} ${TYPE_NAMES[e.type] || e.type} ${g.nodes[e.to]?.short} (${e.status})`));
      edgeLayer.append(line);
    }

    const nodeLayer = svg("g", { class: "nodes" });
    const showHop2Labels = hop2.length <= 24;
    for (const [ref, p] of pos) {
      const n = g.nodes[ref];
      if (!n) continue;
      const isCenter = ref === state.center;
      const ring = isCenter ? "center" : hop1.includes(ref) ? "hop1" : "hop2";
      const grp = svg("g", {
        class: `node w-${n.work} ${ring}${ref === state.selected ? " selected" : ""}`,
        tabindex: 0, role: "button", "aria-label": `${n.label}${isCenter ? " (center)" : ""}`, "data-ref": ref,
      });
      grp.append(svg("circle", { cx: p.x, cy: p.y, r: radius(ref) }));
      grp.append(svg("title", {}, n.label));
      if (isCenter) {
        grp.append(svg("text", { x: C, y: C + 36, "text-anchor": "middle", class: "label center-label" }, n.short));
      } else if (ring === "hop1" || showHop2Labels || ref === state.selected) {
        const cos = Math.cos(p.a), sin = Math.sin(p.a);
        const off = radius(ref) + 6;
        grp.append(svg("text", {
          x: p.x + cos * off, y: p.y + sin * off + 4,
          "text-anchor": cos > 0.25 ? "start" : cos < -0.25 ? "end" : "middle",
          class: `label ${ring}-label`,
        }, n.short));
      }
      const pick = () => { state.selected = ref; render(); };
      grp.addEventListener("click", pick);
      grp.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); }
      });
      nodeLayer.append(grp);
    }

    const defs = svg("defs");
    const marker = svg("marker", { id: "graph-arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" });
    marker.append(svg("path", { d: "M0,0 L10,5 L0,10 z", class: "arrow" }));
    defs.append(marker);
    canvas.replaceChildren(defs, svg("circle", { cx: C, cy: C, r: r1, class: "ring" }),
      ...(hop2.length ? [svg("circle", { cx: C, cy: C, r: r2, class: "ring" })] : []), edgeLayer, nodeLayer);
    canvas.setAttribute("aria-label", `${g.nodes[state.center]?.label}: ${hop1.length} direct connection${hop1.length === 1 ? "" : "s"}, ${hop2.length} at two steps`);

    // Highlight the selected node's edges.
    canvas.querySelectorAll<SVGLineElement>("line.edge").forEach((l) => {
      l.classList.toggle("lit", l.dataset.from === state.selected || l.dataset.to === state.selected);
    });

    renderInfo(drawn, hop1, hop2, hidden);
    title.textContent = g.nodes[state.center]?.label || state.center;
  }

  function renderInfo(drawn: Edge[], hop1: string[], hop2: string[], hidden: number) {
    const ref = state.selected;
    const n = g.nodes[ref];
    const parts: HTMLElement[] = [];
    parts.push(el("span", `gi-work w-${n?.work}`, WORK_NAMES[n?.work] || n?.work || ""));
    parts.push(el("h3", undefined, n?.label || ref));
    parts.push(el("p", "gi-ref", ref));
    const mine = drawn.filter((e) => e.from === ref || e.to === ref);
    const ul = el("ul", "gi-links");
    for (const e of mine.slice(0, 12)) {
      const li = el("li", `s-${e.status}`);
      const out = e.from === ref;
      const otherRef = out ? e.to : e.from;
      li.textContent = `${out ? TYPE_NAMES[e.type] : `${TYPE_NAMES[e.type]} by`.replace("quotes by", "quoted by").replace("cites by", "cited by")} ${g.nodes[otherRef]?.short || otherRef}`;
      if (e.status === "suggested") li.append(el("span", "badge suggested", "Suggested"));
      ul.append(li);
    }
    if (mine.length > 12) ul.append(el("li", "muted", `and ${mine.length - 12} more`));
    parts.push(ul);
    const actions = el("div", "gi-actions");
    if (n?.url && n.url.startsWith("/") && !n.url.startsWith("//")) {
      const a = el("a", "btn btn-primary", "Open passage");
      a.href = BASE + n.url;
      a.addEventListener("click", (ev) => {
        // Same page: select it in the reader instead of reloading.
        if (a.pathname === location.pathname) {
          ev.preventDefault();
          dialog.close();
          onOpenPassage(ref);
        }
      });
      actions.append(a);
    }
    if (ref !== state.center) {
      const b = el("button", "btn btn-ghost", "Center here");
      b.type = "button";
      b.addEventListener("click", () => { state.center = ref; render(); });
      actions.append(b);
    }
    parts.push(actions);
    const summary = el("p", "gi-summary",
      `${hop1.length} direct connection${hop1.length === 1 ? "" : "s"}, ${hop2.length} at two steps${hidden ? ` (${hidden} more not shown)` : ""}.`);
    parts.push(summary);
    info.replaceChildren(...parts);
  }

  legend.replaceChildren(
    ...works.map((w) => { const s = el("span", `lg w-${w}`); s.append(el("i"), document.createTextNode(WORK_NAMES[w] || w)); return s; }),
    (() => { const s = el("span", "lg dashed"); s.append(el("i"), document.createTextNode("suggested, not yet reviewed")); return s; })(),
  );

  render();
  if (!dialog.open) dialog.showModal();
}
