# unit: adapters/ecommerce/python/lived_world.py
anchor: adapters/ecommerce/python/lived_world.py:1-812

## purpose
LIVED-WORLD-V2 (docs/25) — population discovery BEFORE product ideation: nominate leads, hand the agent one VOI-ranked batch per round, recompute evidence cards/clusters, gate rounds, validate lineage (`adapters/ecommerce/python/lived_world.py:1-21` [DERIVED]). Deterministic φ owns every step; "No LLM calls, ever. Same input state + policies → same output." (`adapters/ecommerce/python/lived_world.py:20` [DERIVED]).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| nominate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:269-293 | Executor python.population_nominate (docstring, :270) [DERIVED] |
| queue | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:372-388 | Executor python.population_queue (:373) [DERIVED] |
| cards | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:420-499 | Executor python.evidence_cards (:421) [DERIVED] |
| gate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:503-538 | Executor python.population_gate (:504) [DERIVED] |
| compile_corpus_questions | def | (state, policies) -> str | adapters/ecommerce/python/lived_world.py:743-777 | Executor python.corpus_question_compiler, on_enter of corpus_mechanisms (FACTS doc) [DERIVED] |
| anchor_threshold | def | (state: dict, policies: dict) -> dict | adapters/ecommerce/python/lived_world.py:83-95 | — |
| all_leads / lead_by_id | def | (state) -> list[dict] / dict | adapters/ecommerce/python/lived_world.py:73-79 | — |
| rank_leads | def | (state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:314-345 | nominate (:289), eligible_leads (:351) [DERIVED] |
| eligible_leads | def | (state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:348-357 | queue (:377), gate (:521) [DERIVED] |
| ensure_lead_queries | def | (state, policies) -> int | adapters/ecommerce/python/lived_world.py:360-369 | queue (:375) [DERIVED] |
| friction_key | def | (wording) -> str | adapters/ecommerce/python/lived_world.py:412-417 | cards (:452) [DERIVED] |
| lineage_ref_errors | def | (refs, state, relevance, label) -> list[str] | adapters/ecommerce/python/lived_world.py:542-565 | validate_primitives (:599, :603, :608) [DERIVED] |
| validate_relevance_map | def | (rel: dict, state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:568-579 | validate_primitives (:588) [DERIVED] |
| validate_primitives | def | (prim, state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:582-618 | "the controller's submit path and the governed binding" (:583-584) [DERIVED] |
| merge_relevance | def | (state, rel) -> None | adapters/ecommerce/python/lived_world.py:621-627 | — |
| validate_leads | def | (items: list[dict], state) -> list[str] | adapters/ecommerce/python/lived_world.py:631-642 | — |
| validate_records | def | (items, state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:645-655 | — |
| validate_situations | def | (items, state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:658-702 | — |
| validate_hypothesis_anchors | def | (hypotheses, state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:705-728 | — (docs/25 §5 per FACTS doc) |
| validate_portfolio_anchors | def | (hypotheses, state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:731-739 | — |
| summary | def | (state) -> str | adapters/ecommerce/python/lived_world.py:781-802 | — |

## contracts

**anchor_threshold(state, policies) -> dict** `:83-95`
- in: `policies["lived_world"]["anchor_threshold"]` overrides; optional `settings.effective(state, "lived_world.anchor_{key}", None)` for `min_records`/`min_threads`/`min_independent_voices` `:85-92`
- post: defaults `min_records=5, min_threads=2, min_independent_voices=3`; run settings may only TIGHTEN: `base[key] = max(int(base[key]), int(val))` `:86,:92`
- pre: settings module optional — missing settings keeps the floor `:93-94`

**nominate(state, policies) -> str** `:269-293`
- in: `state["data"]` keys `signal`, `communities`, `primitives`, `latent_structures`, `corpus_evidence` `:99-107,:138,:177,:233,:247`
- effect: five lanes — SIGNAL + CORPUS + LATENT + REGISTRY + FIELD_RECORDS `:274-276`; dedupe on `lead["id"]` and `name.strip().lower()` `:280-283`; compiles `channel_queries` `:284`; appends to `population_leads`/`community_leads` `:285-286`; calls `rank_leads` `:289`
- out: `"nominated N leads {lane:count} (T total, S restate the seed population) — leads are places to look, never demand"` `:292-293`

**rank_leads(state, policies) -> list[str]** `:314-345`
- post: writes `lead["voi"]` on every lead; `voi = yield * missing * impact / cost` `:339`; missing by status: DROPPED/anchored 0.1, NOMINATED 1.0, EXHAUSTED 0.2, else `0.4 + 0.5 * max(0.0, 1 - recs/min_records)` `:327-335`; impact `0.5 + 0.5 * min(1.0, len(toks & vocab)/3.0)` `:337`; cost `max(0.5, len(channel_queries)/4.0)` `:338`; `seed_population` → `voi *= float(lw.get("seed_population_discount", 0.5))` `:340-341`
- out: ids sorted by `(-voi, lead_id)` `:344`

**eligible_leads(state, policies) -> list[str]** `:348-357`
- post: `NOMINATED`, or `INSTANTIATED` and no ANCHOR cluster and `int(rounds_visited) < 2` `:354-355`

**queue(state, policies) -> str** `:372-388`
- effect: `batch = eligible_leads(...)[: int(lw.get("batch_size", 4))]` `:377`; batch leads → `status="INSTANTIATING"`, `rounds_visited += 1` `:379-381`; writes `state["population_queue"] = {round: prev.round+1, batch, started_at: prev.started_at or now(), batch_queries, remaining_eligible}` `:382-385`

**cards(state, policies) -> str** `:420-499`
- pre: records with `contradicts` or `duplicate_of` excluded (gap B-62) `:425`
- effect: participant cards per `(platform, author_key)` `:429-444`; clusters per `(_norm_community, friction_key(friction_family))` `:450-452`; cluster label = most common wording, ties by first occurrence `:456-458`; independence = governed `independence_group` count when all records carry one, else `_ver.independence_groups(items)["independent_groups"]` `:461-464`
- post: `d["participant_cards"]`, `d["lived_clusters"]` overwritten `:486-487`; leads: `record_ids` refreshed, `INSTANTIATING` → `INSTANTIATED` (has records) or `EXHAUSTED` `:493-496`
- out: `"{N} participant cards, {M} clusters ({A} ANCHOR, {T} THIN) from {R} records — threshold {thr}"` `:498-499`

**gate(state, policies) -> str** `:503-538`
- post: `cont = need and not reasons`; `need = anchors < int(lw.get("min_anchor_clusters", 2))` `:520,:533`; stop reasons: anchors satisfy min, `max_rounds` default 3 `:526`, stagnation (`stagnation_rounds` default 1) `:519,:528`, `wall_clock_minutes` default 45 `:529`, no eligible leads `:531`
- effect: writes `state["population_loop"]` `{continue, rounds, anchors, records, elapsed_min, remaining_eligible, reason}` `:534-536`

**friction_key(wording) -> str** `:412-417`
- post: lowercase, `_`→space, `_FRICTION_STOP` dropped, `_stem` applied, sorted, space-joined; empty → `"unassigned"` `:415-417`

**lineage_ref_errors(refs, state, relevance, label) -> list[str]** `:542-565`
- pre: refs must be list/tuple; each ref a plain `str` `:551-556`
- post: corpus row UNCLASSIFIED → error (fail-closed); IRRELEVANT → "dead for lineage"; ref must exist among corpus_evidence / observations / field_records / lived_clusters / latent_structures / corpus_observations `:548-564`

**validate_primitives(prim, state, policies) -> list[str]** `:582-618`
- checks: relevance map well-formed `:588`; `latent_structures`/`corpus_observations` schema via `models.validate(x, "latent_structure"|"corpus_observation")` `:596-603`; `evidence_refs` obeys lineage law `:604-608`; `frictions`/`shared_predicates`/`communities` must be lists of strings (gap B-31) `:611-617`
- unreadable shape → error string, never a crash (gap B-01) `:589`

**merge_relevance(state, rel) -> None** `:621-627` — updates `state["data"]["row_relevance"]` and stamps `r["relevance"]` on matching corpus rows.

**validate_leads / validate_records** `:631-642, :645-655`
- lead: COMMUNITY needs `community_key` or `platform`; status only `NOMINATED`; authority only `LEAD` `:636-641`
- record: `_ver.admit_observations(items, policies)` contract + `lead_id` must be a known lead `:648-652`; `quote_ref` required `:653`

**compile_corpus_questions / summary** `:743-777, :781-802` — bodies not in provided SOURCE; per FACTS: compiles corpus questions (on_enter of corpus_mechanisms), builds summary.

## effect surface
- state["data"] writes: `population_leads`, `community_leads` append `:285-286`; `participant_cards`, `lived_clusters` `:486-487`; `row_relevance` `:625-627`
- state writes: `population_queue` `:382`, `population_loop` `:534`
- Postgres tables: none (FACTS tables_read/tables_written empty)
- function-local imports: `settings.effective` `:88`, `registry.load_snapshot()` `:140-141`, `executors._gap_keywords`/`channel_queries` `:257,:261`, `models.validate` `:585`
- clock: `_dt.datetime.now(_dt.timezone.utc)` `:515`
- network/subprocess/env flags: none visible

## invariants
INVARIANT: cluster authority ANCHOR ⟺ `len(items) >= thr["min_records"] and len(threads) >= thr["min_threads"] and ind >= thr["min_independent_voices"]` (defaults 5/2/3) — :467,:86 [DERIVED]
  fails-if: FIELD_ANCHORED situations get claimed on single-thread evidence.
INVARIANT: settings override ≥ floor, i.e. `max(int(base[key]), int(val))` — :92 [DERIVED]
  fails-if: a run loosens the policy floor (docs/16 law violated).
INVARIANT: token length `>= (2 if _dense(word) else 4)`; seed word `>= (2 if dense else 5)` — :54,:60 [DERIVED]
  fails-if: dense-script seeds (CJK/Hangul/kana) fall below the ASCII keyword floor.
INVARIANT: batch size ≤ `int(lw.get("batch_size", 4))` — :377 [DERIVED]
  fails-if: fan-out the sequential controller cannot service.
INVARIANT: re-eligible INSTANTIATED lead has `rounds_visited < 2` — :354-355 [DERIVED]
  fails-if: exhausted leads cycle forever through the queue.
INVARIANT: every new lead has `authority="LEAD"`, `status="NOMINATED"`, `rounds_visited=0` — :125 [DERIVED]
  fails-if: a lead arrives pre-established, i.e. demand invented without records.
INVARIANT: records with `contradicts` or `duplicate_of` never count toward cards/clusters — :425 [DERIVED]
  fails-if: duplicates inflate record/thread/voice counts into fake ANCHORs.
INVARIANT: nominate adds a lead only when `id` unseen AND `name.strip().lower()` unseen — :280-283 [DERIVED]
  fails-if: duplicate leads split evidence across ids.
INVARIANT: LATENT lead queries use friction language (`expected_frictions[:2]` or post-colon name), never a group name — :249-251 [DERIVED]
  fails-if: unknown-population search degenerates into guessing group names.
INVARIANT: `lead["id"] = stable_id("lead", kind, lane, name.strip().lower())` — :123 [DERIVED]
  fails-if: renaming key material orphans every state reference to the old id.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `_dt.datetime.now(_dt.timezone.utc)` in gate :515 — FACTS nondeterminism, single entry) [DERIVED]; the clock only feeds `elapsed_min` and the wall-clock stop reason `:515,:529`; everything else is pure over state+policies per module claim :20 [DERIVED]
idempotency: SAFE for nominate (dedupe :280-283) and cards (full recompute, overwrite :486-487); UNSAFE for queue (each call increments `round` and `rounds_visited`, flips status to INSTANTIATING :379-385) [DERIVED]

## failure behaviour
- `anchor_threshold`: `except Exception: pass` — missing/broken `settings` silently ignored; caller receives floor defaults `:93-94` [DERIVED]
- `_registry_nominations`: `except Exception: snap = None` → returns `[]` — registry unavailable silently empties that lane `:142-145` [DERIVED]
- `gate`: `except ValueError: elapsed = 0.0` — unparsable `started_at` resets the wall clock `:516-517` [DERIVED]
- `validate_primitives`: unreadable shapes become error strings the agent can correct, never a crash `:589` [DERIVED]

## dumb-code flags
- Two different stop-word lists: `_STOP` :32-34 vs `_FRICTION_STOP` :398-399 (e.g. "about" only in `_STOP`; "the"/"and" only in `_FRICTION_STOP`) [DERIVED]
- Magic VOI weights: 0.1/1.0/0.2/0.4+0.5 :327-335; impact 0.5+0.5, /3.0 :337; cost floor 0.5, /4.0 :338; discount 0.5 :341; caps 6 :156,:232; defaults 4/3/2/1/45 :377,:526,:520,:519,:529 [DERIVED]
- `_stem` documented collisions: `"access" -> "acces"` :407, `"bounce"/"bouncing" -> "bounc"` :409 — distinct frictions can share a `friction_key` [DERIVED]
- `friction_key` empty fallback `"unassigned"` :417 collapses all empty wordings into one cluster key [DERIVED]
- Fallback refs literal `"primitives"` duplicated at :185 and :235 [DERIVED]
- `queue` calls `eligible_leads` twice in one call (:377 and :388); the second reflects post-INSTANTIATING statuses [INFERRED — statuses mutated at :379-381 between the calls]
- `gate` dead literal: `"; ".join(reasons) or "proceed"` — when `cont` is False, `reasons` is provably non-empty (`not need` appends a reason :523-524), so `"proceed"` never renders :533-536 [INFERRED]

## refactor notes
- Private cross-module reach: `_ex._gap_keywords` and `_ex.channel_queries` from `executors` :257,:261 — renaming executors internals silently blanks lead queries (the exact failure `ensure_lead_queries` was written to fix :360-363) [DERIVED]
- `stable_id` key material (`"lead"`/`"card"`/`"cluster"` tuples :123,:438,:477) is a persistence contract — changing it orphans existing state [DERIVED]
- `cards` couples card recompute, cluster recompute, and lead status transitions :486-496 — splitting it moves when INSTANTIATING→INSTANTIATED/EXHAUSTED happens [DERIVED]
- `anchor_threshold` keys are mirrored as settings names `lived_world.anchor_{key}` :90 — rename either side and overrides silently stop applying [DERIVED]
- `validate_primitives` has two documented callers (controller submit path + governed binding) :583-584 — signature changes hit both [DERIVED]
- state keys written here (`population_queue`, `population_loop`, `lived_clusters`, `row_relevance`) are read by rank/eligible/gate and the FIELD_ANCHORED validation path :349,:511,:621-627, docstring :15 [DERIVED]

## VERIFY
```verify
grep -Fq 'base.setdefault("min_records", 5); base.setdefault("min_threads", 2); base.setdefault("min_independent_voices", 3)' adapters/ecommerce/python/lived_world.py
grep -Fq 'anchor = (len(items) >= thr["min_records"] and len(threads) >= thr["min_threads"] and ind >= thr["min_independent_voices"])' adapters/ecommerce/python/lived_world.py
grep -Fq 'batch = eligible_leads(state, policies)[: int(lw.get("batch_size", 4))]' adapters/ecommerce/python/lived_world.py
grep -Fq 'elapsed = (_dt.datetime.now(_dt.timezone.utc) - started).total_seconds() / 60.0' adapters/ecommerce/python/lived_world.py
grep -Fq 'voi *= float(lw.get("seed_population_discount", 0.5))' adapters/ecommerce/python/lived_world.py
test "$(grep -c -F 'Executor python.' adapters/ecommerce/python/lived_world.py)" -ge 5
! grep -Fq 'openai' adapters/ecommerce/python/lived_world.py
```
