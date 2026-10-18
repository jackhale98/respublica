// Build-time data access. Everything here comes from `python -m tools.site_data`
// (site/.data/), which owns URLs, page structure and text runs. This module
// only loads it.

import fs from "node:fs";
import path from "node:path";

// Astro bundles this module before running it, so import.meta.url is not
// stable; the build always runs from site/ (see the Makefile).
const DATA = path.resolve(process.cwd(), ".data");
if (!fs.existsSync(path.join(DATA, "site.json"))) {
  throw new Error(`site data missing in ${DATA}; run \`make site-data\` from the repository root`);
}

const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf-8"));
const cache = new Map();
const cached = (key, fn) => (cache.has(key) ? cache.get(key) : cache.set(key, fn()).get(key));

export const loadSite = () => cached("site", () => readJson(path.join(DATA, "site.json")));
export const loadPage = (id) => cached(`page:${id}`, () => readJson(path.join(DATA, "pages", `${id}.json`)));
export const loadRefs = () => cached("refs", () => readJson(path.join(DATA, "refs.json")));
export const loadManifest = () => cached("manifest", () => readJson(path.resolve(process.cwd(), "..", "sources", "manifest.json")));

// Only http(s) URLs from data are ever rendered (CLAUDE.md rule 8).
export function safeUrl(url) {
  if (typeof url !== "string" || url !== url.trim()) return null;
  try {
    const u = new URL(url);
    return (u.protocol === "http:" || u.protocol === "https:") && u.host ? u.href : null;
  } catch {
    return null;
  }
}

// The path the site is served under: "" at a domain root, "/respublica" on
// jackhale98.github.io. Set in site/site.config.json (docs/decisions.md 22).
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// Site data and templates use root-relative paths ("/federalist/10/");
// every one goes through href() so the base path is applied in one place.
export function href(path) {
  return typeof path === "string" && path.startsWith("/") && !path.startsWith("//") ? BASE + path : path;
}

// Internal links from site data: site-relative paths only, with the base applied.
export function localUrl(url) {
  return typeof url === "string" && url.startsWith("/") && !url.startsWith("//") ? BASE + url : null;
}

// Author identity for The Federalist, in the fixed order of the author
// palette (see styles/tokens.css: --author-*).
export const AUTHORS = [
  { key: "hamilton", label: "Hamilton", match: (a) => a.kind === "single" && a.names[0] === "Alexander Hamilton" },
  { key: "disputed", label: "Disputed", match: (a) => a.kind === "disputed" },
  { key: "joint", label: "Joint", match: (a) => a.kind === "joint" },
  { key: "madison", label: "Madison", match: (a) => a.kind === "single" && a.names[0] === "James Madison" },
  { key: "jay", label: "Jay", match: (a) => a.kind === "single" && a.names[0] === "John Jay" },
];

export const authorKey = (attr) => (attr ? AUTHORS.find((a) => a.match(attr))?.key : undefined);

export const formatNumber = (n) => n.toLocaleString("en-US");

// "Article I, Section 8" -> "Section 8"
export const shortLabel = (label) => label.split(", ").at(-1);

// First date printed in a newspaper line, if any.
export function printedDate(publication = []) {
  for (const line of publication) {
    const m = line.match(/([A-Z][a-z]+ \d{1,2}, \d{4})/);
    if (m) return m[1];
  }
  return null;
}

export function newspaper(publication = []) {
  const first = publication[0] || "";
  return first.replace(/^(From|For) (the )?/, "").replace(/\.\s*([A-Z][a-z]+day.*)?$/, "").replace(/\.$/, "");
}

export const COLLECTIONS = {
  founding: "Founding document",
  federalist: "The ratification debate",
};

// "1787-09-17" -> "September 17, 1787"; "1791-12-15/1992-05-07" -> "1791–1992"
export function formatDate(iso) {
  if (!iso) return null;
  if (iso.includes("/")) {
    const [a, b] = iso.split("/");
    return a.slice(0, 4) === b.slice(0, 4) ? a.slice(0, 4) : `${a.slice(0, 4)}–${b.slice(0, 4)}`;
  }
  const d = new Date(`${iso}T12:00:00Z`);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
}

export const readingMinutes = (words) => Math.max(1, Math.round(words / 230));

export function authorText(attr) {
  if (!attr) return "";
  if (attr.kind === "disputed") return `${attr.names.map((n) => n.split(" ").at(-1)).join(" or ")} (disputed)`;
  if (attr.kind === "joint") return attr.names.map((n) => n.split(" ").at(-1)).join(" and ");
  return attr.text;
}
