# unit: adapters/ecommerce/python/intelligence.py
anchor: adapters/ecommerce/python/intelligence.py:1-406

## purpose
Commercial Intelligence layer (docs/11), shared by OPPORTUNITY_RESEARCH and NICHE_LOADOUT; turns research-graph truth into market/product/style/positioning/ad intelligence without re-reasoning facts — adapters/ecommerce/python/intelligence.py:2-5 [DERIVED].
φ role: θ generates angles/claims/briefs, this module admits them (lineage resolves, authority computed not trusted, duplicates/generic angles die, survivors selected as a SET); it may add intelligence objects only and can never touch hypotheses, observations, verdicts or research state — adapters/ecommerce/python/intelligence.py:9-15 [DERIVED].
CLI: `packet` builds sanitized θ inputs; `admit` validates/grades/dedupes/selects, then merges + mirrors to Work Graph — adapters/ecommerce/python/intelligence.py:17-20 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| admit | def | (state: dict, payload: dict, policies: dict) -> dict | adapters/ecommerce/python/intelligence.py:308-358 | — |
| build_packet | def | (state: dict) -> dict | adapters/ecommerce/python/intelligence.py:271-304 | — |
| select_angle_portfolio | def | (angles: list[dict], policies: dict, state: dict \| None = None) -> dict | adapters/ecommerce/python/intelligence.py:130-164 | — |
| admit_angles | def | (angles, key, state, policies) -> tuple[list[dict], list[str], list[dict]] | adapters/ecommerce/python/intelligence.py:87-127 | — |
| admit_claims | def | (claims, state, policies) -> tuple[list[dict], list[str], list[dict]] | adapters/ecommerce/python/intelligence.py:168-189 | — |
| admit_chains | def | (chains, state, policies) -> tuple[list[dict], list[str]] | adapters/ecommerce/python/intelligence.py:192-207 | — |
| admit_briefs | def | (briefs, admitted_angles, state, policies) -> tuple[list[dict], list[str]] | adapters/ecommerce/python/intelligence.py:210-227 | — |
| admit_storefront | def | (strategies, state) -> tuple[list[dict], list[str]] | adapters/ecommerce/python/intelligence.py:230-243 | — |
| admit_style | def | (style: dict \| list, state) -> tuple[list[dict], list[str]] | adapters/ecommerce/python/intelligence.py:246-267 | — |
| resolvable_ids | def | (state: dict) -> set[str] | adapters/ecommerce/python/intelligence.py:51-56 | — |
| genericness | def | (thesis: str, pol: dict) -> float | adapters/ecommerce/python/intelligence.py:70-78 | — |
| main | def | () -> int | adapters/ecommerce/python/intelligence.py:362-402 | CLI (`packet`/`admit` subcommands) — :17-20, :364-372 |

Private helpers: `_pol` :46-47, `_evidence_state` :59-63, `_word` regex `[a-z']+` :67, `_jaccard` :81-83. Constants: `INTEL_KEYS` :35-38, `ANGLE_KEYS` :39-40, `_ANGLE_TYPE_BY_KEY` :41-43.

## contracts

**admit(state, payload, policies) -> dict** — :308-358
- in: every payload key must be in `INTEL_KEYS` (10 keys: `market_analysis`, `style_intelligence`, `market_angles`, `product_angles`, `style_angles`, `collection_angles`, `ad_angles`, `creative_briefs`, `storefront_strategies`, `analysis_chains`) — :309-313, :35-38 [DERIVED]
- pre: `state` must contain `data`, `run_id`, `status` (direct indexing at :53, :274, :388) [DERIVED]
- out ok: `{"ok": True, "admitted": {key: count}, "receipts": [...], "angle_portfolio": {...}}` — :355-358 [DERIVED]
- out fail: `{"ok": False, "schema_errors": all_errors[:20]}` (truncated to 20) or illegal-key error with `"allowed": INTEL_KEYS` — :311-313, :346 [DERIVED]
- post: staged items merged into `state["data"][key]`, skipping ids already present — :348-351 [DERIVED]
- post: `state["angle_portfolio"]` recomputed over all `ANGLE_KEYS` data — :352-354 [DERIVED]

**admit_angles(angles, key, state, policies)** — :87-127
- pre: `models.validate(a, "angle")` passes; `angle_type` must equal `_ANGLE_TYPE_BY_KEY[key]`; every `evidence_refs` entry must resolve via `resolvable_ids(state)` — :95-101 [DERIVED]
- post: `evidence_state` is recomputed by `_evidence_state`; a differing θ claim yields an `AUTHORITY_RECOMPUTED` receipt — :106-110 [DERIVED]
- post: `disposition` ∈ `REJECT` (DUPLICATE_ANGLE or GENERIC_ANGLE receipt), `HOLD` (SPECULATIVE), or `ADVANCE` — :114-125 [DERIVED]

**_evidence_state(refs, known, pol)** — :59-63
- resolving-ref count `n >= int(pol.get("grounded_min_refs", 2))` → `"GROUNDED"`; `n == 1` → `"PARTIAL"`; else `"SPECULATIVE"` — :61-63 [DERIVED]

**genericness(thesis, pol)** — :67-78
- tokens via regex `[a-z']+`; empty thesis → `1.0`; score = `round(min(1.0, hits / len(toks)), 3)` where hits = phrase matches from `genericness_lexicon` + token matches — :71-78 [DERIVED]

**select_angle_portfolio(angles, policies, state=None)** — :130-164
- in: pool = angles with `disposition == "ADVANCE"` only — :140 [DERIVED]
- pre: when `state` is given, `size_max` is overwritten by `settings.effective(state, "report_angle_count", pol.get("size_max", 8))` — :136-139 [DERIVED]
- rule: greedy marginal gain of `w_cov * distinct(hook_type or angle_type) − w_red * pairwise thesis _jaccard`; `hook_coverage_weight` default `1.0`, `redundancy_penalty` default `0.8` — :141-148 [DERIVED]
- post: stops at `size_max` (default 8) or when gain ≤ 0 with `len(selected) >= size_min` (default 3); returns `{"selected": [ids], "covered_hooks": sorted(...), "size": n}` — :151, :158-159, :162-164 [DERIVED]

**admit_claims(claims, state, policies)** — :168-189
- pre: `models.validate(c, "analysis_claim")` passes; `evidence_refs` must resolve — :176-179 [DERIVED]
- post: `classification == "OBSERVED"` with no `evidence_refs` is downgraded to `"INFERRED"` with an `OBSERVED_DOWNGRADED` receipt — :184-187 [DERIVED]

**admit_chains / admit_briefs / admit_storefront / admit_style**
- chains: `models.validate(ch, "analysis_chain")`; every link named in policy `chain_links` must be present; `evidence` must resolve — :198-201 [DERIVED]
- briefs: `models.validate(b, "ad_creative_brief")`; `angle_id` must be an ADVANCE angle; `evidence_refs` must resolve — :216-222 [DERIVED]
- storefront: `models.validate(s, "storefront_strategy")`; `authority` computed as `"EVIDENCE_GROUNDED_ANALYSIS"` if any ref resolves, else `"CREATIVE_RECOMMENDATION"` — :234-241 [DERIVED]
- style: accepts dict or list; `id` required; `kind` defaults to `"observed"`; `kind == "observed"` requires ≥1 resolving ref (else error "mark kind=inferred"); `authority` = `"OBSERVED"` or `"CREATIVE_RECOMMENDATION"` — :254-265 [DERIVED]

**build_packet(state) -> dict** — :271-304
- out: projection of state — bridges from `hypotheses` (fields `id/path/target_mechanism/status/invariant`), observations (fields `id/quote_ref/source/community/evidence_roles/freshness`), products from `d.get("leads") or d.get("loadout") or d.get("product_candidates")` — :281-296 [DERIVED]
- out: `prompt_file: "prompts/commercial_intelligence.md"`, `output_contract` mapping every `INTEL_KEYS` key to `"list"`, plus the `law` string ("Creative claims may never exceed the evidence...") — :299-303 [DERIVED]

## effect surface
- Files read: `--state` via `models.load_state(args.state)` — :374; payload `--file` via `open`/`json.load` — :386-387 [DERIVED]
- Files written: packet to `--out` (UTF-8) or stdout — :378-384; state file overwritten in place via `models.save_state(state, args.state)` — :395 [DERIVED]
- Module calls: `graph.load_policies()` — :389; `memory.sync_work_nodes(run_id, state)` — :396; `memory.record_event(run_id, "INTELLIGENCE_ADMITTED", {... "policy_hash": memory.config_hashes()["policy_hash"] ...})` — :397-400; `settings.effective` — :138 [DERIVED]
- Import side effect: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` before importing `memory`/`models` — :30-33 [DERIVED]
- Postgres/Qdrant: none visible (`tables_read: []`, `tables_written: []` in FACTS) [DERIVED]

## invariants
INVARIANT: disposition values == {`REJECT`, `HOLD`, `ADVANCE`} only — :115, :118, :122, :124 [DERIVED]
  fails-if: portfolio pool filter `disposition == "ADVANCE"` (:140) silently drops any new disposition value.
INVARIANT: GROUNDED when resolving refs >= `grounded_min_refs` (default 2); PARTIAL == exactly 1; SPECULATIVE == 0 — :61-63 [DERIVED]
  fails-if: policy raising `grounded_min_refs` reclassifies existing PARTIAL claims without any receipt.
INVARIANT: angle REJECTed when `_jaccard(thesis, seen) >= dedupe_jaccard` (default `0.6`) — :113-116 [DERIVED]
  fails-if: threshold drift between policy file and this default changes which near-duplicates survive.
INVARIANT: angle REJECTed when `genericness >= genericness_reject` (default `0.34`) — :117-120 [DERIVED]
  fails-if: generic filler ("helps runners"-class theses) enters the ADVANCE pool.
INVARIANT: portfolio size <= `size_max` (default 8, overridden by user `report_angle_count`); early stop only when gain <= 0 AND size >= `size_min` (default 3) — :138-139, :151, :158-159 [DERIVED]
  fails-if: brief/report rendering gets fewer than 3 or more than the user's preferred count of angles.
INVARIANT: `(state["verdict"], state["status"])` identical before and after `admit`; asserted in `main` — :388, :393-394 [DERIVED]
  fails-if: AssertionError "intelligence admission altered the research verdict — refusing"; state file never saved (:395 is after the assert).
INVARIANT: merge appends only ids not already in `state["data"][key]` — :350-351 [DERIVED]
  fails-if: duplicate intelligence objects accumulate across repeated admit runs.
INVARIANT: payload keys ⊆ INTEL_KEYS (10 keys) — :309-313, :35-38 [DERIVED]
  fails-if: any research-state key in the payload aborts the whole admission with ok=False.
INVARIANT: admission is all-or-nothing — the schema_errors return (:346) precedes the merge loop (:348) [DERIVED]
  fails-if: partial merges would leave half-validated intelligence in canonical state.
INVARIANT: brief `angle_id` ∈ ids of ADVANCE angles from the same payload call — :213, :217-219, :322, :333 [DERIVED]
  fails-if: briefs referencing angles admitted in an earlier call are rejected ("is not an ADVANCE angle").

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db in the unit; greedy argmax keeps the first pool item on ties (`if gain is None or gv > gain`, :156); outputs depend only on state + payload + policies dict (from `graphmod.load_policies()`, :389) and, for portfolio size, the user preference read via `settings.effective` (:137-139) [DERIVED]
idempotency: SAFE — re-admitting the same payload merges 0 new rows (id dedupe, :350-351) and only recomputes `state["angle_portfolio"]` (:352-354); each successful CLI run does append one new `INTELLIGENCE_ADMITTED` event (:397), so the event stream is not deduped [DERIVED]

## failure behaviour
- Illegal payload keys → `{"ok": False, "error": "intelligence layer cannot mutate research state: {illegal}", "allowed": INTEL_KEYS}`; `main` prints it and returns exit code 1 — :309-313, :390-392 [DERIVED]
- Any schema/lineage error → `{"ok": False, "schema_errors": all_errors[:20]}`; nothing is merged — :345-348 [DERIVED]
- Verdict/status mutation → AssertionError with message "intelligence admission altered the research verdict — refusing"; state not saved — :393-395 [DERIVED]
- θ's claimed `evidence_state` silently overwritten when it disagrees with the computed value (AUTHORITY_RECOMPUTED receipt, not an error) — :106-110 [DERIVED]
- OBSERVED claim without evidence_refs silently downgraded to INFERRED (OBSERVED_DOWNGRADED receipt), not an error — :184-187 [DERIVED]
- No try/except anywhere in the unit; a missing `--file` or invalid JSON raises from `open`/`json.load` — :386-387 [INFERRED: no handler visible in SOURCE]

## dumb-code flags
- `size_max` default `8` duplicated at :139 and :151 — changing one silently diverges from the other. [DERIVED]
- `select_angle_portfolio` with `state=None` skips the `report_angle_count` override (:136-139) — same function, different cap for library vs CLI callers. [DERIVED]
- Magic truncation number `20` in two places: `all_errors[:20]` (:346) and `result["receipts"][:20]` (:400). [DERIVED]
- `genericness` mixes units: phrase hits (`" " in w and w in text`) + token hits, divided by token count — :76-78. [DERIVED]
- Verdict guard is an `assert` (:393) — compiled out under `python -O`. [INFERRED: assert semantics]
- Dedup memory `seen_theses` only records ADVANCE theses (:125), so a thesis matching a HOLD/REJECT angle is never deduped against it — :112-125. [DERIVED]
- Error-prefix literals re-hardcode INTEL_KEYS names: `"market_analysis["` :181, `"analysis_chains["` :204, `"creative_briefs["` :224, `"storefront_strategies["` :236, `"style_intelligence["` :255. [DERIVED]
- `"CREATIVE_RECOMMENDATION"` literal duplicated in `admit_storefront` (:241) and `admit_style` (:265). [DERIVED]
- Receipt coverage inconsistent: `admit_chains`/`admit_briefs` return no receipts (:207, :227) while `admit_angles`/`admit_claims` do (:127, :189). [DERIVED]
- Docstring claims `report_angle_count` "caps size within schema bounds" (:134, :137) but code applies no upper clamp beyond `int()` — :138-139. [INFERRED: no clamp visible]

## refactor notes
- `INTEL_KEYS`/`ANGLE_KEYS`/`ANGLE_TYPE_BY_KEY` (:35-43) are the θ wire contract, echoed back as `"allowed"` (:313) and driving `output_contract` (:300); renaming any key changes the `prompts/commercial_intelligence.md` expectations (:299).
- `admit_briefs` accepts only angle_ids from the same call's ADVANCE accumulator (:314, :322, :333, :217-219); supporting previously-admitted angles requires rebuilding `advanced` from `state["data"]` instead of the per-call list.
- `main` asserts verdict/status immutability before `models.save_state` (:388-395) and mirrors via `memory.sync_work_nodes` + `INTELLIGENCE_ADMITTED` event whose payload reads `result["admitted"]` and `result["receipts"]` (:396-400) — changing the result dict shape (:355-358) breaks the event consumer.
- `resolvable_ids` scans every list value in `state["data"]` (:52-56) and is re-invoked by each `admit_*` family member — cost grows linearly with state size.
- Sibling imports `memory`, `models`, `settings`, `graph` depend on the `sys.path.insert` at :30-33, :137, :363 — moving this file breaks all four imports.

## VERIFY
```verify
grep -Fq 'grounded_min_refs' adapters/ecommerce/python/intelligence.py
grep -Fq 'pol.get("dedupe_jaccard", 0.6)' adapters/ecommerce/python/intelligence.py
grep -Fq 'pol.get("genericness_reject", 0.34)' adapters/ecommerce/python/intelligence.py
grep -Fq '"prompt_file": "prompts/commercial_intelligence.md"' adapters/ecommerce/python/intelligence.py
grep -Fq 'INTELLIGENCE_ADMITTED' adapters/ecommerce/python/intelligence.py
grep -Fq 'report_angle_count' adapters/ecommerce/python/intelligence.py
test "$(grep -c -F 'CREATIVE_RECOMMENDATION' adapters/ecommerce/python/intelligence.py)" -ge 2
! grep -Fq 'INSERT INTO' adapters/ecommerce/python/intelligence.py
```
