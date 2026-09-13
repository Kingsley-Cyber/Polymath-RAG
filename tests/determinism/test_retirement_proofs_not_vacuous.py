"""The retirement scripts must not authorise destruction from an absent measurement.

These two scripts produce the most consequential verdicts in the repository — one
authorises `DROP TABLE`, the other deletes fact rows — and each had a path where a
MISSING measurement read as a PERMISSIVE one:

  * `retire_claim_sets.py` treated "no row in pg_stat_user_tables" as "never written".
    Statistics vanish on `pg_stat_reset()`, on a replica, or for a schema the query does
    not cover — so "we have no evidence of writes" was being read as "there were none",
    on the verdict that authorises an irreversible DROP.
  * its code census ran `git grep` and read an empty result as "nothing references this
    table". A pattern the local grep cannot parse, or a wrong cwd, produces the same
    empty result — indistinguishable from the real thing, and the real thing authorises
    the drop.
  * `retire_pronoun_facts.py` has the MIRROR risk: `acronymic` is the set protecting
    "US"/"IT"/"WHO" from deletion. An empty protection set does not block a deletion, it
    ENABLES a larger one.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"rt_{name}", ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[f"rt_{name}"] = m
    spec.loader.exec_module(m)
    return m


class _Conn:
    def __init__(self, exists=True, rows=0, stats=None):
        self._exists, self._rows, self._stats = exists, rows, stats

    def execute(self, sql, *a, **k):
        if "to_regclass" in sql:
            out = (self._exists,)
        elif "count(*)" in sql:
            out = (self._rows,)
        elif "pg_stat_user_tables" in sql:
            out = self._stats
        else:
            out = None
        class _R:
            def fetchone(_s): return out
            def fetchall(_s): return []
        return _R()


def test_absent_write_statistics_do_not_prove_the_table_was_never_written():
    """The reading that authorised a DROP: no stats row -> 'never written'."""
    m = _load("retire_claim_sets")
    holds, findings = m.reprove(_Conn(exists=True, rows=0, stats=None))
    assert holds is False
    assert "UNPROVEN" in findings["verdict"]
    assert "pg_stat_user_tables" in findings["verdict"]


def test_real_statistics_showing_no_writes_still_prove_it(monkeypatch):
    """The strictness must not cost the real case."""
    m = _load("retire_claim_sets")
    monkeypatch.setattr(m, "_code_references", lambda: [])
    holds, findings = m.reprove(_Conn(exists=True, rows=0, stats=(0, 0, 0, 5, 7)))
    assert holds is True and "still holds" in findings["verdict"]


def test_any_lifetime_write_breaks_the_proof(monkeypatch):
    m = _load("retire_claim_sets")
    monkeypatch.setattr(m, "_code_references", lambda: [])
    holds, findings = m.reprove(_Conn(exists=True, rows=0, stats=(1, 0, 0, 5, 7)))
    assert holds is False and "NO LONGER HOLDS" in findings["verdict"]


def test_the_code_census_refuses_when_it_cannot_find_a_table_it_must_find(monkeypatch):
    """A census that matches nothing looks exactly like a table nothing references."""
    m = _load("retire_claim_sets")
    monkeypatch.setattr(m, "_census", lambda table: [])      # broken machinery
    with pytest.raises(SystemExit) as e:
        m._code_references()
    assert "self-test FAILED" in str(e.value)


def test_the_census_positive_control_really_is_present_in_this_repo():
    """The control is only a control if the repository genuinely references it."""
    m = _load("retire_claim_sets")
    hits = m._census(m._CONTROL_TABLE)
    assert hits, f"`{m._CONTROL_TABLE}` is no longer referenced by SQL; pick another control"


def test_the_pronoun_script_refuses_when_its_protection_set_is_empty():
    """The mirror risk: an empty protection set enables a LARGER deletion, so it must be
    checked before --apply, not treated as 'nothing to protect'."""
    src = (ROOT / "scripts" / "retire_pronoun_facts.py").read_text()
    assert "REFUSING" in src and "protection set is EMPTY" in src
    # and the refusal must come BEFORE the apply branch, or it protects nothing
    assert src.index("protection set is EMPTY") < src.index('if not args.apply')


def test_both_scripts_still_run_dry_without_touching_anything():
    """Dry run is the default and must stay that way."""
    for script in ("retire_claim_sets.py", "retire_pronoun_facts.py"):
        r = subprocess.run([str(ROOT / ".venv/bin/python"), f"scripts/{script}"],
                           cwd=ROOT, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"{script}: rc={r.returncode}\n{r.stdout[-800:]}{r.stderr[-800:]}"
        assert "DRY RUN" in r.stdout, f"{script} did not announce a dry run"
