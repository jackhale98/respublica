// @ts-check
import fs from "node:fs";
import { defineConfig } from "astro/config";

// Where the site is served: site/site.config.json (also read by
// tools/check_site.py). Moving to library.commonhall.org means setting
// "url" to that domain and "base" to "".
const where = JSON.parse(fs.readFileSync(new URL("./site.config.json", import.meta.url), "utf-8"));

// Static site; no server, no third-party scripts. The Content Security
// Policy is emitted by Astro as a <meta> tag on every page, with hashes for
// the few scripts and styles Astro itself generates. 'wasm-unsafe-eval'
// lets Pagefind's search index compile WebAssembly; it does not allow
// JavaScript eval (docs/decisions.md).
export default defineConfig({
  site: where.url,
  base: where.base || "/",
  output: "static",
  trailingSlash: "always",
  build: { format: "directory", inlineStylesheets: "never" },
  security: {
    csp: {
      algorithm: "SHA-256",
      directives: [
        "default-src 'self'",
        "img-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
      ],
      scriptDirective: { resources: ["'self'", "'wasm-unsafe-eval'"] },
      styleDirective: { resources: ["'self'"] },
    },
  },
  vite: {
    build: { assetsInlineLimit: 0 },
  },
});
