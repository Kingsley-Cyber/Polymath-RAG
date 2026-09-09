export type Mode = "VECTOR" | "HYBRID" | "GRAPH" | "WILDCARD";

export interface Corpus {
  corpus_id: string;
  /** Display name; server falls back to corpus_id when unset. */
  name: string;
  purpose: string;
  query_enabled: boolean;
  documents: number;
  query_ready: boolean;
}

export interface Synthesizer {
  id: string;
  label: string;
  description: string;
  default?: boolean;
  /** MODEL-PICKER-V1: grouping fields from the catalog (provider row id, display name, bare model name). */
  provider?: string;
  provider_label?: string;
  model?: string;
  kind?: string;
  available?: boolean;
}

export interface Phase {
  stage: string;
  label: string;
  t: number;
  [k: string]: unknown;
}

export interface ChunkRef {
  locator: string;
  /** CARRY-V2: this item was admitted from an earlier turn, not retrieved now. */
  carried?: boolean;
  doc_id?: string;
  kind?: string;
  preview?: string;
  // UI-V3: human identity (empty on pre-presentation payloads)
  source_name?: string;
  title?: string;
  heading_path?: string;
  human_locator?: string;
}

export interface Degradation {
  component: string;
  effect: string;
  reason: string;
  /** GENERATION-BOUND-V1: how the component degraded when it did not go away ("cut", "bound refused"); absent = unavailable. */
  state?: string;
}

export interface WildcardBridge {
  /** B12: false = shipped without the two-hop judge (finish budget missed); the label says so. */
  verified?: boolean;
  parent_id: string;
  doc_id: string;
  source_name: string;
  principle: string;
  why_it_may_transfer: string;
  source_evidence: { chunk_id?: string; text: string; source_name?: string };
  scores?: Record<string, number | null>;
  channels?: string[];
}

/** [S#] legend entry (CITATION-TAGS-V1 / CARRY-V2): tag → real locator. */
export interface LegendEntry {
  tag: string;
  locator: string;
  chunk_id?: string | null;
  doc_id?: string | null;
  /** CARRY-V2: evidence admitted from an earlier turn of this chat. */
  carried?: boolean;
  carry_score?: number | null;
}

export interface Retrieval {
  mode: string;
  /** Chunk ids behind the [S#] tags the model actually emitted. */
  used_evidence?: string[];
  legend?: LegendEntry[];
  /** CARRY-V2 accounting: in / hydrated / admitted / dropped_* / floor. */
  carry?: Record<string, unknown>;
  /** DIVERGENT-RETRIEVAL-V1: labelled derived insights, never evidence. */
  wildcard?: WildcardBridge[] | null;
  evidence_count: number;
  graph_fact_count?: number;
  chunks: ChunkRef[];
  counts?: Record<string, number>;
  /** Lanes that degraded rather than failing (e.g. parked reranker). */
  degraded?: Degradation[];
  /** LATENT-DIAGNOSTICS-V1: survival attribution for the latent lane. */
  latent?: {
    enabled: boolean;
    parents_nominated?: number;
    parents_survived?: number;
    children_admitted?: number;
    kinds?: Record<string, number>;
    degraded?: string | null;
  } | null;
}

export interface Citation {
  citation_id: number;
  locators: string[];
  source_document_ids: string[];
}

export interface ChatAnswer {
  kind: "chat" | "ask" | "llm";
  result: any;
  retrieval: Retrieval;
  latency_ms: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  phases?: Phase[];
  /** Streamed model thinking (reasoning card), never part of the answer. */
  reasoning?: string;
  answer?: ChatAnswer;
  error?: { error_code?: string; message?: string };
  pending?: boolean;
  mode?: Mode;
}

export interface Chat {
  id: string;
  title: string;
  created: number;
  corpus: string;
  mode: Mode;
  synthesizer: string;
  /** v3.3 reasoning-layer mode key; "none" answers directly. */
  reasoning?: string;
  /** LATENT rescue flag (HYBRID/GRAPH); undefined inherits the server default. */
  latent?: boolean;
  messages: Message[];
}

export interface ReasoningModeInfo {
  id: string;
  label: string;
  description: string;
}

export interface DocumentRow {
  doc_id: string;
  source_name: string;
  media_type: string;
  bytes: number;
  created_at: string;
  chunks: number;
  // enrichment indicator (UI-V3): sections vs latent-enriched sections
  parents?: number;
  enriched?: number;
  enrich_failed?: number;
  // RAG-PIPELINE-FINISH Phase 18: active parent maps (vNext pMAP coverage) for the row badge.
  map_active?: number;
}

// CANONICAL-DOCUMENT-STATUS-V1 (GET /documents/{doc_id}/status) — the fields the Files
// status panel renders. The endpoint returns more; this types the rendered subset.
export interface DocumentStatus {
  found: boolean;
  vnext_ready?: boolean;
  identity?: { doc_id: string; corpus_id: string; source_name: string; run_id?: string | null };
  chunks?: { children_total: number; parents_total: number };
  profile?: { present: boolean; valid: boolean; vnext: boolean; quality?: number | null;
              prompt_version?: string | null; compiler_version?: string | null };
  pmap?: { schema?: string | null; eligible?: number; mapped_active?: number; excluded?: number;
           unresolved?: number; batches_total?: number; batches_done?: number; batches_partial?: number };
  state?: { run_status?: string | null; vnext_ready?: boolean; corpus_vnext_verdict?: string };
  stages?: { stage: string; status: string; attempt: number; last_error?: string | null }[];
  blockers?: string[];
}

export interface RunRow {
  run_id: string;
  status: string;
  created_at: string;
  /** Latest stage failure note (e.g. a duplicate-document refusal). */
  error?: string | null;
}
