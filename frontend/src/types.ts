export type Mode = "VECTOR" | "HYBRID" | "GRAPH" | "ASK";

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
}

export interface Phase {
  stage: string;
  label: string;
  t: number;
  [k: string]: unknown;
}

export interface ChunkRef {
  locator: string;
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
}

export interface Retrieval {
  mode: string;
  evidence_count: number;
  graph_fact_count?: number;
  chunks: ChunkRef[];
  counts?: Record<string, number>;
  /** Lanes that degraded rather than failing (e.g. parked reranker). */
  degraded?: Degradation[];
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
}

export interface RunRow {
  run_id: string;
  status: string;
  created_at: string;
  /** Latest stage failure note (e.g. a duplicate-document refusal). */
  error?: string | null;
}
