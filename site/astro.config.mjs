// @ts-check
import { defineConfig } from "astro/config";

// Static site; no server, no third-party scripts. The Content Security
// Policy is emitted by Astro as a <meta> tag on every page, with hashes for
// the few scripts and styles Astro itself generates. 'wasm-unsafe-eval'
// lets Pagefind's search index compile WebAssembly; it does not allow
// JavaScript eval (docs/decisions.md).
export default defineConfig({
  site: "https://library.commonhall.org",
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
