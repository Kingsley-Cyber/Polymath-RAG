import { describe, expect, it } from "vitest";
import { apiPaths } from "../../vite.config";

/**
 * F11 guard — every backend route must be reachable through the dev proxy.
 *
 * A path missing from `apiPaths` does not fail loudly: vite answers it itself with a
 * 404 "did you mean /v2/...?", which in the UI is indistinguishable from a backend
 * error. That cost two debugging rounds (`/ready` in F1, `/compare` in F12), so this
 * walks the LIVE openapi document against the proxy list.
 *
 * Skips when no backend is reachable, so it never blocks an offline build.
 */
// import.meta.env keeps this free of @types/node in a browser-targeted tsconfig.
const BASE = (import.meta as { env?: Record<string, string> }).env?.POLYMATH_BASE_URL
  ?? "http://127.0.0.1:7200";

async function openapi(): Promise<Record<string, unknown> | null> {
  try {
    const r = await fetch(`${BASE}/openapi.json`, { signal: AbortSignal.timeout(5000) });
    return r.ok ? ((await r.json()) as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

describe("dev proxy", () => {
  it("covers every backend route prefix", async () => {
    const doc = await openapi();
    if (!doc) return;                       // no live backend — nothing to check
    const paths = Object.keys((doc.paths ?? {}) as Record<string, unknown>);
    expect(paths.length).toBeGreaterThan(0);

    const uncovered = paths.filter((p) => {
      if (p.startsWith("/openapi") || p.startsWith("/docs") || p.startsWith("/redoc")) return false;
      return !apiPaths.some((prefix) => p === prefix || p.startsWith(`${prefix}/`));
    });
    expect(uncovered, `backend routes not proxied (the UI would see a vite 404): ${uncovered.join(", ")}`)
      .toEqual([]);
  });
});
