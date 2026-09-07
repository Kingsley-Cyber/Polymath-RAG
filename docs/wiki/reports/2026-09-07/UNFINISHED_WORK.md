---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
supersedes: UNFINISHED-WORK.md
---

# UNFINISHED WORK — inventory ordered by dependency and impact (2026-09-07)

Ordering: U1 → U2 are the architecture's critical path; U3–U6 are reliability items that the critical path touches; U7+ are owner decisions and improvements. See `DEPENDENCY_MAP.md` for the graph.

> **Next-phase plan admitted 2026-09-07 (slice S0, register 11.129).** The owner's
> plan of record `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` (slices S0–S16)
> extends this critical path. **U1** (DOCUMENT_PROFILE retrieval lane) folds into
> its slice **S12** (runtime profile/map lane); **U2** (QUERY_READY flip) into its
> slice **S15** (QUERY_READY promotion, owner go). The plan inserts new prerequisite
> slices before them: **S1** deterministic ParentSkeleton → S2 map compiler → S3
> token packer → S4 SQL durability → S5 profile vNext + fingerprint → S6 combined
> one-call canary → S7 shared Groq budget → S8 `doc_profile` refactor → S9
> `doc_parent_map` worker → S10 `project_doc_profile` → S11 shadow verifier → S12 →
> S13 Vocabulary Bridge → S14 quality gate + backfill → S15 → S16 old-parent
> ablation. Execute in that dependency order; the plan §40 is authoritative, this
> inventory is the reliability/owner-decision context around it. **Current slice:
> S0-S4 DONE (11.129-11.135: admission, ParentSkeleton, map compiler, token packer, corrective checkpoint, Groq routing policy + router core, SQL durability); S5 profile vNext + fingerprint next. Groq live wiring + reindex canary gated.**

---

```text
ID: U1
Title: DOCUMENT-PROFILE-V1 step 6 — retrieval lane DOCUMENT_PROFILE
Status: planned, not started (owner plan of record; no go needed)
Objective: documents nominated by the profile collection boost and deepen chunk retrieval; the B16 title ranker reads the same ranking.
Current implementation: profile collection populated (67 cinema points; named dense title/identity/theme + multivectors questions/searches/theories/concepts/seealso); scripts/document_profile_gate.py already performs the query shape (prefetch identity/theme/title + [vec] on questions/searches → FusionQuery RRF, payload doc_id).
What remains: (1) a lane in shared/polymath_shared/candidate_engine.py (or chat_retrieval.py) that embeds the plan's PRIMARY once (reuse the lane-A vector), runs the prefetch/RRF against collection_name(active_contract()) filtered by corpus_id, takes top-k documents, and enters their children into fusion with provenance "DOCUMENT_PROFILE" (boost weight, never a filter); (2) receipts: meta.lanes gains the lane, per-document scores and the k; (3) compiler_context.rank_documents accepts the same ranking so titles and the lane agree; (4) knobs: POLYMATH_CHAT_PROFILE_LANE (on/off), top-k, boost weight; (5) measurement: frozen fixtures B / M floors held, distinct cited documents up on synthesis questions, the punch question cites the Laban Workbook without the titles workaround.
Why unfinished: step 5 (backfill) had to exist first; finished 15:03Z today.
Blocking issue: none technical.
Dependent modules: candidate_engine fusion, chat_retrieval._attach_graph ordering, compiler_context, query_receipts meta, evidence legend.
Depends on: nothing open (U5 pacing is independent).
Tests already present: tests/determinism/test_document_profile_projection.py (vector shapes), gate JSON docs/wiki/experiments/document-profile-gate-gate1.json (baseline: top-1 85.8 %, top-3 99.5 %).
Tests still needed: lane pin (one embedding reused, lane present in meta.lanes, off-switch), fusion provenance pin, frozen-fixture replay with the lane on (10-question loop), punch-question acceptance.
Files involved: shared/polymath_shared/candidate_engine.py, orchestrator/orchestrator/api/chat_retrieval.py, shared/polymath_shared/compiler_context.py, shared/polymath_shared/document_profile/projection.py (ANSWER_SURFACES / EXPLORATION_SURFACES constants).
Relevant commits: 0953a10, 0c78579.
Relevant documentation: docs/wiki/plans/DOCUMENT-PROFILE-V1.md §Retrieval and §Gate; OWNER-BACKLOG B18; IMPLEMENTATION-TODO §10.
Recommended next action: build behind an env flag, measure with scripts/presentation_probe.py-style 10-question loops on fixtures B and M before defaulting on.
Risk if modified incorrectly: turning the lane into a filter (WHERE doc_id IN top_k) silently gates retrieval — explicitly forbidden by the owner; using SEEALSO/theories/concepts in normal answers changes answer topicality.
```

```text
ID: U2
Title: DOCUMENT-PROFILE-V1 phase B — the profile becomes a QUERY_READY requirement
Status: planned; owner go required for the flip
Objective: ingested != query_ready — a document serves only when its profile artifact and vectors exist.
Current implementation: STAGE_DAG has doc_profile LAST and in NON_BLOCKING_STAGES (phase A); the DAG mints doc_profile for every new run; readiness half-contracts exist (profile_valid, has_required_vectors).
What remains: move the DAG entry ahead of verify_projections; remove "doc_profile" from NON_BLOCKING_STAGES; make verify_projections require the doc_profile artifact (tolerant: core + hook + vectors); update test_control_plane_v2 DAG order pin and the stage test; run the cinema census to confirm all 67 stay ready; decide behaviour for other corpora (their documents have no profile yet → they would become not-ready: backfill them first).
Why unfinished: gating before step 6 proves value would gate nothing useful (register 11.126 rejected claim); other corpora not backfilled.
Blocking issue: U1 gate evidence; owner go; backfill of non-cinema corpora (scripts/backfill_document_profiles.py --corpus <id>).
Dependent modules: control/control/tickets.py (STAGE_DAG, NON_BLOCKING_STAGES), verify worker, census.
Depends on: U1 (evidence), U5 (pacing safe for larger corpora).
Tests already present: test_control_plane_v2 (DAG order), test_document_profile_stage (DAG pin).
Tests still needed: readiness flips when the profile is missing; tolerant minimum accepted; existing ready runs unaffected until re-verified.
Files involved: control/control/tickets.py, workers/workers/verify_worker.py, tests above.
Relevant documentation: DOCUMENT-PROFILE-V1.md §Readiness; register 11.126.
Recommended next action: after U1, backfill every corpus, then flip behind a census check.
Risk if modified incorrectly: every document in an unprofiled corpus stops serving.
```

```text
ID: U3
Title: INTERACTIVE-RELIEF-V1 after-measurement and rerank deadline restoration
Status: implemented but unverified (register 11.124 IMPLEMENTED)
Objective: confirm judge timeouts are gone under normal load and restore POLYMATH_CHAT_RERANK_DEADLINE_S from 12 to 8.
Current implementation: caps, deadline 12 s, length rule, carry artifact live since the 14:2xZ boot.
What remains: read query_receipts for the owner's next 40 UI turns (meta.degraded rerank_timeout / embed_deadline counts, generation seconds, carry on rewrite turns); when the project_qdrant backlog (19 at 15:05Z) is 0, set the deadline to 8 in .env (owner edits .env) and respawn the orchestrator; record in work-log 2026-09-07-interactive-relief and flip 11.124 to DONE.
Why unfinished: needs real owner turns (the 15 receipts since the boot were the test suite's fixtures).
Blocking issue: owner UI usage; backlog drain.
Depends on: nothing.
Tests still needed: none new; measurement only.
Files involved: .env, orchestrator/orchestrator/api/ui.py (no change expected).
Risk if modified incorrectly: dropping the deadline while the embedder is still contended re-creates the dead-judge symptom.
```

```text
ID: U4
Title: B16 titles — owner hand-test and fixture M dense arm
Status: implemented but unverified (register 11.122 IMPLEMENTED)
Objective: promote the dense titles block to DONE with the owner's acceptance.
Current implementation: dense default, sparse via env, per-request titles_rank.
What remains: complete the fixture M dense arm (10 questions; the earlier arm was interrupted at 6), compare distinct cited documents vs sparse (24 → 31) and off; owner's manual verdict.
Depends on: nothing; U1 may later supply the ranking from the profile lane (then re-measure).
Tests present: compiler-context pins. Needed: none beyond the measurement.
Risk: none.
```

```text
ID: U5
Title: Durable shared rate budget for the profile pool (and honest RPD)
Status: planned
Objective: six processes should draw from ONE per-key budget that survives restarts, instead of six in-process limiters.
Current implementation: limiter.py threading locks per process; rows rpm 2 / conc 1 / tpm 60000 / rpd 230 per slot; per-slot key offset avoids collisions in steady state; AIMD halves on 429/503; retry-after header not read.
What remains: decide DB-backed (a limiter_state row per lane, advisory lock) vs supervisor-level budget; implement; read retry-after; pin.
Why unfinished: not needed for cinema (67 docs); becomes relevant at corpus scale or when RPD (250/day/key) matters.
Depends on: nothing. Blocks: U2 for large corpora (throughput/ceilings), not for cinema.
Tests still needed: two processes cannot exceed the shared budget; restart keeps the day count.
Files: shared/polymath_shared/llm_extraction/limiter.py, client.py, limiter.yaml.
Risk: an over-strict shared budget starves other stages sharing Gemini keys (fallback lanes share provider keys with enrichment).
```

```text
ID: U6
Title: Re-profile the one low-quality document and add --requeue-below to the backfill script
Status: planned (small)
Objective: RAPO paper profile quality 0.13 (compound wrote `Retrieval:` / `Diffusion:` style lines parsed as unknown tags).
What remains: scripts/backfill_document_profiles.py gains --requeue-below <q> (mint a fresh ticket for artifacts under q; lane rotation makes a different key likely); optionally teach the compiler to treat `<Word>:` lines that are not tags as list items under the last list tag (risky: real unknown tags would be swallowed — pin carefully).
Depends on: nothing.
Files: the script; compiler.py (optional).
Risk: swallowing genuine unknown tags.
```

```text
ID: U7
Title: Pure-rank composition (owner decision)
Status: intentionally deferred — owner ruling given, replacement not specified
Objective: remove judged_prefix round robin, aspect_prefix_seats, compose_diversity_slots and let the judge's rank compose evidence.
Current implementation: quotas present with knobs (aspect_prefix_seats 3, compose_diversity_slots 4, compose_dominance_share 0.6).
What remains: the owner names the composition rule; implement behind a flag; 10-question loops on fixtures B and M; floors held.
Depends on: owner. Interacts with U1 (a profile-boosted candidate set changes what pure rank composes).
Risk: multi-document synthesis questions may collapse to one book without any diversity mechanism — measure before default.
```

```text
ID: U8
Title: B17 LEAN-PROMPT
Status: queued (owner)
Objective: instructions 17 037 chars/turn vs ≈ 6 500 chars evidence → cut the instruction share.
Depends on: owner scope; after U3 measurement.
Files: orchestrator/orchestrator/api/ui.py prompt blocks.
Risk: presentation regressions; measure with the presentation probe.
```

```text
ID: U9
Title: B14 abstraction ladder — L3 as HyDE passages in the compiler vocabulary
Status: queued (owner agreed 2026-09-07; step 1 = L3 alone)
Depends on: U1 preferably (the profile lane gives the compiler document-level aim); owner go on the step.
Files: compiler prompt (chat_plan), compiler_context.
Risk: extra compiler tokens per turn (see U8).
```

```text
ID: U10
Title: Data hygiene decisions (owner)
Status: intentionally deferred — owner decisions
Items: delete "Framed Environment Design.md" (OCR garbage); "How to Draw Manga: Illustrating Battles" carries Document2PDF watermark text; "Manga in Theory and Practice" has no active document summary; summaries production policy; rotate the six Groq keys pasted in chat.
Depends on: owner. Risk: deletions are irreversible (DOCUMENT-DELETE-V1 path; 409 runs_in_flight retry).
```

```text
ID: U11
Title: Local test hygiene
Status: planned (small)
Items: rerank_deadline_s pin should not depend on the shell's .env (read the default or monkeypatch); test_incremental_census parity should snapshot or tolerate a moving project_qdrant backlog; one live pronoun endpoint ("you") in dev facts data.
Depends on: nothing. Risk: none.
```

```text
ID: U12
Title: Owner backlog B4 / B5 / B6 / B10 residuals
Status: as listed in docs/wiki/plans/OWNER-BACKLOG.md (B4 keys-in-.env policy standing; B5 judge fast path comparison run; B6 Docker volumes kept; B10 ablation follow-ups).
```
