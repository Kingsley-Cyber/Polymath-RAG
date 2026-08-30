"""P23 SUMMARY-IDEMPOTENCY-V1 — logical job identity and summary authority.

TWO defects, one symptom, both measured on the live database.

CONTROL PLANE. `summary_jobs` had no uniqueness beyond the surrogate
`ticket_id`, and the ticket id is derived from the RUN
(`summary_worker_impl._stage_ticket`), so every run re-ticketed every
parent. Worse, the done-check was BY ticket_id — run-scoped, so it never
matched across runs and the work was re-executed every time.
MEASURED: 21,315 PARENT_SUMMARY tickets for 3,025 distinct input_hash
values — 7.0x, up to 12x for 533 hashes. The logical identity of summary
work is (stage, input_hash): same inputs and contract, same answer.

PERSISTENCE. `parent_summaries` had no notion of authority. summary_id
is content-addressed under ON CONFLICT (summary_id) DO NOTHING, so a
parent summarised before its entities were ready and again afterwards
kept BOTH rows with nothing saying which one counts. MEASURED: 3,025
rows for 1,784 parents; 1,241 parents held two rows written 4h15m apart
with different artifact_hash.

WHY IT BLOCKED THE REBUILD: P14 re-tickets every parent WHILE changing
contract generation, so the same mechanism could leave one parent
holding a v1 row and a v2 row at once — exactly the half-old/half-new
generation P13 exists to prevent — and would inflate P17's counts.

THE FIX IS IDENTITY AND AUTHORITY, not a read-site band-aid. A
`SELECT DISTINCT` or `ORDER BY created_at DESC LIMIT 1` would have hidden
the defect while leaving the pipeline able to produce two live rows.

APPLIED (migration 0039): summary_jobs 21,516 -> 3,063 rows (18,453
duplicate tickets collapsed); parent_summaries 1,784 authoritative rows,
exactly one per parent, 1,241 explicitly superseded and retained.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

WORKER = ROOT / "workers" / "workers" / "summary_worker_impl.py"
RUNTIME = ROOT / "shared" / "polymath_shared" / "summary_runtime.py"
MIGRATION = (ROOT / "stores" / "postgres" / "migrations"
             / "0039_summary_idempotency.sql")


def _pg():
    try:
        import psycopg
        return psycopg.connect(DSN, connect_timeout=3)
    except Exception:
        return None


pg_required = pytest.mark.skipif(_pg() is None, reason="postgres unavailable")


# ================================================ LOGICAL JOB IDENTITY
def test_done_check_uses_logical_identity_not_the_run_ticket():
    """THE CONTROL-PLANE DEFECT. Checking by ticket_id could never match
    across runs, because the ticket id is derived from the run."""
    src = WORKER.read_text()
    assert "def _job_done(conn: Connection, stage: str, input_hash: str)" in src, (
        "the done-check no longer keys on (stage, input_hash); work will "
        "be re-executed on every run")
    assert "WHERE stage=%s AND input_hash=%s" in src


@pytest.mark.parametrize("stage", ["PARENT_SUMMARY", "DOCUMENT_SUMMARY",
                                   "CORPUS_MAPPING", "VOCABULARY_MAPPING"])
def test_every_stage_checks_logical_identity(stage):
    """All four stages had the same bug. Fixing one is not fixing it."""
    src = WORKER.read_text()
    assert f'_job_done(conn, "{stage}", input_hash)' in src, (
        f"{stage} still decides completion from a run-scoped ticket")


def test_ticket_insert_is_an_upsert_on_logical_identity():
    src = WORKER.read_text()
    assert "ON CONFLICT (stage, input_hash) DO UPDATE" in src, (
        "a retry can still create a second job row instead of recording "
        "an attempt on the existing one")
    assert "attempts = summary_jobs.attempts + 1" in src


def test_migration_enforces_identity_in_the_database():
    """Convention at the callsite is not enforcement. Another writer, or
    a replay, must not be able to create the second row."""
    sql = MIGRATION.read_text()
    assert "CREATE UNIQUE INDEX" in sql and "summary_jobs (stage, input_hash)" in sql


# ==================================================== SUMMARY AUTHORITY
def test_writer_supersedes_before_inserting():
    """THE PERSISTENCE DEFECT. Without this a parent keeps both rows and
    nothing says which is authoritative."""
    src = RUNTIME.read_text()
    assert "UPDATE parent_summaries SET superseded_at = now()" in src, (
        "the writer no longer supersedes the previous summary; two live "
        "rows per parent become possible again")
    assert "WHERE parent_id = %s AND superseded_at IS NULL" in src


def test_only_one_live_row_per_parent_is_possible():
    """Scope the check to the INDEX STATEMENT. A bare substring search
    passes on the backfill UPDATE, which also contains
    "WHERE superseded_at IS NULL" — that false pass let a mutation
    removing the partial predicate survive."""
    import re as _re

    sql = MIGRATION.read_text()
    stmt = _re.search(
        r"CREATE UNIQUE INDEX[^;]*parent_summaries \(parent_id\)[^;]*;", sql)
    assert stmt, "the unique index on parent_summaries(parent_id) is gone"
    assert "WHERE superseded_at IS NULL" in stmt.group(0), (
        "the index lost its partial predicate, so it now forbids "
        "superseded history instead of forbidding a second live row")


def test_superseded_rows_are_retained_not_deleted():
    """Superseding is an authority decision, not a deletion. The old
    summary stays auditable."""
    sql = MIGRATION.read_text()
    assert "DELETE FROM parent_summaries" not in sql, (
        "the migration deletes superseded summaries; supersede must "
        "retain history")
    assert "ADD COLUMN IF NOT EXISTS superseded_at" in sql


@pytest.mark.parametrize("path,marker", [
    ("workers/workers/summary_worker_impl.py", "superseded_at IS NULL"),
    ("shared/polymath_shared/semantic_readiness.py", "superseded_at IS NULL"),
])
def test_readers_select_the_authoritative_row(path, marker):
    """A reader that ignores authority gets whichever row the planner
    returns first — the exact ambiguity this phase removes."""
    assert marker in (ROOT / path).read_text(), (
        f"{path} reads parent_summaries without filtering to the "
        "authoritative row")


def test_authority_is_not_faked_at_the_read_site():
    """ORDER BY created_at DESC LIMIT 1 would hide the defect while
    leaving the pipeline able to produce two live rows."""
    for path in (WORKER, ROOT / "shared" / "polymath_shared"
                 / "semantic_readiness.py"):
        src = path.read_text()
        lowered = src.lower()
        if "from parent_summaries" in lowered:
            assert "order by created_at desc" not in lowered, (
                f"{path.name} picks a summary by recency instead of by "
                "authority; that hides duplicates rather than preventing "
                "them")


# ========================================================= LIVE STATE
@pg_required
def test_no_parent_has_two_authoritative_summaries():
    """ACCEPTANCE: one authoritative row per parent."""
    conn = _pg()
    with conn:
        dupes = conn.execute(
            "SELECT count(*) FROM (SELECT parent_id FROM parent_summaries "
            "WHERE superseded_at IS NULL GROUP BY parent_id "
            "HAVING count(*) > 1) t").fetchone()[0]
    assert dupes == 0, f"{dupes} parents have more than one live summary"


@pg_required
def test_no_logical_job_is_ticketed_twice():
    """ACCEPTANCE: identical (stage, input_hash) cannot produce a second
    execution."""
    conn = _pg()
    with conn:
        dupes = conn.execute(
            "SELECT count(*) FROM (SELECT stage, input_hash FROM "
            "summary_jobs GROUP BY stage, input_hash HAVING count(*) > 1) t"
        ).fetchone()[0]
    assert dupes == 0, f"{dupes} logical jobs carry more than one ticket"


@pg_required
def test_a_second_ticket_for_settled_work_is_refused_by_the_database():
    """Enforcement, not convention: try it and be rejected."""
    import psycopg
    import psycopg.errors as pgerr

    stage = "PARENT_SUMMARY"
    ih = "in_p23_" + uuid.uuid4().hex
    conn = psycopg.connect(DSN, connect_timeout=5)
    try:
        # Everything inside a rolled-back transaction: test_incremental_census
        # keys on a GLOBAL watermark, so any committed write here can
        # perturb it. Leave zero residue.
        with conn.transaction(force_rollback=True):
            conn.execute(
                "INSERT INTO summary_jobs (ticket_id, stage, corpus_id, "
                "input_hash, contract_version) VALUES (%s,%s,%s,%s,%s)",
                ("tkt_" + uuid.uuid4().hex, stage, "p23-probe", ih, "t"))
            with pytest.raises(pgerr.UniqueViolation):
                with conn.transaction(force_rollback=True):
                    conn.execute(
                        "INSERT INTO summary_jobs (ticket_id, stage, "
                        "corpus_id, input_hash, contract_version) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        ("tkt_" + uuid.uuid4().hex, stage, "p23-probe",
                         ih, "t"))
    finally:
        conn.close()

    # residue check: the probe must not exist after the test
    check = psycopg.connect(DSN, connect_timeout=5)
    with check:
        left = check.execute(
            "SELECT count(*) FROM summary_jobs WHERE input_hash=%s",
            (ih,)).fetchone()[0]
    assert left == 0, "the probe left rows behind"


@pg_required
def test_generation_change_cannot_leave_two_live_rows():
    """The P14 hazard, stated directly: a contract-generation change must
    supersede, never coexist."""
    conn = _pg()
    with conn:
        rows = conn.execute(
            "SELECT count(*) FROM (SELECT parent_id FROM parent_summaries "
            "WHERE superseded_at IS NULL GROUP BY parent_id "
            "HAVING count(DISTINCT contract_version) > 1) t").fetchone()[0]
    assert rows == 0, (
        f"{rows} parents hold live summaries from two contract "
        "generations — the half-old/half-new state P13 must prevent")
