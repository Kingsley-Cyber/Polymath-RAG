# NEXT_SESSION HANDOFF — 2026-08-24 (late)

Read this file top-to-bottom, then run the bootstrap commands. Do not
re-derive state from chat history — this file + the DB are the
authorities.

## WHERE WE ARE

Architecture is FROZEN and feature-complete. The intelligence stack
(extraction v2 / artifacts / summaries / corpus map / vocabulary /
router) is built, unit-tested, and shadow-validated. What remains:

1. Verify the CATEGORY-D binding fix on live extraction (this session's
   last commit — unit-verified, NOT yet re-extracted end-to-end).
2. Drain convergence → PHASE_1 reliability package.
3. Cutover restart with the full env (below) → enforcement decision.
4. A1 registries / A2 concept policy (owner decisions, blocked on
   nothing technical).

## BOOTSTRAP (run in order)

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
export POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
git log --oneline -5          # expect HEAD at/after 12c713d
git status                    # must be clean
docker ps                     # postgres/redis/qdrant/neo4j up?
```

Then verify fleet liveness:
```bash
curl -s -m 3 http://127.0.0.1:8740/ready   # gliner
curl -s -m 3 http://127.0.0.1:8744/ready   # spacy
curl -s -m 3 http://127.0.0.1:8742/ready   # embedder
ps aux | grep -E "control.main|extract_worker" | grep -v grep
```
If workers are down: `POLYMATH_PROFILE=pipeline nohup bash
scripts/boot_polymath.sh > /tmp/polymath_fleet/boot.log 2>&1 &`

## CURRENT DRAIN STATE (at handoff)

done ≈ 3,424 · pending ≈ 4,680 · ready 441 · **dead letters 0**.
Convergence watcher: `/tmp/polymath_fleet/convergence_watch.sh`
(logs `/tmp/polymath_fleet/watch.log`; exits when open ≤50 or dead>0).
Telemetry: `/tmp/polymath_fleet/drain_metrics.jsonl` (~1,150 samples,
30s cadence). Copy BOTH to `eval/v5/scale/` before they rotate.

## THE ONE OPEN DEFECT: CATEGORY_D (role binding)

Doc01 of s-validation-v1 ("Adaptive Neural Reasoning Systems") produced
0 candidates despite anchors resolving and endpoints GLOBAL-admitted.

**FIX ALREADY COMMITTED (12c713d)**: sidecar emits dep labels without
colons (`nsubjpass`) while kimi expects UD style (`nsubj:pass`).
`DEP_LABEL_ALIASES` normalization added in `_syntax_tokens`.
Unit-verified: passive subject now binds.

**STILL TO DO**: re-extract s-validation doc01 under enforce env and
confirm ≥3 facts (introduced_by / trained_on / evaluated_on). Red
fixtures in `tests/determinism/test_sval_doc01_red.py` mark the target;
they turn green only via live verification.

## CUTOVER RESTART CHECKLIST (after drain converges)

Stop fleet (SIGTERM supervisor first, then children; VERIFY pids die —
launchctl no-ops here), then boot with FULL env:

```bash
export POLYMATH_PROFILE=pipeline
export POLYMATH_RELATION_PIPELINE=kimi_v1
export POLYMATH_PREDICATE_V2=enforce   # or shadow for one more pass
export POLYMATH_SYNTAX_PROVIDER=spacy
nohup bash scripts/boot_polymath.sh > /tmp/polymath_fleet/boot.log 2>&1 &
```

Then confirm: new PIDs for control+workers, sidecars ready (8740/42/44),
and re-run the three-corpus replay scripts in eval/v5/replay/.

## KEY FILES

| What | Where |
|---|---|
| Router v1.1 | shared/polymath_shared/knowledge_router/ |
| Frame/definite/compound resolvers | shared/polymath_shared/rulepack/frame_roles.py |
| Ontology (incl created_by/developed_by) | rulepack/scientific-predicate-ontology-v2.yaml |
| Artifacts | knowledge_objects/{knowledge_artifact,procedure,concept}.py |
| Registries (A1 substrate) | resources/registries/scientific-registries.yaml |
| GO/NO-GO harness | eval/v5/rag_gonogo.py |
| Doc01 trace + red fixtures | eval/v5/replay/scientific_trace_doc01.py · tests/determinism/test_sval_doc01_red.py |
| Reliability package generator | eval/v5/scale/phase1_baseline_report.py |

## REPORTS ON RECORD (all committed)

- RAG-GONOGO-RESULTS.md — 6 PASS / H1+H3 partial
- SCIENTIFIC-KAG-INTELLIGENCE-BASELINE.md — TEST.md 0→5 facts
- COMBINED-EXTRACTION-REPORT.md — 5-corpus precision analysis
- EXTRACTION-REPORT-s-validation-v1.md — latest 4-doc set
- SUMMARY-RUNTIME-FIX-REPORT.md — D1/D2/D3 closed
- DECISION-A1-A2-POLICY.md

## TRAPS (learned the hard way this session)

1. `documents.doc_id` is GLOBALLY unique by content hash — identical
   bytes into a second corpus silently no-op. Use tagged variants for
   evaluation reruns (marker comment appended changes content hash).
2. Sidecar dep labels have NO colons (`nsubjpass`). Anything matching
   UD-style deps must normalize first.
3. `psql -c "..." < file` ignores stdin — pipe the file instead.
4. launchctl kickstart silently no-ops under ~/Documents (TCC).
5. Shell cwd resets between tool calls — prefix every command.
6. extract worker crash-loops at boot until sidecars answer /ready;
   wait ~60s before diagnosing.

## ENV FLAGS (for cutover restart)

```
POLYMATH_RELATION_PIPELINE=kimi_v1     # role-oriented binding
POLYMATH_PREDICATE_V2=shadow|enforce   # frame lane + precedence
POLYMATH_KNOWLEDGE_ROUTER=1            # classification profile stored
                                       # (persistence slice pending)
```

Default remains legacy_v1/off — pre-cutover behavior unchanged.
