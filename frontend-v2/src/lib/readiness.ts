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
  const docs = v.documents ?? 0;
  const served = typeof v.vnext_served === "number" ? v.vnext_served : null;
  if (v.verdict === "VNEXT_COMPLETE") {
    // SERVED-PROFILE-LABEL: green only when search USES the vNext cards (cinema: 77 written, 0 used — the guard kept the basic)
    if (served !== null && docs > 0 && served < docs) {
      return { state: "degraded", label: "SEARCHABLE · BASIC PROFILES",
               detail: `vNext cards written for ${(v.vnext_profiles ?? docs).toLocaleString()}/${docs.toLocaleString()} files · ` +
                       `search uses ${served.toLocaleString()} (the selection guard kept the richer basic cards) · ${detail}` };
    }
    return { state: "ready", label: v.verdict, detail };
  }
  if (p && p.unresolved === 0 && docs > 0 && typeof v.profiled === "number" && v.profiled >= docs) {
    return { state: "degraded", label: "SEARCHABLE · BASIC PROFILES",
             detail: `${(served ?? v.vnext_profiles ?? 0).toLocaleString()}/${docs.toLocaleString()} files use the vNext profile · ${detail}` };
  }
  return { state: "blocked", label: v.verdict, detail };
}

/** FILES-READY-LABEL (the owner, 2026-09-29: "why are files blocked?") — a file whose parents are all mapped and which has a
 *  profile is SEARCHABLE, whichever profile it has. Since 2026-09-17 the fleet writes the base profile for new files
 *  (`POLYMATH_DOC_PROFILE_VNEXT=0`), so a missing vNext profile alone is never "Blocked". */
export function docSearchable(d: DocSummary | null | undefined): boolean {
  return !!d && (d.vnext_ready || (d.map_unresolved === 0 && d.profile_present));
}

/** SERVED-PROFILE-LABEL (the owner, 2026-10-01: "fix the cinema badge so this confusion doesnt happen"): a file is vNext
 *  only when SEARCH serves its vNext card. A written vNext card the selection guard refused (thinner than the basic card it
 *  would replace) does not count. Without the index's answer (older backend / index unread) the written state stands. */
export function servesVnext(d: DocSummary | null | undefined): boolean {
  if (!d) return false;
  return d.profile_served === undefined ? d.vnext_ready : d.vnext_ready && d.profile_served === "vnext";
}

/** The writer of the card search serves for a file ("vnext" | "basic" | null = no card); without the index's answer, the
 *  latest card's writer (the written state). The Profile column shows this — a card property, not the file's readiness. */
export function servedWriter(d: DocSummary | null | undefined): "vnext" | "basic" | null {
  if (!d) return null;
  if (d.profile_served !== undefined) return d.profile_served;
  return d.profile_vnext ? "vnext" : d.profile_present ? "basic" : null;
}

/** Per-document readiness, from the backend's own counts: Ready (search uses the vNext card) · Ready · basic profile
 *  (searchable on the basic card) · Blocked (unresolved parents or no profile: retrieval misses part of the file). */
export function docVnext(d: DocSummary): Verdict {
  if (servesVnext(d)) return { state: "ready", label: "READY" };
  if (docSearchable(d)) {
    return { state: "degraded", label: "READY · BASIC PROFILE",
             detail: d.profile_vnext && d.profile_served === "basic"
               ? "searchable; search uses the basic card (a vNext card was written, but the selection guard kept the richer basic one)"
               : "searchable; search uses the basic card (no vNext card built)" };
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
