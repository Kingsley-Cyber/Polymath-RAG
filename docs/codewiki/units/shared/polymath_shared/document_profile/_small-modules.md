# unit: shared/polymath_shared/document_profile/_small-modules
anchor: shared/polymath_shared/document_profile/__init__.py:1-6

## purpose
Small pure-policy modules of DOCUMENT-PROFILE-V1: Groq account routing (`groq_accounts`, `groq_router`), the parent-map prompt and ticket mint (`map_prompt`, `map_trigger`), profile prompts (`prompt.py` v3.2, `profile_prompt_vnext`), scout fusion (`profile_scout`), projection selection (`selection`), served-card accounting (`served`). shared/ policy code: no I/O, no model, no clock of its own except `map_trigger` (DB + env) and `served` (injected client) — groq_router.py:6-9, map_prompt.py:13-15, profile_scout.py:4-8. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `account_states` | def | (lane_snapshots, account_of, account_rpd) -> list[AccountState] | groq_accounts.py:22-53 | unit importers |
| `snapshot_from_registry` | def | (registry, lanes, account_of, account_rpd, *, now=None) -> list[AccountState] | groq_accounts.py:56-72 | unit importers |
| `AccountState` | class | frozen dataclass (account, remaining_rpd, rolling_rpm, tpm_used, in_flight=0, locked_until=0.0, breaker_open=False, latency_ewma) | groq_router.py:37-49 | groq_accounts.py:19 |
| `RouteDecision` | class | frozen dataclass (account, model, reason, wait_seconds=0.0) + `routed` property | groq_router.py:52-61 | unit importers |
| `choose` | def | (work_class, accounts, *, now, est_total_tokens, rpm_ceiling=4, tpm_ceiling=TPM_CEILING) -> RouteDecision | groq_router.py:89-148 | groq_routing.py [INFERRED: importer name] |
| `build_map_user_prompt` | def | (skeletons, grounding=None) -> str | map_prompt.py:93-114 | workers/doc_parent_map_worker.py [INFERRED: importer name] |
| `build_map_prompt` | def | (skeletons, *, grounding=None, is_combined=False) -> (system, user) | map_prompt.py:117-126 | unit importers |
| `doc_parent_map_enabled` | def | () -> bool | map_trigger.py:25-26 | control/control/scheduler.py [INFERRED: gate consumer] |
| `doc_parent_map_corpus_scope` | def | () -> str \| None | map_trigger.py:29-31 | — |
| `doc_parent_map_since` | def | () -> str \| None | map_trigger.py:34-42 | — |
| `mint_doc_parent_map` | def | (conn, *, corpus_id, run_id) -> dict | map_trigger.py:45-62 | workers/doc_parent_map_stage_worker.py [INFERRED: importer name] |
| `build_vnext_profile_user_prompt` | def | (fingerprint) -> str | profile_prompt_vnext.py:81-84 | workers/doc_profile_worker.py [INFERRED: importer name] |
| `build_vnext_profile_prompt` | def | (fingerprint) -> (system, user) | profile_prompt_vnext.py:87-89 | — |
| `output_fields` | def | () -> tuple[str, ...] | profile_prompt_vnext.py:92-97 | — |
| `ScoutHit` / `ProjectionContribution` / `ProfileNomination` / `ProfileScoutResult` | class | frozen dataclasses | profile_scout.py:26-68 | unit importers |
| `fuse_profile_scout_hits` | def | (profile_hits, atom_hits, *, rrf_k=60, max_documents=8) -> ProfileScoutResult | profile_scout.py:71-120 | orchestrator/orchestrator/api/chat_retrieval.py [INFERRED: importer name] |
| `profile_hits_from_doc_ids` | def | (doc_ids) -> list[ScoutHit] | profile_scout.py:125-130 | — |
| `atom_hits_from_search` | def | (rows, *, group_of) -> list[ScoutHit] | profile_scout.py:133-146 | — |
| `build_user_prompt` | def | (title, structure, excerpts) -> str | prompt.py:91-94 | — |
| `Fitness` / `Decision` | class | Fitness has `as_dict`; Decision is a result record | selection.py:41-48, 68-73 | — |
| `profile_fitness` | def | (surface_counts) -> Fitness | selection.py:51-57 | — |
| `select` | def | (existing_counts, incoming_counts, force) -> Decision | selection.py:76-96 | — |
| `writer_of` | def | (prompt_version) -> writer label | served.py:24-28 | — |
| `served_profiles` | def | (corpus_id, client, embedding_contract_id, timeout) -> dict | served.py:31-65 | shared/polymath_shared/control_plane_status.py [INFERRED: importer name] |
| `apply_served` | def | (summaries, served) -> None (in-place) | served.py:68-74 | orchestrator/orchestrator/api/ui.py [INFERRED: importer name] |
| `served_vnext_count` | def | (doc_ids, served) -> int \| None | served.py:77-80 | — |

Unit-level importers (FACTS): control/control/scheduler.py; orchestrator/orchestrator/api/{chat_retrieval,health,ui}.py; shared/polymath_shared/{_small-modules-3, control_plane_status, resolution_lift_gather}.py; shared/polymath_shared/document_profile/{fingerprint, giant_profile, groq_routing, profile_coverage, projection}.py; workers/workers/{doc_parent_map_stage_worker, doc_parent_map_worker, doc_profile_worker}.py.

## contracts

**choose** (groq_router.py:89-148)
- in: `work_class` must be a key of `WORK_CLASS_MODEL` (`GLOBAL_DOCUMENT_PROFILE`/`PARENT_ROUTING_MAP`/`COMBINED_ONE_CALL`); `now` epoch seconds; `est_total_tokens` — groq_router.py:25-29, 105-107.
- pre: unknown class raises `ValueError` — groq_router.py:105-106.
- post: `routed == (account is not None)` — groq_router.py:59-61. `reason` ∈ `selected`/`all_locked`/`no_capacity`/`empty_pool` (comment, :57) plus `rpd_exhausted` (:147). No feasible account + a time-locked one → `wait_seconds = min(locked_until - now)` (:142-144); capacity-limited → `wait_seconds = 5.0` (:147-148). Deterministic given (accounts, now, tokens) (:98-100).
- feasibility gate `_feasible`: breaker_open → False; locked_until > now → False; remaining_rpd <= 0 → False; rolling_rpm >= token_feasible_rpm(...) → False; tpm_used + est_total_tokens > tpm_ceiling → False — groq_router.py:71-86.

**account_states** (groq_accounts.py:22-53)
- in: lane→snapshot dicts (`day_count`, `remaining_rpd`, `rolling_rpm`, `tpm_used`, `in_flight`, `locked_until`, `breaker_open`), lane→account map, account→daily-budget map — groq_accounts.py:23-25, 37-50.
- post: one `AccountState` per account; `remaining_rpd = max(0, budget - Σ day_count)` when budget truthy, else `min(lanes' remaining_rpd)`; RPM/TPM/in-flight summed; `locked_until` = max; `breaker_open` = any — groq_accounts.py:37-50. Output sorted by `account` — groq_accounts.py:52.

**fuse_profile_scout_hits** (profile_scout.py:71-120)
- in: two ranked `ScoutHit` lists; `rrf_k=60`, `max_documents=8` — profile_scout.py:22-23, 74-76.
- post: each projection casts ≤1 vote per doc = `1/(rrf_k + best_rank)` (best = lowest rank) — profile_scout.py:80-82, 96-99. `fused_score = Σ contributions`; ordering `fused_score` desc then `doc_id` asc — profile_scout.py:101, 113. ≤ `max_documents` nominations — profile_scout.py:118-119. Empty inputs → empty result — profile_scout.py:86.

**mint_doc_parent_map** (map_trigger.py:45-62)
- in: DB conn with `.execute(sql, params)`, `corpus_id`, `run_id`.
- post: upsert `stage_tickets` row reset to `status='ready'`, `lease_owner=NULL`, `lease_expires_at=NULL` (:49-55); upsert `outbox_events` with `delivered_at=NULL` (:57-61); returns `{"run_id", "ticket_id", "corpus_id"}` (:62). Idempotent, restart-safe — map_trigger.py:46-47.

**build_map_user_prompt** (map_prompt.py:93-114)
- post: same (grounding, skeletons) ⇒ same prompt; `grounding=None` byte-identical to v1 — map_prompt.py:99-100, 109-110. Footer demands exactly `len(skeletons)` MAP lines for exactly the supplied aliases — map_prompt.py:105-107.

**writer_of / served** (served.py:24-80)
- in: prompt_version string; `VNEXT_PREFIX = "doc-profile-vnext"` — served.py:20.
- post: `doc-profile-vnext-*` → vnext, any other → basic — served.py:25. `served_profiles` → `doc_id -> {"writer","prompt_version","compiled_hash"}` — served.py:33. `apply_served` sets `profile_served` `"vnext"|"basic"|None` in place — served.py:69-70. `served_vnext_count` → None when the index could not be read — served.py:79-80.

**output_fields** (profile_prompt_vnext.py:92-97)
- post: `SOURCE_ANCHORED_FIELDS + ROUTING_INFERRED_FIELDS`, imported from `fingerprint` (single source of truth) — profile_prompt_vnext.py:23-28, 96-97.

## effect surface
- Postgres written: `stage_tickets` (map_trigger.py:49-55), `outbox_events` (map_trigger.py:57-61). Tables read: none recorded (FACTS `tables_read` empty).
- Search index read via injected `client` + `embedding_contract_id` in `served_profiles` — served.py:31-33. [DERIVED]
- Env read: `POLYMATH_DOC_PARENT_MAP_ENABLED = ''` (map_trigger.py:26), `POLYMATH_DOC_PARENT_MAP_CORPUS = ''` (:30), `POLYMATH_DOC_PARENT_MAP_SINCE = ''` (:41).
- No files, no subprocess, no direct network; provider calls happen in the injected `infer` closure of the S9 worker — map_prompt.py:14-15.

## invariants
INVARIANT: fused_score == Σ 1/(rrf_k + best_rank) with rrf_k = 60 — profile_scout.py:75, 96-101 [DERIVED]
  fails-if: score formula drifts, rankings change silently.
INVARIANT: votes per (doc, source) <= 1 (best-rank collapse) — profile_scout.py:80-82 [DERIVED]
  fails-if: a doc with many atom rows gains fusion weight from row count.
INVARIANT: nominations count <= max_documents = 8 — profile_scout.py:23, 118-119 [DERIVED]
  fails-if: scout floods the planner with candidates.
INVARIANT: account remaining_rpd == max(0, budget - Σ lane day_count) when budget set — groq_accounts.py:37-45 [DERIVED]
  fails-if: per-lane tracking double-counts or under-counts the shared account budget.
INVARIANT: breaker_open == any(lane breaker_open); locked_until == max(lane locked_until) — groq_accounts.py:49-50 [DERIVED]
  fails-if: one lane's 429 lock fails to lock the whole account (key burning, groq_router.py:16-17).
INVARIANT: choose tie-break order == (remaining_rpd, TPM headroom, -in_flight, -rolling_rpm, lexicographic account) — groq_router.py:101-104, 128-137 [DERIVED]
  fails-if: routing becomes non-replayable.
INVARIANT: ticket_id == "tkt_" + content_hash({"run": run_id, "stage": STAGE})[:40]; one ticket per (run, stage) — map_trigger.py:47-48 [DERIVED]
  fails-if: re-mint duplicates or orphans tickets.
INVARIANT: outbox idempotency_key == f"pmap:{run_id}" — map_trigger.py:56 [DERIVED]
  fails-if: duplicate doc_parent_map.v1 events per run.
INVARIANT: grounding=None output == v1 bytes — map_prompt.py:38-39, 109-110 [DERIVED]
  fails-if: v2 prompt change breaks the byte-identity migration contract.

## determinism & idempotency
| module | determinism | idempotency |
|---|---|---|
| groq_router | DETERMINISTIC (no clock — `now` and state injected, groq_router.py:6-8) | SAFE (pure) |
| groq_accounts.account_states | DETERMINISTIC (pure aggregation) | SAFE |
| groq_accounts.snapshot_from_registry | NONDETERMINISTIC (live registry reads, groq_accounts.py:64-66) | SAFE (read-only) |
| map_prompt | DETERMINISTIC (same inputs ⇒ same prompt, map_prompt.py:99-100) | SAFE |
| map_trigger | NONDETERMINISTIC (db via conn, env flags, map_trigger.py:26-41, 49-61) | SAFE (idempotent upserts, restart-safe, :46-61) |
| profile_prompt_vnext | DETERMINISTIC (pure render, :81-89) | SAFE |
| profile_scout | DETERMINISTIC (no I/O, no LLM, profile_scout.py:4-8, 86) | SAFE |
| served | NONDETERMINISTIC (injected index client, served.py:31-33) | SAFE (read-only) |

## failure behaviour
- `served.py:60` — `Exception` SWALLOWED → `return None`; caller sees `None`, and `served_vnext_count` then returns None = "index could not be read" (served.py:79-80); `apply_served` treats it as no served card (served.py:69-70).
- `groq_router.choose` raises `ValueError(f"unknown Groq work class: {work_class!r}")` — groq_router.py:105-106.
- `fuse_profile_scout_hits`: empty inputs → empty `ProfileScoutResult`; the caller fails open to normal retrieval — profile_scout.py:12-13, 86.
- `snapshot_from_registry`: a lane absent from the registry or lacking `capacity_snapshot` is silently skipped — groq_accounts.py:65-66.
- `build_vnext_profile_user_prompt`: empty fingerprint block renders as `(no document evidence)` — profile_prompt_vnext.py:83-84.

## dumb-code flags
- `RouteDecision.reason` comment lists only `"selected" | "all_locked" | "no_capacity" | "empty_pool"` (groq_router.py:57) but `choose` also returns `"rpd_exhausted"` (groq_router.py:147) — comment/code drift. [DERIVED]
- `choose`'s `max()` key carries a comment about negating the name (groq_router.py:124-126) but no name term in the key; the name tie-break is re-implemented as a separate tied-list + `min()` pass (groq_router.py:128-137) — duplicated tie-break logic. [DERIVED]
- `account_states` uses `min((...), default=0)` where `snaps` is always non-empty inside the loop — dead `default=0` (groq_accounts.py:42). [INFERRED: `by_account` values only exist via append]
- `build_map_prompt` accepts `is_combined` and ignores it — accepted for the worker's `infer` signature, not yet specialized (map_prompt.py:121-125). [DERIVED]
- `DEFAULT_RPM_CEILING = 4` vs the provider's 30 — deliberate target, not a bug (groq_router.py:31-32). [DERIVED]
- Prompt-version literals live in three places: `"doc-profile-v3.2"` (prompt.py:6), `"doc-profile-vnext-v1"` (profile_prompt_vnext.py:30), `"doc-profile-vnext"` prefix (served.py:20) — `served.writer_of` depends on the prefix matching the vnext version string. [DERIVED]

## refactor notes
- Tag vocabulary comes from `fingerprint` (`SOURCE_ANCHORED_FIELDS`, `ROUTING_INFERRED_FIELDS`, `RESEARCH_INDEX_TAGS`); `output_fields()` just concatenates them — changing `fingerprint.py`'s constants silently changes compiler tolerance and the vNext prompt contract (profile_prompt_vnext.py:23-28, 92-97).
- `WORK_CLASS_MODEL` is a closed vocabulary; adding a work class requires the map edit plus every caller that names classes (control/control/scheduler.py, workers — FACTS.importers; unknown key raises ValueError, groq_router.py:105-106).
- `STAGE`/`EVENT_TYPE` are baked into the `ticket_id` hash and the `pmap:{run_id}` idempotency key — renaming either strands in-flight pMAP tickets and events (map_trigger.py:21-22, 48, 56).
- `grounding=None` byte-identity with map-prompt v1 is a migration contract; any prompt text change must preserve it (map_prompt.py:36-39, 109-110).
- `ProfileNomination` deliberately carries no planner fields (`recommended_mode`, `required_subquery`, `must_use_graph`, `intent_override`, `answer_strategy`) — adding them turns the scout into a hidden planner (profile_scout.py:50-54).
- `prompt.py` (`doc-profile-v3.2`) is the live writer and `profile_prompt_vnext.py` its additive successor; the live prompt/compiler are deliberately untouched until the S8 switch (profile_prompt_vnext.py:14-17) — the two must not be merged casually.
- Selection policy constants (`DIRECT_SURFACES`, `DISCOVERY_SURFACES`, `PRESENCE_SURFACES`, `REGRESSION_RATIO = 0.5`, `SELECTION_VERSION = "canonical-profile-selection-v1"`) — selection.py:28-37 — are the compatibility identity of stored projection decisions.

## VERIFY
```verify
grep -Fq 'DEFAULT_RPM_CEILING = 4' shared/polymath_shared/document_profile/groq_router.py
grep -Fq 'rpd_exhausted' shared/polymath_shared/document_profile/groq_router.py
grep -Fq 'RRF_K = 60' shared/polymath_shared/document_profile/profile_scout.py
grep -Fq 'MAX_DOCUMENTS = 8' shared/polymath_shared/document_profile/profile_scout.py
grep -Fq 'MAP_PROMPT_VERSION = "map-prompt-v2"' shared/polymath_shared/document_profile/map_prompt.py
grep -Fq 'POLYMATH_DOC_PARENT_MAP_SINCE' shared/polymath_shared/document_profile/map_trigger.py
grep -Fq 'canonical-profile-selection-v1' shared/polymath_shared/document_profile/selection.py
grep -Fq 'doc-profile-vnext' shared/polymath_shared/document_profile/served.py
```
