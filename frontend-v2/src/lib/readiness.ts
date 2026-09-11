/**
 * The three readiness concepts (FRONTEND-V2-PLAN §7).
 *
 * These functions READ backend verdicts. They do not decide readiness — the backend
 * owns that. The only judgement here is presentational: which of ready/blocked/unknown
 * to paint, and what the backend said the blocker was.
 *
 * The legacy `query_ready` boolean is deliberately NOT accepted by any function in
 * this module. Measured 2026-09-10: cinema.query_ready = true while SEMANTIC and
 * VNEXT were both INCOMPLETE with 10,176 unresolved parents and 14/67 documents ready.
 */
import type { ControlPlane, DocSummary, SemanticReadiness } from "./contracts";

export type ReadyState = "ready" | "blocked" | "degraded" | "unknown";

export interface Verdict {
  state: ReadyState;
  /** the backend's own word, shown verbatim so the UI never paraphrases a verdict */
  label: string;
  detail?: string;
}

/** CONTROL READY — is the machinery healthy? */
export function controlReady(
  ready: { ready: boolean; sidecars: Record<string, boolean> } | null,
  pipeline: Record<string, unknown> | null,
): Verdict {
  if (!ready) return { state: "unknown", label: "UNKNOWN", detail: "/ready not reachable" };
  const state = typeof pipeline?.state === "string" ? (pipeline.state as string) : null;
  const dark = Object.entries(ready.sidecars ?? {})
    .filter(([name, up]) => !up && name !== "cloud-modal")   // cloud-modal is optional
    .map(([name]) => name);
  if (!ready.ready || dark.length) {
    return { state: "blocked", label: state ?? "NOT READY", detail: dark.length ? `sidecars down: ${dark.join(", ")}` : undefined };
  }
  if (state && state !== "OK" && state !== "HEALTHY") {
    return { state: "degraded", label: state, detail: describeStalls(pipeline) };
  }
  return { state: "ready", label: state ?? "READY" };
}

function describeStalls(pipeline: Record<string, unknown> | null): string | undefined {
  const open = pipeline?.stalls_open;
  const queued = pipeline?.queued_tickets;
  const parts: string[] = [];
  if (typeof open === "number" && open > 0) parts.push(`${open} open stall${open === 1 ? "" : "s"}`);
  if (typeof queued === "number" && queued > 0) parts.push(`${queued} queued`);
  return parts.length ? parts.join(" · ") : undefined;
}

/** SEMANTIC READY — is the corpus's meaning built? */
export function semanticReady(sr: SemanticReadiness | null): Verdict {
  if (!sr) return { state: "unknown", label: "UNKNOWN" };
  return sr.verdict === "SEMANTIC_COMPLETE"
    ? { state: "ready", label: sr.verdict }
    : { state: "blocked", label: sr.verdict };
}

/** VNEXT READY — can this corpus answer from source? */
export function vnextReady(sr: SemanticReadiness | null): Verdict {
  if (!sr?.vnext) return { state: "unknown", label: "UNKNOWN" };
  const p = sr.vnext.parents;
  const detail = p
    ? `${p.mapped.toLocaleString()}/${p.eligible.toLocaleString()} parents mapped` +
      (p.unresolved ? ` · ${p.unresolved.toLocaleString()} unresolved` : "")
    : undefined;
  return sr.vnext.verdict === "VNEXT_COMPLETE"
    ? { state: "ready", label: sr.vnext.verdict, detail }
    : { state: "blocked", label: sr.vnext.verdict, detail };
}

/** Per-document vNext, with the backend's own blocking counts. */
export function docVnext(d: DocSummary): Verdict {
  if (d.vnext_ready) return { state: "ready", label: "VNEXT READY" };
  const why: string[] = [];
  if (d.map_unresolved > 0) why.push(`${d.map_unresolved.toLocaleString()} unresolved parents`);
  if (!d.profile_vnext) why.push("profile not vNext");
  if (!d.profile_present) why.push("no profile");
  return { state: "blocked", label: "BLOCKED", detail: why.join(" · ") || undefined };
}

/**
 * GAP-4 (F0 / register 11.195): `control_plane.summary.processing` counts runs in
 * ('intake','reconciling','degraded') with NO age qualifier. Measured 2026-09-10:
 * cinema reported processing=64 for runs last touched 2026-09-07. Until the backend
 * age-qualifies it, the UI must NOT present that number as live activity.
 */
export function processingIsTrustworthy(_cp: ControlPlane | null): boolean {
  return false;
}
