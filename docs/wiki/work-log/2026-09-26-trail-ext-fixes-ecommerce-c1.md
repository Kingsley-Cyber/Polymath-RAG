---
change_id: TRAIL-EXT-BUGHUNT-V1-FIXES-ECOMMERCE-C1
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Ecommerce batch C (binding.py / executors.py / adapter_receipt.py / query_semantics.py share). Fixed: B-31, B-32, B-33, B-34, B-35, B-52, B-54, B-55, B-60. Skipped: B-64 (owner decision + manifest wiring). Code commit 2337bc53."
architecture_impact: "adapters/ecommerce/binding.py (context-tag grammar, supply join, field records, lineage word lists, product-reality blank-search guard), adapters/ecommerce/python/executors.py (_gap_keywords in any script, supplier dedupe per listing), adapters/ecommerce/python/adapter_receipt.py (supplier-lane tags), adapters/ecommerce/schemas/supplier_candidate.json (+concept_id, channel, intent_id); tests: test_adapter_ecommerce_supply_join.py, test_adapter_ecommerce_field_records.py, tests/contracts/test_ecommerce_query_words.py (new), two pinned counters updated."
last_reviewed: 2026-09-26
---

# TRAIL-EXT-BUGHUNT-V1 fixes, ecommerce batch C: the supply join, the lived world's inputs, words in any script

## Contract
- TRAIL-EXT-BUGHUNT-V1 findings (docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md), batch C, this group's share:
  B-31, B-35, B-52, B-54, B-60, B-64 (binding.py), B-33, B-34 (executors.py), B-32 (adapter_receipt.py), B-55 (query_semantics.py).
  Rules: handoff `bugfix_rules.md` (fail-first test per fix, narrow fix; never edit lived_world.py, report.py, graph.py, bridge.py,
  product_reality.py — the second batch-C helper's files — nor the runtime group's; dead `POLYMATH_PG_DSN`; never `git stash`).

## Changes
- **B-31 — the lineage law names a word written as an object.** Population nomination reads `frictions`, `shared_predicates` and
  `communities` as words. `_op_validate_primitives` now says `primitives.frictions[0]: expected a string` (or `expected a list of
  strings`), so reasoning corrects it. Nomination itself stopped crashing on these shapes in batch A (B-01, `lived_world._strs`).
- **B-32 — the receipt builder's supplier lane carries the join's tags.** `adapter_receipt._supplier_items` appends
  `channel:`, `concept:` and `intent:` from the candidate; `schemas/supplier_candidate.json` declares `concept_id`, `channel`,
  `intent_id` (optional; the schema has no `additionalProperties: false`).
- **B-33 — one listing = one candidate.** `executors.supplier` keys its dedupe on (concept, URL, title, supplier): the price and MOQ
  observations of one listing merge, and the first fills a price or MOQ it lacks from its twin; the same title under another
  concept or at another URL is another listing. `supply.leads` counts `joined.merged_duplicates` and names each lead's own
  observation (the lookup also compares the concept).
- **B-34 — the concept tag.** `supply.leads` reads `pc_1 (heated glove liner)` / `PC_1` as `pc_1`; a tag naming no concept is counted
  (`joined.unknown_concept`), left to name overlap, and listed in the new `unjoined` output when nothing resolves it.
- **B-35 — the channel.** `_supply_channel`: the tag normalised (`CJ Dropshipping` / `CJdropshipping` = `cjdropshipping`, so the
  default MOQ 1 applies), else the site the URL belongs to (`m.alibaba.com`, `app.cjdropshipping.com`); a first host label only for
  a site the engine does not know.
- **B-52 — the context-tag grammar.** `_context_field`: a title (`listing:` / `product:`) keeps its `|` and `;` and ends at ` · `, a
  line break, or a separator that starts a known tag. A tag whose every occurrence follows the title is read at its last occurrence
  (the writer's own, after the title); a tag written before the title at its first. Contexts without a title read as before.
- **B-54 — TrailSignal's per-hypothesis relation in the lived world.** The single-hypothesis case was fixed in batch B (B-11). Now a
  record linked to several hypotheses keys the cluster of one TrailSignal says it SUPPORTS before one it contradicts, and every
  field record carries `contradicts_hypothesis_ids`.
- **B-55 — words in any script.** `executors._gap_keywords` (behind `query_semantics.keywords`) tokenises by Unicode category after
  NFC: `fotógrafos` stays one word; Chinese and Japanese runs stay whole; kana, CJK and Hangul words count from 2 characters. ASCII
  text tokenises exactly as before (pinned). `product_reality.plan` reports a job whose search compiled to no word as unresolved
  (`missing: market_phrase`) instead of issuing an empty template. `query_semantics.py` needed no change.
- **B-60 — TrailSignal's duplicates.** A record `duplicate_of` another stays in `field_records` (citable, flagged) but is never a
  second record, thread or voice in the lived world; `joined.duplicates` counts them.

## Proof
- Environment of every run: `POLYMATH_PG_DSN` and `POLYMATH_TEST_DSN` on a dead port (`postgresql://nobody@127.0.0.1:1/none`); every
  determinism file grepped first for a hard-coded fallback (only `test_adapter_service_store.py`, which reads the variable first).
- Fail first: a scratch export of `1a21b31f` with the 3 new test files on top, run on that export's own packages (no `git stash`):
  17 failed, 4 passed — the passes are controls (2 code-location checks, a lawful interpretation, a tag written before the title).
  With the fix: 21 passed.
  - `tests/determinism/test_adapter_ecommerce_supply_join.py` (9: B-32, B-33, B-34, B-35, B-52).
  - `tests/determinism/test_adapter_ecommerce_field_records.py` (9: B-31, B-54, B-60).
  - `tests/contracts/test_ecommerce_query_words.py` (3: B-55).
  - Two existing assertions that pin the exact `joined` counters gained the new zero counters
    (`test_adapter_ecommerce_lived_world.py`, `test_adapter_ecommerce_products_supply.py`, one line each).
- `tests/contracts -k "not test_live_"`: 324 passed (incl. the engine's own `tests/run_all.py`, which pins the supplier dedupe and
  the price / MOQ parsers).
- 27 adapter / Trail determinism files (every `test_*adapter*` / `test_*trail*` except the two fleet-database files and
  `test_adapter_harness_action.py`, which skips only when the DSN is unset; `test_http_routes_are_thin_wrappers` deselected): 264
  passed, 5 skipped (`test_adapter_service_store.py`'s database tests on the dead port).
- `scripts/agent_preflight.py`, `scripts/repo_guard.py`, `scripts/wiki_worm.py --check`: exit 0.
- ruff (HEAD copy vs working copy of every changed Python file): no new findings (38 now vs 39 before); the new test files are clean.

## Contract dispositions
- `scripts/contract_impact.py`: CONTRACT IMPACT: none. No changed file maps to an architecture contract.
- ADAPTER_RUNTIME: NOT_AFFECTED (no path of it changed; the DOMAIN_OPERATION protocol is unchanged). Outputs gained additive keys:
  `supply.leads` `joined.unknown_concept`, `joined.merged_duplicates`, `unjoined`; `population.evidence_cards` `joined.duplicates`,
  field records' `contradicts_hypothesis_ids` and `duplicate_of`.
- The adapter manifest `config/adapters/ecommerce.product_research.json`: TESTED_UNCHANGED (not edited; the e2e, embedded-Trail,
  dossier and fidelity suites that drive it pass).
- The engine schema `adapters/ecommerce/schemas/supplier_candidate.json`: UPDATED (three optional fields). The deployed Hermes copy
  drifts from the repo until the next deploy (`adapters/ecommerce/tests/mirror_check.py`), as with every engine change.

## Rejected claims
- None of the ten findings was rejected.
- B-64 (skipped, not rejected): the governed binding deliberately takes the batch as a pure function of C_population's output
  (`_op_population_nominate` docstring: the engine's stateful `queue` is not used). Advancing it per round changes which populations
  rounds 2-3 research (a behaviour a person would notice) and needs manifest wiring the binding cannot supply (J_cards' lead statuses
  and the prior intent index into H_plan, the batch into I_research's materials — `config/adapters/`, the runtime group's). The
  finding itself notes no effect on search today (S-17 drops lead intents over the cap).

## Open contract gaps
- **B-64 (owner decision)**: per-round lead batches — decide, then wire in the manifest and return lead statuses from J_cards.
- **Second batch-C helper's files** (reported, not edited):
  - B-31: `lived_world.validate_primitives` (the standalone controller's path) lacks the word-list check the binding now applies.
  - B-55: `lived_world._toks` is still ASCII-only (lead VOI, seed matching, corpus-question words). A lead with no word of 3+ letters
    (e.g. "VR users") still compiles blank channel queries at nomination, which `research.plan` would issue as empty templates.
  - B-34: `product_reality.join` counts an annotated concept tag as unknown rather than normalising it.
  - B-54: `lived_world.cards` clusters by community x friction family, so two hypotheses sharing a family share a cluster; the new
    `contradicts_hypothesis_ids` lets it drop a record from a hypothesis it contradicts.
- **B-52 (runtime / owner)**: a title can still inject a tag the writer never wrote (e.g. a `concept:` when the harness wrote none).
  Closing that needs structured tags in the receipt contract and the harness guide (`shared/polymath_shared/adapter/harness_guide.py`).
