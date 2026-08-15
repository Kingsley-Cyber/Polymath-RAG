# Next Session

## Start Here

Read:
1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. `RAG_E2E_CHECKLIST.md` (next unchecked gate: I1)

## Last Completed

- **Q1** — heterogeneous production extraction qualification: **PASS**
  (frozen). Corpus `eval/gold/qualification_q1.yaml` (53 items, 11
  classes, sha `2ce1d237…`); frozen report `eval/q1/REPORT_Q1.md`;
  regression locks `tests/contracts/test_q1_qualification_regression.py`.
  Production (lexical) arm: P/R 0.943, 0 wrong-predicate, 0
  wrong-scope; residual failures all catalogued classes. Pipeline E2E
  with real GLiNER: 0 failed attempts, 0 degraded runs, full
  provenance. Q1-discovered defect fixed: census chain reordered
  (canonicalize → project_canonical → verify_projections).
  **Production extraction is qualified. Further extraction changes
  require a demonstrated regression or separately measured
  improvement.** Evidence: work log
  `2026-08-14-q1-qualification.md`, refactor 0006.
- **C2** / **C1** — canonicalization layer + canonical KG (refactors
  0005/0004, ADR 0009).
- **R3b** / **R3a** — grounded answer path (refactors 0003/0002).
- Phase H v1.1 — hybrid REJECT as production default (frozen evidence).

## What Was Validated (at checkpoint)

- 134 unit tests passed / 21 skipped; 18 integration passed / 2 skipped.
- All three guards green (preflight / repo guard / wiki worm).
- Frozen hashes re-verified: relations_v1 `fdfd75b4…`, relations_v1.1
  `3ee7065a…`, resource contract `03a513ec…`, tables `0ac3002a…`,
  compiled lexical `5c58adbd…`, Q1 corpus `2ce1d237…`, Q1 scorer
  `94fdc6a9…`.

## Current Verified Commit

- branch: `main` (tracks `origin/main`:
  `https://github.com/Kingsley-Cyber/Polymath-RAG.git`)
- Sync with `git fetch && git pull --ff-only` before work.

## Priority (critical)

Do NOT begin E1 yet (deferred measured improvement).

MILESTONE A — CORPUS_INGEST_READY (current priority):
1. ~~Stage-2 corpus-level canonicalization/merge (C1)~~ COMPLETE
2. ~~canonical KG + provenance projection (C2)~~ COMPLETE
3. ~~heterogeneous extraction qualification (Q1)~~ COMPLETE (PASS)
4. manifest-driven bulk ingestion (I1) ← NEXT
5. corpus-scale integrity qualification (I2)

CORPUS_INGEST_READY is achieved only when C1+C2+Q1+I1+I2 pass.

MILESTONE B — RAG_V1_E2E (after Milestone A):
R2 (reranker, bypassable) → M1–M5 (MCP) → R4 → O2 → O1 → A1 → V1.
R3a and R3b are already COMPLETE. R2/MCP are NOT prerequisites for
CORPUS_INGEST_READY.

E1 may be pulled back onto the critical path only if an E2E acceptance
test demonstrates that one of those extraction defects blocks the
production lexical path.

## Next Unchecked Critical-Path Gate

**I1** — manifest-driven bulk ingestion. A manifest (file list /
directory walk / list of sources) drives idempotent bulk intake of
many documents through the production pipeline; per-source intake
status, retries, and a final summary are reported; replay of the same
manifest is a no-op. Extraction is qualified — do not tune it. Then
I2 (corpus-scale integrity run) → CORPUS_INGEST_READY.

## Do Not Do

- Do NOT begin E1 (deferred measured improvement).
- No production extraction changes without a measured delta.
- No edits to `eval/gold/relations_v1.yaml` / `relations_v1.1.yaml`.
- No fuzzy SemLink joins; no composed-as-direct attestation.
- Never prune Docker volumes (`docker volume prune`, `docker system
  prune --volumes`, or any `docker volume rm`) without explicit
  approval.
- The live v3.3 stack (ports 6333/7474/7687/8000/3000/4000/8765/8080/
  27017/6379) must never be touched.

## Verification Before Work

```bash
git fetch && git status --short && git rev-parse HEAD
make guards
.venv/bin/python -m pytest tests -q
shasum -a 256 eval/gold/relations_v1.1.yaml   # expect 3ee7065a…
```

## Notes Requiring Attention

* Qdrant for this repo is on 6334; the live v3.3 stack on 6333/7474 is
  off-limits.
* v4 store data lives in bind mounts under `stores/` (not Docker
  volumes); `polymath-v4-redis-1` is compose-defined but never started
  (Redis is notification-only; Postgres outbox is authority).
* OOM evidence (5 dead v3.3 workers): `~/repo-backups/oom-evidence-2026-08-14/`.
