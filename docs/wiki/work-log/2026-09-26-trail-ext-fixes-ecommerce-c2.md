---
change_id: TRAIL-EXT-BUGHUNT-V1-FIXES-ECOMMERCE-C2
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Ecommerce adapter bug-hunt, batch C (second helper): lived world, bridge, graph, product reality, dossier. Fixed: B-36, B-37, B-39 (legacy half), B-40, B-58, B-61, B-62 (engine half; the binding half landed as B-60 in 2337bc53). Skipped for an owner decision: B-38, B-59. Rejected: B-39's ecommerce half (unreachable)."
architecture_impact: "adapters/ecommerce/python/{bridge,graph,lived_world,product_reality,report}.py; tests: tests/determinism/test_adapter_ecommerce_law_edges.py (new), tests/contracts/test_ecommerce_dossier_labels.py (new), tests/contracts/test_ecommerce_policy_overlay.py (new). No file of the runtime group (config/adapters/, shared/polymath_shared/adapter/, workers/) and none of binding.py / executors.py / adapter_receipt.py / query_semantics.py was edited."
last_reviewed: 2026-09-26
---

# TRAIL-EXT-BUGHUNT-V1 fixes: ecommerce batch C, second helper (lived world, bridge, graph, product reality, dossier)

## Contract
- TRAIL-EXT-BUGHUNT-V1 findings (docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md), batch C ("live but low severity,
  or latent"), group `ecommerce`: B-36, B-37, B-38, B-39, B-40, B-58, B-59, B-61, B-62. Rules: handoff `bugfix_rules.md` (a test that
  fails on the unfixed code per finding, a narrow fix; reject with evidence; skip what needs an owner decision). Branch
  `fix/trail-ext-bugeco2` from `feat/fix-it-all` at `82692183`. The files `binding.py`, `executors.py`, `adapter_receipt.py` and
  `query_semantics.py` belong to the other batch-C helper (`fix/trail-ext-bugeco`) and were not edited.

## Changes
- **B-36 — the bridge law and the dossier read the evidence boundary one way.** `bridge.validate_hop_refs` strips
  `first_inference_at` exactly as `validate_bridge` does. Read raw, a trailing newline made the boundary "not a hop" there while
  `validate_bridge` admitted it: the hop-ref check returned `[]`, the bridge was admissible with no hop refs, and the dossier tagged
  every hop evidence-backed. A boundary that names no hop is now an error of its own ("hop_refs cannot be checked — …") instead of
  a silent pass. `report._first_inferred_hop` (the governed transduction AND the standalone Reasoning Bridge) compares stripped hops
  with the stripped boundary; a boundary that names no hop tags every hop inferred.
- **B-37 — what the substitute job finds counts for every sibling.** `product_reality.plan` issues ONE substitute job per hypothesis
  (under its first concept, with `applies_to_concepts`); `join` attached its finds to the tagged concept only. Now a product whose
  `intent:` tag names a substitute job counts for every concept of that job's `applies_to_concepts` that exists and shares the
  tagged concept's hypothesis. Each product row carries `applies_to_concepts` (the tagged concept first); `concept_reality` reads it
  and the dossier lists the product under each such concept. A product found by a concept's own job, or with no `intent:` tag,
  still counts for its tagged concept only. `intent_for` is unchanged: the join keys the expansion on the job the harness names, so
  the harness keeps ONE `concept:` tag (a multi-id tag would be unreadable to the join, which would count it UNKNOWN_CONCEPT).
- **B-39 — the legacy dossier names the listing's supplier.** In `build_model_from_governed`'s legacy branch (a result without
  `sourcing_coverage`, e.g. `trail.product_discovery`): the supplier is the observation's `supplier:` tag — a placeholder (`None`,
  `unknown`, `unresolved …`) names nobody, the binding's own S-06 rule — else "not named on the listing"; TrailSignal's independence
  group (the platform) stays the channel only. A metric under another name than the receipt builder's `unit_price_low` /
  `minimum_order_quantity` is shown raw (`listing metric: unit_price 3.2 USD`) instead of only "price not parsed".
- **B-40 — What the Field Actually Said.** Field-stage admitted records only (never a product-reality or supply row), a TrailSignal
  duplicate once. The label is the observation's `community:` tag, else the source host, else the source class — never the
  independence group. Each quote carries `polarity`, `stage` and `contradicts` (the hypotheses it contradicts by TrailSignal's
  relation, ADR-069); the page marks them ("contradicts hyp_…"). The 14 are taken in turn from the contradicting records and the
  others, each in admission order, so admission order can no longer crowd a contradicting voice out.
- **B-58 — the loadout overlay extends the policies, never replaces one.** `graph.load_policies` merges `loadout_policies.yaml` block
  by block; a key both files declare raises `yaml.YAMLError` (the loader's own "fail closed, never last-wins"). `portfolio` now
  holds policies.yaml's hypothesis-portfolio law (min/max_hypotheses, max_exploratory, distinct_target_mechanisms,
  min_lived_anchored) beside the loadout selection keys that `executors.portfolio_gate` and `loadout_math` read, unchanged. No verdict
  changes today: the laws' hard-coded fallbacks equal the shipped values.
- **B-61 — a FIELD_ANCHORED situation cites its own cluster.** `lived_world.validate_situations`: every FIELD_OBSERVATION ref of a
  FIELD_ANCHORED situation must be one of its cluster's `record_ids`. `cards()` keeps contradicting records out of every cluster, so
  a contradicting record is refused by the same rule. RECONSTRUCTED and SIMULATED situations keep the documented contract (docs/25
  §4: known refs).
- **B-62 — a TrailSignal duplicate never counts toward an anchor (engine half).** `lived_world.cards` skips a record carrying
  `duplicate_of` (TrailSignal's own rule: duplicates are left out of qualification and scoring). The binding half — carrying
  `duplicate_of` into the field record — is `binding.py` (not this helper's file); it landed as B-60 in `2337bc53` on
  `fix/trail-ext-bugeco`, which also filters duplicates before `cards()`. Once both branches merge, the governed path is covered by
  both, and the engine rule covers every other caller.

## Proof
- Environment of every run: `POLYMATH_PG_DSN` and `POLYMATH_TEST_DSN` set to a dead port (`postgresql://nobody@127.0.0.1:1/none`),
  never unset; `PYTHONPATH` = this worktree's shared / orchestrator / workers / control (`polymath_shared` resolves in the worktree).
  No `git stash`; no call to the live system, a database or an LLM.
- Fail first: the 19 new tests were laid on a `git archive` export of the unfixed parent `82692183` and run with that export's own
  packages: 17 failed, 2 passed (the checkout check and the RECONSTRUCTED control). One of the 17 (the concept-own-job control of
  B-37) fails there only on the new `applies_to_concepts` field. With the fix: 19 passed.
  - `tests/determinism/test_adapter_ecommerce_law_edges.py` (9: B-36, B-61, B-62, B-37) — one operation at a time through the real
    `exec_domain`, the binding out of process.
  - `tests/contracts/test_ecommerce_dossier_labels.py` (7: B-36 dossier, B-37 dossier, B-39, B-40) — synthetic journals and a
    standalone state rendered out of process through the engine's own `report` module.
  - `tests/contracts/test_ecommerce_policy_overlay.py` (3: B-58) — the checkout's policies, and scratch copies whose YAML the test edits.
- `tests/contracts -k "not test_live_"`: 373 passed (incl. the engine's own `tests/run_all.py` via `test_ecommerce_engine_import.py`).
- Adapter / Trail determinism files (25: every `test_*adapter*` / `test_*trail*` except `test_adapter_worker_registration.py`,
  `test_adapter_product_discovery_loop.py`, `test_adapter_service_store.py`, `test_adapter_harness_action.py`; each grepped first
  for `5432` / `polymath-dev`, none found): 255 passed. The other determinism files that drive the ecommerce engine
  (`test_semantic_restoration_gate.py`, `test_conformance_agnostic.py`, `test_autoresearch_harness_contract.py`,
  `test_autoresearch_sources_harness.py`, `test_worker_call_sites_merged.py`): 58 passed.
- `scripts/agent_preflight.py`, `scripts/repo_guard.py`, `scripts/wiki_worm.py --check`: exit 0.
- ruff (HEAD copy vs working copy of each changed file): bridge 0/0, graph 0/0, lived_world 3/3, product_reality 1/1, report 10/10;
  the three new test files are clean.
- Contract dispositions: `scripts/contract_impact.py --files <changed files>` → CONTRACT IMPACT: none. ADAPTER_RUNTIME NOT_AFFECTED
  (the DOMAIN_OPERATION protocol is unchanged; `product_reality.join` rows gained the additive key `applies_to_concepts`). The
  manifest `config/adapters/ecommerce.product_research.json`: TESTED_UNCHANGED.

## Rejected claims
- **B-39, ecommerce half** (the `or "supply"` label fallback in the `sourcing_coverage` branch): unreachable, so not changed.
  `binding._op_supply_leads` sets each lead's `admitted_evidence_id` from the supplier candidate whose id IS the admitted id,
  matched on url + product_name, which `executors.join_leads` copies unchanged — the role lookup always resolves. The finding's
  own skeptic refuted this half.
- **B-62, the `product_reality.join` part of the fix sketch** (skip `duplicate_of` rows there too): not done. TrailSignal's duplicate
  key is (independence group, normalised claim); the concept tag lives in the observation context, not the claim. The same claim
  recorded for a second concept is marked a duplicate, and that row can be the only link from the product to the second concept —
  skipping it would drop the link. The join makes no count TrailSignal scores.
- **B-37, the `intent_for` part** (state the siblings so the harness can tag them): not needed and not done — see Changes.

## Open contract gaps
- **B-38 (owner decision)**: the lived-anchor laws (`require_lived_anchor`, `min_lived_anchored`) run only when
  `inputs.lived_clusters` is a list; the one `hypotheses.validate_bridge` step (`C_bridge_law`) runs before `J_cards` with inputs
  {corpus_evidence, hypotheses}, so in governed runs `anchor_errors` is always `[]`. Either add a post-research law step (after
  `J_cards`, before `N_jobs`) that passes `lived_clusters` and let `K_revise` set `lived_anchor_ids` / `grounding` (a manifest
  change), or set `require_lived_anchor: false` for governed runs and record the gap. `validate_hypothesis_anchors` still counts an
  unused `anchored`.
- **B-59 (owner decision; runtime file)**: `exec_domain` (`workers/workers/adapter_step_worker.py`) records only `binding_sha256`
  in `_domain`, and every DOMAIN_OPERATION re-reads `graph/policies.yaml` + `graph/loadout_policies.yaml`: a policy edit or deploy
  between two steps of one run changes a law's verdict with an identical `_domain`. Proposal: record `domain_sha256` over binding.py +
  python/*.py + graph/*.yaml, pin it at the run's first DOMAIN_OPERATION, and on a later mismatch return a typed gap
  `DOMAIN_DRIFT` (or record a drift warning). Refusing a run that spans a deploy is a behaviour change, hence the owner.
- **B-61 scope**: a FIELD_OBSERVATION friction of a RECONSTRUCTED situation may still cite a contradicting record (docs/25 §4
  admits any known ref there). Tightening that is a contract change beyond the finding.
- `binding._op_product_reality_join`'s docstring still says a contested concept's "siblings are untouched" — true now only for a
  product found by a concept's own job (B-37). `binding.py` belongs to the other helper.
