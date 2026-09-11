import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// FRONTEND-V2-PLAN §0: V2 consumes backend authority. Every path here is a READ of a
// contract the backend already owns — the proxy exists so the browser talks to :7200
// without CORS, never to reshape a response.
const BACKEND = "http://127.0.0.1:7200";
const apiPaths = [
  "/chat", "/ask", "/retrieve", "/evidence", "/corpora", "/documents",
  "/upload", "/synthesizers", "/semantic_readiness", "/health", "/runs",
  "/control_plane", "/fleet", "/reasoning_modes", "/capabilities", "/queries",
  // /ready and /status are single-segment paths that vite would otherwise answer
  // itself with a 404 "did you mean /v2/ready?" — they must be proxied explicitly.
  "/ready", "/status", "/sidecars", "/generated", "/llm",
  // COMPARE-REVIEW-V1 + GRAPH-BROWSE-V1 (F6/F7/F9).
  "/compare", "/review", "/graph",
  // found by the guard test below, not by a user hitting a mystery 404
  "/intake", "/ui_pulse",
];

// A backend path missing from the list above does NOT fail loudly — vite answers it
// with its own 404 ("did you mean /v2/...?"), which looks like a backend error. That
// bit twice (/ready in F1, /compare in F12), so `npm test` now walks the live
// /openapi.json against this list. Export it so the test can read it.
export { apiPaths };

export default defineConfig({
  plugins: [react()],
  base: "/v2/",
  server: {
    port: 5273,
    strictPort: true,
    proxy: Object.fromEntries(apiPaths.map((p) => [p, { target: BACKEND }])),
  },
});
