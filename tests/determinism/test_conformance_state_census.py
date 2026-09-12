"""PRODUCTION-CONFORMANCE-AUDIT-V1 follow-up (2026-09-12) — two static-census bugs
found while manually investigating the 4 RETIRE_CANDIDATE state rows a live audit
run (--no-spend) produced, per the execution authority's retirement law ("neither
[static nor dynamic proof] alone is sufficient... never call something dead without
FILE:SYMBOL proof").

1. `reader_writer_census` excluded `docs/` and `tests/` from its git-grep scan,
   directly contradicting its own docstring ("over-counting readers only DELAYS a
   retirement, while under-counting enables a wrong deletion"). Measured false
   negative: `knowledge_tier_facts` — referenced by a real contract test
   (`tests/contracts/test_admission_boundary.py::test_...` asserts
   `"knowledge_tier_facts" in src`) and two docs — was reported as having ZERO
   readers/writers and classified RETIRE_CANDIDATE. It is load-bearing.
2. `durable_tables` selected from `information_schema.tables` without filtering
   `table_type`, so VIEWS (which hold no storage of their own) were audited
   alongside real tables and could be misread as reclaimable state.

Both tests run against this actual repository's real content — not a synthetic
fixture — because the bug IS the mismatch between the census and this repo's real,
already-known ground truth.
"""
from __future__ import annotations

from polymath_shared.conformance.evidence import reader_writer_census


def test_a_contract_test_reference_now_counts_as_a_reader():
    """Ground truth: tests/contracts/test_admission_boundary.py really does assert
    `"knowledge_tier_facts" in src`, and docs/SEMANTIC_CONTRACTS.md +
    docs/WAY_AHEAD.md really do document it. None of that may be silently dropped."""
    census = reader_writer_census(["knowledge_tier_facts"])
    readers = census["knowledge_tier_facts"]["readers"]
    assert any("tests/contracts/test_admission_boundary.py" in r for r in readers), readers
    assert any(r.startswith("docs/") for r in readers), readers


def test_claim_sets_has_no_code_reader_or_writer_anywhere():
    """claim_sets has genuinely zero CODE references anywhere outside its own
    CREATE TABLE statement (the real RETIRE_CANDIDATE this investigation confirmed,
    LEGACY-STATE-RETIREMENT-AUDIT-V1) — the census must still report it as code-
    reader-and-writer-free, i.e. this fix must not make the census over-eager and
    start inventing false positives. Doc mentions ARE expected and excluded from
    this assertion: this investigation's own work-log/register entries now name
    `claim_sets` by design (documenting that it's dead), which correctly makes it a
    doc "reader" per the fixed census — that's the fix working as intended, not a
    contradiction of "no code reads or writes it"."""
    census = reader_writer_census(["claim_sets"])
    code_readers = [r for r in census["claim_sets"]["readers"] if not r.startswith("docs/")]
    assert code_readers == [], code_readers
    assert census["claim_sets"]["writers"] == []
