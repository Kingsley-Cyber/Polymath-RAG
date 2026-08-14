# Next Session

## Start Here

Read:
1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. `RAG_E2E_CHECKLIST.md` (next unchecked gate: C2)

## Last Completed

- **C1** — deterministic Stage-2 corpus canonicalization (ADR 0009).
  New census stage `canonicalize` + migration 0005 registry
  (`canonical_entities`, `canonical_memberships`,
  `canonicalization_decisions`) + pure deterministic canonicalizer.
  Content-hash canonical ids; conservative SAME_AS/ALIAS_OF/DISTINCT/
  AMBIGUOUS policy; full lineage back to source-local knowledge;
  order-independent, replay-safe, incremental delta. Live E2E
  verified. Evidence: work log `2026-08-14-c1-canonicalization.md`,
  refactor 0004.
- **R3b** — grounded answer generation + /chat (work log
  `2026-08-14-r3b-grounded-answer.md`, refactor 0003).
- **R3a** — grounded EvidenceBundle assembly (work log
  `2026-08-14-r3a-evidence-bundle.md`, refactor 0002).
- Phase H v1.1 — hybrid REJECT as production default (frozen evidence).

## What Was Validated (at checkpoint)

- 127 unit tests passed / 20 skipped; 17 integration passed / 2 skipped.
- All three guards green (preflight / repo guard / wiki worm).
- Frozen hashes re-verified: relations_v1 `fdfd75b4…`, relations_v1.1
  `3ee7065a…`, resource contract `03a513ec…`, tables `0ac3002a…`,
  compiled lexical `5c58adbd…`.

## Current Verified Commit

- branch: `main` (tracks `origin/main`:
  `https://github.com/Kingsley-Cyber/Polymath-RAG.git`)
- Sync with `git fetch && git pull --ff-only` before work.

## Priority (critical)

Do NOT begin E1 yet (deferred measured improvement).

CRITICAL PATH TO RAG v1.0 (in order):
1. ~~grounded EvidenceBundle assembly (R3a)~~ COMPLETE
2. ~~functional answer generation and /chat path (R3b)~~ COMPLETE
3. ~~Stage-2 corpus-level canonicalization/merge (C1)~~ COMPLETE
4. canonical KG + source/provenance linkage (C2) ← NEXT
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

E1 may be pulled back onto the critical path only if an E2E acceptance
test demonstrates that one of those extraction defects blocks the
production lexical path.

## Next Unchecked Critical-Path Gate

**C2** — canonical KG + source/provenance linkage. Project the C1
registry (canonical entities + memberships) into Neo4j as a
rebuildable projection: canonical entity nodes, canonical membership
edges to local entities, and provenance links from the canonical layer
back to source-local facts. Postgres remains authority; Neo4j stays
disposable/rebuildable. The milestone after C2 is Q1 (heterogeneous
corpus qualification), then I1/I2 (bulk ingest + integrity) →
CORPUS_INGEST_READY.

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
