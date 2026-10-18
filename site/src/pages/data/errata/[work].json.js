// /data/errata/{work}.json: one work's uncertain words, with the words around
// them, each scan's reading and the page images (built by tools/site_data.py).
// The errata page loads a work when it is opened.
import { loadErrata, loadErrataWork } from "../../../lib/data.js";

export function getStaticPaths() {
  return loadErrata().works.map((w) => ({ params: { work: w.id } }));
}

export function GET({ params }) {
  return new Response(JSON.stringify(loadErrataWork(params.work)), { headers: { "Content-Type": "application/json" } });
}
