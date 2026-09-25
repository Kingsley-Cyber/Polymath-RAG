---
title: "Reconciliation: the external end-to-end audit of the code RAG plan (2026-09-24)"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "ADMITTED (register 11.471). The audit is stored verbatim at docs/code-knowledge-v1/ADDENDUM_2026-09-24_EXTERNAL_E2E_AUDIT.md; the amendments below are folded into CODE-RAG-IMPLEMENTATION-V1.md. Nothing is built by this document."
owner: "@king"
scope: "Per-item verdict on the audit's corrections to the code RAG plan, with the evidence re-checked here, plus the owner's 2026-09-24 rule on pMAP for code."
---

# Reconciliation: external end-to-end audit of the code RAG plan

**Verdict on the audit:** sound and useful.
- Its FAIL is about the code path, which is not built yet (expected: C1 has not started). It explicitly says the book
  RAG is not broken.
- It keeps the roadmap order, rejects new services and rejects replacing pMAP. It found real flaws in the implementation
  file; the two biggest were re-checked in code here.
- It was written at `c28c9b8`, before L1–L3, so its provider prerequisites (L-track) are now largely done (L1–L4a,
  11.465–11.470).

## The owner's rule (2026-09-24, chat)

> "i understand pmap does a determinsitic parse and curations of docuemnts headings and subheading but for codes i dont
> want thats."

→ **R11:** code never goes through the document heading skeleton (`build_parent_skeletons`, `parent_skeleton.py`) or its
curation. The language parser defines code units (module, class, function; screen, control, formula), and a unit's
description is written from its complete source. This matches C-12, the plan's C6/C7 modify point ("a code document's
batches come from `enrich_context`, not `build_parent_skeletons`") and the audit's "full-source pMAP batches".

What stays (the owner may overrule): one plain-English description per code unit. It is what lets a question in normal
words ("where do we retry failed uploads?") find the right function (R1).

## Item-by-item

| # | Audit finding | Evidence re-checked here | Verdict | Lands in |
|---|---|---|---|---|
| A1 | The C1 passthrough sits after byte normalization | READ: `intake_worker.py:168-172` computes `doc_id` and `content_hash` from `normalize_document_bytes(raw)` (BOM strip, CRLF → LF, NFC: `identity.py:95`) BEFORE materialization (`:186`). The plan's passthrough is in `materializer.py`, too late. | ACCEPT — new gap **C-28** | C1: branch before normalization; keep the original bytes; a code identity from project + repository-relative path + raw hash (snapshot kept separately) |
| A2 | Reference books cannot be copied into a code project's corpus | READ: `intake_worker.py:221-231` refuses identical content in a second corpus; already gap **C-26** | CONFIRMED — the owner's decision is narrowed (below) | C1 / K1 |
| A3 | Nested symbols vs non-overlapping children have no ownership rule | design | ACCEPT | C2 / C3: the symbol tree nests with exact spans; physical children partition the source; a method is read by its own span, never by joining every child of its class |
| A4 | No durable per-unit description record; "unit → file" vs "pMAP before profile" is circular | design (the plan's C6/C7 text says both) | ACCEPT | C6 / C7: per-unit records keyed by input hash, checkpointed on provider refusal; the file rollup waits for its unit records; pMAP runs from the same full source independently; no sampling fallback |
| A5 | Freshness hashes only callee signatures | design (R7 wording) | ACCEPT — R7 amended | C6 / C7: hash the exact context supplied (callee bodies or behaviour records used, parser / binder / prompt versions) |
| A6 | The K1 rollback turns scope filtering off | design | ACCEPT | K1: a rollback never widens a reference-only request; missing role metadata is not permission (fail closed) |
| A7 | `code/store.py` and the Luau subprocess placed in `shared/` | design (ownership rule: shared policy has no I/O) | ACCEPT | §3 module layout: database, filesystem and subprocess work lives in workers / orchestrator; shared stays pure |
| A8 | DAX and Power Query M contracts | — | CANDIDATE (unchanged) | stays in §6 item 4 until the owner promotes them |
| A9 | Every route (FAST's real lanes, HYBRID, GRAPH, WILDCARD, HTTP `/retrieve`, MCP) must join one nomination → hydration contract; unit descriptions also go to the base section routing so FAST can find them | matches C-15 … C-18 | ACCEPT | C9 / C10 |
| A10 | Acceptance verifiers V-DOC … V-PROVIDER | — | ACCEPT as exit proofs | each slice's Acceptance |
| A11 | Open-source shortlist (CodeGraphContext, code-graph-rag, Graphify, Potpie, codebase-memory-mcp, GraphRAG; GitNexus excluded, noncommercial) | matches the sources list (11.454) | STUDY ONLY | no product is installed; license notices kept when a pattern is copied |

## The owner decision this narrows (C-26)

The 2026-09-24 decision "project = corpus; its reference documents join the same corpus" works as long as each reference
book belongs to ONE project: upload it into that project's corpus. It fails only for a book wanted in TWO corpora.
Intake refuses the second copy (content-addressed identity, one owning corpus).

For that case the audit recommends querying a corpus SET (the code corpus plus the book's corpus) instead of copying.
Today only ASK takes several corpora; FAST / HYBRID / GRAPH / WILDCARD / GNN take one.

**Question for the owner:** will the same book be used by more than one project?
- No → nothing changes.
- Yes → multi-corpus queries join K1's scope work.
