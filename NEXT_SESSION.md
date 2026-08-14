# Next Session

## Start Here

Read:
1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. `RAG_E2E_CHECKLIST.md` (next unchecked gate: R3a)

## Last Completed

- Phase H v1.1 — boundary corpus (33 items, frozen `3ee7065a…`) +
  rerun: hybrid **REJECT** as production default (Δcorrect +1,
  Δincorrect +4, Δmissed −4). Evidence: `eval/phase_h/REPORT_v1.1.md`.
- Bootstrap continuity system — `AGENTS.md` §0 (Mandatory Bootstrap),
  `CURRENT_STATE.md`, `NEXT_SESSION.md`, `RAG_E2E_CHECKLIST.md`.
- Docker hygiene (approved only): 20.76GB build cache pruned, one
  dangling image removed, five OOM-killed v3.3 worker containers
  removed after `docker inspect`/log evidence was preserved to
  `~/repo-backups/oom-evidence-2026-08-14/`.

## What Was Validated (at checkpoint)

- 77 unit tests passed / 15 skipped; 12 integration passed / 2 skipped.
- All three guards green (preflight / repo guard / wiki worm).
- Frozen hashes re-verified: relations_v1 `fdfd75b4…`, relations_v1.1
  `3ee7065a…`, resource contract `03a513ec…`, tables `0ac3002a…`,
  compiled lexical `5c58adbd…`.

## Current Verified Commit

- branch: `main` (tracks `origin/main`:
  `https://github.com/Kingsley-Cyber/Polymath-RAG.git`)
- The remote blocker is RESOLVED: origin exists and the checkpoint is
  pushed. Sync with `git fetch && git pull --ff-only` before work.

## Priority Change (critical)

Do NOT begin E1 yet.

The project priority is now to finish a usable Polymath RAG application
end-to-end. E1 improves a hybrid extraction path that has already been
rejected as the production default, so it is not currently an E2E
blocker.

CRITICAL PATH TO RAG v1.0 (in order):
1. grounded EvidenceBundle assembly (R3a)
2. functional answer generation and /chat path (R3b)
3. Stage-2 corpus-level canonicalization/merge (C1)
4. canonical KG + source/provenance linkage (C2)
5. reranking qualification (R2 — bypassable for first /chat E2E)
6. Polymath MCP contract (M1)
7. Polymath MCP server (M2)
8. Claude MCP end-to-end qualification (M3)
9. Hermes Agent MCP end-to-end qualification (M4)
10. MCP read/write/admin permission boundaries (M5)
11. graph/retrieval scale qualification (R4)
12. model digest pinning (O2)
13. clean-clone + backup/recovery drill (O1)
14. fresh-machine + fresh-agent E2E acceptance (A1)
15. RAG v1.0 checkpoint (V1)

DEFERRED MEASURED IMPROVEMENT (NOT critical path):
- E1-a roleset compatibility
- E1-b composed-FN filter correction

E1 may be pulled back onto the critical path only if an E2E acceptance
test demonstrates that one of those extraction defects blocks the
production lexical path.

## Next Unchecked Critical-Path Gate

**R3a** — grounded EvidenceBundle assembly: every answer claim must
assemble from traceable evidence bundles (fact + source span +
provenance). First implementation gate.

## Do Not Do

- Do NOT begin E1 (deferred measured improvement).
- No production extraction changes without a measured delta.
- No edits to `eval/gold/relations_v1.yaml` / `relations_v1.1.yaml`.
- No fuzzy SemLink joins; no composed-as-direct attestation.
- Never prune Docker volumes (`docker volume prune`, `docker system
  prune --volumes`, or any `docker volume rm`) without explicit
  approval. Docker cleanup performed this session was approved and is
  recorded above; anything else requires approval.
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
