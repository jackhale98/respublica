// /data/graph/{page}.json: the links within two hops of a reader page's
// passages (built by tools/site_data.py). The graph view loads it on demand.
import { loadGraph, loadSite } from "../../../lib/data.js";

export function getStaticPaths() {
  return loadSite().pages.filter((p) => p.kind === "work" || p.kind === "part" || p.kind === "case").map((p) => ({ params: { page: p.id } }));
}

export function GET({ params }) {
  return new Response(JSON.stringify(loadGraph(params.page)), { headers: { "Content-Type": "application/json" } });
}
