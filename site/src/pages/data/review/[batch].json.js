// /data/review/{batch}.json: one linker run's suggested links, with both
// passages (built by tools/site_data.py). The review page loads a batch
// when it is opened.
import { loadReview, loadReviewBatch } from "../../../lib/data.js";

export function getStaticPaths() {
  return loadReview().groups.flatMap((g) => g.batches.map((b) => ({ params: { batch: b.batch } })));
}

export function GET({ params }) {
  return new Response(JSON.stringify(loadReviewBatch(params.batch)), { headers: { "Content-Type": "application/json" } });
}
