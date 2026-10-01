# unit: adapters/ecommerce/python/lived_world.py
anchor: adapters/ecommerce/python/lived_world.py:1-781

## purpose
LIVED-WORLD-V2 (docs/25): deterministic population discovery BEFORE product ideation for the ecommerce adapter — nominates PopulationLead/CommunityLead objects (authority LEAD, "never demand"), VOI-ranks them into one sequential batch per round, recomputes participant evidence cards and lived clusters, gates rounds, and validates agent submissions under the lineage law — adapters/ecommerce/python/lived_world.py:1-21 [DERIVED]. Module law: "No LLM calls, ever. Same input state + policies → same output." — adapters/ecommerce/python/lived_world.py:20 [DERIVED]. Callers are the executor harness (python.population_nominate / population_queue / evidence_cards / population_gate / corpus_question_compiler) — adapters/ecommerce/python/lived_world.py:271,373,399,474,713 [DERIVED].
Note: repository material shows SOURCE only through :659; symbols at :660-781 are documented from FACTS metadata only.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| nominate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:269-293 [DERIVED] | executor python.population_nominate (:271) |
| queue | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:372-388 [DERIVED] | executor python.population_queue (:373) |
| cards | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:398-468 [DERIVED] | executor python.evidence_cards (:399) |
| gate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/lived_world.py:472-507 [DERIVED] | executor python.population_gate (:474) |
| compile_corpus_questions | def | (state: dict, policies: dict) -> ? | adapters/ecommerce/python/lived_world.py:712-746 [DERIVED] | executor python.corpus_question_compiler, on_enter of corpus_mechanisms (FACTS doc) |
| validate_primitives | def | (prim: dict, state: dict, policies: dict) -> list[str] | adapters/ecommerce/python/lived_world.py:551-587 [DERIVED] | controller submit path + governed binding (:552-553) |
| lineage_ref_errors | def | (refs, state: dict, relevance: dict, label: str) -> list[str] | adapters/ecommerce/python/lived_world.py:511-534 [DERIVED] | validators in this unit; — externally |
| validate_relevance_map | def | (rel: dict, state: dict, policies: dict) -> list[str] | adapters/ecommerce/python/lived_world.py:537-548 [DERIVED] | — |
| merge_relevance | def | (state: dict, rel: dict) -> None | adapters/ecommerce/python/lived_world.py:590-596 [DERIVED] | — |
| validate_leads / validate_records / validate_situations | def | (items: list[dict], state[, policies]) -> list[str] | adapters/ecommerce/python/lived_world.py:600-611 / 614-624 / 627-671 [DERIVED] | — |
| validate_hypothesis_anchors / validate_portfolio_anchors | def | (hypotheses, state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:674-697 / 700-708 [DERIVED] | — (beyond truncated source) |
| anchor_threshold | def | (state: dict, policies: dict) -> dict | adapters/ecommerce/python/lived_world.py:83-95 [DERIVED] | rank_leads, cards |
| all_leads / lead_by_id | def | (state: dict) -> list[dict] / dict | adapters/ecommerce/python/lived_world.py:73-75 / 78-79 [DERIVED] | — |
| rank_leads / eligible_leads | def | (state, policies) -> list[str] | adapters/ecommerce/python/lived_world.py:314-345 / 348-357 [DERIVED] | — |
| ensure_lead_queries | def | (state: dict, policies: dict) -> int | adapters/ecommerce/python/lived_world.py:360-369 [DERIVED] | queue (:375) |
| summary | def | (state: dict) -> ? | adapters/ecommerce/python/lived_world.py:750-771 [DERIVED] | — (FACTS only) |

## contracts
**nominate(state, policies) -> str** — adapters/ecommerce/python/lived_world.py:269-293
- in: reads `state["data"]` keys signal, communities, primitives, latent_structures, corpus_evidence, population_leads, community_leads (:99-107, :138, :174-189, :204, :271-277)
- pre: none enforced; missing keys tolerated via `or []` / `or {}`
- post: new leads appended to `population_leads` (POPULATION) or `community_leads` (COMMUNITY) (:285-287); each new lead gets `channel_queries` (:284); `voi` written on every lead via `rank_leads` (:289, :342)
- dedup: skip when lead id already known OR `name.strip().lower()` seen (:280-283)
- out: `"nominated {n} leads {dict(added)} ({total} total, {seeded} restate the seed population) — leads are places to look, never demand"` (:292-293)

**queue(state, policies) -> str** — adapters/ecommerce/python/lived_world.py:372-388
- in: `eligible_leads` order (VOI best-first); batch = first `int(lw.get("batch_size", 4))` (:377)
- post: batch leads → status `"INSTANTIATING"`, `rounds_visited` +1 (:380-381); `state["population_queue"]` = round+1, batch, `started_at` (prev or `now()`), batch_queries, remaining_eligible (:382-385)
- out: `"population round {round}: {len(batch)} leads to instantiate {names} ({batch_queries} channel queries) — VOI order, sequential"` (:387-388)

**cards(state, policies) -> str** — adapters/ecommerce/python/lived_world.py:398-468
- pre: field_records carrying `contradicts` or `duplicate_of` are excluded from everything (:403, gap B-62)
- post: `data["participant_cards"]` = one card per (platform, author) from `_ident` (:407-423); `data["lived_clusters"]` = one per (`_norm_community`, `friction_family` or `"unassigned"`) (:425-454); per-lead `record_ids` refreshed and INSTANTIATING → INSTANTIATED (has records) or EXHAUSTED (:462-465)
- out: `"{n} participant cards, {m} clusters ({a} ANCHOR, {t} THIN) from {r} records — threshold {thr}"` (:467-468)

**gate(state, policies) -> str** — adapters/ecommerce/python/lived_world.py:472-507
- rule: `cont = need and not reasons`; `need = anchors < int(lw.get("min_anchor_clusters", 2))` (:489, :502)
- stop reasons: rounds ≥ `lw.get("max_rounds", 3)`; stagnation (no new record/anchor and rounds > `lw.get("stagnation_rounds", 1)`); elapsed ≥ `lw.get("wall_clock_minutes", 45)`; no eligible leads (:488-501)
- post: writes `state["population_loop"]` = {continue, rounds, anchors, records, elapsed_min, remaining_eligible, reason} (:503-505)

**anchor_threshold(state, policies) -> dict** — adapters/ecommerce/python/lived_world.py:83-95
- floors: `min_records` 5, `min_threads` 2, `min_independent_voices` 3 (:86); `settings.effective` values may only tighten: `base[key] = max(int(base[key]), int(val))` (:92)

**_compile_lead_queries(lead, state, policies)** (internal, shared by nominate :284 and ensure_lead_queries :367) — adapters/ecommerce/python/lived_world.py:247-266
- LATENT leads search by `expected_frictions[:2]` or the name after ":" — never a group name (:249-251)
- if `_ex._gap_keywords(question)` yields nothing AND own_words is empty → zero queries (:257-260, gap B-55)

**validate_records** — adapters/ecommerce/python/lived_world.py:614-624: delegates roles×source×freshness to `_ver.admit_observations(items, policies)` (:617); `lead_id` must be a known lead (:620-621); non-empty `quote_ref` required — "a record without a recoverable quote is hearsay" (:622-623).
**validate_situations** — adapters/ecommerce/python/lived_world.py:627-671: FIELD_ANCHORED requires an existing cluster_id, cluster authority == "ANCHOR", ≥1 FIELD_OBSERVATION friction, and those frictions' refs inside the cluster's own record_ids (:646-659, gap B-61).
**lineage_ref_errors** — adapters/ecommerce/python/lived_world.py:511-534: corpus-row refs must be classified and not IRRELEVANT (fail-closed, docs/26 §2); non-corpus refs must exist among observations, field_records, lived_clusters, latent_structures, corpus_observations (:518-534).

## effect surface
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` both empty).
- Qdrant collections: none in this unit.
- Lazy imports: `settings` (:88), `registry` with `_reg.load_snapshot()` (:140-141), `executors` (:248), `models` (:554).
- Network / subprocess / env flags: none; "No LLM calls, ever" (:20) — adapters/ecommerce/python/lived_world.py:20 [DERIVED]
- State mutations (the real effect): `data.population_leads`/`community_leads` append (:285-287); per-lead `channel_queries` (:284, :367), `voi` (:342), `status`/`rounds_visited` (:380-381, :464-465), `record_ids` (:463); `data.participant_cards`/`lived_clusters` overwrite (:455-456); `state.population_queue` (:382-385); `state.population_loop` (:503-505); `data.row_relevance` + per-row `relevance` stamp (:591-596) — adapters/ecommerce/python/lived_world.py:284-296 [DERIVED]

## invariants
INVARIANT: anchor floors min_records=5, min_threads=2, min_independent_voices=3 ≤ any settings override (max-tighten only) — adapters/ecommerce/python/lived_world.py:86-92 [DERIVED]
  fails-if: a settings value below a floor is silently clamped up; a code change to `max` would let runs loosen the policy floor (docs/16 law).
INVARIANT: cluster authority == "ANCHOR" iff record_count ≥ min_records AND thread_count ≥ min_threads AND independent_voices ≥ min_independent_voices — adapters/ecommerce/python/lived_world.py:436,449 [DERIVED]
  fails-if: THIN evidence gets claimed as FIELD_ANCHORED via validate_situations (:646-653).
INVARIANT: records with `contradicts` or `duplicate_of` never reach cards, clusters, voices or threads — adapters/ecommerce/python/lived_world.py:403 [DERIVED]
  fails-if: duplicates inflate independent_voices/thread_count and a THIN cluster crosses the anchor threshold.
INVARIANT: `_toks` word floor len ≥ 4 (≥ 2 when `_dense`); `_seed_word` floor len ≥ 5 (≥ 2 dense) — adapters/ecommerce/python/lived_world.py:54,60 [DERIVED]
  fails-if: a 4-letter token counts toward vocab overlap (`impact`) but can never be a seed term — a lead restating the signal is not flagged `seed_population` and escapes the 0.5 discount.
INVARIANT: dense-script ranges are kana ぀-ヿ, CJK 㐀-鿿, Hangul 가-힣, compat ideographs 豈-﫿 — adapters/ecommerce/python/lived_world.py:40 [DERIVED]
  fails-if: non-covered scripts (e.g. Thai) get the 4-letter floor and CJK runs of 1 char are dropped.
INVARIANT: voi = source_yield (default 0.5) × missing × impact / cost; seed_population leads × `seed_population_discount` default 0.5; `voi` rounded to 4 — adapters/ecommerce/python/lived_world.py:339-342 [DERIVED]
  fails-if: ordering of the queue batch changes; sequential controller visits different leads.
INVARIANT: missing-info scores NOMINATED 1.0 > instantiated 0.4-0.9 > EXHAUSTED 0.2 > DROPPED/anchored 0.1 — adapters/ecommerce/python/lived_world.py:327-335 [DERIVED]
  fails-if: anchored or dropped leads outrank fresh ones and waste a batch slot.
INVARIANT: re-eligibility requires status NOMINATED, or INSTANTIATED and not anchored and `rounds_visited` < 2 — adapters/ecommerce/python/lived_world.py:354-356 [DERIVED]
  fails-if: a barren lead loops forever, or a promising one is dropped after one thin round.
INVARIANT: lead id = `stable_id("lead", kind, lane, name.strip().lower())`; nominated_by deduped, sorted, capped `[:10]` — adapters/ecommerce/python/lived_world.py:123-124 [DERIVED]
  fails-if: duplicate leads re-enter on name variants; cap change alters stored ids (blast radius: field_records.lead_id, cluster.lead_id).
INVARIANT: nomination caps default 6 for REGISTRY and LATENT lanes; batch_size default 4; gate defaults min_anchor_clusters=2, max_rounds=3, stagnation_rounds=1, wall_clock_minutes=45 — adapters/ecommerce/python/lived_world.py:156,232,377,488-499 [DERIVED]
  fails-if: policy dict omitting `lived_world` silently falls back to these literals everywhere.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `_dt.datetime.now(_dt.timezone.utc)` in gate elapsed — adapters/ecommerce/python/lived_world.py:484; `models.now` fallback for missing `started_at` in queue — adapters/ecommerce/python/lived_world.py:383, and in gate — adapters/ecommerce/python/lived_world.py:483; FACTS nondeterminism lists only :484) [DERIVED]
idempotency: SAFE — nominate (dedup by id + lowercased name — adapters/ecommerce/python/lived_world.py:280-283), cards (wholesale recompute overwrite :455-456), ensure_lead_queries (fills only missing :366-368); UNSAFE — queue (advances round and `rounds_visited`, flips status to INSTANTIATING :380-385), gate (elapsed_min grows with the wall clock :484) [DERIVED]

## failure behaviour
- `except Exception: pass` in anchor_threshold — settings module/values unavailable are SWALLOWED; caller sees the default floors {5, 2, 3} — adapters/ecommerce/python/lived_world.py:93-94 [DERIVED]
- `except Exception: snap = None` in _registry_nominations — registry load failure handled by assignment; function returns `[]`, so REGISTRY-lane leads silently vanish from the nominate summary — adapters/ecommerce/python/lived_world.py:142-145 [DERIVED]
- `except ValueError: elapsed = 0.0` in gate — malformed `started_at` disables the wall-clock stop reason — adapters/ecommerce/python/lived_world.py:485-486 [DERIVED]
- Malformed agent shapes become returned error strings, never exceptions ("a crash fails the run: gap B-01") — adapters/ecommerce/python/lived_world.py:558 [DERIVED]
- No error codes raised; all validators return `list[str]` errors for the caller to surface — adapters/ecommerce/python/lived_world.py:511-534,600-624 [DERIVED]

## dumb-code flags
- Comment/code mismatch: comment says "friction-only matches when no predicate hit" but the `for fam in fams:` loop appends seed indices unconditionally — adapters/ecommerce/python/lived_world.py:153-154 [INFERRED] (comment contradicts the unconditional loop right below it)
- Policy defaults duplicated between comparison and message string: `min_anchor_clusters` 2 (:489/:493), `max_rounds` 3 (:494/:495), `wall_clock_minutes` 45 (:498/:499) — adapters/ecommerce/python/lived_world.py:489-499 [DERIVED]
- `"FRICTION", "WORKAROUND", "ADAPTATION"` hardcoded at :239 re-lists members of `_LATENT_SEARCHABLE` (:220-222) — adapters/ecommerce/python/lived_world.py:239 [DERIVED]
- Private cross-module reach: `_ex._gap_keywords` — adapters/ecommerce/python/lived_world.py:257 [DERIVED]
- Platform hardcoded `"reddit"` in signal nominations and as default in field-record nominations — adapters/ecommerce/python/lived_world.py:196,211 [DERIVED]
- Two token floors (4 vs 5) between `_toks` and `_seed_word` — see invariant — adapters/ecommerce/python/lived_world.py:54,60 [DERIVED]

## refactor notes
- `_compile_lead_queries` depends on `executors._gap_keywords` (private) and `executors.channel_queries` (:248-262); renaming the private helper silently produces leads with zero queries — the exact bug `ensure_lead_queries` was added to patch ("a round handed out '4 leads, 0 channel queries'", :361-363) — adapters/ecommerce/python/lived_world.py:247-266,360-369
- `validate_primitives` has two callers ("the controller's submit path and the governed binding", :552-553); any signature/behaviour change hits both — adapters/ecommerce/python/lived_world.py:551-587
- `cards()` wholesale replaces `data.participant_cards` / `data.lived_clusters` (:455-456); anything else augmenting those lists loses its writes on every recompute — adapters/ecommerce/python/lived_world.py:455-456
- Lead status vocabulary NOMINATED / INSTANTIATING / INSTANTIATED / EXHAUSTED / DROPPED is spread across nominate/queue/cards/rank_leads/eligible_leads (:129, :326-333, :354-356, :380, :464-465); renaming one status breaks the others' branching — adapters/ecommerce/python/lived_world.py:326-356,380,464-465
- Lead ids feed `field_records.lead_id` and `cluster.lead_id`; changing the `stable_id("lead", kind, lane, name.strip().lower())` composition orphans existing references — adapters/ecommerce/python/lived_world.py:123,620-621,446
- SOURCE beyond :659 was truncated in this material; refactors touching validate_hypothesis_anchors (:674-697), validate_portfolio_anchors (:700-708), compile_corpus_questions (:712-746), summary (:750-771) need the rest of the file — adapters/ecommerce/python/lived_world.py:674-771 [INFERRED] (lines past the provided excerpt)

## VERIFY
```verify
grep -Fq 'base.setdefault("min_records", 5); base.setdefault("min_threads", 2); base.setdefault("min_independent_voices", 3)' adapters/ecommerce/python/lived_world.py
grep -Fq 'voi = yields.get(lead.get("source_lane"), 0.5) * missing * impact / cost' adapters/ecommerce/python/lived_world.py
grep -Fq 'lw.get("batch_size", 4)' adapters/ecommerce/python/lived_world.py
grep -Fq 'elapsed = (_dt.datetime.now(_dt.timezone.utc) - started).total_seconds() / 60.0' adapters/ecommerce/python/lived_world.py
grep -Fq 'anchor = (len(items) >= thr["min_records"] and len(threads) >= thr["min_threads"] and ind >= thr["min_independent_voices"])' adapters/ecommerce/python/lived_world.py
! grep -Fq 'import openai' adapters/ecommerce/python/lived_world.py
test "$(grep -c -F 'lw.get(' adapters/ecommerce/python/lived_world.py)" -ge 5
```
