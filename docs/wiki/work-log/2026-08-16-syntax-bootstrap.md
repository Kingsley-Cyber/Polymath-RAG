---
change_id: syntax-bootstrap
owner: sidecar-cpu
date: 2026-08-16
status: complete
architecture_impact: adds-optional-sidecar-no-boundary-change
last_reviewed: 2026-08-16
---

# SYNTAX-BOOTSTRAP: spaCy syntax sidecar (install + wire only)

## Contract

Explicitly authorized gate (`AUTHORIZE SYNTAX-BOOTSTRAP`, 2026-08-16).
Infrastructure only: install an isolated, host-native spaCy syntax
sidecar and make its evidence available to the extraction layer behind
a feature flag that defaults to `disabled`.

In scope: `sidecars/spacy_runtime/` (own venv, never the root venv that
hosts GLiNER/PyTorch/MPS), `spacy[apple]==3.8.15` +
`en_core_web_sm==3.8.0` (NER disabled at load), a versioned
`syntax-evidence-v1` wire contract (tokens + noun chunks, offsets
relative to the supplied sentence text), health/ready with runtime
provenance (spaCy/thinc/thinc-apple-ops versions, backend, batch size),
registry entry on :8744, and an optional client wired into the extract
worker between GLiNER proposal and `build_candidates`.

Out of scope (explicitly prohibited by the authorization): any change
to extraction decisions, GLiNER, candidate pairs, fact acceptance, or
entity typing; spaCy NER; any I4R repair work.

The repository prohibition on "adding spaCy … without explicit
authorization" (CURRENT_STATE.md, Explicitly Prohibited Actions) is
satisfied by this named authorization; spaCy here is a syntax-evidence
source only, and GLiNER remains the only entity/relation proposal
model.

## Changes

- `sidecars/spacy_runtime/` — new sidecar runtime: `requirements.txt`
  (pinned spacy[apple]==3.8.15, en_core_web_sm==3.8.0 wheel URL,
  fastapi/uvicorn matched to the root venv, resolved thinc +
  thinc-apple-ops pins), `manifest.toml` (pinned model identity +
  weights digest), `server.py` (FastAPI, batched `nlp.pipe`, NER
  disabled with startup asserts, `/manifest` `/health` `/ready` `/infer`),
  `benchmark.py` (batch-size microbenchmark).
- `sidecars/spacy-syntax.toml` — registry entry (device cpu, owner
  sidecar-cpu, manifest :8744).
- `deployment/launchd/ai.polymath.spacy.plist` — supervision unit
  using the sidecar's own venv interpreter.
- `contracts/extraction/v1/syntax_evidence.schema.json` — public wire
  contract (request/response, offset invariants).
- `shared/polymath_shared/settings.py` —
  `SidecarSettings.syntax_provider` (`POLYMATH_SYNTAX_PROVIDER`,
  default `disabled`) and `spacy_url` (`POLYMATH_SPACY_URL`, :8744).
- `shared/polymath_shared/clients.py` — `SpacySyntaxClient`
  (SidecarClient subclass; validates the `syntax-evidence-v1` contract
  id on every response).
- `workers/workers/candidates.py` — `SentenceSlice.syntax` optional
  field (default None; nothing reads it in this gate).
- `workers/workers/extract_worker.py` — `_syntax_evidence()` called
  after pass A (same sentence slices GLiNER saw, one batched call per
  document), evidence attached per slice, runtime provenance recorded
  as a stage artifact when enabled; provider `disabled` executes no
  new code on the extraction path.
- `Makefile` — `setup-spacy`, `dev-spacy`; `.env.example` — new vars.
- `tests/integration/test_spacy_syntax_sidecar.py`,
  `tests/contracts/test_syntax_provider_gate.py`.
- Scaffold TREE, ARCHITECTURE_CHANGELOG.md, CURRENT_STATE.md refresh.

## Proof

- `make guards` green (repo guard validates TREE, work logs, deps).
- Unit/contract tests: `SpacySyntaxClient` contract validation,
  provider gate (disabled default = no HTTP, no syntax artifact;
  enabled + unreachable sidecar = loud failure; unknown provider =
  loud failure).
- Integration tests (POLYMATH_INTEGRATION=1, live sidecar): health
  provenance + NER-disabled proof, POS/lemma/dep/head present, noun
  chunks returned, exact-offset invariant
  (`sentence_text[start:end] == surface` for every token and chunk),
  batch identity/order preservation, duplicate-text independence.
- Regression with provider disabled: full pytest suite (Q1
  qualification lock byte-identical), integration suite, E3B verifier
  — no extraction output change.
- Microbenchmark: batch sizes 32/64/128/256 over I4-corpus-length
  sentences; default stays 128.

## Rejected claims

- No claim that spaCy syntax improves extraction: no extraction
  decision consumes the evidence in this gate.
- No spaCy entity usage of any kind: NER is disabled at load and
  asserted absent at startup and in health output.
- No multiprocessing claim: single process, `nlp.pipe` batching only
  (macOS spawn makes `n_process>1` counterproductive at sm scale).

## Open contract gaps

- The reconciliation/rescue layer that would consume
  `SentenceSlice.syntax` is future work and requires its own
  authorization (I4R posture unchanged; frozen I4 artifacts untouched).
- Weights digest is trust-on-first-use recorded then pinned in
  `manifest.toml` at install time; `POLYMATH_REQUIRE_PINNED=0`
  posture inherited from the other sidecars.
