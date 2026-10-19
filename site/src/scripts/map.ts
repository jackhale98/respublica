// The overview map (/map/): the founding documents as a spine, passage by
// passage; above each, a stacked bar of the links that reach it from the
// debates, by side; below it, a dot for each case whose Constitution
// Annotated essays cite it, oldest nearest the spine. Then an arc diagram of
// the debate's works answering one another. Drawn with d3 (selection, zoom,
// transition); data is /data/map.json from tools/site_data.py (build_map).
// Wide screens read along a horizontal spine that pans and zooms; phones
// read down a vertical one. Decision 51.

import { select, type Selection } from "d3-selection";
import { zoom, zoomIdentity, type D3ZoomEvent } from "d3-zoom";
import "d3-transition";

type Item = { group: string; label: string; ref: string; short: string; url: string | null; totals: Record<string, number> };
type Mark = [number, string, string, number, string]; // spine index, side, kind, reviewed, work or case
type Case = { label: string; overruled: boolean; url: string | null; year: string };
type Arc = { from: string; to: string; kind: string; n: number; reviewed: number };
type Work = { short: string; side: string; title: string; parts: number; linked_parts: number; url: string | null };
type MapData = { spine: Item[]; debate: Mark[]; interprets: Mark[]; cases: Record<string, Case>; arcs: Arc[]; works: Record<string, Work> };

const SIDES = ["federalist", "anti", "congress", "other"];
const SIDE_NAMES: Record<string, string> = {
  federalist: "Federalist side", anti: "Anti-Federalists", congress: "Congress", other: "Other", cases: "Cases",
};
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const local = (url: string | null) => (url && url.startsWith("/") && !url.startsWith("//") ? BASE + url : null);
// Group labels on the spine: "I" for Article I, "14" for Amendment 14.
const tag = (g: string) => g === "Declaration" ? "Decl." : g === "Preamble" ? "Pre." : g.replace(/^(Article|Amendment) /, "");

const root = document.querySelector<HTMLElement>("[data-map]")!;
const chartBox = root.querySelector<HTMLElement>("[data-map-chart]")!;
const arcBox = root.querySelector<HTMLElement>("[data-map-arcs]")!;
const tip = root.querySelector<HTMLElement>("[data-map-tip]")!;
const filterBox = root.querySelector<HTMLElement>("[data-map-filters]")!;

const shown = new Set([...SIDES, "cases"]);
let reviewedOnly = false;

function text(tag: string, cls: string, content: string) {
  const e = document.createElement(tag);
  e.className = cls;
  e.textContent = content;
  return e;
}

// ---------------------------------------------------------------- tooltip

function showTip(lines: HTMLElement[], x: number, y: number) {
  tip.replaceChildren(...lines);
  tip.hidden = false;
  const box = root.querySelector<HTMLElement>(".map-figure")!.getBoundingClientRect();
  const w = tip.offsetWidth, h = tip.offsetHeight;
  const left = Math.min(Math.max(8, x - box.left + 14), box.width - w - 8);
  const top = y - box.top - h - 14 < 0 ? y - box.top + 18 : y - box.top - h - 14;
  tip.style.transform = `translate(${left}px, ${top}px)`;
}
const hideTip = () => { tip.hidden = true; };

// ---------------------------------------------------------------- the spine chart

function drawChart(data: MapData) {
  chartBox.replaceChildren();
  const vertical = chartBox.clientWidth < 640;
  const n = data.spine.length;
  const groupStart = data.spine.map((it, i) => i === 0 || data.spine[i - 1].group !== it.group);
  const groups = groupStart.filter(Boolean).length;
  const GAP = vertical ? 6 : 5;

  // Along the spine: a slot per passage, a gap between groups.
  const width = chartBox.clientWidth;
  const alongLen = vertical ? n * 9 + groups * GAP + 40 : width;
  const PAD = 12;
  const slot = (alongLen - 2 * PAD - (groups - 1) * GAP) / n;
  const pos0 = new Array<number>(n);
  let g = -1;
  data.spine.forEach((_, i) => { if (groupStart[i]) g++; pos0[i] = PAD + i * slot + g * GAP + slot / 2; });

  // Across the spine: bars on one side, cases on the other.
  const BAR = vertical ? Math.max(90, width * 0.42 - 20) : 190;
  const DOTS = vertical ? Math.max(70, width * 0.38 - 20) : 170;
  const BAND = 24;
  const spineAt = vertical ? width * 0.5 - BAND / 2 : BAR + 14; // the near edge of the spine band
  const acrossLen = vertical ? width : BAR + 14 + BAND + DOTS + 18;

  // (along, across) -> (x, y)
  const xy = (a: number, c: number): [number, number] => (vertical ? [c, a] : [a, c]);
  const rect = (a0: number, aLen: number, c0: number, cLen: number) => {
    const [x, y] = xy(a0, c0);
    return vertical ? { x, y, width: cLen, height: aLen } : { x, y, width: aLen, height: cLen };
  };

  const svg = select(chartBox).append("svg")
    .attr("class", vertical ? "map-svg vertical" : "map-svg")
    .attr("width", vertical ? width : width)
    .attr("height", vertical ? alongLen : acrossLen)
    .attr("role", "img")
    .attr("tabindex", 0)
    .attr("aria-label", `Map of ${n} passages of the founding documents with their links and cases. The table below the map gives the same counts.`);
  const view = svg.append("g");
  const bands = view.append("g").attr("class", "bands");
  const bars = view.append("g").attr("class", "bars");
  const dots = view.append("g").attr("class", "dots");
  const names = view.append("g").attr("class", "names");
  const hits = view.append("g").attr("class", "hits");
  // A passage's name within its group: "Art. I §8 cl. 4" -> "§8 cl. 4".
  const within = (it: Item) => it.short.replace(/^(Art\. [IVX]+|Amend\. [IVXL]+|Decl\.)\s*/, "") || it.short;

  // Visible marks under the filters; counted again when a filter changes.
  const keep = (m: Mark) => (m[1] === "case" ? shown.has("cases") : shown.has(m[1])) && (!reviewedOnly || m[3] === 1);
  let stacks: Record<string, number>[] = [];
  let caseDots: { i: number; k: number; c: Case; ref: string }[] = [];
  let maxBar = 1, maxDots = 1;
  function recount() {
    stacks = data.spine.map(() => Object.fromEntries(SIDES.map((s) => [s, 0])) as Record<string, number>);
    for (const m of data.debate) if (keep(m)) stacks[m[0]][m[1]]++;
    caseDots = [];
    const perPassage = new Array<number>(n).fill(0);
    for (const m of data.interprets) if (keep(m)) caseDots.push({ i: m[0], k: perPassage[m[0]]++, c: data.cases[m[4]], ref: m[4] });
    maxBar = Math.max(1, ...stacks.map((s) => SIDES.reduce((t, k) => t + s[k], 0)));
    maxDots = Math.max(1, ...perPassage);
  }
  recount();

  let pos = pos0.slice();
  let w = slot;

  function layout(animate: boolean) {
    const unit = BAR / maxBar;
    const r = Math.max(1.2, Math.min(w / 2 - 0.6, 3.2));
    const step = Math.min(2 * r + 1, DOTS / maxDots);
    const t = (sel: Selection<any, any, any, any>) => (animate && !reduceMotion() ? sel.transition().duration(350) : sel);

    // Bars grow away from the spine.
    const segs: { i: number; side: string; from: number; len: number }[] = [];
    stacks.forEach((s, i) => {
      let acc = 0;
      for (const side of SIDES) {
        if (s[side]) segs.push({ i, side, from: acc, len: s[side] * unit });
        acc += s[side] * unit;
      }
    });
    const barSel = bars.selectAll<SVGRectElement, (typeof segs)[number]>("rect").data(segs, (d) => `${d.i}-${d.side}`);
    barSel.exit().remove();
    const barEnter = barSel.enter().append("rect").attr("class", (d) => `bar s-${d.side}`).each(function (d) {
      // New segments grow out of the spine.
      const a = rect(pos[d.i] - Math.max(0.6, w - 1) / 2, Math.max(0.6, w - 1), spineAt, 0);
      select(this).attr("x", a.x).attr("y", a.y).attr("width", a.width).attr("height", a.height);
    });
    t(barEnter.merge(barSel)).each(function (d) {
      const a = rect(pos[d.i] - Math.max(0.6, w - 1) / 2, Math.max(0.6, w - 1), spineAt - d.from - d.len, d.len);
      select(this).attr("x", a.x).attr("y", a.y).attr("width", a.width).attr("height", a.height);
    });

    // Cases: dots away from the spine on the other side, oldest nearest.
    const dotSel = dots.selectAll<SVGCircleElement, (typeof caseDots)[number]>("circle").data(caseDots, (d) => `${d.i}-${d.ref}`);
    dotSel.exit().remove();
    const dotEnter = dotSel.enter().append("circle").attr("class", (d) => (d.c.overruled ? "dot overruled" : "dot"));
    t(dotEnter.merge(dotSel)).each(function (d) {
      const [x, y] = xy(pos[d.i], spineAt + BAND + 6 + r + d.k * step);
      select(this).attr("cx", x).attr("cy", y).attr("r", r);
    });

    // The spine band: one segment per group, labelled where it has room.
    const spans: { name: string; a0: number; a1: number }[] = [];
    data.spine.forEach((it, i) => {
      if (groupStart[i]) spans.push({ name: it.group, a0: pos[i] - w / 2, a1: pos[i] + w / 2 });
      else spans[spans.length - 1].a1 = pos[i] + w / 2;
    });
    const band = bands.selectAll<SVGGElement, (typeof spans)[number]>("g").data(spans, (d) => d.name);
    const bandEnter = band.enter().append("g");
    bandEnter.append("rect").attr("class", "band").attr("rx", 3);
    bandEnter.append("text").attr("class", "band-label").text((d) => tag(d.name));
    bandEnter.append("title").text((d) => d.name);
    bandEnter.merge(band).each(function (d) {
      const a = rect(d.a0, Math.max(1, d.a1 - d.a0), spineAt, BAND);
      const sel = select(this);
      sel.select("rect").attr("x", a.x).attr("y", a.y).attr("width", a.width).attr("height", a.height);
      // The label sits in the middle of the part of the group in view, so it stays visible when zoomed in.
      const lo = vertical ? d.a0 : Math.max(d.a0, 0), hi = vertical ? d.a1 : Math.min(d.a1, alongLen);
      const [x, y] = xy((lo + hi) / 2, spineAt + BAND / 2);
      const room = hi - lo > (vertical ? 12 : tag(d.name).length * 6.5 + 4);
      sel.select("text").attr("x", x).attr("y", y).attr("display", room ? null : "none");
    });

    // Zoomed in far enough, each passage is named along the far edge.
    const named = !vertical && w >= 34;
    const nameSel = names.selectAll<SVGTextElement, Item>("text").data(named ? data.spine : [], (d) => d.ref);
    nameSel.exit().remove();
    nameSel.enter().append("text").attr("class", "name").text(within).merge(nameSel).each(function (_, i) {
      select(this).attr("x", pos[i]).attr("y", acrossLen - 4).attr("display", pos[i] < 0 || pos[i] > alongLen ? "none" : null);
    });

    // Hit areas: a full-length strip per passage for pointer and focus.
    const hitSel = hits.selectAll<SVGRectElement, Item>("rect").data(data.spine, (d) => d.ref);
    hitSel.enter().append("rect").attr("class", "hit").merge(hitSel).each(function (_, i) {
      const a = rect(pos[i] - w / 2, w, 0, acrossLen);
      select(this).attr("x", a.x).attr("y", a.y).attr("width", a.width).attr("height", a.height);
    });
  }

  // ---- tooltip and selection
  let active = -1;
  function describe(i: number): HTMLElement[] {
    const it = data.spine[i];
    const out = [text("strong", "", it.label)];
    const counts = SIDES.filter((s) => stacks[i][s]).map((s) => `${SIDE_NAMES[s]} ${stacks[i][s]}`);
    out.push(text("span", "", counts.length ? `Links: ${counts.join(" · ")}` : "No links from the debates shown"));
    const cs = caseDots.filter((d) => d.i === i);
    if (cs.length) {
      const names = cs.slice(0, 6).map((d) => `${d.c.label} (${d.c.year})${d.c.overruled ? ", overruled" : ""}`);
      out.push(text("span", "", `${cs.length} ${cs.length === 1 ? "case" : "cases"}: ${names.join("; ")}${cs.length > 6 ? "; …" : ""}`));
    }
    out.push(text("em", "", "Select to open"));
    return out;
  }
  function focus(i: number, at?: [number, number]) {
    active = i;
    hits.selectAll<SVGRectElement, Item>("rect").classed("on", (_, k) => k === i);
    if (i < 0) return hideTip();
    const node = hits.selectAll<SVGRectElement, Item>("rect").nodes()[i];
    const b = node.getBoundingClientRect();
    showTip(describe(i), at ? at[0] : b.left + b.width / 2, at ? at[1] : b.top + (vertical ? b.height / 2 : 20));
  }
  const open = (i: number) => { const u = local(data.spine[i].url); if (u) location.href = u; };

  hits.on("pointermove", (e: PointerEvent) => {
    const i = hits.selectAll("rect").nodes().indexOf(e.target as Element);
    if (i >= 0) focus(i, [e.clientX, e.clientY]);
  }).on("pointerleave", () => focus(-1))
    .on("click", (e: MouseEvent) => {
      const i = hits.selectAll("rect").nodes().indexOf(e.target as Element);
      if (i >= 0) open(i);
    });
  svg.on("keydown", (e: KeyboardEvent) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (step) {
      e.preventDefault();
      focus(Math.min(n - 1, Math.max(0, (active < 0 ? -step : active) + step)));
      const node = hits.selectAll<SVGRectElement, Item>("rect").nodes()[active];
      node?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    } else if (e.key === "Enter" && active >= 0) open(active);
    else if (e.key === "Escape") focus(-1);
  }).on("blur", () => focus(-1));

  // ---- pan and zoom along the spine (wide screens)
  if (!vertical) {
    const z = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .translateExtent([[0, 0], [width, acrossLen]])
      .filter((e: any) => (e.type === "wheel" ? e.ctrlKey || e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY) : !e.button))
      .on("zoom", (e: D3ZoomEvent<SVGSVGElement, unknown>) => {
        const k = e.transform.k;
        pos = pos0.map((p) => e.transform.applyX(p));
        w = slot * k;
        hideTip();
        layout(false);
      });
    svg.call(z as any).on("dblclick.zoom", null);
    svg.call(z.transform as any, zoomIdentity);
  }
  layout(false);
  return { update: () => { recount(); hideTip(); layout(true); } };
}

// ---------------------------------------------------------------- the arc diagram

function drawArcs(data: MapData) {
  arcBox.replaceChildren();
  const arcs = data.arcs.filter((a) => (!reviewedOnly || a.reviewed > 0) && shown.has(data.works[a.from]?.side ?? "other"));
  const used = new Set(arcs.flatMap((a) => [a.from, a.to]));
  const order = Object.keys(data.works)
    .filter((w) => used.has(w))
    .sort((a, b) => SIDES.indexOf(data.works[a].side) - SIDES.indexOf(data.works[b].side) || data.works[a].short.localeCompare(data.works[b].short));
  if (!order.length) {
    arcBox.append(text("p", "muted", "No links between works match the filters."));
    return;
  }
  const width = Math.max(arcBox.clientWidth, order.length * 46);
  const step = (width - 150) / Math.max(1, order.length - 1); // room on the right for the last slanted label
  const x = Object.fromEntries(order.map((w, i) => [w, 30 + i * step]));
  const maxSpan = Math.max(...arcs.map((a) => Math.abs(x[a.to] - x[a.from])));
  const base = Math.min(maxSpan / 2, 220) + 16;
  const height = base + 120;

  const svg = select(arcBox).append("svg").attr("class", "arc-svg").attr("width", width).attr("height", height)
    .attr("role", "img").attr("aria-label", `${arcs.length} groups of links between ${order.length} works of the debate`);
  const paths = svg.append("g").selectAll("path").data(arcs).enter().append("path")
    .attr("class", (a) => `arc s-${data.works[a.from]?.side ?? "other"}`)
    .attr("d", (a) => {
      const x1 = x[a.from], x2 = x[a.to], r = Math.abs(x2 - x1) / 2;
      const h = Math.min(r, base - 10);
      return `M${x1},${base} C${x1},${base - h * 1.33} ${x2},${base - h * 1.33} ${x2},${base}`;
    })
    .attr("stroke-width", (a) => 1 + Math.sqrt(a.n) * 1.4);
  paths.on("pointermove", (e: PointerEvent, a: Arc) => {
    const kind = { answer: "answers or rebuttals", cite: "quotations or citations", theme: "shared themes", case: "case links" }[a.kind] || a.kind;
    showTip([text("strong", "", `${data.works[a.from].short} → ${data.works[a.to].short}`), text("span", "", `${a.n} ${kind}${a.reviewed ? `, ${a.reviewed} reviewed` : ""}`)], e.clientX, e.clientY);
  }).on("pointerleave", hideTip);

  const nodes = svg.append("g").selectAll("g").data(order).enter().append("g")
    .attr("class", "arc-node")
    .attr("transform", (w) => `translate(${x[w]},${base})`)
    .attr("tabindex", 0)
    .attr("role", "link")
    .attr("aria-label", (w) => `${data.works[w].title}: open`);
  nodes.append("circle").attr("r", 5).attr("class", (w) => `s-${data.works[w].side}`);
  nodes.append("text").attr("class", "arc-label").attr("transform", "rotate(40) translate(9,4)").text((w) => data.works[w].short);
  const go = (w: string) => { const u = local(data.works[w].url); if (u) location.href = u; };
  nodes.on("click", (_: MouseEvent, w: string) => go(w))
    .on("keydown", (e: KeyboardEvent, w: string) => { if (e.key === "Enter") go(w); })
    .on("pointerenter", (_: PointerEvent, w: string) => paths.classed("dim", (a: Arc) => a.from !== w && a.to !== w))
    .on("pointerleave", () => paths.classed("dim", false));
}

// ---------------------------------------------------------------- start

fetch(`${BASE}/data/map.json`)
  .then((r) => r.json())
  .then((data: MapData) => {
    let chart = drawChart(data);
    drawArcs(data);
    filterBox.hidden = false;
    filterBox.addEventListener("click", (e) => {
      const b = (e.target as HTMLElement).closest<HTMLButtonElement>("button");
      if (!b) return;
      const on = b.getAttribute("aria-pressed") !== "true";
      b.setAttribute("aria-pressed", String(on));
      if (b.dataset.side) on ? shown.add(b.dataset.side) : shown.delete(b.dataset.side);
      else reviewedOnly = on;
      chart.update(); // the bars and dots move to the new counts
      drawArcs(data);
    });
    let last = chartBox.clientWidth;
    new ResizeObserver(() => {
      if (Math.abs(chartBox.clientWidth - last) < 24) return;
      last = chartBox.clientWidth;
      chart = drawChart(data);
      drawArcs(data);
    }).observe(chartBox);
  })
  .catch(() => chartBox.replaceChildren(text("p", "muted", "The map could not be loaded; the table below has the same counts.")));
