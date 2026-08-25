# SESSION CONTEXT PACKET — 2026-08-25 closeout
# For a fresh agent: read this, then NEXT_SESSION_HANDOFF.md, then AGENTS.md.
# Everything below is MEASURED state as of this commit.

## ONE-PARAGRAPH STATE

POLYMATH v4 is a queryable knowledge engine: deterministic ingestion →
frozen scientific extraction (Predicate Compiler v2 ENFORCE) →
facts/procedures/concepts persisted with execution-bundle provenance →
parent/document/corpus-map summaries produced by a live summaries
worker → /ask answers FACT/PROCEDURE/CONCEPT/POLYMATH questions from
stored objects only (acceptance 4/4 grounded). Control-plane scaling
under the 10k backlog is the active engineering front: lock-contention
root causes fixed (heartbeat restored after >1 day), census redesign
telemetry-justified and queued next.

## FROZEN (do not touch)

- Scientific extraction: GLiNER lanes, semantic frames, Predicate
  Compiler v2, role binding, admission E1–E7/F1–F8 policies.
- Artifact taxonomy: FACT / PROCEDURE / CONCEPT only.
- Summary hierarchy: chunk → parent → document → corpus map.
- Graph semantics: typed edges only (fact predicates; procedure
  USES_TOOL/REQUIRES; concept SUPPORTED_BY). No RELATED_TO soup.

## LIVE RUNTIME

- Profile `pipeline` = control + intake/profile/extract/canonicalize/
  project_canonical/neo4j/qdrant/verify/**summaries** +
  gliner(8740)/spacy(8744)/embedder(8742). No orchestrator/reranker.
- Env at boot: kimi_v1 + PREDICATE_V2=enforce + SYNTAX_PROVIDER=spacy
  (+ QUERY_POLICY=v3, RESCUE=on, CHUNKER=legacy via boot script).
- Execution bundle fence: workers refuse claims on disk drift; facts
  carry generated_by_bundle_hash. Fence must print PASS 12/12 scoped to
  pipeline slots — stale-memory or dirty-tree FAILs are real signals,
  not flakes.

## TOP OPEN ITEMS (ordered)

1. Incremental census (dirty-run set) — tick ~24min cold under backlog;
   telemetry proves census Python loop over 25k attempts/10k runs.
2. Triage 74 failed intake tickets (KeyError corpus_id from restart
   backfill; adapter fixed post-incident): archive test corpora, revive
   release-books-v1 trio via re-emit.
3. Contract freeze docs (chunk hierarchy from ACTUAL chunker code;
   storage/Qdrant metadata extension per charter).
4. Three-mode same-query benchmark harness (VECTOR/HYBRID/GRAPH).
5. Real-corpus pilot 50–100 docs; then resume scale qualification.

## GOTCHAS THAT BIT US (all live-earned)

- Clean tree whenever workers boot (integrity gate + bundle fence).
- Restart backfill can mint bare {run_id, ticket_id} payloads for ANY
  stage — event_adapter._REQUIRED must list every consumed key; extend
  it when adding stages.
- pkill leaves orphan PG backends running old queries; cancel via
  pg_stat_activity after killing controls. Multiple control.main
  accumulate across restarts — verify exactly one.
- doc_id dedup is global by content hash → tagged variants for reruns.
- launchctl no-ops under ~/Documents; psql absent on host (docker exec);
  shell cwd resets between tool calls; extract crash-loops ~60s until
  sidecars ready.

## VERIFICATION SHORTLIST

- Fence: eval/v5/verify_live_build.py (scoped POLYMATH_FLEET_ONLY)
- Science: tests/determinism/test_sval_doc01_red.py (14/14 with
  category_d_followup + kimi_candidates)
- Fence logic: tests/determinism/test_execution_bundle.py,
  test_lock_contention_v2.py
- /ask smoke: orchestrator.api.ask.ask(AskRequest(question=...))
- Live plan: .venv/bin/python eval/v5/implementation_plan.py

## WHERE THINGS ARE

Handoff: NEXT_SESSION_HANDOFF.md (authoritative, detailed)
Work logs: docs/wiki/work-log/2026-08-24-*.md (five entries today)
Reports: docs/wiki/plans/SHADOW-PARITY-REPORT.md,
         eval/v5/scale/INGESTION-WATERFALL-V1.md
Migrations new this session: 0031 execution_bundles,
  0032 dead_letter_archive, 0033 knowledge artifacts
