# 21 — The utilization receipt and Polymath-native mode

Owner (2026-09-03): "make this polymath native while allowing the skill to
also work in any new versions or work in others … make it aware so it knows
its polymath and allow polymath to own certain things … test with a control
to see before and after what improves or changes."

## §1 The evidence-utilization receipt (the instrument)

`python/utilization.py::compute(state)` is pure and runs at `qualify`
(written to `data.utilization`), in `status` at qualify/stop, in
`triage-run --markdown` and in the report ("Evidence utilization"). It says
which evidence earned its keep:

- corpus: backend, mode (native | generic), version, plan source, rows by
  kind, rows with query provenance, distinct documents
- citations: primitives and hops by row kind, distinct corpus rows cited
- analogies by authority (SEED_HYPOTHESIS vs CORPUS_FACT_HYPOTHESIS)
- observations: total, by source family, by freshness, distinct threads,
  with query provenance, from corpus rows (`corpus_row_id`, step 3)
- gaps: by status, gaps with corpus support
- research rounds; leads across concepts and mechanisms; registry candidates

No Polymath-side change is promoted unless it moves this table against the
targets fixed in advance (owner plan 2026-09-03): typed rows ≥ 50 % of
corpus citations; ≥ 50 % of gaps with corpus support on a repeat signal;
30 % fewer fresh threads to reach the bar; rounds, verdict and suite unchanged.

## §2 Capability negotiation (aware, not dependent)

`python/corpus_polymath.py` probes `GET /capabilities` once per run. The
answer (or its absence) is recorded as `data.corpus_backend`
`{name, url, mode, version, contracts, plan_source, plan_ids?, plan_parity?}`
— an optional output of the `corpus` node — and every consumer switches on a
CONTRACT, never on the name:

| contract advertised | native behaviour | otherwise |
|---|---|---|
| `corpus-plan` + `retrieve-evidence-rows` | one `POST /retrieve/plan` per corpus; Polymath compiles the reformulations and returns rows with `query_ids`; the local plan (still compiled on entry) is checked for parity | local plan, per-query `/retrieve`, lane fallback (docs/18) |
| `typed-rows` (step 4) | primitives read typed claim rows | passage mining |
| `field-evidence-corpus` | the ledger corpus is appended to the run's corpora; rows carrying `FIELD_OBS` paragraphs are tagged `field_evidence`; `python3 python/field_evidence.py --state run.json --out cands.json` turns them into observation candidates for the current open gaps (same gap id on a repeat signal, keyword overlap otherwise) with the ORIGINAL author/thread identity, recomputed freshness and `corpus_row_id` — review, then submit at web_research; `--no-field-evidence` = control | — |

Rules: a backend with no `/capabilities` is served generically with no error;
a native call that fails outright falls back and records `native_error`;
`--generic` forces the docs/18 path against the same backend — that is the
control arm of every before/after. Both paths run in the harness against a
stub backend, and the frozen sample response and plan fixture are checked in
here (`tests/fixtures/`) and in Polymath (`contracts/retrieve/v1/`).

## §3 Ownership

Polymath owns: retrieval, the reformulation plan, extraction, memory (and
soon the field-evidence corpus and typed rows). TRAIL owns: what counts as
evidence (docs/04), allocation (docs/20), the bridge and portfolio laws
(docs/17, 19), sourcing per concept (docs/20), the receipt (this doc).
Neither repo imports the other; the contract and its fixtures are the seam.
