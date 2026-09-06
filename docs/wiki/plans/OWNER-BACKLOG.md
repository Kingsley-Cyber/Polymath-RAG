---
title: "OWNER BACKLOG — work the owner has parked, in the owner's words, with the state it was left in"
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: living
---

# OWNER BACKLOG

Items the owner has explicitly deferred ("we won't do it now"). Each entry names the decision needed, the state on the day it was parked, and where the evidence lives. Nothing here is started without the owner saying so.

| # | parked | item | state when parked | pointers |
|---|---|---|---|---|
| B1 | 2026-09-06 | **Near-duplicate guard at intake (DUPLICATE-DOCUMENT-GUARD layer 3).** Shingle + MinHash containment of the normalised text against the corpus's existing documents; ≥ ~0.9 containment refused as "near-duplicate of X" with the pair in a receipt; explicit override to keep both; the Files tab reports a refused duplicate as "already in corpus (same bytes / same text / near-duplicate of X)" instead of "failed: 409"; a folder drop ends with a summary (N new, N exact, N near). Touches ingestion (intake worker) — owner go required. | Layers 1 (byte hash at upload) and 2 (normalised-text hash in the intake worker) exist and refuse loudly; the cinema corpus holds a Sound Design twin 8 bytes apart that both layers miss. | `orchestrator/orchestrator/api/ui.py` (upload guard), `workers/workers/intake_worker.py` (layer 2), `frontend/src/components/FilesView.tsx` (state wording) |
| B2 | 2026-09-06 | **Delete the Sound Design duplicate in `cinema`.** Two files, 1,067,157 vs 1,067,149 bytes, 255 sections each, different hashes ("… Cinema.md" and "… Cinema (1).md"); one copy to go via the documents API, no re-ingest. Deferred so the owner's mode comparisons run on an unchanged corpus. | Both copies live and competing for evidence slots. | documents API; corpus `cinema` |
| B3 | 2026-09-06 | **Corpus shaping for `cinema`** (owner is weighing it): the owner's own `handbook.html` (802 sections) into its own corpus, and/or a document-kind tag (book / paper / manual / handbook) with a scope filter in the UI. | Control turn: 6 of 68 documents reached the final set; the handbook took 8 rows / 4 citations against the two target books' 16 / 10. | receipts of 2026-09-06 19:04 (VECTOR control); per-document competition table offered after the owner's HYBRID / GRAPH / WILDCARD runs |
| B4 | 2026-09-06 | **Rotate the OpenCode and Alibaba Model Studio keys** (both were pasted in chat). | Keys live in `.env` only; never in the repo. | `.env` (owner-held) |
| B5 | 2026-09-06 | **bge-reranker-v2-m3 comparison** against Qwen3-Reranker-0.6B (owner: "hold off on model change"). | Judge fast path shipped (11.100); no comparison run. | `scripts/rerank_judge_bench.py` |
| B6 | 2026-09-06 | **v33 database salvage assessment** (summaries / entity extractions mapped to documents). | Five `polymath_v33_*` Docker volumes kept; software removed. | `~/polymath-v33-archive`, Docker volumes |
| B7 | 2026-09-06 | **Receipt whitelist: add `generation`** (finish_reason / max_tokens) to the stored query receipt — one line in `shared/polymath_shared/query_receipts.py`; needs a fence round + respawn, so parked until the owner pauses testing. | The answer event and the /chat JSON carry it; the DB receipt drops it. | 11.106 work-log, Open contract gaps |
