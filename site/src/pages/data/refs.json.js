// /data/refs.json: every ref with its label and URL. Used by "jump to"
// search, and a stable lookup for other sites (e.g. CommonHall).
import { loadRefs } from "../../lib/data.js";

export function GET() {
  return new Response(JSON.stringify(loadRefs()), { headers: { "Content-Type": "application/json" } });
}
