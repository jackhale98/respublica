// Build-time data access. Reads the repository's texts/, cases/ and
// sources/manifest.json, plus the link index written by
// `python -m tools.site_data` (site/.data/links.json).

import fs from "node:fs";
import path from "node:path";

// Astro bundles this module before running it, so import.meta.url is not
// stable; the build always runs from site/ (see the Makefile).
const SITE_DIR = process.cwd();
const REPO = path.resolve(SITE_DIR, "..");
if (!fs.existsSync(path.join(REPO, "texts"))) {
  throw new Error(`run the site build from site/ (looked for texts/ in ${REPO})`);
}

const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf-8"));

// Works are listed in this order in the library; any other work follows.
const ORDER = ["constitution", "amendments", "federalist"];

// Works with more segments than this get one page per top-level division.
const SPLIT_THRESHOLD = 300;

let cache;

export function loadWorks() {
  if (cache) return cache;
  const dirs = ["texts", "cases"].map((d) => path.join(REPO, d)).filter((d) => fs.existsSync(d));
  const works = dirs.flatMap((dir) =>
    fs.readdirSync(dir).filter((f) => f.endsWith(".json")).sort().map((f) => readJson(path.join(dir, f))),
  );
  works.sort((a, b) => rank(a.id) - rank(b.id) || a.id.localeCompare(b.id));
  for (const w of works) {
    w.split = w.segments.length > SPLIT_THRESHOLD;
    w.groups = groupByTopDivision(w);
  }
  cache = works;
  return works;
}

function rank(id) {
  const i = ORDER.indexOf(id);
  return i === -1 ? ORDER.length : i;
}

// Top-level divisions, each with the segments under it, in text order.
function groupByTopDivision(work) {
  const tops = (work.divisions || []).filter((d) => d.level === 1);
  const groups = tops.map((d) => ({ division: d, slug: slugFor(work, d.ref), segments: [] }));
  const orphan = { division: null, slug: "other", segments: [] };
  for (const s of work.segments) {
    const g = groups.find((x) => s.ref === x.division.ref || s.ref.startsWith(x.division.ref + "."));
    (g || orphan).segments.push(s);
  }
  if (orphan.segments.length) groups.push(orphan);
  return groups;
}

// "Federalist.10" -> "10"; "Constitution.Preamble" -> "preamble"
function slugFor(work, ref) {
  return ref.slice(work.ref_prefix.length + 1).toLowerCase().replace(/[^a-z0-9]+/g, "-") || "all";
}

export function workFor(ref) {
  return loadWorks().find((w) => ref === w.ref_prefix || ref.startsWith(w.ref_prefix + "."));
}

// URL of the page (and anchor) where a ref is shown.
export function refUrl(ref) {
  const work = workFor(ref);
  if (!work) return null;
  const base = `/texts/${work.id}/`;
  if (!work.split) return `${base}#${anchor(ref)}`;
  const g = work.groups.find((x) => x.division && (ref === x.division.ref || ref.startsWith(x.division.ref + ".")));
  if (!g) return base;
  return ref === g.division.ref ? `${base}${g.slug}/` : `${base}${g.slug}/#${anchor(ref)}`;
}

export const anchor = (ref) => ref;

export function loadManifest() {
  return readJson(path.join(REPO, "sources", "manifest.json"));
}

export function loadLinkIndex() {
  const p = path.join(SITE_DIR, ".data", "links.json");
  return fs.existsSync(p) ? readJson(p) : { by_ref: {}, overruled: [] };
}

// Only http(s) URLs from data are ever rendered (see CLAUDE.md rule 8).
export function safeUrl(url) {
  if (typeof url !== "string" || url !== url.trim()) return null;
  try {
    const u = new URL(url);
    return (u.protocol === "http:" || u.protocol === "https:") && u.host ? u.href : null;
  } catch {
    return null;
  }
}

// Split segment text into paragraphs/lines/runs with emphasis applied.
// Returns [[ [ {text, em} ] per line ] per paragraph].
export function richText(segment) {
  const text = segment.text;
  const spans = segment.emphasis || [];
  const runs = [];
  let pos = 0;
  for (const [a, b] of spans) {
    if (a > pos) runs.push({ text: text.slice(pos, a), em: false });
    runs.push({ text: text.slice(a, b), em: true });
    pos = b;
  }
  if (pos < text.length) runs.push({ text: text.slice(pos), em: false });

  const paras = [[[]]];
  for (const run of runs) {
    const pieces = run.text.split(/(\n\n|\n)/);
    for (const piece of pieces) {
      if (piece === "\n\n") paras.push([[]]);
      else if (piece === "\n") paras.at(-1).push([]);
      else if (piece) paras.at(-1).at(-1).push({ text: piece, em: run.em });
    }
  }
  return paras;
}

export const LINK_TYPE_LABELS = {
  quotes: "quotes",
  cites: "cites",
  responds_to: "responds to",
  rebuts: "rebuts",
  shared_theme: "shares a theme with",
  interprets: "interprets",
  overrules: "overrules",
  implements: "implements",
};
