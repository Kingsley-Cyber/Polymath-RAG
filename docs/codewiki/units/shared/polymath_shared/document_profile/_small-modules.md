# unit: shared/polymath_shared/document_profile/_small-modules
anchor: shared/polymath_shared/document_profile/__init__.py:1-6

## purpose
Small pure-policy modules of the DOCUMENT-PROFILE-V1 package: Groq account/model capacity routing, parent-map (pMAP) prompt + trigger, profile prompts (live `doc-profile-v3.2` and additive vNext), RRF profile-scout fusion, and canonical-projection selection. Consumed by workers (`doc_profile_worker`, `doc_parent_map*`), control scheduler, and orchestrator API. Package plan: docs/wiki/plans/DOCUMENT-PROFILE-V1.md — shared/polymath_shared/document_profile/__init__.py:1-6 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `account_states` | def | (lane_snapshots, account_of, account_rpd) -> list[AccountState] | groq_accounts.py:22-53 | groq_routing.py (unit importers) |
| `snapshot_from_registry` | def | (registry, lanes, account_of, account_rpd, *, now=None) -> list[AccountState] | groq_accounts.py:56-72 | — |
| `AccountState` | class | frozen dataclass (account, remaining_rpd, rolling_rpm, tpm_used, in_flight=0, locked_until=0.0, breaker_open=False, latency_ewma={}) | groq_router.py:38-49 | groq_accounts.py:19 |
| `RouteDecision` | class | frozen dataclass (account, model, reason, wait_seconds=0.0) + property `routed` | groq_router.py:53-61 | — |
| `choose` | def | (work_class, accounts, *, now, est_total_tokens, rpm_ceiling=4, tpm_ceiling=TPM_CEILING) -> RouteDecision | groq_router.py:89-148 | groq_routing.py |
| `build_map_user_prompt` | def | (skeletons, grounding=None) -> str | map_prompt.py:93-114 | doc_parent_map workers |
| `build_map_prompt` | def | (skeletons, *, grounding=None, is_combined=False) -> (system, user) | map_prompt.py:117-126 | doc_parent_map workers |
| `doc_parent_map_enabled` | def | () -> bool | map_trigger.py:25-26 | control scheduler |
| `doc_parent_map_corpus_scope` | def | () -> str \| None | map_trigger.py:29-31 | control scheduler |
| `doc_parent_map_since` | def | () -> str \| None | map_trigger.py:34-42 | control scheduler |
| `mint_doc_parent_map` | def | (conn, *, corpus_id, run_id) -> dict | map_trigger.py:45-62 | scheduler, stage worker |
| `build_vnext_profile_user_prompt` | def | (fingerprint) -> str | profile_prompt_vnext.py:81-84 | doc_profile_worker |
| `build_vnext_profile_prompt` | def | (fingerprint) -> (system, user) | profile_prompt_vnext.py:87-89 | doc_profile_worker |
| `output_fields` | def | () -> tuple[str, ...] = SOURCE_ANCHORED_FIELDS + ROUTING_INFERRED_FIELDS | profile_prompt_vnext.py:92-97 | S8 compiler |
| `ScoutHit` | class | frozen dataclass (doc_id, source, rank, surface=None, surface_type=None, text=None, score=None) | profile_scout.py:27-36 | chat_retrieval, projection |
| `fuse_profile_scout_hits` | def | (profile_hits, atom_hits, *, rrf_k=60, max_documents=8) -> ProfileScoutResult | profile_scout.py:71-120 | orchestrator chat_retrieval/ui |
| `profile_hits_from_doc_ids` | def | (doc_ids) -> list[ScoutHit] | profile_scout.py:125-130 | P5b caller |
| `atom_hits_from_search` | def | (rows, *, group_of) -> list[ScoutHit] | profile_scout.py:133-147 | P5b caller |
| `ProfileNomination` / `ProjectionContribution` / `ProfileScoutResult` | class | frozen dataclasses (provenance-only nomination types) | profile_scout.py:40-68 | — |
| `build_user_prompt` | def | (title, structure, excerpts) -> str | prompt.py:91-94 | doc_profile_worker (live path) |
| `Fitness` | class | dataclass + `as_dict`, from `{surface: count}` | selection.py:41-48 | projection.py |
| `profile_fitness` | def | (surface_counts) -> Fitness | selection.py:51-57 | projection.py |
| `Decision` | class | selection decision result | selection.py:68-73 | — |
| `select` | def | (existing_counts, incoming_counts, force) -> Decision | selection.py:76-96 | projection.py |

Unit-level importers (FACTS.importers): control/control/scheduler.py, orchestrator/orchestrator/api/chat_retrieval.py, orchestrator/orchestrator/api/ui.py, shared fingerprint.py / giant_profile.py / groq_routing.py / profile_coverage.py / projection.py / resolution_lift_gather.py, workers doc_parent_map_stage_worker.py / doc_parent_map_worker.py / doc_profile_worker.py.

## contracts

### account_states — groq_accounts.py:22-53
- in: `lane_snapshots` {lane → capacity_snapshot() dict}, `account_of` {lane → account id}, `account_rpd` {account → shared daily budget} — groq_accounts.py:23-25
- pre: a lane with no `account_of` entry is silently skipped — groq_accounts.py:32-34
- post: `remaining_rpd = max(0, budget − Σ day_count)` when budget truthy; else `min(lanes' remaining_rpd)` default 0; RPM/TPM/in-flight summed; `locked_until` = max; `breaker_open` = any — groq_accounts.py:37-50
- post: output sorted by `account` name — groq_accounts.py:52

### snapshot_from_registry — groq_accounts.py:56-72
- in: duck-typed registry (`get(name)` → limiter-or-None with `capacity_snapshot`) — groq_accounts.py:64-66
- pre: lane absent from registry or lacking `capacity_snapshot` is skipped — groq_accounts.py:68-71
- out: delegates to `account_states` — groq_accounts.py:72

### choose — groq_router.py:89-148
- pre: `work_class` must be a key of `WORK_CLASS_MODEL` else `ValueError` — groq_router.py:105-106
- in: `now`, all account state injected; no clock/I/O of its own — groq_router.py:6-8
- feasible iff: not breaker_open, `locked_until <= now`, `remaining_rpd > 0`, `rolling_rpm < token_feasible_rpm(est_total_tokens, target_rpm=rpm_ceiling, tpm_ceiling)`, `tpm_used + est_total_tokens <= tpm_ceiling` — groq_router.py:71-86
- post: best = max by (remaining_rpd, TPM headroom, −in_flight, −rolling_rpm); ties → lexicographically smallest account name — groq_router.py:117-137
- out: `RouteDecision`; reasons `"selected"`, `"empty_pool"`, `"all_locked"` (wait = soonest unlock delta), `"rpd_exhausted"`, `"no_capacity"` (both with wait 5.0) — groq_router.py:108,138,142-148

### build_map_user_prompt / build_map_prompt — map_prompt.py:93-126
- in: ordered `ParentSkeleton`s, optional `DocumentGroundingContextV1` — map_prompt.py:93-95
- post: empty skeletons → header + `"(no sections)"`; else every skeleton in ordinal order + footer naming the exact alias list and count — map_prompt.py:101-108
- post: `grounding=None` output byte-identical to v1 (MAP_PROMPT_VERSION `"map-prompt-v2"`) — map_prompt.py:38-39,108-110
- `is_combined` accepted for the worker's `infer` signature, not yet specialized — map_prompt.py:124-125

### mint_doc_parent_map — map_trigger.py:45-62
- pre: caller holds a DB conn; gate flags read elsewhere (`doc_parent_map_enabled` etc.)
- post: `ticket_id = "tkt_" + content_hash({"run": run_id, "stage": "doc_parent_map"})[:40]`; upsert into `stage_tickets` re-arms status `'ready'`, clears lease/archive; upsert into `outbox_events` with `idempotency_key = f"pmap:{run_id}"` resets `delivered_at` — map_trigger.py:48-61
- out: `{"run_id", "ticket_id", "corpus_id"}` — map_trigger.py:62

### fuse_profile_scout_hits — profile_scout.py:71-120
- in: two already-normalized ranked `ScoutHit` lists (no I/O, no injected search callable) — profile_scout.py:3-8
- pre: hits with empty `doc_id` dropped — profile_scout.py:89-91
- post: per (doc, source) exactly one vote `1.0/(rrf_k + best_rank)`; `fused_score` desc then `doc_id` asc; top `max_documents` (default 8); every hit kept in `provenance`; best-rank text hit is representative — profile_scout.py:96-119
- post: empty inputs → empty `ProfileScoutResult` — profile_scout.py:86-88

### atom_hits_from_search / profile_hits_from_doc_ids — profile_scout.py:125-147
- in: rows `{doc_id, atom_kind, text, score}`; rows without `doc_id` dropped; `surface_type` via injected `group_of` (no registry dependency here) — profile_scout.py:135-146
- profile hits: `rank` = 1-based position; surface/text/score stay `None` — profile_scout.py:127-130

### build_vnext_profile_prompt / output_fields — profile_prompt_vnext.py:81-97
- in: `DocumentFingerprint` (uses `render_block`; falls back to `str()`); empty block → `"(no document evidence)"` — profile_prompt_vnext.py:82-84
- post: `output_fields() == SOURCE_ANCHORED_FIELDS + ROUTING_INFERRED_FIELDS` (constants imported from `fingerprint`, single source of truth) — profile_prompt_vnext.py:96-97

### build_user_prompt (live) — prompt.py:91-94
- in: title, structure, excerpts fill `USER_TEMPLATE` `"DOCUMENT\n\nTITLE:\n{title}\n\nTABLE OF CONTENTS / HEADINGS:\n{structure}\n\nDOCUMENT EVIDENCE:\n{excerpts}\n"` — prompt.py:78 (FACTS)

### select / profile_fitness — selection.py:51-96
- in: `{surface: count}` maps for existing vs incoming projection; `force` flag — selection.py:54-56,79-81 (FACTS)
- out: `Decision` whether incoming replaces the active projection; version tag `"canonical-profile-selection-v1"` — selection.py:28,76 (FACTS)

## effect surface
- Postgres writes: `stage_tickets` (upsert on `ticket_id`), `outbox_events` (upsert on `idempotency_key`) — map_trigger.py:49-61. Reads: none per FACTS (`tables_read: []`).
- Env flags read (all default `''`): `POLYMATH_DOC_PARENT_MAP_ENABLED`, `POLYMATH_DOC_PARENT_MAP_CORPUS`, `POLYMATH_DOC_PARENT_MAP_SINCE` — map_trigger.py:26,30,41.
- Network/Qdrant/files/subprocess: none — router/prompt/scout modules are declared no-I/O, clock injected — groq_router.py:6-8, map_prompt.py:13-15, profile_scout.py:3-8. The provider call lives in the worker's injected `infer` closure — map_prompt.py:14-15.

## invariants
INVARIANT: account remaining_rpd = max(0, account_rpd[acct] − Σ lane `day_count`) when budget truthy — groq_accounts.py:37-45 [DERIVED]
  fails-if: router's `remaining_rpd <= 0` feasibility check (groq_router.py:76-77) sees wrong budget, routes into an exhausted account.
INVARIANT: fused_score = Σ per-source 1.0/(60 + best_rank), at most one vote per source — profile_scout.py:96-101 [DERIVED]
  fails-if: a doc with many atom rows gains fusion weight by row count (the exact distortion best-rank collapse prevents).
INVARIANT: nominations sorted `fused_score` desc, `doc_id` asc, capped at MAX_DOCUMENTS = 8 — profile_scout.py:113-119 [DERIVED]
  fails-if: nondeterministic ordering between runs.
INVARIANT: choose is a pure function of (work_class, accounts, now, est_total_tokens, ceilings) — groq_router.py:6-8,98-99 [DERIVED]
  fails-if: replay/retest of routing decisions diverges.
INVARIANT: `WORK_CLASS_MODEL` maps exactly {`COMBINED_ONE_CALL`→`groq/compound`, `GLOBAL_DOCUMENT_PROFILE`→`groq/compound`, `PARENT_ROUTING_MAP`→`groq/compound-mini`} — groq_router.py:25-29 [DERIVED]
  fails-if: a caller's new work class raises `ValueError` (groq_router.py:105-106).
INVARIANT: ticket_id = `"tkt_" + content_hash({"run": run_id, "stage": "doc_parent_map"})[:40]`; event key = `"pmap:" + run_id`; one ticket per (run, stage) — map_trigger.py:46-48,56 [DERIVED]
  fails-if: re-mint duplicates tickets/events instead of re-arming.
INVARIANT: `grounding=None` map prompt is byte-identical to v1 — map_prompt.py:38-39,108-110 [DERIVED]
  fails-if: silent prompt drift invalidates cached/compared prompts.
INVARIANT: selection surfaces split DIRECT [`questions`,`searches`] / DISCOVERY [`theories`,`concepts`,`seealso`] / PRESENCE [`identity`,`theme`]; REGRESSION_RATIO = 0.5 — selection.py:31-37 [DERIVED]
  fails-if: `Fitness` computed over the wrong surface set mis-ranks projections.

## determinism & idempotency
determinism: DETERMINISTIC — router/accounts/prompts/scout/selection are pure with injected `now` (groq_router.py:6-8, profile_scout.py:78-86); EXCEPTION: map_trigger gate functions read `os.environ` — map_trigger.py:26,30,41 [DERIVED]
idempotency: SAFE — `mint_doc_parent_map` upserts re-arm ticket + event ("idempotent, restart-safe") — map_trigger.py:45-61; all other functions are pure [DERIVED]

## failure behaviour
- `choose` raises `ValueError(f"unknown Groq work class: {work_class!r}")` for unmapped classes — groq_router.py:105-106.
- No feasible account: `all_locked` → `wait_seconds` = soonest `locked_until − now`; `rpd_exhausted` / `no_capacity` → `wait_seconds` = 5.0; empty list → `empty_pool` — groq_router.py:142-148.
- `snapshot_from_registry` silently skips lanes missing from the registry or without `capacity_snapshot` — groq_accounts.py:68-71; an under-counted pool can then look smaller than reality.
- Scout empty inputs → empty result; the caller "fails open to normal retrieval" — profile_scout.py:11-13,86-88.
- Missing account budget falls back to `min(lanes' remaining_rpd)` default 0, never raises — groq_accounts.py:41-42.
- `mint_doc_parent_map` has no try/except: SQL errors propagate to the caller — map_trigger.py:49-61.

## dumb-code flags
- `RouteDecision.reason` comment lists `"selected" | "all_locked" | "no_capacity" | "empty_pool"` but `choose` also returns `"rpd_exhausted"` — groq_router.py:56 vs groq_router.py:147 [DERIVED]
- Dead comment inside the `max()` key about "negate the name"; the name is not in the key — the real tie-break is the separate `tied`/`min()` block — groq_router.py:124-126,128-137 [DERIVED]
- `if budget:` truthiness: an explicit `account_rpd[acct] = 0` budget falls into the min-fallback branch instead of "exhausted" — groq_accounts.py:38-42 [DERIVED]
- `is_combined` parameter accepted and ignored — map_prompt.py:121,124-125 [DERIVED]
- `AccountState.latency_ewma` is declared "per model" but is never read by `_feasible`/`choose` in this module — groq_router.py:49 vs groq_router.py:71-86 [INFERRED: field unused on this code path]
- FACTS `tables_written` contains a literal `"set"` entry — static-analysis artifact (a serialized Python set), not a table — FACTS.tables_written [DERIVED]
- `DEFAULT_RPM_CEILING = 4` is described as "a TARGET, not the provider's 30" — the provider number appears only in the comment — groq_router.py:31-32 [DERIVED]
- `tpm_ceiling` default is `TPM_CEILING` imported from `map_batches`; its numeric value is not visible in this unit — groq_router.py:22,96 [DERIVED]

## refactor notes
- MAP line format `MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>` is a parser contract with the S2 `map_compiler`; changing `MAP_SYSTEM` rules or the footer changes repair rates at minimum — map_prompt.py:8,19-27,105-107.
- Live `prompt.py`/`compiler.py` are deliberately untouched until S8 switches the worker behind the quality canary; `profile_prompt_vnext.py` is additive only — profile_prompt_vnext.py:14-17.
- Tag vocabulary is imported from `fingerprint` (RESEARCH_INDEX_TAGS, ROUTING_INFERRED_FIELDS, SOURCE_ANCHORED_FIELDS); changing labels there flows into both prompt and `output_fields()` — profile_prompt_vnext.py:23-28,92-97.
- `ProfileNomination` deliberately carries no planner fields (`recommended_mode`, `required_subquery`, `must_use_graph`, `intent_override`, `answer_strategy`); adding any makes the scout a hidden planner — profile_scout.py:50-54.
- The pMAP stage stays outside `STAGE_DAG`; the mint path must remain flag-gated + `SINCE`-bounded so historical corpora (cinema) are never swept — map_trigger.py:2-13,34-42.
- `WORK_CLASS_MODEL` keys are a contract with scheduler/worker callers (importers include control scheduler and both doc_parent_map workers); removing a key breaks them with `ValueError` — groq_router.py:25-29,105-106.
- Blast radius of any signature change: 13 importer modules per FACTS.importers (scheduler, chat_retrieval, ui, five document_profile siblings, resolution_lift_gather, three workers).

## VERIFY
```verify
grep -Fq 'DEFAULT_RPM_CEILING = 4' shared/polymath_shared/document_profile/groq_router.py
grep -Fq 'rpd_exhausted' shared/polymath_shared/document_profile/groq_router.py
grep -Fq 'MAP_PROMPT_VERSION = "map-prompt-v2"' shared/polymath_shared/document_profile/map_prompt.py
grep -Fq 'RRF_K = 60' shared/polymath_shared/document_profile/profile_scout.py
grep -Fq 'PROMPT_VERSION = "doc-profile-v3.2"' shared/polymath_shared/document_profile/prompt.py
grep -Fq 'POLYMATH_DOC_PARENT_MAP_SINCE' shared/polymath_shared/document_profile/map_trigger.py
grep -Fq 'REGRESSION_RATIO = 0.5' shared/polymath_shared/document_profile/selection.py
```
