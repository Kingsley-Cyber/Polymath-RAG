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
  profile_vnext: boolean;
  graph_entities: number;
  graph_relations: number;
  vnext_ready: boolean;
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
  summary: { documents: number; semantic_ready: number; processing: number;
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

/** The four PUBLIC retrieval modes. VECTOR is a backend primitive, not a public mode (plan §2). */
export const PUBLIC_MODES = ["HYBRID", "GRAPH", "WILDCARD"] as const;
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
  latency_ms?: number;
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
    lane_sizes?: Record<string, number> | null; funnel_lanes?: Record<string, number> | null;
    union_size?: number; latency_ms?: number;
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
