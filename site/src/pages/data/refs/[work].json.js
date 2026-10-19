// /data/refs/{work}.json: the paragraphs of one debate in Congress, ref ->
// {label, url} (decision 63). Named by the debate's entry in /data/refs.json.
import { listRefParts, loadRefPart } from "../../../lib/data.js";

export function getStaticPaths() {
  return listRefParts().map((work) => ({ params: { work } }));
}

export function GET({ params }) {
  return new Response(JSON.stringify(loadRefPart(params.work)), { headers: { "Content-Type": "application/json" } });
}
