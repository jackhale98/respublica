// Graph view: a passage at the center, its connections one and two hops out.
// Laid out by a force simulation (d3-force) and drawn in SVG with zoom, pan
// and drag (d3-zoom, d3-drag); see docs/decisions.md 28. This module and the
// d3 code it imports load only when a reader opens the graph. Data is
// /data/graph/{page}.json, built by tools/site_data.py.

import { forceCollide, forceLink, forceManyBody, forceRadial, forceSimulation, type Simulation, type SimulationNodeDatum } from "d3-force";
import { select } from "d3-selection";
import { drag } from "d3-drag";
import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import "d3-transition";

type Node = { label: string; short: string; url: string | null; work: string };
type Edge = { id: string; from: string; to: string; type: string; status: string; confidence: string };
type Graph = { nodes: Record<string, Node>; edges: Edge[] };
type Ring = "center" | "hop1" | "hop2";
type SimNode = SimulationNodeDatum & { id: string; ring: Ring; w: number; h: number };
type SimLink = { source: SimNode; target: SimNode; edge: Edge };

const SVG = "http://www.w3.org/2000/svg";
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const MAX_HOP1 = 28;
const MAX_HOP2 = 48;
const RING_R: Record<Ring, number> = { center: 0, hop1: 190, hop2: 360 };
const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

const WORK_ORDER = ["constitution", "amendments", "federalist"];
const WORK_NAMES: Record<string, string> = { constitution: "Constitution", amendments: "Amendments", federalist: "The Federalist" };
const workName = (w: string) => WORK_NAMES[w] || w.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const workClass = (w: string | undefined) => `w-${w && WORK_ORDER.includes(w) ? w : "other"}`;
const TYPE_NAMES: Record<string, string> = {
  quotes: "quotes", cites: "cites", responds_to: "responds to", rebuts: "rebuts",
  shared_theme: "shared theme", interprets: "interprets", overrules: "overrules", implements: "implements",
};
const PASSIVE: Record<string, string> = {
  quotes: "quoted by", cites: "cited by", responds_to: "answered by", rebuts: "rebutted by",
  shared_theme: "shares a theme with", interprets: "interpreted by", overrules: "overruled by", implements: "implemented by",
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

/** Where the line from (x, y) toward a node's center leaves the node's chip. */
function chipExit(n: SimNode, fromX: number, fromY: number, pad: number) {
  const cx = n.x!, cy = n.y!;
  const dx = fromX - cx, dy = fromY - cy;
  const hw = n.w / 2 + pad, hh = n.h / 2 + pad;
  if (!dx && !dy) return { x: cx, y: cy };
  const t = Math.min(dx ? hw / Math.abs(dx) : Infinity, dy ? hh / Math.abs(dy) : Infinity);
  return { x: cx + dx * t, y: cy + dy * t };
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
  const controls = dialog.querySelector<HTMLElement>("[data-graph-controls]");

  // The dialog must be open for text to be measured.
  if (!dialog.open) dialog.showModal();

  let sim: Simulation<SimNode, SimLink> | null = null;
  const positions = new Map<string, { x: number; y: number }>(); // kept across re-renders
  const viewport = svg("g", { class: "viewport" });
  const zoomer: ZoomBehavior<SVGSVGElement, unknown> = zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.25, 3])
    .on("zoom", (ev) => viewport.setAttribute("transform", ev.transform.toString()));
  select(canvas).call(zoomer).on("dblclick.zoom", null);

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
      ...works.map((w) => chip(workName(w), state.works.has(w), toggle(state.works, w), workClass(w))),
      chip("Reviewed only", state.reviewedOnly, () => { state.reviewedOnly = !state.reviewedOnly; render(); }, "reviewed"),
    );
  }

  /** Zoom so the nodes fill the canvas (the dotted backdrop is not counted). */
  function fit(animate: boolean) {
    const layer = viewport.querySelector<SVGGElement>(".nodes");
    const rect = canvas.getBoundingClientRect();
    if (!layer || !rect.width) return;
    const box = layer.getBBox();
    if (!box.width) return;
    const pad = 40;
    const k = Math.min(1.35, (rect.width - pad * 2) / box.width, (rect.height - pad * 2) / box.height);
    const t = zoomIdentity.translate(rect.width / 2, rect.height / 2).scale(k)
      .translate(-(box.x + box.width / 2), -(box.y + box.height / 2));
    const s = select(canvas);
    if (animate && !reduceMotion()) s.transition().duration(600).call(zoomer.transform, t);
    else s.call(zoomer.transform, t);
  }

  function render() {
    renderFilters();
    sim?.stop();
    const edges = visibleEdges();
    const adj = new Map<string, Edge[]>();
    for (const e of edges) {
      (adj.get(e.from) ?? adj.set(e.from, []).get(e.from)!).push(e);
      (adj.get(e.to) ?? adj.set(e.to, []).get(e.to)!).push(e);
    }
    const other = (e: Edge, r: string) => (e.from === r ? e.to : e.from);
    const hop1All = [...new Set((adj.get(state.center) || []).map((e) => other(e, state.center)))].sort(byWork(g));
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
    const ringOf = (r: string): Ring => (r === state.center ? "center" : hop1.includes(r) ? "hop1" : "hop2");
    const shown = [state.center, ...hop1, ...hop2].filter((r) => g.nodes[r]);
    const shownSet = new Set(shown);
    const drawn = edges.filter((e) => shownSet.has(e.from) && shownSet.has(e.to));

    // ---------------------------------------------------------- scene
    const defs = svg("defs");
    defs.innerHTML = `
      <pattern id="graph-dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" class="dot" /></pattern>
      <filter id="graph-shadow" x="-30%" y="-60%" width="160%" height="220%"><feDropShadow dx="0" dy="3" stdDeviation="4" class="shadow" /></filter>
      <radialGradient id="graph-glow"><stop offset="0" class="glow-in" /><stop offset="1" class="glow-out" /></radialGradient>
      ${["base", "quotes", "lit"].map((k) => `<marker id="graph-arrow-${k}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" class="arrow arrow-${k}" /></marker>`).join("")}`;
    const backdrop = svg("rect", { x: -4000, y: -4000, width: 8000, height: 8000, fill: "url(#graph-dots)", class: "backdrop" });
    const rings = svg("g", { class: "rings" });
    rings.append(svg("circle", { r: 90, fill: "url(#graph-glow)", class: "halo" }));
    rings.append(svg("circle", { r: RING_R.hop1, class: "ring" }));
    if (hop2.length) rings.append(svg("circle", { r: RING_R.hop2, class: "ring" }));
    const edgeLayer = svg("g", { class: "edges" });
    const labelLayer = svg("g", { class: "edge-labels" });
    const nodeLayer = svg("g", { class: "nodes" });
    viewport.replaceChildren(backdrop, rings, edgeLayer, labelLayer, nodeLayer);
    canvas.replaceChildren(defs, viewport);

    // Nodes: a label chip with a dot in its work's color.
    const nodes: SimNode[] = [];
    const nodeEls = new Map<string, SVGGElement>();
    for (const ref of shown) {
      const n = g.nodes[ref];
      const ring = ringOf(ref);
      const grp = svg("g", {
        class: `node ${workClass(n.work)} ${ring}`,
        tabindex: 0, role: "button", "data-ref": ref,
        "aria-label": `${n.label}${ring === "center" ? " (center)" : ""}`,
      });
      const rect = svg("rect", { class: "chip" });
      const dot = svg("circle", { class: "chip-dot", r: ring === "center" ? 5 : 4 });
      const text = svg("text", { class: "chip-text", "dominant-baseline": "central" }, n.short);
      grp.append(svg("title", {}, n.label), rect, dot, text);
      nodeLayer.append(grp);
      const tw = text.getComputedTextLength() || n.short.length * 7;
      const padX = ring === "center" ? 16 : ring === "hop1" ? 12 : 9;
      const h = ring === "center" ? 42 : ring === "hop1" ? 30 : 24;
      const dotSpace = ring === "center" ? 16 : 13;
      const w = tw + padX * 2 + dotSpace;
      for (const [k, v] of Object.entries({ x: -w / 2, y: -h / 2, width: w, height: h, rx: h / 2 })) rect.setAttribute(k, String(v));
      dot.setAttribute("cx", String(-w / 2 + padX + 3));
      text.setAttribute("x", String(-w / 2 + padX + dotSpace));
      if (ring !== "hop2") rect.setAttribute("filter", "url(#graph-shadow)");
      nodeEls.set(ref, grp);

      // Start where it was, or on its ring (children behind their parent).
      const prev = positions.get(ref);
      let x = 0, y = 0;
      if (ring !== "center" && prev) { x = prev.x; y = prev.y; } else if (ring !== "center") {
        const idx = ring === "hop1" ? hop1.indexOf(ref) : hop1.indexOf(parentOf.get(ref)!);
        const jitter = ring === "hop2" ? ((hop2.indexOf(ref) % 5) - 2) * 0.09 : 0;
        const a = -Math.PI / 2 + (idx / Math.max(hop1.length, 1)) * 2 * Math.PI + jitter;
        x = Math.cos(a) * RING_R[ring]; y = Math.sin(a) * RING_R[ring];
      }
      const sn: SimNode = { id: ref, ring, w, h, x, y };
      if (ring === "center") { sn.fx = 0; sn.fy = 0; }
      nodes.push(sn);

      const pick = () => { state.selected = ref; highlight(); renderInfo(drawn, hop1, hop2, hidden); };
      grp.addEventListener("click", (ev) => { ev.stopPropagation(); pick(); });
      grp.addEventListener("dblclick", (ev) => { ev.stopPropagation(); if (ref !== state.center) { state.center = ref; state.selected = ref; render(); } });
      grp.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); }
      });
      grp.addEventListener("mouseenter", () => highlight(ref));
      grp.addEventListener("mouseleave", () => highlight());
      grp.addEventListener("focus", () => highlight(ref));
      grp.addEventListener("blur", () => highlight());
    }
    const byId = new Map(nodes.map((n) => [n.id, n]));

    // Edges: gentle arcs, the arrow at the passage cited or quoted.
    const links: SimLink[] = drawn.map((e) => ({ source: byId.get(e.from)!, target: byId.get(e.to)!, edge: e }));
    const pathEls = new Map<string, SVGPathElement>();
    const labelEls = new Map<string, SVGTextElement>();
    for (const l of links) {
      const e = l.edge;
      const p = svg("path", { class: `edge t-${e.type} s-${e.status}` });
      p.append(svg("title", {}, `${g.nodes[e.from]?.label} ${TYPE_NAMES[e.type] || e.type} ${g.nodes[e.to]?.label}${e.status === "suggested" ? " (suggested)" : ""}`));
      edgeLayer.append(p);
      pathEls.set(e.id, p);
      const t = svg("text", { class: "edge-label", "text-anchor": "middle", "dominant-baseline": "central" }, TYPE_NAMES[e.type] || e.type);
      labelLayer.append(t);
      labelEls.set(e.id, t);
    }

    function draw() {
      for (const n of nodes) {
        nodeEls.get(n.id)!.setAttribute("transform", `translate(${n.x!.toFixed(1)},${n.y!.toFixed(1)})`);
        positions.set(n.id, { x: n.x!, y: n.y! });
      }
      for (const l of links) {
        const s = l.source, t = l.target;
        const dx = t.x! - s.x!, dy = t.y! - s.y!;
        const len = Math.hypot(dx, dy) || 1;
        // Bend each arc a little to one side; reciprocal links bend apart.
        const bend = Math.min(36, len * 0.12) * (l.edge.from < l.edge.to ? 1 : -1);
        const mx = (s.x! + t.x!) / 2 - (dy / len) * bend, my = (s.y! + t.y!) / 2 + (dx / len) * bend;
        const a = chipExit(s, mx, my, 2), b = chipExit(t, mx, my, 6);
        pathEls.get(l.edge.id)!.setAttribute("d", `M${a.x.toFixed(1)},${a.y.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`);
        const lab = labelEls.get(l.edge.id)!;
        lab.setAttribute("x", (0.25 * a.x + 0.5 * mx + 0.25 * b.x).toFixed(1));
        lab.setAttribute("y", (0.25 * a.y + 0.5 * my + 0.25 * b.y).toFixed(1));
      }
    }

    // Hovering or selecting a passage lights its links and fades the rest.
    function highlight(hover?: string) {
      const focus = hover || state.selected;
      const near = new Set([focus]);
      for (const l of links) if (l.source.id === focus || l.target.id === focus) { near.add(l.source.id); near.add(l.target.id); }
      const dimming = !!hover || focus !== state.center;
      for (const [ref, grp] of nodeEls) {
        grp.classList.toggle("selected", ref === state.selected);
        grp.classList.toggle("dim", dimming && !near.has(ref));
      }
      for (const l of links) {
        const lit = l.source.id === focus || l.target.id === focus;
        const p = pathEls.get(l.edge.id)!;
        p.classList.toggle("lit", lit);
        p.classList.toggle("dim", dimming && !lit);
        p.setAttribute("marker-end", `url(#graph-arrow-${lit ? "lit" : l.edge.type === "quotes" ? "quotes" : "base"})`);
        labelEls.get(l.edge.id)!.classList.toggle("show", lit && dimming);
      }
    }

    // ---------------------------------------------------------- layout
    const radius = (n: SimNode) => Math.min(n.w / 2, 70) * 0.75 + n.h / 2;
    sim = forceSimulation<SimNode, SimLink>(nodes)
      .force("link", forceLink<SimNode, SimLink>(links).id((n) => n.id).distance(165).strength(0.2))
      .force("charge", forceManyBody<SimNode>().strength((n) => (n.ring === "hop2" ? -160 : -380)))
      .force("collide", forceCollide<SimNode>(radius).strength(0.95).iterations(2))
      .force("ring", forceRadial<SimNode>((n) => RING_R[n.ring], 0, 0).strength((n) => (n.ring === "center" ? 0 : 0.6)))
      .alphaDecay(0.04)
      .on("tick", draw);

    const moved = positions.size > shown.length / 2;
    sim.stop();
    // Settle before the first frame (fully, without motion), then let it
    // breathe; fit once the info panel has taken its place.
    for (let i = 0; i < (reduceMotion() ? 300 : 120); i++) sim.tick();
    draw();
    requestAnimationFrame(() => fit(moved));
    if (!reduceMotion()) sim.alpha(0.12).restart();

    for (const n of nodes) {
      if (n.ring === "center") continue;
      const grp = nodeEls.get(n.id)!;
      select(grp).call(drag<SVGGElement, unknown>()
        .on("start", (ev) => { if (!ev.active) sim!.alphaTarget(0.2).restart(); n.fx = n.x; n.fy = n.y; grp.classList.add("dragging"); })
        .on("drag", (ev) => { n.fx = ev.x; n.fy = ev.y; })
        .on("end", (ev) => { if (!ev.active) sim!.alphaTarget(0); n.fx = null; n.fy = null; grp.classList.remove("dragging"); }));
    }

    highlight();
    canvas.setAttribute("aria-label", `${g.nodes[state.center]?.label}: ${hop1.length} direct connection${hop1.length === 1 ? "" : "s"}, ${hop2.length} at two steps`);
    renderInfo(drawn, hop1, hop2, hidden);
    title.textContent = g.nodes[state.center]?.label || state.center;
  }

  function renderInfo(drawn: Edge[], hop1: string[], hop2: string[], hidden: number) {
    const ref = state.selected;
    const n = g.nodes[ref];
    const parts: HTMLElement[] = [];
    parts.push(el("span", `gi-work ${workClass(n?.work)}`, workName(n?.work || "")));
    parts.push(el("h3", undefined, n?.label || ref));
    parts.push(el("p", "gi-ref", ref));
    const mine = drawn.filter((e) => e.from === ref || e.to === ref);
    const ul = el("ul", "gi-links");
    for (const e of mine.slice(0, 12)) {
      const li = el("li", `s-${e.status}`);
      const out = e.from === ref;
      const otherRef = out ? e.to : e.from;
      const b = el("button", "gi-node", g.nodes[otherRef]?.short || otherRef);
      b.type = "button";
      b.addEventListener("click", () => {
        state.selected = otherRef;
        canvas.querySelector<SVGGElement>(`g.node[data-ref="${CSS.escape(otherRef)}"]`)?.dispatchEvent(new MouseEvent("click"));
      });
      li.append(el("span", `gi-verb t-${e.type}`, out ? TYPE_NAMES[e.type] || e.type : PASSIVE[e.type] || e.type), b);
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
    parts.push(el("p", "gi-summary",
      `${hop1.length} direct connection${hop1.length === 1 ? "" : "s"}, ${hop2.length} at two steps${hidden ? ` (${hidden} more not shown)` : ""}.`));
    parts.push(el("p", "gi-tip", "Drag to pan; scroll or pinch to zoom. Drag a passage to move it; double-click one to put it at the center."));
    info.replaceChildren(...parts);
  }

  const lg = (cls: string, label: string) => { const s = el("span", `lg ${cls}`); s.append(el("i"), document.createTextNode(label)); return s; };
  legend.replaceChildren(
    ...works.map((w) => lg(workClass(w), workName(w))),
    ...(types.includes("quotes") ? [lg("e-quotes", "quotes")] : []),
    ...(types.some((t) => t !== "quotes") ? [lg("e-cites", types.filter((t) => t !== "quotes").map((t) => TYPE_NAMES[t] || t).join(", "))] : []),
    lg("dashed", "suggested, not yet reviewed"),
  );

  if (controls) {
    controls.onclick = (ev) => {
      const action = (ev.target as HTMLElement).closest<HTMLElement>("[data-zoom]")?.dataset.zoom;
      const s = select(canvas);
      if (action === "in") s.transition().duration(200).call(zoomer.scaleBy, 1.35);
      if (action === "out") s.transition().duration(200).call(zoomer.scaleBy, 1 / 1.35);
      if (action === "fit") fit(true);
    };
  }
  // A click on empty canvas goes back to the center passage.
  canvas.onclick = (ev) => {
    const t = ev.target as Element;
    if (t === canvas || t.classList.contains("backdrop")) {
      state.selected = state.center;
      canvas.querySelector<SVGGElement>("g.node.center")?.dispatchEvent(new MouseEvent("click"));
    }
  };
  // Refit when the canvas changes size (rotation, window resize).
  let lastSize = "";
  const resized = new ResizeObserver(() => {
    const r = canvas.getBoundingClientRect();
    const size = `${Math.round(r.width)}x${Math.round(r.height)}`;
    if (lastSize && size !== lastSize) fit(false);
    lastSize = size;
  });
  resized.observe(canvas);
  dialog.addEventListener("close", () => { sim?.stop(); resized.disconnect(); }, { once: true });

  render();
}
