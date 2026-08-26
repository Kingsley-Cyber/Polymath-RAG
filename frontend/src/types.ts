export type Mode = "VECTOR" | "HYBRID" | "GRAPH" | "ASK";

export interface Corpus {
  corpus_id: string;
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
}

export interface Retrieval {
  mode: string;
  evidence_count: number;
  graph_fact_count?: number;
  chunks: ChunkRef[];
  counts?: Record<string, number>;
}

export interface Citation {
  citation_id: number;
  locators: string[];
  source_document_ids: string[];
}

export interface ChatAnswer {
  kind: "chat" | "ask";
  result: any;
  retrieval: Retrieval;
  latency_ms: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  phases?: Phase[];
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
  messages: Message[];
}

export interface DocumentRow {
  doc_id: string;
  source_name: string;
  media_type: string;
  bytes: number;
  created_at: string;
  chunks: number;
}

export interface RunRow {
  run_id: string;
  status: string;
  created_at: string;
}
