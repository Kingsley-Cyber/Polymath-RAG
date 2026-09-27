---
change_id: TRAIL-EXT-BUGHUNT-V1-FIXES-ECOMMERCE
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Ecommerce adapter bug-hunt fixes. Fixed: B-01, B-07, B-08, B-09 (binding side), B-10, B-11, B-12, B-13, B-14, B-16 (report side). Skipped: B-15 (owner decision; its binding half landed with B-09). The halves that live in config/adapters/ and shared/polymath_shared/adapter/ belong to the runtime group and are listed under Open contract gaps."
architecture_impact: "adapters/ecommerce/binding.py (law verdicts never crash, bridge law vs ledger, unique ids, per-hypothesis polarity), adapters/ecommerce/python/{lived_world,bridge,ideation,executors,product_reality,adapter_receipt,report}.py; tests: tests/determinism/test_adapter_ecommerce_domain_laws.py (new), tests/contracts/test_ecommerce_price_parse.py (new), tests/contracts/test_ecommerce_dossier_report.py (new), additions to test_adapter_ecommerce_products_supply.py, test_adapter_product_reality.py, test_adapter_ecommerce_lived_world.py."
last_reviewed: 2026-09-26
---

# TRAIL-EXT-BUGHUNT-V1 fixes: the ecommerce adapter (lived world, product reality, bridge, binding, executors, ideation, dossier)

## Contract
- TRAIL-EXT-BUGHUNT-V1 findings (docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md), group `ecommerce`:
  Batch A (crash) B-01; Batch B (wrong results) B-07 … B-16. Rules: handoff `bugfix_rules.md` (fail-first test per finding,
  narrow fix, no edits to the runtime group's files `shared/polymath_shared/adapter/`, `workers/`, `config/adapters/`).

## Changes
- **B-01 — a law never crashes on a shape the manifest leaves open.** A crash of the out-of-process binding is recorded as
  STEP_EXECUTOR_ERROR: the run FAILS and the repair branch never runs.
  - `lived_world.validate_primitives` / `validate_relevance_map` / `lineage_ref_errors` name the bad shape as a law error:
    `evidence_refs` not an object, a refs value not a list, a `{kind, id}` ref, a relevance class written as an object,
    `row_relevance` as a list, a latent structure / corpus observation that is not an object, a non-list of them.
  - `bridge.validate_hop_refs`: `hop_refs` not an object, or a hop's refs not a list of id strings, is a bridge error.
  - `binding._op_validate_situations`: the law judges the situations whose shape `models.validate` accepts (a list
    `cluster_id` or object `refs` is already a schema error); the well-formed ones are still judged.
  - `lived_world._corpus_nominations` / `_registry_nominations` (C_population, not a law): a lead's frictions / activities /
    contexts / evidence refs written as one string become a list of one; objects are skipped. A friction written as an
    object names no registry family.
- **B-08 — the same for `products.validate_concepts`, and a net under every law.** `_mechanisms` no longer hashes a
  list `hypothesis_id`; the law says `mechanisms[i].hypothesis_id: expected one live hypothesis id string`. `binding.handle`
  turns a TypeError / AttributeError / KeyError / ValueError raised inside one of the four law operations
  (`LAW_VERDICTS`) into that law's unlawful verdict with a `shape:` error, so the manifest branches back to reasoning.
  Every other operation still crashes loudly.
- **B-07 — one id names one concept and one mechanism.** `ideation.validate_concepts` refuses a repeated concept id;
  `_op_validate_concepts` refuses a repeated mechanism id. A repeat that still reaches `supply.plan`,
  `product_reality.plan`, `product_reality.join` or `supply.leads` is a typed refusal `CONCEPT_IDS_NOT_UNIQUE`.
- **B-09 — the bridge law compares the bridges with the ledger.** `_op_validate_bridge` always names two bridges for one
  hypothesis. Given `live_hypotheses` (= `context.hypotheses`) it also names a bridge for a hypothesis that is not live, a live
  hypothesis without a bridge, and a live count outside the portfolio bounds. The new output flag `portfolio_unreachable`
  says no bridge can repair that. The manifest does not pass `live_hypotheses` yet (see Open contract gaps).
- **B-10 — a price is USD only when it is USD.** `executors._parse_price` reads an amount stated in US$ / USD where it
  stands (`¥18.50 (≈ US$2.60)` → 2.60), refuses every other X$ dollar (HK$, NZ$, A$, C$, CA$, AU$, S$, SG$, NT$, R$ …) as
  well as the existing non-USD markers, and a bare-`$` range keeps its upper end (`$3.20 - $4.10` → 3.20–4.10). The receipt
  builder's USD metric uses the same parser.
- **B-11 — TrailSignal's per-hypothesis relation (ADR-069).** `adapter_receipt.polarity_for` mirrors Trail's
  `relation_polarity`. `product_reality.join` contests a concept by the relation to THAT concept's hypothesis and stores that
  polarity on the product row. `_field_records_from_admissions` sets `contradicts` (and a new `polarity`) from the relation to
  the hypothesis that keys the record's cluster. The dossier counts and the Polarity column use it too (below).
- **B-12 — the dossier shows a qualification's state.** `report.py` renders `state` (then `verdict` / `status` for older
  records), each gate `observed/minimum passed|unmet`, and the open-gap count. `_qualifications` also flattens a
  `qualifications_by_step` list (every qualify stage), one record once, market delta before supply.
- **B-13 — Field + / − as TrailSignal counts it.** The hypothesis row counts every admitted FIELD-stage record linked to the
  hypothesis, duplicates excluded, by Trail's relation to that hypothesis (`field_counts_from: ADMISSIONS`); the view's
  24-row sample is used only when the result carries no admission. Open gaps = the view's open ledger gaps plus every
  open ledger-origin gap the loop recorded (`unresolved_research_gaps`); the row says `open gaps (N)` and `(+k more)`.
- **B-14 — absent, not zero.** A terminal gap / failed / cancelled run whose result carries no step outputs no longer shows
  "admitted 0 · rejected 0" beside a lineage of admitted ids: the Field Observations header names the admitted ids the lineage
  holds and says their records are not in the result; TrailSignal's Record says the outputs are absent.
- **B-16 — Unresolved leads with the loop's open questions; no silent cuts.** Unresolved = `unresolved_research_gaps`
  (question — hypothesis (origin)), then `remaining_uncertainty`, then harness limitations, uncut in the model. The steps'
  `unknowns` are a separate counted list (`governed.unknowns`). Leads, clusters, situations and the Unresolved list say
  "showing N of M" when the page cuts them.

## Proof
- Fail first: the 37 new tests were run against the unfixed sources (the 8 changed engine files at HEAD, the new tests in
  place): 34 failed, 3 passed (three control cases that pin lawful inputs). With the fix: all pass.
  - `tests/determinism/test_adapter_ecommerce_domain_laws.py` (23: B-01, B-08, B-09), through the real `exec_domain` with
    the binding out of process.
  - `tests/determinism/test_adapter_ecommerce_products_supply.py` +3 (B-07); `test_adapter_product_reality.py` +1 and
    `test_adapter_ecommerce_lived_world.py` +1 (B-11).
  - `tests/contracts/test_ecommerce_price_parse.py` (3: B-10, incl. the receipt builder's metric).
  - `tests/contracts/test_ecommerce_dossier_report.py` (6: B-11 column + counts, B-12, B-13, B-14, B-16), each rendering a
    synthetic journal through the engine's own `report` module, out of process.
- `tests/contracts -k "not test_live_"`: 321 passed (incl. the engine's own `tests/run_all.py` via
  `test_ecommerce_engine_import.py`).
- Adapter / Trail determinism files (25 files: every `test_*adapter*` / `test_*trail*` except the two fleet-database files and
  `test_adapter_service_store.py`, plus the new file): 246 passed, 1 skipped. `test_adapter_service_store.py` was not re-run
  (see the note under Rejected claims).
- `scripts/agent_preflight.py`, `scripts/repo_guard.py`, `scripts/wiki_worm.py --check`: exit 0.
- ruff (apples-to-apples, HEAD copy vs working copy of every changed file): no new findings (61 now vs 62 at HEAD); the
  three new test files are clean.

## Contract dispositions
- `scripts/contract_impact.py --files <changed files>`: CONTRACT IMPACT: none. No changed file maps to an architecture contract.
- ADAPTER_RUNTIME: NOT_AFFECTED (no path of it changed; the DOMAIN_OPERATION request/response protocol is unchanged; law
  outputs gained the additive keys `portfolio_unreachable` and a field record's `polarity`).
- The adapter manifest `config/adapters/ecommerce.product_research.json`: TESTED_UNCHANGED (not edited; the e2e, embedded-Trail,
  dossier and fidelity suites that drive it pass).

## Rejected claims
- None of the eleven findings was rejected; B-15 is skipped for an owner decision, not rejected.
- Note for the gate list: `tests/determinism/test_adapter_service_store.py` connects to the fleet Postgres through its default
  DSN (`POLYMATH_PG_DSN` unset → `127.0.0.1:5432/polymath`) and writes and deletes probe runs. At baseline (before any change
  here) `test_worker_leases_claim_renew_release_and_expire` failed at the lease-expiry claim. It was not re-run after the fix
  (no database writes); nothing in this change touches `service` / `store`.

## Open contract gaps
- **B-15 (owner decision)**: C_hypotheses allows 1–8 hypotheses while the bridge portfolio law needs 3–6, and
  `C_bridge_route` only loops back to C_bridge. Either tighten C_hypotheses (minItems 3 / maxItems 6, `budgets.max_hypotheses`
  6) or route `steps.C_bridge_law.output.portfolio_unreachable == true` to C_hypotheses (or straight to Z_refuse_bridge).
- **Runtime group (config/adapters/, shared/polymath_shared/adapter/)**:
  - B-09: add `"live_hypotheses": "context.hypotheses"` to `C_bridge_law.config.inputs` — until then only the duplicate check runs.
  - B-12: replace the plain `qualifications` include of X_compile (ecommerce.product_research.json and trail.product_discovery.json)
    with `{"collect_all": "qualifications", "as": "qualifications_by_step"}` (report.py already reads it), or flatten in
    `service._compile_result`; today R_qualify's market-delta records never reach the result.
  - B-14: `service.result()` should compile a terminal run without a stored result with `output=None` (gather the includes).
  - B-13 / B-11: `semantic_view` clips `knowledge_gaps` to the first 12 BEFORE the open filter, and its `field_evidence` rows
    (from `evidence_boundary._index_rows`) mix stages and carry only the global polarity; they should filter open gaps first and
    carry `hypothesis_relations`.
  - B-01 / B-08 (defense in depth): type the fields the laws index in the manifest output schemas (C_primitives evidence_refs /
    row_relevance / latent_structures / population_leads, K_situations items, C_bridge hop_refs, N_concepts
    mechanisms[].hypothesis_id), so a bad shape gets a 422 at submit and spends no branch loop.
- A record NEUTRAL for the hypothesis that keys its cluster still counts as a cluster voice (`lived_world.cards` drops only
  `contradicts`); left as is.
