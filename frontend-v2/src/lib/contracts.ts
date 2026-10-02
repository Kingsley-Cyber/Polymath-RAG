/**
 * Typed mirrors of the BACKEND contracts V2 consumes.
 *
 * FRONTEND-V2-PLAN §0.2: the backend is the authority. Every type here describes a
 * response shape the backend already owns (verified live 2026-09-10, F0 / register
 * 11.195). Nothing here computes policy — if a field is absent, the UI shows it as
 * unknown, it never derives a substitute.
 */

/* ── readiness: three DISTINCT concepts (plan §7) ─────────────────────────── */

/** `/semantic_readiness?corpus_id=` — contract `semantic-readiness-v1`. */
export interface SemanticReadiness {
  contract: string;
  corpus_id: string;
  /** SEMANTIC_COMPLETE | SEMANTIC_INCOMPLETE */
  verdict: string;
  counts: Record<string, number>;
  vnext: {
    /** VNEXT_COMPLETE | VNEXT_INCOMPLETE */
    verdict: string;
    pending: string[];
    parents: { eligible: number; mapped: number; excluded: number; unresolved: number };
    vnext_profiles?: number;
    /** documents with ANY profile, base or vNext (LIBRARY-READY-LABEL); absent on an older backend */
    profiled?: number | null;
    /** SERVED-PROFILE-LABEL: files SEARCH serves with a vNext card (the verdict above counts WRITTEN cards); absent when
     *  the profile index could not be read */
    vnext_served?: number | null;
    documents?: number;
  };
  warnings?: unknown[];
  extraction?: unknown;
}

/** One row of `/documents/summary?corpus_id=` (per-document vNext truth). */
export interface DocSummary {
  children: number;
  parents: number;
  map_eligible: number;
  map_active: number;
  map_excluded: number;
  map_unresolved: number;
  profile_present: boolean;
  /** the LATEST card was written by the vNext writer (not necessarily the card search uses) */
  profile_vnext: boolean;
  /** from the file's extraction report; null when no extraction finished */
  graph_entities: number | null;
  graph_relations: number | null;
  /** mapped + the latest card is vNext (written state; scripts read it) */
  vnext_ready: boolean;
  /** SERVED-PROFILE-LABEL: the writer of the card SEARCH serves ("vnext" | "basic"; null = none served). Absent when the
   *  profile index could not be read — the labels then keep the written state. */
  profile_served?: "vnext" | "basic" | null;
  /** FILES-STATUS-TRUTH-V1: the file's own run status (`query_ready` = every required step done); absent on an older backend */
  run_status?: string | null;
  /** stages still queued or running for the file (ready / leased / pending) */
  work_open?: string[];
  /** stages that failed with their retries spent, with the failure note */
  work_failed?: { stage: string; note: string | null }[];
}

/** `GET /documents?corpus_id=` — the IDENTITY authority for the Files screen.
 *  `source_name` is the human filename that survives ingestion; the operational
 *  detail (pMAP / profile / graph / vNext) is merged in from DocSummary by doc_id.
 *  Verified against the live route (orchestrator/api/ui.py::documents) 2026-09-12. */
export interface DocumentRow {
  doc_id: string;
  source_name: string;
  media_type: string;
  bytes: number;
  created_at: string;
  chunks: number;
  parents: number;
  enriched: number;
  enrich_failed: number;
  map_active: number;
}

export interface DocumentRun {
  run_id: string;
  status: string;
  created_at: string;
  error: string | null;
}

export interface DocumentsResponse {
  corpus_id: string;
  documents: DocumentRow[];
  runs: DocumentRun[];
}

/** `POST /upload` reply (the fields the UI surfaces; the run submission carries more). */
export interface UploadResult {
  corpus_id: string;
  source_name: string;
  bytes: number;
  sha256: string;
  near_duplicate_override: boolean;
}

/** `GET /llm/providers` — a configured LiteLLM provider. The backend NEVER returns a raw
 *  key: `api_key` is either the last 4 chars, or the env var NAME (`env:NAME`), and
 *  `api_key_set` says whether a usable key resolves. Verified against
 *  orchestrator/api/ui.py::llm_providers 2026-09-12. */
export interface LlmProvider {
  provider_id: string;
  provider: string;
  api_key: string;      // masked (…last4) or "env:NAME" — never the real key
  api_key_set: boolean;
  api_base: string;
  models: string[];
  enabled: boolean;
  ready: boolean;
}

/** `POST /llm/providers` body (ProviderUpsert). An empty `api_key` on an existing
 *  provider keeps the stored key (masked round-trip). */
export interface ProviderUpsertBody {
  provider: string;
  api_key?: string;
  api_base?: string;
  models: string[];
  enabled: boolean;
}

/** `POST /llm/test` — one-shot connectivity/credential check for a model string. */
export interface LlmTestResult {
  ok: boolean;
  model: string;
  reply?: string;
  error?: string;
}

/** `/control_plane?corpus_id=` — CONTROL-PLANE-STATUS-V1.
 *  Verified against a live response 2026-09-10: `pools` is a MAP keyed by function
 *  name, and the queue counters sit at the TOP level of each pool (not nested).
 *  `control_ready` (GAP-1) and `summary.processing_active`/`processing_stalled`
 *  (GAP-4) added 2026-09-12 — composed server-side; the UI renders them, it does
 *  not re-derive them from `/ready` + `/health/pipeline` itself. */
export interface ControlPlane {
  contract: string;
  corpus_id: string;
  control_ready: { state: "ready" | "blocked" | "degraded"; label: string; detail?: string;
                    pipeline?: Record<string, unknown> };
  /** semantic_ready = files with the vNext profile; basic_profile = searchable on the base profile; blocked = files
   *  retrieval would miss part of (unresolved parents or no profile) — LIBRARY-READY-LABEL */
  summary: { documents: number; semantic_ready: number; vnext_served?: number | null; basic_profile?: number; processing: number;
             processing_active: number; processing_stalled: number; blocked: number };
  pools: Record<string, ControlPlanePool>;
}

export interface ControlPlanePool {
  lanes?: { active: number; total: number; credential_absent: number; disabled: number; active_lanes: string[] };
  queued?: number;
  processing?: number;
  retry?: number;
  failed?: number;
  /** `limiter_refused` is LOCAL (0 HTTP); `http_429` cost a real provider request. */
  provider?: Record<string, number | null>;
}

/** `/control_plane/pool/{function}` — model → account lanes. ENV NAMES only, never secrets. */
export interface PoolLanes {
  function: string;
  models: { model: string; lanes: PoolLane[] }[];
}

export interface PoolLane {
  lane: string;
  account_env: string;
  configured: boolean;
  reachability: string;
  role: string;
  family: string | null;
  capacity: { rpm: number | null; tpm: number | null; rpd: number | null; concurrency: number | null; map_batch_cap: number | null };
  live: Record<string, unknown>;
}

/** `/corpora`. `query_ready` is carried ONLY so the UI can refuse to use it (plan §7). */
export interface Corpus {
  corpus_id: string;
  name?: string;
  purpose?: string;
  documents: number;
  query_ready: boolean;
  query_enabled: boolean;
}

/* ── chat ─────────────────────────────────────────────────────────────────── */

/** The PUBLIC retrieval modes. VECTOR is a backend primitive, not a public mode (plan §2).
 *  GNN (GNN-RETRIEVAL-V1) is the experimental fifth mode: graph-neural PARENT routing over the
 *  existing corpus — the GNN routes, original children prove, the same reranker judges. It is
 *  sent as `mode: "GNN"` through the very same /chat path as every other mode. */
export const PUBLIC_MODES = ["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const;
export type PublicMode = (typeof PUBLIC_MODES)[number];

/** `/synthesizers` catalog row. `provider`/`provider_label`/`model` are the
 *  grouping fields MODEL-PICKER-V2 renders — they come from the catalog itself,
 *  never from parsing ids (verified live: the endpoint returns all of them). */
export interface Synthesizer {
  id?: string; name?: string; label?: string; offered?: boolean;
  description?: string; kind?: string; available?: boolean; default?: boolean;
  provider?: string; provider_label?: string; model?: string;
}
export interface ReasoningMode { id: string; label: string; description: string }

/**
 * `answer.retrieval` on the `/chat/stream` answer frame — the Query Inspector's
 * whole source of truth (plan §3).
 */
export interface RetrievalReceipt {
  engine: string;
  mode: string;
  lane_sizes?: Record<string, number>;
  /** chunk_id -> the lanes that delivered it (union + survival evidence) */
  arrivals?: Record<string, string[]>;
  funnel?: unknown;
  composition?: unknown;
  aspects?: unknown;
  weak_aspects?: unknown;
  legend?: unknown;
  chunks?: unknown[];
  used_evidence?: unknown[];
  final_detail?: unknown;
  evidence_count?: number;
  graph_fact_count?: number;
  graph_seeds?: unknown;
  graph_bounds?: unknown;
  graph_degraded?: unknown;
  wildcard?: unknown;
  wildcard_diagnostics?: unknown;
  latent?: unknown;
  chat_plan?: { intent?: string; [k: string]: unknown };
  degraded?: string[];
  /** v2: the per-stage retrieval timings (embed, lanes, rerank, compose, total — ms; an absent stage is null);
   *  v1: one number. Render `total`, never the map itself (it rendered as "NaNs"). */
  latency_ms?: number | Record<string, number | null>;
}

export interface AnswerFrame {
  kind: string;
  latency_ms?: number;
  result?: unknown;
  retrieval?: RetrievalReceipt;
}

/* ── /retrieve ────────────────────────────────────────────────────────────── */

export interface RetrieveResponse {
  evidence: unknown[];
  meta: { mode: string; plan_version: string; engine?: string; corpus_id: string; evidence_count: number; degraded: string[]; [k: string]: unknown };
  query: unknown;
  selected_documents: unknown[];
  selected_sections: unknown[];
  trace: Record<string, unknown>;
}

/* ── graph (GRAPH-BROWSE-V1) ──────────────────────────────────────────────── */

export interface GraphEntity {
  normalized_surface: string; surface: string; core_type: string | null;
  mentions: number; documents: number; entity_id: string;
}
export interface GraphEntities {
  contract: string; corpus_id: string; query: string; entities: GraphEntity[];
}
export interface GraphSource {
  doc_id: string; chunk_id: string; source_name: string | null; text: string;
}
export interface GraphRelationship {
  fact_id: string; predicate: string;
  subject_id: string; subject: string; object_id: string; object: string;
  direction: "in" | "out";
  /** Source attestation — the reason this relationship may be shown at all. */
  sources: GraphSource[]; source_count: number;
}
export interface GraphRelationships {
  contract: string; corpus_id: string; entity_id: string;
  relationships: GraphRelationship[];
  /** Relationships withheld because nothing in THIS corpus attests them. */
  dropped_unattested: number;
}

/* ── compare + review (COMPARE-REVIEW-V1) ────────────────────────────────── */

export interface CompareArm {
  mode: string; ok: boolean; latency_ms: number; error?: string;
  retrieval?: {
    engine?: string; plan_version?: string; degraded?: string[] | null;
    evidence_count?: number; selected_documents?: number; selected_sections?: number;
    lane_sizes?: Record<string, number> | null;
    /** lane -> the chunk ids that lane delivered (not counts; `lane_sizes` has the counts) */
    funnel_lanes?: Record<string, string[]> | null;
    union_size?: number;
    /** per-stage timings of this arm (embed, lanes, rerank …); the arm-level `latency_ms` is the total */
    latency_ms?: Record<string, unknown> | null;
    documents?: string[];
    rows?: { chunk_id?: string; doc_id?: string; source_name?: string; score?: number; arrival?: string }[];
  };
}
export interface CompareResponse {
  contract: string; corpus_id: string; question: string; arms: CompareArm[];
}

export interface ReviewScores {
  grounding?: number; correctness?: number; completeness?: number;
  citation_support?: number; retrieval_adequacy?: number;
  unsupported_claims?: string[]; missing_evidence?: string[]; verdict?: string;
}
export interface ReviewResponse {
  contract: string; reviewer: string;
  review: ReviewScores | null; parse_error: string | null; raw: string | null;
}

/* ── TRAIL-INTERFACE-V1 (GET /adapter/runs, GET /adapter/{id}/view) ─────────────────────────────────────────────────── */
export interface RunSummary {
  run_id: string; adapter_id: string; adapter_version: string | null; title: string; status: string;
  current_step_id: string | null; steps_accepted: number; harness_actions: number;
  started_at: string | null; updated_at: string | null; finished_at: string | null;
  agent_identity: string | null; owner: string | null; outcome: string;
}
export interface RunProgressRow { step_id: string; type: string | null; title: string; state: string; visits: number }
export interface GateResult { gate_id?: string; name?: string | null; minimum?: number; observed?: number; passed?: boolean }
export interface OpenGap { gap_id?: string; question?: string; evidence_role?: string; hypothesis_id?: string }
export interface Qualification {
  record_id?: string; stage?: string; state?: string; hypothesis_ids?: string[]; gate_results?: GateResult[]; open_gaps?: OpenGap[];
}
export interface ScoreRefusal { record_id?: string; reason_code?: string; hypothesis_id?: string; detail?: string }
export interface Admission {
  admission_id?: string; admitted?: { evidence_role?: string; independence_group?: string; source_class?: string }[];
  rejected?: { reason_code?: string; detail?: string; observation_id?: string }[];
}
export interface LivedCluster {
  id?: string; community?: string; friction_family?: string; authority?: string; record_count?: number; thread_count?: number;
  threshold?: { min_records?: number; min_threads?: number; min_independent_voices?: number };
}
export interface ProductConcept { id?: string; name?: string; buyer?: string; form_factor?: string; differentiator?: string }
export interface ConceptReality { concept_id?: string; concept?: string; status?: string; existing_products?: number }
export interface HypothesisView { hypothesis?: { hypothesis_id?: string; statement?: string; status?: string } }
/** T5: TrailSignal's registry as the run met it — the owner's view only (a friend's view has no `registry` key). */
export interface RegistryPrior { registry_record_id?: string; prior_role?: string; label?: string | null; hypothesis_ids?: string[] }
export interface RegistryTerritory { territory_id?: string; territory?: string; territory_name?: string | null; hypothesis_ids?: string[] }
export interface RunRegistry {
  snapshot: { snapshot_id?: string; content_hash?: string } | null; snapshot_ids: string[];
  priors: RegistryPrior[]; territories: RegistryTerritory[];
}
export interface RunView {
  run: {
    run_id: string; adapter_id: string; adapter_version: string | null; title: string; status: string; terminal: boolean;
    current_step_id: string | null; started_at: string | null; updated_at: string | null; finished_at: string | null;
    agent_identity: string | null; gap: { code?: string; message?: string } | null; steps_accepted: number; harness_actions: number;
  };
  progress: RunProgressRow[];
  sections: {
    qualifications?: Qualification[]; trail_scores?: { record_id?: string; hypothesis_id?: string }[]; score_refusals?: ScoreRefusal[];
    evidence_admissions?: Admission[]; lived_clusters?: LivedCluster[]; product_concepts?: ProductConcept[];
    concept_reality?: ConceptReality[]; unresolved_research_gaps?: OpenGap[]; hypothesis_semantics?: HypothesisView[];
  };
  other_output_keys: string[]; contradictions: unknown[]; unknowns: unknown[]; stored_result_shadowed: boolean;
  report?: { available: boolean };                 // T5: GET /adapter/{id}/report exists for this run's adapter
  registry?: RunRegistry | null;
}

/* ── DEEP-RESEARCH-MODE-V1 §11.3 (DR7): the plan card, coverage frames, the report model, the sentence audit ─────────── */
/** `POST /research/deep/plan` — the level-1 planner's queries with the controller's quota (one model call, no run). */
export interface DeepResearchPlan {
  intent?: string; evaluative?: boolean; preset?: string;
  goals: DeepPlanGoal[];
  estimate?: { searches?: number; llm_calls?: number; seconds?: number };
}
export interface DeepPlanGoal { id: string; goal: string; query: string; move: string }
/** `event: coverage` after each level: each goal's findings and books so far (`documents` = a count, or the doc ids). */
export interface DeepCoverage { goals: DeepCoverageGoal[]; documents?: number; passages?: number }
export interface DeepCoverageGoal { id: string; learnings?: number; documents?: number | string[] }
/** `result.meta.deep_research.report_model` — the deterministic evidence model (§11.4) the Evidence / Sources / Method tabs draw. */
export interface DeepReportModel {
  goals?: DeepReportGoal[]; counter?: DeepCounterFinding[];
  open_questions?: (string | { question?: string; text?: string })[];
  sources?: DeepReportSource[]; method?: Record<string, unknown>;
}
export interface DeepReportGoal { id: string; goal: string; findings?: DeepFinding[]; documents?: number | string[] }
/** `confidence`: strong | single_source | contested (§11.4). */
export interface DeepFinding { text: string; cids?: string[]; confidence?: string; move?: string }
export interface DeepCounterFinding { text: string; cids?: string[]; goal_id?: string }
export interface DeepReportSource { doc_id?: string; title?: string; cids?: string[]; findings?: number }
/** `result.meta.deep_research.audit` — every prose sentence (headings skipped) checked for a valid [cN]; `uncited` = indices. */
export interface DeepAudit { sentences?: number; cited?: number; uncited?: number[]; invalid_cids?: string[] }

/* ── chat answers of a synthesis task (FACET-RETRIEVAL-V1 F5 / F6) ───────────────── */

/** `result.meta.synthesis` on a chat answer of a GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turn: the graded evidence per
 *  facet of the request (`confidence` as §11.4: strong = two or more books, single_source, contested), the sources by document
 *  in the deep report's shape (the cids are the answer's own [S#] tags, resolved through the chat receipt) and the document
 *  share the composer measured. Absent on a QA / lookup turn and on every turn saved before F5. */
export interface ChatSynthesisFacet {
  id: string; name?: string; covered?: boolean | null; docs?: string[]; tags?: string[]; sentences?: number; confidence?: string | null;
}
export interface ChatSynthesis {
  contract?: string; task_type?: string; facets?: ChatSynthesisFacet[]; sources?: DeepReportSource[];
  documents?: { in_evidence?: number; cited?: number; multi_doc_sentences?: number };
  share?: { top_doc?: string | null; top_title?: string | null; top_share?: number | null; doc_counts?: Record<string, number> } | null;
  sentences?: number; uncited?: number;
}
/** `result.meta.gap_check` — the answer's "not covered" claims the check searched again: what each found, whether it was
 *  refuted (the "More on this" addition carries the citations) and how its wording was edited. */
export interface ChatGapClaim {
  text?: string; source?: string; query?: string; found?: number; cited_added?: string[]; refuted?: boolean; edited?: string | null;
}
export interface ChatGapCheck { contract?: string; claims?: ChatGapClaim[]; searches?: unknown[]; section_added?: boolean; error?: string }
