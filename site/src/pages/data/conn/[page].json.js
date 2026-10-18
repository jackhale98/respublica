// /data/conn/{page}.json: full connection details for every passage on a
// reader page (ref -> connections). The reader loads it the first time a
// passage is selected, so pages stay small however many links a clause has.
import { loadPage, loadSite } from "../../../lib/data.js";

export function getStaticPaths() {
  return loadSite().pages.filter((p) => p.kind === "work" || p.kind === "part").map((p) => ({ params: { page: p.id } }));
}

export function GET({ params }) {
  const page = loadPage(params.page);
  const out = {};
  for (const b of [...(page.blocks || []), ...(page.notes || [])]) {
    if (b.type === "passage" && b.connections?.length) out[b.ref] = b.connections;
  }
  return new Response(JSON.stringify(out), { headers: { "Content-Type": "application/json" } });
}
