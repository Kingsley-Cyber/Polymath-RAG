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

/** VNEXT READY — can this corpus answer from source? LIBRARY-READY-LABEL (the owner, 2026-10-01: "why is a corpus for taste
 *  showing files as red"): the per-file rule (`docSearchable`) at library level — every parent mapped and every file profiled
 *  means the library is searchable and only the richer vNext profiles are missing: amber, never red. Red stays for a library
 *  retrieval would miss part of (unresolved parents, a file with no profile). The backend verdict itself is unchanged. */
export function vnextReady(sr: SemanticReadiness | null): Verdict {
  if (!sr?.vnext) return { state: "unknown", label: "UNKNOWN" };
  const v = sr.vnext;
  const p = v.parents;
  const detail = p
    ? `${p.mapped.toLocaleString()}/${p.eligible.toLocaleString()} parents mapped` +
      (p.unresolved ? ` · ${p.unresolved.toLocaleString()} unresolved` : "")
    : undefined;
  if (v.verdict === "VNEXT_COMPLETE") return { state: "ready", label: v.verdict, detail };
  const docs = v.documents ?? 0;
  if (p && p.unresolved === 0 && docs > 0 && typeof v.profiled === "number" && v.profiled >= docs) {
    return { state: "degraded", label: "SEARCHABLE · BASIC PROFILES",
             detail: `${(v.vnext_profiles ?? 0).toLocaleString()}/${docs.toLocaleString()} files have the vNext profile · ${detail}` };
  }
  return { state: "blocked", label: v.verdict, detail };
}

/** FILES-READY-LABEL (the owner, 2026-09-29: "why are files blocked?") — a file whose parents are all mapped and which has a
 *  profile is SEARCHABLE, whichever profile it has. Since 2026-09-17 the fleet writes the base profile for new files
 *  (`POLYMATH_DOC_PROFILE_VNEXT=0`), so a missing vNext profile alone is never "Blocked". */
export function docSearchable(d: DocSummary | null | undefined): boolean {
  return !!d && (d.vnext_ready || (d.map_unresolved === 0 && d.profile_present));
}

/** Per-document readiness, from the backend's own counts: Ready (the vNext profile) · Ready · basic profile (searchable, the
 *  richer vNext profile not built) · Blocked (unresolved parents or no profile: retrieval misses part of the file). */
export function docVnext(d: DocSummary): Verdict {
  if (d.vnext_ready) return { state: "ready", label: "READY" };
  if (docSearchable(d)) {
    return { state: "degraded", label: "READY · BASIC PROFILE", detail: "searchable; the richer vNext profile is not built" };
  }
  const why: string[] = [];
  if (d.map_unresolved > 0) why.push(`${d.map_unresolved.toLocaleString()} unresolved parents`);
  if (!d.profile_present) why.push("no profile");
  return { state: "blocked", label: "BLOCKED", detail: why.join(" · ") || undefined };
}


/** Loading is not failure (FRONTEND-REFRESH-V1 P4): while the data has not arrived and nothing failed, the verdict reads
 *  "Checking", never "UNKNOWN — /control_plane not reachable". */
export const CHECKING: Verdict = { state: "unknown", label: "CHECKING" };

export function settled<T>(a: { data: T | null; error: string | null }, verdict: (d: T | null) => Verdict): Verdict {
  return a.data == null && !a.error ? CHECKING : verdict(a.data);
}
