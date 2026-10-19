// /data/preview/{ref}.json: the far ends of one passage's connections, to
// read in the panel without leaving the page (built by tools/site_data.py).
// The reader fetches it the first time a preview is opened on that passage.
import { listPreviews, loadPreview } from "../../../lib/data.js";

export function getStaticPaths() {
  return listPreviews().map((ref) => ({ params: { ref } }));
}

export function GET({ params }) {
  return new Response(JSON.stringify(loadPreview(params.ref)), { headers: { "Content-Type": "application/json" } });
}
