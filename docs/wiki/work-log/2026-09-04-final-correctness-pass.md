---
title: "WORK LOG — TRAIL-SIGNAL v2.1.2: final correctness pass (research/)"
change_id: RESEARCH-FINAL-CORRECTNESS-V2.1.2
date: 2026-09-04
owner: governance
last_reviewed: 2026-09-04
last_touched: 2026-09-04
status: shipped
register: 11.74
package: research/
architecture_impact: "research/ only — canary semantics split (open-field vs LATENT resolution, explicit SOURCE_AGNOSTIC_CALIBRATION mode), corpus-presence receipt via existing /documents + /retrieve, deterministic field origin, fail-closed document scope, controller admission fixes (hop refs, empty submitted lists, terminal verdict), transitions law (all bridges dead → NO_DEFENSIBLE_BRIDGE), L4 dossier lanes. Graph topology, prompts' laws, Polymath API and extraction untouched. One data-provenance fix in corpus ecom-meta-v1 (mislabeled novel re-ingested under its real title)."
---

# WORK LOG — TRAIL-SIGNAL v2.1.2: final correctness pass

Owner directive (2026-09-04): verified defect → owning file → failing regression → minimum change → targeted pass → full harness → live calibration → freeze. No redesign, no new modes, no loosened invariants.

## Contract

- **Population canary split** (`research/tests/calibration_acceptance.py`): `open_field_population_discovery` (mandatory) and `latent_population_resolution` (LATENT lead + admitted structure + INSTANTIATED + admitted records whose `lead_id` points back; advisory in STANDARD, mandatory in SOURCE_AGNOSTIC_CALIBRATION). OPEN_FIELD never satisfies latent resolution.
- **Explicit calibration mode** `--calibration-mode STANDARD|SOURCE_AGNOSTIC_CALIBRATION`; `heterogeneous_source_reasoning` is NOT_EVALUATED in STANDARD and measures GENERATION (a relevant heterogeneous row fed a structure or a hop; death allowed) in the dedicated mode.
- **CorpusPresenceReceipt** (`research/python/provenance.py::corpus_presence`, `corpus_polymath.py --presence`): per final concept, from `GET /documents` (documents_checked) and `POST /retrieve` for the concept's normalized phrase; consumed by `lineage` and by the acceptance test; naming only, never demand.
- **Field origin** (`provenance.py::field_origin`): FIELD_NAMED / WORKAROUND_DERIVED / NOT_FIELD_ORIGINATED with a receipt; one generic token never establishes lineage; `field_originated = origin ∈ {FIELD_NAMED, WORKAROUND_DERIVED} AND not corpus-named`.
- **Document scope fails closed** (`corpus_polymath.py`): no advertised `document_ids` → `capability_failure {document_scoped_corpus_retrieval, BLOCKED_CAPABILITY_UNAVAILABLE}`, no request issued, `--generic` cannot bypass.
- **Receipt terminology**: `legitimate_echo_survival` → `legitimate_corpus_overlap_survival`; per-concept receipts expose `corpus_named`, `corpus_example_overlap`, `field_origin`.
- **Zero-product outcomes** (Law 12): concept canaries NOT_TRIGGERED, named in `not_triggered_mandatory`; NOT_EVALUATED never satisfies a mandatory canary.

## Changes

`research/tests/calibration_acceptance.py` (rewritten), `research/python/provenance.py`, `research/python/corpus_polymath.py`, `research/python/controller.py` (hop refs admit latent structures / observations; empty submitted list satisfies a node; `no_defensible_bridge` edge sets its verdict), `research/python/context.py` (`all_rejected` in the manifest instead of a deficit), `research/python/transitions.py` (all bridges dead → evidence sufficient), `research/python/evaluator.py` (dossier carries field-record and latent-structure lanes), `research/python/lived_world.py` (summary counts LATENT-lane leads), `research/python/utilization.py`, `research/python/report.py`, `research/graph/policies.yaml` (calibration classes), `research/docs/26_*.md` (§6, §8), `research/SKILL.md`, `research/manifest.yaml` (2.1.2), `research/WORKLOG.md`, `research/tests/run_all.py` (section 23, 555 checks), `scripts/repo_guard.py` (ignores the git-ignored evidence ledger), calibration receipts `research/docs/calibration/2026-09-04-books-run-01-regression.{md,json}` and `2026-09-04-novel-run-02.{md,json}`. Data: corpus `ecom-meta-v1` document `doc_d444fe46…` ("Alchemy (Sutherland)") deleted and the same bytes re-ingested as `Always_Alchemy_Hart.md` (`doc_57aab6bb…`, 1,514 chunks) with corrected title / author frontmatter.

## Proof

- `python3 research/python/controller.py doctor` → ok, errors [].
- `RUN_ALL_CONTINUE=1 python3 research/tests/run_all.py` → ALL 555 CHECKS PASSED; every item in section 23 was run failing against the previous implementation before its fix.
- Books regression (`2026-09-04-books-run-01-regression.md`): pass; corpus_independence / open_field / field_originated / irrelevant_source_rejection / hypothesis_death PASS; heterogeneous NOT_EVALUATED; latent resolution FAIL (advisory — 6 nominated, 0 instantiated in the baseline, which the old canary had hidden).
- Novel calibration (`2026-09-04-novel-run-02.md`, SOURCE_AGNOSTIC_CALIBRATION): pass; heterogeneous_source_reasoning PASS (81 novel rows, 7 relevant, 74 IRRELEVANT, 5 structures + 4 hypotheses fed), latent_population_resolution PASS (r/daddit, r/beyondthebump, r/Fosterparents — 30 records pointing back), irrelevant_source_rejection PASS, hypothesis_death PASS (2 field-caused); NO_DEFENSIBLE_BRIDGE.
- Mirror parity and CI receipts: `research/MIRROR_RECEIPT.json` (reference commit, standalone commit, drift []), GitHub Actions `research-harness` (Polymath) and `harness` / `tests` (standalone).

## Rejected claims

- "The books run proved LATENT → population → field" — it did not (0 LATENT leads instantiated); the split canary shows it.
- "An unrelated novel that yields nothing is a calibration failure" — rejected: any source MAY generate, no source MUST.
- "Not named in the retrieved rows means not named in the corpus" — rejected; the presence receipt audits the corpus.
- "One shared token is field lineage" — rejected (the keychain fob lost its field origin under the corrected law).
- "The novel-seeded run should be made to yield a product" — rejected; NO_DEFENSIBLE_BRIDGE on field contradiction is the honest result.

## Open contract gaps

- Run 02's persisted verdict label is `STOPPED_WITHOUT_QUALIFICATION` (the edge-verdict defect it exposed); terminal runs are immutable, so the label stands beside the deterministic disposition in the receipt.
- The presence audit is retrieval-sampled (the default lane's corpus-wide lexical scan), not a full-text scan; `method_version` records this.
- Pre-existing Polymath CI failures (determinism / contracts: `psycopg` missing in the runner; repo-governance wiki front matter) are outside `research/`; the two wiki front-matter items were fixed in this pass.
