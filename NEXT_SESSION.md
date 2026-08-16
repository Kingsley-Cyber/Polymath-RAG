# Next Session

## Start Here

Read:
1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. `RAG_E2E_CHECKLIST.md` (next unchecked gate: I1)

## Last Completed

- **E5 track — CLOSED** (closeout work log
  `2026-08-16-e5-track-closeout.md`; commits `8323304` → `ba363ec` →
  `0632132`). Final interpretation of both frozen findings:
  (1) deterministic concept candidate primitive
  (`concept-inventory-v1`) = QUALIFIED EXPERIMENTAL PRIMITIVE —
  preserved with tests, frozen evidence, and the negative routing
  result, but with NO production use and NO production dependency;
  (2) concept-enriched semantic routing
  (`routing-concept-enriched-v1`) = REJECTED (doc/sec R@1 0.882 →
  0.853, psychology regressions, coverage unchanged). Production
  posture unchanged: entity/graph lane stays GLiNER → admission →
  E3B gates → compiler; retrieval lane stays summaries → Qwen3
  embedding → FAST/HYBRID/GRAPH. GLiNER-only extraction remains
  qualified (abstract-concept recall limitation measured, documented,
  NOT a compiler defect; graph stays sparse and precise — text
  retrieval protects recall). E5C hypotheses frozen as future
  research only (preferred future shape: summary semantic vector +
  independent concept/lexical rank fusion, NOT concatenated
  enrichment). **Do not start another extraction-recall experiment or
  synthesis/answerability work without explicit user authorization.**
- **E5B — deterministic concept inventory: CLOSED, verdict REJECT**
  (work logs `2026-08-15-e5b-concept-inventory.md` +
  `2026-08-16-e5b-routing-qualification.md`, report `eval/e5b/REPORT.md`,
  frozen evidence `eval/e5b/evidence_p2.json`). Part 1 (discovery):
  psychology candidates 13/13 vs GLiNER 2/13, admitted 5/13 @ budget 8,
  zero-delta, determinism green. Part 2 (routing A/B on re-ingested
  I2 corpus, harness validated by exact R1B reproduction 0.882/0.912/
  0.912): candidate doc/sec R@1 0.882 → 0.853 (one query each; both
  real regressions psychology — iso/memory_note.txt concept lists
  absorb query terms), R1A coverage unchanged (0.870/0.778/0.889),
  graph/extraction/Neo4j zero-delta, determinism green, ~1 ms/doc
  extraction, search latency unchanged. Verdict REJECT per decision
  rule; no tuning performed; no production integration. E5C
  hypotheses recorded only (occurrence floor, summary-co-occurrence
  gate, corpus-level frequency normalization, short-doc budgets) —
  require separate experiment authorization.

- **D4.1 — answer-support model qualification: REJECT (frozen)** (work
  log `2026-08-15-d41-answer-support-model-qualification.md`, report
  `eval/d4/REPORT_D41.md`). 794 frozen (query, passage) pairs, 4
  candidates: NLI DeBERTa (task mismatch, recall≈0) and QNLI
  cross-encoders (right family, distributions separated, but max
  precision 0.80/0.58 at any threshold; contradiction pairs score as
  support; abstract-term hallucination; q4 fails). No production
  wiring. Next: user decision — fine-tune a 3-way classifier, accept
  graph-only abstention, or other.
- **D4 — TEXT support admission: REJECT (insufficient signals)**
  (work log `2026-08-15-d4-text-support-admission.md`, report
  `eval/d4/REPORT.md`). Frozen development set (7 answerable +
  6 unsupported) measured against the FROZEN pipeline: dense,
  lexical, and G3 rerank scores all fail to separate answer support
  from topical relatedness — same-domain unsupported queries outscore
  true positives (u5: 6.44, u6: 6.50 vs q5 true support 1.25-2.25).
  No threshold, no heuristic, no production change. Next: user
  decision — authorize an entailment/answerability-model track, or
  accept current semantics.
- **I2 — corpus-scale integrity qualification: FAIL (frozen)** (work
  log `2026-08-15-i2-corpus-integrity-qualification.md`, report
  `eval/i2/REPORT.md`). Frozen 28-doc multi-format corpus ingested
  live: 28/28 query_ready, eligibility-aware census exact, no generic
  hubs, identity invariants 4/4, isolation clean, replay idempotent.
  FAILING gate: queryability — unsupported questions do not abstain;
  the TEXT lane returns 96 cited passages for any query (no
  deterministic text support bound). Owning layers recorded; NOT
  patched per gate rules. Next authorized work: TEXT-lane support
  bound (D4) — pending user decision.
- **I1 — manifest-driven bulk ingestion** (ADR 0013, refactor 0010,
  work log `2026-08-15-i1-manifest-driven-bulk-ingestion.md`).
  Manifest contract v1 + pure policy + shared intake writer (one
  execution path; POST /intake delegates to it) + control-plane
  plan/execute/status + CLI (`make ingest-plan/run/status`) + frozen
  fixture. Live verification: 6 submitted → 6 query_ready via the
  real control plane; replay submits 0; changed-content, partial-
  failure resume, corpus propagation, and batch-bounded resumable
  submission all proven by the integration suite. Deletions deferred
  by design.
- **Live entity-admission E2E smoke gate — PASS** (work log
  `2026-08-15-smoke-admission-e2e-pass.md`). After D1
  (shared Neo4j-eligibility predicate: parked MENTION_ONLY facts are
  not projection failures — receipt census/verify/projector agree)
  and D2 (corpus-authorized graph expansion: seeds from in-scope
  evidence, no facts supported exclusively by another corpus), the
  frozen metacognition document passed: query_ready, all six queries
  corpus-clean with zero foreign citations, vague "system" query
  gains no legacy-hub authority, replay idempotent (identical run_id
  + semantic hashes), Neo4j reconstruction exact, determinism PASS,
  suites/guards green. **I1 unblocked.**
- **E2/C1.1 production wiring** — entity admission boundary (ADR 0011,
  refactor 0008). Production identity allocation now runs the
  qualified entity-admission-v1.1 policy: GLOBAL / CORPUS_SCOPED /
  DOCUMENT_SCOPED / MENTION_ONLY with identity contract
  entity-identity-v2 (migration 0007). MENTION_ONLY entities never
  project to Neo4j; facts with a MENTION_ONLY endpoint are parked as
  Postgres-only evidence. Graph expansion promoted to canonical
  bidirectional hop1 (directed UNION, dedupe by fact_id): downstream
  G4 rerun 12 useful / 0 noise, q09 clean; Phase H P/R 0.9355 both
  arms unchanged; compiler untouched. Evidence: work log
  `2026-08-15-e2-admission-production-wiring.md`, ADR 0011.
- **I0** — native document materialization (ADR 0010). Deterministic
  PDF/EPUB/DOCX/TXT/MD/HTML → normalized text + structural source map
  (page/chapter/section/paragraph) fed into the frozen pipeline; typed
  LOUD failures (unsupported/encrypted/corrupted/empty/low-yield);
  migration 0006 persists source_hash/materialization/source_map;
  extract consumes authoritative Postgres chunks. Live E2E: both book
  samples (psychology + technical) through the full pipeline with
  fact → evidence → chunk → source-map → page/chapter lineage.
  Evidence: work log `2026-08-14-i0-native-documents.md`,
  refactor 0007.
- **Q1** — heterogeneous extraction qualification: **PASS** (frozen
  report `eval/q1/REPORT_Q1.md`; P/R 0.943; regression locks added).
  **Production extraction is qualified. Further extraction changes
  require a demonstrated regression or separately measured
  improvement.** Evidence: work log
  `2026-08-14-q1-qualification.md`, refactor 0006.
- **C2** / **C1** — canonicalization layer + canonical KG (refactors
  0005/0004, ADR 0009).
- **R3b** / **R3a** — grounded answer path (refactors 0003/0002).

## What Was Validated (at checkpoint)

- 152 unit tests passed / 22 skipped; 19 integration passed / 2 skipped.
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
4. ~~native document materialization (I0)~~ COMPLETE
5. ~~entity admission production wiring (E2/C1.1)~~ COMPLETE (ADR 0011)
6. ~~live admission smoke gate + D1/D2 defect fixes~~ COMPLETE (PASS)
7. ~~manifest-driven bulk ingestion (I1)~~ COMPLETE (ADR 0013)
8. ~~corpus-scale integrity qualification (I2)~~ RUN — FAIL on queryability (TEXT lane support bound = next)

CORPUS_INGEST_READY is achieved only when C1+C2+Q1+I0+I1+I2 pass.

MILESTONE B — RAG_V1_E2E (after Milestone A):
R2 (reranker, bypassable) → M1–M5 (MCP) → R4 → O2 → O1 → A1 → V1.
R3a and R3b are already COMPLETE. R2/MCP are NOT prerequisites for
CORPUS_INGEST_READY.

E1 may be pulled back onto the critical path only if an E2E acceptance
test demonstrates that one of those extraction defects blocks the
production lexical path.

## Next Unchecked Critical-Path Gate

**I1** — manifest-driven bulk ingestion. BLOCKED: I1 is NOT authorized
to force a new entity-architecture decision. The realistic-prose
entity boundary gap is documented (EP1/EM1/SR1, frozen FAIL) and
entity-architecture escalation is STOPPED. I1 resumes when a
deliberate product decision addresses the gap or accepts documented
conservative prose coverage. Extraction fixes are prioritized ONLY by
demonstrated downstream waterfall/retrieval delta (see the
consolidated backlog in CURRENT_STATE.md).

Phase H v1.1 status (restored): corpus relations_v1.1 frozen
(`3ee7065a…`); lexical-vs-hybrid verdict **REJECT** as production
default (Δ +1/+4/−4); evidence `eval/phase_h/REPORT_v1.1.md`.

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
