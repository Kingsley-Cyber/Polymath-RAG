# Next Session

## Start Here

Read:
1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. `RAG_E2E_CHECKLIST.md` (next unchecked gate: C1)

## Last Completed

- **R3b** — grounded answer generation + /chat. POST /chat runs the
  R3a bundle through a deterministic propose→validate→render pipeline
  (`shared/polymath_shared/answer_synthesis.py`, contract
  `contracts/answer/v1/chat_response.schema.json`). The validator is
  the trust boundary: supports must resolve to real bundle items,
  fabrication tokens are rejected, conflicts represented (never
  arbitrated), epistemic scope survives, insufficient evidence
  abstains. Live E2E verified (cited grounded conflict answer).
  Evidence: work log `2026-08-14-r3b-grounded-answer.md`, refactor 0003.
- **R3a** — grounded EvidenceBundle assembly (work log
  `2026-08-14-r3a-evidence-bundle.md`, refactor 0002).
- Phase H v1.1 — hybrid REJECT as production default (frozen evidence).
- Bootstrap continuity system + Docker hygiene (approved only).

## What Was Validated (at checkpoint)

- 108 unit tests passed / 19 skipped; 16 integration passed / 2 skipped.
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
3. Stage-2 corpus-level canonicalization/merge (C1) ← NEXT
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

E1 may be pulled back onto the critical path only if an E2E acceptance
test demonstrates that one of those extraction defects blocks the
production lexical path.

## Next Unchecked Critical-Path Gate

**C1** — Stage-2 corpus-level canonicalization / cross-document merge.
Facts are per-document today; C1 adds the deterministic merge layer
(cross-document entity merge) WITHOUT touching the frozen per-document
extraction path. See `CURRENT_STATE.md` (Knowledge Extraction State)
for the current absence.

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
