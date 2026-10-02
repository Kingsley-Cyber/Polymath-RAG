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

/** `working` (FILES-STATUS-TRUTH-V1): in progress and expected to finish on its own — neither healthy-done nor a problem. */
export type ReadyState = "ready" | "blocked" | "degraded" | "unknown" | "working";

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
 *  showing files as red"): the per-file rule (`docSearchable`) at library level. FILES-STATUS-TRUTH-V1 (the owner,
 *  2026-10-02: "THE UI MAY NEED TO BE UPDATED ESPECIALLY FILES COLOR AND STATUSES"): every parent mapped and every file
 *  profiled is a working library — the basic profile is the default card (vNext writing is off since 2026-09-17), so it
 *  reads green "Searchable · basic profiles", never amber. Red stays for a library retrieval would miss part of
 *  (unresolved parents, a file with no profile). The backend verdict itself is unchanged. */
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
      return { state: "ready", label: "SEARCHABLE · BASIC PROFILES",
               detail: `vNext cards written for ${(v.vnext_profiles ?? docs).toLocaleString()}/${docs.toLocaleString()} files · ` +
                       `search uses ${served.toLocaleString()} (the selection guard kept the richer basic cards) · ${detail}` };
    }
    return { state: "ready", label: v.verdict, detail };
  }
  if (p && p.unresolved === 0 && docs > 0 && typeof v.profiled === "number" && v.profiled >= docs) {
    return { state: "ready", label: "SEARCHABLE · BASIC PROFILES",
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

const STAGE_WORDS: Record<string, string> = {
  intake: "intake", extract: "fact extraction", profile_document: "document scan", project_qdrant: "search index",
  project_neo4j: "graph", canonicalize: "entity merge", project_canonical: "entity graph", verify_projections: "verification",
  compile_objects: "knowledge objects", parent_summary: "section summaries", document_summary: "document summary",
  corpus_summary: "library summary", vocabulary: "vocabulary", parent_enrichment: "enrichment", doc_profile: "document profile",
  doc_parent_map: "pMAP",
};

/** A pipeline stage in plain words ("project_neo4j" → "graph"); an unknown stage keeps its own name. */
export function stageWords(stage: string): string {
  return STAGE_WORDS[stage] ?? stage.replace(/_/g, " ");
}

/** FILES-STATUS-TRUTH-V1 (the owner, 2026-10-02: "THE UI MAY NEED TO BE UPDATED ESPECIALLY FILES COLOR AND STATUSES IDK
 *  WHATS WRONG"): one status per file from the backend's own state, in the order a person acts on it —
 *    Not searchable (red)   unresolved parents or no profile: retrieval misses part of the file
 *    Needs retry (amber)    a step failed with its retries spent (which step and why, in the title)
 *    Processing (blue)      the file's required steps are still running: its run is not yet query_ready
 *    Ready (green)          searchable and every required step done; summaries still being written show in the title
 *  Measured before: every cinema file read amber "Ready · basic profile", including five whose graph steps had failed and
 *  were running again, and commerce's two books whose fact extraction had failed. The basic profile is the normal card,
 *  never a warning; without the run fields (an older backend) a searchable file reads Ready. */
export function docStatus(d: DocSummary): Verdict {
  if (!docSearchable(d)) {
    const why: string[] = [];
    if (d.map_unresolved > 0) why.push(`${d.map_unresolved.toLocaleString()} unresolved parents`);
    if (!d.profile_present) why.push("no profile");
    return { state: "blocked", label: "NOT SEARCHABLE", detail: why.join(" · ") || undefined };
  }
  const failed = d.work_failed ?? [];
  if (failed.length) {
    return { state: "degraded", label: "NEEDS RETRY",
             detail: failed.map((f) => `${stageWords(f.stage)} failed${f.note ? `: ${f.note}` : ""}`).join(" · ") +
                     " · the file is searchable meanwhile" };
  }
  const open = d.work_open ?? [];
  if (d.run_status === "degraded" || d.run_status === "failed") {
    return { state: "degraded", label: d.run_status.toUpperCase(),
             detail: "the file is searchable; its run was not promoted — open the file's details for the reason" };
  }
  if (d.run_status && d.run_status !== "query_ready") {
    return { state: "working", label: "PROCESSING",
             detail: open.length ? `running: ${open.map(stageWords).join(", ")}` : "every step is done; waiting to be marked ready" };
  }
  return { state: "ready", label: "READY",
           detail: open.length ? `searchable; still writing: ${open.map(stageWords).join(", ")}` : "searchable; every step done" };
}

/** pMAP coverage of a file: mapped + excluded out of the eligible parents; red while any parent is unresolved. */
export function docPmap(d: DocSummary): Verdict {
  if (!d.map_eligible) return { state: "unknown", label: "—", detail: "no parents to map" };
  const label = `${(d.map_active + d.map_excluded).toLocaleString()}/${d.map_eligible.toLocaleString()}`;
  const detail = `mapped ${d.map_active.toLocaleString()} · excluded ${d.map_excluded.toLocaleString()} · ` +
                 `unresolved ${d.map_unresolved.toLocaleString()} of ${d.map_eligible.toLocaleString()} eligible parents`;
  return { state: d.map_unresolved > 0 ? "blocked" : "ready", label, detail };
}

/** The document profile: built, and IN USE — the profile index serves its card, which is what retrieval and routing read
 *  (SERVED-PROFILE-LABEL). Built but not in the index is amber; none is red; without the index's answer the writer of the
 *  latest card shows in grey (in use unknown). */
export function docProfile(d: DocSummary): Verdict {
  const w = servedWriter(d);
  if (!d.profile_present && w === null) return { state: "blocked", label: "NONE", detail: "no document profile built yet" };
  if (d.profile_served === undefined) {
    return { state: "unknown", label: w === "vnext" ? "VNEXT" : "BASIC",
             detail: "built; the profile index was not read, so whether search uses it is unknown" };
  }
  if (w === null) {
    return { state: "degraded", label: "NOT IN INDEX",
             detail: "a profile was built, but the profile index serves no card for this file: retrieval and routing cannot use it" };
  }
  return { state: "ready", label: w === "vnext" ? "VNEXT · IN USE" : "BASIC · IN USE",
           detail: "built and in the profile index: retrieval and routing use it" +
                   (w === "basic" && d.profile_vnext ? " (a vNext card was written; the selection guard kept the richer basic card)" : "") };
}

/** Loading is not failure (FRONTEND-REFRESH-V1 P4): while the data has not arrived and nothing failed, the verdict reads
 *  "Checking", never "UNKNOWN — /control_plane not reachable". */
export const CHECKING: Verdict = { state: "unknown", label: "CHECKING" };

export function settled<T>(a: { data: T | null; error: string | null }, verdict: (d: T | null) => Verdict): Verdict {
  return a.data == null && !a.error ? CHECKING : verdict(a.data);
}
