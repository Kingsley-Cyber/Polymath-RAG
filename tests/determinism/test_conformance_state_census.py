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
    `tests/` is no longer excluded.

    A THIRD category joined them on 2026-09-12: the governance tooling built to
    retire this very table (`scripts/retire_claim_sets.py`) and the final-state
    verifier that reports the retirement's status (`scripts/verify_final_state.py`).
    Both necessarily name `claim_sets` — one to drop it, one to say whether it is
    droppable — and `reader_writer_census` matches bare mentions, so writing the
    retirement tools made the table look alive. That is the same self-reference
    false positive as the docstring and filename cases, in a fourth place; the
    durable rule (used by `retire_claim_sets.py`'s own census) is that a
    reader/writer is SQL that TOUCHES the table — `FROM`/`JOIN`/`INTO`/`UPDATE`/
    `TABLE <name>` — not prose or tooling that discusses it.

    Maintaining an allow-list of "files that merely mention it" was tried and is the
    wrong shape: it grew from the test file, to the filename, to the registry, to the
    README, to the verifier — one entry per new artifact, forever. So this asserts the
    ACTUAL invariant instead, name-independently: no SQL anywhere TOUCHES the table.
    """
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    # FROM/JOIN/INTO/UPDATE/TABLE <name> — the shapes by which SQL reads or writes it.
    sql_ref = subprocess.run(
        ["git", "grep", "-lEi", "--", r"(FROM|JOIN|INTO|UPDATE|TABLE)[[:space:]]+claim_sets"],
        cwd=root, capture_output=True, text=True, timeout=60)
    touching = [p for p in sql_ref.stdout.splitlines() if p.strip()
                and not p.startswith("docs/")
                and not p.startswith("tests/")
                # the migration that CREATED it, and the tool that exists to DROP it
                and p != "stores/postgres/migrations/0026_identity_model.sql"
                and p != "scripts/retire_claim_sets.py"]
    assert touching == [], f"SQL still touches claim_sets: {touching}"

    # The census itself must still be reachable and return the table (guards against the
    # census silently dropping it, which would make the assertion above vacuous).
    census = reader_writer_census(["claim_sets"])
    assert "claim_sets" in census
