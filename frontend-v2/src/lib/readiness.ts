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

/**
 * CONTROL READY — is the machinery healthy?
 *
 * GAP-1 (FRONTEND-V2-CONTRACT-INVENTORY-V1), closed 2026-09-12: this used to compose
 * `/ready` + `/health/pipeline` HERE — two independent calls, arithmetic in the UI,
 * exactly the drift the design law forbids (11.187: two screens composing it
 * differently will disagree). `/control_plane` now returns one composed
 * `control_ready` verdict (`shared/polymath_shared/pipeline_health.py::control_ready`);
 * this function only paints it. Pass `null` while the fetch is in flight.
 */
export function controlReady(cr: ControlPlane["control_ready"] | null | undefined): Verdict {
  if (!cr) return { state: "unknown", label: "UNKNOWN", detail: "/control_plane not reachable" };
  return { state: cr.state, label: cr.label, detail: cr.detail };
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

