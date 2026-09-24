---
change_id: GAP-REGISTER-AND-ROADMAP-V1
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only. A consolidated register of CONFIRMED gaps (LLM provider backend, document retrieval, code RAG) and the plan of record that closes them in strategic slices (Tracks L, D, C, G), including the account-first provider design and the joint code / document graph walk."
last_reviewed: 2026-09-24
---

# Gap register + roadmap (LLM backend, document defects, code RAG, joint graph walk)

## Contract
- The owner, 2026-09-24: "it shouldnt be 18 or 11 api keys, it should be like 4-6 api keys with multiple models
  configured … cloudflare should be wired and working … we need to fix all of this except the ones you said is good like
  cosine floor. you can download the parsers, you can get a luau roblox code file from github … just use 1 file.
  implement this is strategic slices and a plan way ahead … we need to find a way to walk code graph with document graph
  if retrieved." Plus two pasted external reviews (Astra) and: "i want your opinoions but ensure to create a proper md file
  to consolidate determisnitic or confirmed issues and gaps to fix."

## Changes
- `docs/wiki/plans/GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md` (living; 47 confirmed rows: L-01..L-18, D-01..D-02,
  C-01..C-27; confirmed-good list; not-confirmed list).
- `docs/wiki/plans/LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` (plan of record: account registry + ownership + limiter
  semantics; the four-link joint graph walk; 21 slices in order with proofs and gates; Astra reconciliation).
- START-HERE §1 / §4 and CONTINUITY point at both.

## Proof
- Every register row re-checked by hand before admission: the audit's claims (register 11.459) plus Astra's MCP
  truncation (`mcp_server.py:302-303, 323-329`), upload whitelist (`:60, 192, 217`), HTTP `/retrieve` FAST dispatch
  (`api/retrieve.py:199-203`), non-blocking enrichment (`control/tickets.py`), lane E child deepening
  (`candidate_engine.py:929-945`); plus the per-process limiter registry (`limiter.py:1000`), the containment threshold
  (`dedup.py:64`), the BM25 tokenizer (`sparse_bm25.py:24-33`), the numeric-noise rule (`candidate_engine.py:1557`),
  lane A's 6 documents (`:142`), the fact id format (`fact_` + 64 hex, E), all 6 Cloudflare tokens set with 1 account id.

## Rejected claims
- "18 or 11 API keys": there are 6 Groq keys; 18 counted key × model combinations.
- A global cosine floor, a new retrieval mode, a new RAG service or an LLM retrieval judge: not needed (both reviews agree).

## Open contract gaps
- All 47 rows OPEN until their slices close them. Next slice: C0b (downloads approved).
