// /data/refs.json: every ref with its label and URL, except the paragraphs of
// the debates in Congress, which are in /data/refs/{work}.json (the debate's
// own entry names its file, "refs"; decision 63). Used by "jump to" search,
// and a stable lookup for other sites (e.g. CommonHall).
import { loadPublicRefs } from "../../lib/data.js";

export function GET() {
  return new Response(JSON.stringify(loadPublicRefs()), { headers: { "Content-Type": "application/json" } });
}
