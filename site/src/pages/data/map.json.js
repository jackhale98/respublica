// /data/map.json: the overview map's data (tools/site_data.py, build_map):
// the founding documents passage by passage, the links that reach each one
// and the cases that interpret it, and the links between the debate's works.
import { loadMap } from "../../lib/data.js";

export function GET() {
  return new Response(JSON.stringify(loadMap()), { headers: { "Content-Type": "application/json" } });
}
