# Res Publica — Agent Rules

Res Publica is a static, open-source library of American founding texts and landmark Supreme Court cases, with verified links between passages. See `PLAN.md` for the full plan.

## Non-negotiable rules

1. **Never write source text yourself.** Text in `texts/` and `cases/` must come only from importer scripts run on files in `sources/raw/`. Do not type, retype, paraphrase, modernize, or "fix" source text. If an import looks wrong, fix the importer and rerun it.
2. **Never edit `sources/raw/`.** Raw files are downloaded originals. To add one, download it with a script and record its URL, retrieval date, sha256, and license in `sources/manifest.json`.
3. **OCR or transcription errors are flagged, not fixed.** Record suspected errors in `docs/errata.md` with the ref, the suspected problem, and the source page. A human corrects them against the page image, and the correction is applied by the importer and logged.
4. **Links are proposals until reviewed.** Write new links to `links/proposed/` with `status: "suggested"`, a `rationale`, a `confidence`, and `created_by`. Never set `status: "reviewed"`; only a human does that.
5. **Quotes must be exact.** Any `from_quote` or `to_quote` must be an exact substring of the passage. Copy it from the text file programmatically; do not write it from memory.
6. **Refs are permanent.** Never renumber published refs. Use the errata process instead.
7. **No legal characterizations.** Never write what a case held, or whether it is still good law. Holdings come from the opinion or its official syllabus, quoted verbatim. Overrulings are recorded only as `overrules` links that cite a source.
8. **Only `http:` and `https:` URLs.** Reject any other scheme at import time. Never render a URL from data into a page without checking its scheme.
9. **Run `make verify` before finishing any task.** If it fails, fix the cause; never weaken or skip a check to make it pass.

## Reference scheme

- `Constitution.Preamble`, `Constitution.{article}.{section}.{clause}`
- `Amendment.{n}.{section}`
- `Federalist.{paper}.{paragraph}`
- `{Series}.{essay}.{paragraph}` (e.g. `Brutus.1.4`)
- `Case.{courtlistener_cluster_id}`, `Case.{cluster_id}.{paragraph}`

Edge cases (articles without sections, footnotes, signatures) are specified in `docs/references.md`.

## Link types

`quotes`, `cites`, `responds_to`, `rebuts`, `shared_theme`, `interprets`, `overrules`, `implements`. Prefer the most specific type that the text supports. Use `shared_theme` sparingly and explain it in the rationale.

## Working conventions

- Python for importers and tools; Astro for the site.
- Keep JSON pretty-printed with stable key order so diffs stay readable.
- One linker run covers one unit (for example, one Federalist paper) so work can run in parallel and be reviewed in small batches.
- When unsure whether a connection is real, leave it out or mark it `low` confidence with a clear rationale.
- Before writing a parser, check field names against a real downloaded response, not memory.
- New refs go into `refs.lock` with `make lock-refs`. Never remove a ref from it.
- The site renders only what `tools/site_data.py` produces; page structure, URLs and link display rules live there, not in Astro.
- Share helpers (HTTP fetching, PDF text extraction, URL checks) in one module; don't copy them into each importer.
- **Keep docs in step with code.** A change that alters behavior updates the README and docs in the same commit. Read the whole section you are editing before changing it, so you don't duplicate paragraphs or table rows. Append new entries to `docs/decisions.md` at the end, in number order.
- Pin GitHub Actions to commit SHAs and tools to fixed versions. The site needs no secrets; don't add any without asking.
- Ask before adding a new upstream data source or a third-party script.
