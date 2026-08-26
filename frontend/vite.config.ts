import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const BACKEND = "http://127.0.0.1:7200";
const apiPaths = [
  "/chat", "/ask", "/retrieve", "/evidence", "/corpora", "/documents",
  "/upload", "/synthesizers", "/semantic_readiness", "/health", "/runs",
];

export default defineConfig({
  plugins: [react()],
  base: "/ui/",
  server: {
    proxy: Object.fromEntries(apiPaths.map((p) => [p, { target: BACKEND }])),
  },
});
