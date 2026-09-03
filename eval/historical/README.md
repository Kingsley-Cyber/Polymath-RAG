# eval/historical — the syntax-interpreter (GLiNER + spaCy) evaluation harnesses

Moved here under LLM-DIRECT-CANON (ADR-0017, 2026-09-03). These harnesses
prove properties of the retired span-tagger path and MUST NOT be read as
evidence about the production LLM-direct path:

- `replay_full.py` — ledger → settlement → facts replay over the
  sentence-slice manifest (`sentence_slices` is empty under llm_live).
  Superseded by `eval/v5/replay_llm_direct.py` (raw-response ledger).
- `shadow_settlement.py` — shadow identity settlement over the same
  interpreter view.
- `retrieval_validation.py` — retrieval graded against "top admitted fact
  tuples" (self-consistency). Superseded by `eval/v5/holdout/` (answers to
  gold questions).

They are kept runnable for forensics on corpora that still carry the
interpreter view; none is wired to a release gate.
