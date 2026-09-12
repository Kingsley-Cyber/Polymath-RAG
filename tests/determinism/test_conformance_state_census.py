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
    """claim_sets has genuinely zero real-code references anywhere outside its own
    schema-creating migration (the RETIRE_CANDIDATE LEGACY-STATE-RETIREMENT-AUDIT-V1
    confirmed) — the census must still report it as free of code readers/writers,
    i.e. this fix must not make the census over-eager and start inventing false
    positives.

    Two kinds of expected self-reference are excluded below, neither a
    contradiction of "no code reads or writes it": doc mentions (this
    investigation's own work-log/register entries name the table by design,
    documenting that it's dead, and one necessarily quotes the exact migration
    phrasing that created it — exactly the fix working as intended, over-counting a
    doc is harmless), and THIS TEST FILE ITSELF, which necessarily contains the
    table's name and that same migration phrasing as plain text/fixture values, not
    a real SQL reference — now caught by both the reader and writer scan since
    `tests/` is no longer excluded."""
    this_file = "tests/determinism/test_conformance_state_census.py"

    def _real_code(paths):
        return [p for p in paths if not p.startswith("docs/") and p != this_file]

    census = reader_writer_census(["claim_sets"])
    assert _real_code(census["claim_sets"]["readers"]) == []
    assert _real_code(census["claim_sets"]["writers"]) == []
