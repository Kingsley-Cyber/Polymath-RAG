"""CORPUS-ACCESS-PARITY (the owner, 2026-11-01: "the corpus it uses it should be able to use any corpus, idk why we have corpus
false error its just a lot of dumb bugs" / "users of the connector and link works seamlessly as me").

Pinned here, through the REAL code paths (the /corpora route, `retrieve.resolve_http_scope`, the chat runtime's first frames,
web_scope, web_accounts, the owner CLI, /ready, the JSON logger, the hosted acceptance harness):

  * the corpus list says what is usable (`query_ready`), what "all libraries" includes (`in_all_libraries`) and why (`notes`),
    and keeps the old keys for the Overview;
  * "all libraries" = every query-ready library the caller may use — the owner's every real library, a friend's grant (the
    wildcard included, a library created after the grant too); nothing left = a typed 404 with the next step, never a 500 or
    a misleading 403;
  * user-created corpora are production + query-enabled from birth; the seven real libraries are reclassified by an
    idempotent migration;
  * a friend's private library exists from friend creation;
  * /ready includes Postgres; the orchestrator's log lines are JSON with the AGENTS.md §8 fields, no secrets, no source text;
  * the acceptance harness expects friend parity.

Postgres-backed checks run inside a transaction that is rolled back (or on a session TEMP table): nothing persists; they skip
when the database is unreachable.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import json
import logging
import pathlib
import re
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("workers", "orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from polymath_shared import principal_context
from polymath_shared import query_scope as QS
from polymath_shared.query_scope import QueryScope

from orchestrator import web_accounts as W
from orchestrator import web_scope as S

GOOD = "correct horse battery"
SHARED = ("cinema", "commerce-v1", "mythos")
MIGRATION = ROOT / "stores" / "postgres" / "migrations" / "0067_real_libraries_production.sql"
REAL_LIBRARIES = ("cinema", "commerce-v1", "mythos", "social-media-taste", "video-rules", "video-taste", "video-technique")


def test_the_modules_under_test_are_this_checkout():
    for mod in (QS, S, W):
        assert pathlib.Path(mod.__file__).is_relative_to(ROOT), mod.__file__


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def registry(tmp_path, monkeypatch):
    """ann and bob: every library (the wildcard); fred: cinema only. Autocreate is off for the session (tests/conftest.py)."""
    reg = tmp_path / "principals.json"
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(reg))
    for name, grant in (("ann", ["*"]), ("bob", ["*"]), ("fred", ["cinema"])):
        W.add_friend(reg, name, GOOD, corpus_ids=grant, adapter_ids=["ecommerce.product_research"], must_change=False)
    S._ENSURED.clear()
    yield reg
    S._ENSURED.clear()


class _Rows:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class ScopeConn:
    """What resolve_query_scope reads: corpus existence, and the ALL_AUTHORIZED members (production + query-enabled + ready)."""

    def __init__(self, existing=(), members=()):
        self.existing, self.members, self.sqls = set(existing) | set(members), tuple(members), []

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.sqls.append(flat)
        if "FROM corpora c" in flat and "query_ready" in flat:
            return _Rows([(c,) for c in self.members])
        if flat.startswith("SELECT 1 FROM corpora WHERE corpus_id"):
            return _Rows([(1,)] if params[0] in self.existing else [])
        raise AssertionError(f"unexpected SQL: {flat}")


def _req(**scope):
    from orchestrator.api.retrieve import RetrieveRequest
    return RetrieveRequest(query="what sells", **scope)


def _scope(conn, principal=None, **scope):
    from orchestrator.api.retrieve import resolve_http_scope
    with principal_context.acting_as(principal):
        return resolve_http_scope(conn, _req(**scope))


# ---------------------------------------------------------------- 1. the corpus list says what is usable
def _ui():
    from orchestrator.api import ui
    assert pathlib.Path(ui.__file__).is_relative_to(ROOT)
    return ui


#            corpus_id            purpose       enabled docs  ready  name
LIST_ROWS = [("cinema",           "production", True,   77,   True,  "cinema"),
             ("commerce-v1",      "probe",      False,  10,   True,  "commerce-v1"),
             ("fr-ann",           "production", True,   0,    False, None),
             ("fr-bob",           "production", True,   3,    True,  None),
             ("added-after-grant", "production", True,  5,    True,  "Added later"),
             ("empty-probe",      "probe",      False,  0,    False, None)]


def _list(monkeypatch, principal=None, all=False, rows=LIST_ROWS):
    ui = _ui()
    monkeypatch.setattr(ui, "tx", lambda: contextlib.nullcontext(type("C", (), {"execute": lambda _s, *_a: _Rows(rows)})()))
    with principal_context.acting_as(principal):
        return ui.corpora(all=all)


def test_the_corpus_list_explains_its_flags_and_keeps_the_old_keys(monkeypatch):
    out = _list(monkeypatch)
    assert set(out["notes"]) >= {"query_ready", "in_all_libraries", "query_enabled", "purpose", "private"}
    assert "never blocks" in out["notes"]["in_all_libraries"] and "searchable now" in out["notes"]["query_ready"]
    row = next(r for r in out["corpora"] if r["corpus_id"] == "cinema")
    assert row == {"corpus_id": "cinema", "purpose": "production", "query_enabled": True, "documents": 77, "query_ready": True,
                   "in_all_libraries": True, "private": False, "name": "cinema"}


def test_the_owners_list_marks_all_library_membership_and_skips_a_friends_empty_library(monkeypatch):
    rows = {r["corpus_id"]: r for r in _list(monkeypatch)["corpora"]}
    assert sorted(rows) == ["added-after-grant", "cinema", "commerce-v1", "fr-bob"]       # no empty fr-ann, no empty probe
    assert {c: r["in_all_libraries"] for c, r in rows.items()} == {
        "added-after-grant": True, "cinema": True,
        "commerce-v1": False,        # probe: still searchable BY NAME (query_ready true), just not in "all libraries"
        "fr-bob": False}             # a friend's private library is never in the owner's all-library searches
    assert rows["commerce-v1"]["query_ready"] is True and rows["fr-bob"]["private"] is True
    everything = {r["corpus_id"] for r in _list(monkeypatch, all=True)["corpora"]}
    assert everything == {r[0] for r in LIST_ROWS}                                         # the manager still sees every row


def test_a_wildcard_friend_lists_every_shared_library_its_own_and_never_another_friends(monkeypatch, registry):
    calls = []
    monkeypatch.setattr(W, "ensure_private_library", lambda cid: calls.append(cid) or True)
    rows = {r["corpus_id"]: r for r in _list(monkeypatch, "prn_ann")["corpora"]}
    assert sorted(rows) == ["added-after-grant", "cinema", "commerce-v1", "fr-ann"]      # fr-bob never; its own empty one yes
    assert rows["added-after-grant"]["in_all_libraries"] is True                          # created after the grant: reached
    assert rows["fr-ann"]["in_all_libraries"] is False and rows["fr-ann"]["private"] is True   # not query_ready yet
    assert calls == ["fr-ann"]                                                            # F6: its library is ensured...
    _list(monkeypatch, "prn_ann")
    assert calls == ["fr-ann"]                                                            # ...once per process


def test_an_explicit_friend_lists_only_its_grant(monkeypatch, registry):
    monkeypatch.setattr(W, "ensure_private_library", lambda cid: True)
    rows = _list(monkeypatch, "prn_fred", rows=LIST_ROWS + [("fr-fred", "production", True, 0, False, None)])["corpora"]
    assert sorted(r["corpus_id"] for r in rows) == ["cinema", "fr-fred"]


def test_the_query_enabled_switch_says_what_still_keeps_a_library_out(monkeypatch):
    ui = _ui()
    for row, member, note in ((("commerce-v1", True, "probe", True), False, "purpose is 'probe'"),
                              (("mythos", True, "production", False), False, "until it is query_ready"),
                              (("cinema", True, "production", True), True, None)):
        monkeypatch.setattr(ui, "tx", lambda r=row: contextlib.nullcontext(
            type("C", (), {"execute": lambda _s, *_a: _Rows([r])})()))
        out = ui.set_query_enabled(row[0], ui.QueryEnableRequest(query_enabled=True))
        assert out["in_all_libraries"] is member and out["query_enabled"] is True and out["purpose"] == row[2]
        assert (note in out["note"]) if note else "note" not in out


def test_the_query_enabled_route_sql_runs_on_the_real_schema(monkeypatch):
    """The PATCH route's UPDATE … RETURNING (with its correlated query_ready EXISTS) against a session TEMP copy of corpora
    (rolled back; `runs` is only read)."""
    conn = _pg()
    if conn is None:
        pytest.skip("Postgres unreachable")
    ui = _ui()
    try:
        conn.execute("CREATE TEMP TABLE corpora (LIKE public.corpora INCLUDING DEFAULTS) ON COMMIT DROP")
        shadow = conn.execute("SELECT relnamespace = pg_my_temp_schema() FROM pg_class WHERE oid = to_regclass('corpora')").fetchone()
        assert shadow == (True,), shadow
        conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES ('zz-switch', 'zz-switch', 't')")   # probe, false
        monkeypatch.setattr(ui, "tx", lambda: contextlib.nullcontext(conn))
        out = ui.set_query_enabled("zz-switch", ui.QueryEnableRequest(query_enabled=True))
        assert out == {"corpus_id": "zz-switch", "query_enabled": True, "purpose": "probe", "query_ready": False,
                       "in_all_libraries": False, "note": "still out of all-library searches: its purpose is 'probe' (test material)"}
        with pytest.raises(HTTPException) as err:
            ui.set_query_enabled("zz-no-such", ui.QueryEnableRequest(query_enabled=True))
        assert err.value.status_code == 404
    finally:
        conn.rollback()
        conn.close()


# ---------------------------------------------------------------- 2. "all libraries" for the owner, a friend, nobody
def test_the_all_libraries_sql_is_production_query_enabled_and_query_ready():
    conn = ScopeConn(members=("cinema",))
    assert QS.resolve_query_scope(conn, all_authorized=True) == QueryScope("ALL_AUTHORIZED", ("cinema",))
    sql = conn.sqls[-1]
    assert "c.purpose = 'production'" in sql and "c.query_enabled" in sql and "r.status = 'query_ready'" in sql
    # the pure twin used by the corpus list is the same rule
    assert QS.in_all_libraries("production", True, True)
    assert not QS.in_all_libraries("probe", True, True) and not QS.in_all_libraries("production", False, True)
    assert not QS.in_all_libraries("production", True, False)


def test_the_owners_all_libraries_is_every_real_library_but_a_friends_private_one():
    scope = _scope(ScopeConn(members=("cinema", "fr-bob", "video-taste")), all_authorized=True)
    assert scope == QueryScope("ALL_AUTHORIZED", ("cinema", "video-taste"))


def test_a_wildcard_friends_all_libraries_includes_a_library_created_after_the_grant(registry):
    scope = _scope(ScopeConn(members=("added-after-grant", "cinema", "fr-ann", "fr-bob")), "prn_ann", all_authorized=True)
    assert scope.corpus_ids == ("added-after-grant", "cinema", "fr-ann")


def test_an_explicit_friends_all_libraries_is_its_grant_only(registry):
    scope = _scope(ScopeConn(members=("cinema", "video-taste")), "prn_fred", all_authorized=True)
    assert scope.corpus_ids == ("cinema",)


@pytest.mark.parametrize("principal,members", [(None, ()), (None, ("fr-bob",)), ("prn_fred", ("video-taste",))])
def test_nothing_to_search_is_a_typed_404_with_the_next_step_never_a_403_or_500(registry, principal, members):
    with pytest.raises(HTTPException) as err:
        _scope(ScopeConn(members=members), principal, all_authorized=True)
    detail = err.value.detail
    assert err.value.status_code == 404 and detail["error_code"] == "QUERY_SCOPE_EMPTY"
    assert "no library to search" in detail["message"] and "corpus_id" in detail["next_step"]
    assert ("fr-fred" in detail["next_step"]) is (principal == "prn_fred")                # a friend is pointed at its own library


def test_an_empty_all_libraries_chat_turn_is_a_typed_error_frame_not_a_500(monkeypatch):
    ui = _ui()
    monkeypatch.setattr(ui, "tx", lambda: contextlib.nullcontext(ScopeConn(members=())))
    receipts = []
    req = ui.StreamChatRequest(message="what should I sell", all_authorized=True, synthesizer="deterministic-template-v3")
    frames = list(ui.chat_events(req, receipt=receipts.append))
    errors = [json.loads(f.split("data: ", 1)[1]) for f in frames if f.startswith("event: error")]
    assert errors and errors[0]["status"] == 404 and errors[0]["error_code"] == "QUERY_SCOPE_EMPTY", frames
    assert "next_step" in errors[0] and not any("IndexError" in f for f in frames)
    assert receipts and "QUERY_SCOPE_EMPTY" in str(receipts[0].get("error") or receipts[0])


def test_a_workspace_with_none_of_the_friends_libraries_stays_a_403(registry):
    with principal_context.acting_as("prn_fred"), pytest.raises(HTTPException) as err:
        S.narrow_scope(QueryScope("WORKSPACE", ("video-taste",)))
    assert err.value.status_code == 403


def test_require_nonempty_is_the_same_refusal_outside_http():
    with pytest.raises(QS.QueryScopeEmpty) as err:
        QS.require_nonempty(QueryScope("ALL_AUTHORIZED", ()))
    assert err.value.detail()["error_code"] == "QUERY_SCOPE_EMPTY"
    assert QS.require_nonempty(QueryScope("CORPUS", ("cinema",))).corpus_ids == ("cinema",)


# ---------------------------------------------------------------- 3. creation defaults + the migration
def test_user_corpora_are_production_and_query_enabled_and_harnesses_classify_explicitly():
    assert QS.new_corpus_classification() == ("production", True)
    assert QS.new_corpus_classification({"allow_near_duplicate": True}) == ("production", True)
    assert QS.new_corpus_classification({"purpose": "probe"}) == ("probe", False)
    assert QS.new_corpus_classification({"purpose": "evaluation", "query_enabled": True}) == ("evaluation", True)
    with pytest.raises(ValueError):
        QS.new_corpus_classification({"purpose": "nonsense"})


def test_the_intake_worker_classifies_a_new_corpus_on_creation():
    """The upload path's corpus INSERT (the only user creation path besides the private library) carries the classification."""
    src = (ROOT / "workers" / "workers" / "intake_worker.py").read_text()
    insert = src[src.index("INSERT INTO corpora"):src.index("ON CONFLICT (corpus_id) DO NOTHING", src.index("INSERT INTO corpora"))]
    assert "purpose, query_enabled" in insert and "%s, %s, %s, %s, %s, %s, %s" in insert
    assert "new_corpus_classification(payload.get(\"config\"))" in src
    assert "_purpose, _query_enabled)" in src


def test_the_migration_targets_exactly_the_real_libraries_and_is_data_only():
    sql = "\n".join(l for l in MIGRATION.read_text().splitlines() if not l.strip().startswith("--"))
    body = sql.upper()
    for banned in ("DROP ", "DELETE ", "TRUNCATE", "ALTER ", "CREATE ", "INSERT "):
        assert banned not in body, banned
    assert body.count("UPDATE CORPORA") == 1 and "LIKE" not in body                     # an explicit list, never a pattern
    assert sorted(re.findall(r"'([a-z0-9-]+)'", sql.split("WHERE corpus_id IN", 1)[1].split(")", 1)[0])) == sorted(REAL_LIBRARIES)
    assert "IS DISTINCT FROM 'production' OR query_enabled IS DISTINCT FROM true" in sql    # a re-run matches nothing


def _pg():
    try:
        import psycopg
        from polymath_shared.settings import get_settings
        return psycopg.connect(get_settings().postgres.dsn, connect_timeout=3)
    except Exception:  # noqa: BLE001
        return None


def test_the_migration_is_idempotent_on_a_temp_copy_of_corpora():
    conn = _pg()
    if conn is None:
        pytest.skip("Postgres unreachable")
    try:
        conn.execute("CREATE TEMP TABLE corpora (LIKE public.corpora INCLUDING DEFAULTS) ON COMMIT DROP")
        shadow = conn.execute("SELECT relnamespace = pg_my_temp_schema() FROM pg_class WHERE oid = to_regclass('corpora')").fetchone()
        assert shadow == (True,), shadow                                              # `corpora` IS the temp copy: never the real table
        conn.execute("""INSERT INTO corpora (corpus_id, name, config_hash, purpose, query_enabled, updated_at)
                        SELECT x, x, 't', 'probe', x IN ('social-media-taste', 'video-rules', 'video-taste', 'video-technique'),
                               '2020-01-01' FROM unnest(%s::text[]) AS x""", (list(REAL_LIBRARIES[1:]),))
        conn.execute("""INSERT INTO corpora (corpus_id, name, config_hash, purpose, query_enabled, updated_at) VALUES
                        ('cinema', 'cinema', 't', 'production', true, '2020-01-01'),
                        ('zz-fixture', 'zz-fixture', 't', 'probe', false, '2020-01-01')""")
        first = conn.execute(MIGRATION.read_text()).rowcount
        second = conn.execute(MIGRATION.read_text()).rowcount
        rows = {r[0]: r[1:] for r in conn.execute(
            "SELECT corpus_id, purpose, query_enabled, updated_at > '2021-01-01' FROM corpora").fetchall()}
        assert (first, second) == (6, 0)
        assert all(rows[c][:2] == ("production", True) for c in REAL_LIBRARIES)
        assert rows["cinema"][2] is False                                              # already right: untouched
        assert rows["zz-fixture"] == ("probe", False, False)                           # not on the list: untouched
    finally:
        conn.rollback()
        conn.close()


# ---------------------------------------------------------------- 4. the wildcard grant
def test_the_wildcard_reaches_every_library_but_another_friends_private_one_and_never_writes(registry):
    with principal_context.acting_as("prn_ann"):
        assert S.can_see("cinema") and S.can_see("a-library-made-after-the-grant") and S.can_see("fr-ann")
        assert not S.can_see("fr-bob") and not S.can_see("*") and not S.can_see(None)
        assert S.can_see("fr-ann", write=True) and not S.can_see("cinema", write=True)
        S.narrow_scope(QueryScope("CORPUS", ("a-library-made-after-the-grant",)))
        with pytest.raises(HTTPException) as err:
            S.narrow_scope(QueryScope("CORPUS", ("fr-bob",)))
        assert err.value.status_code == 403 and err.value.detail["error_code"] == "CORPUS_NOT_ALLOWED"
        assert [r["corpus_id"] for r in S.filter_by_corpus([{"corpus_id": c} for c in ("cinema", "fr-bob", "fr-ann")])] == ["cinema", "fr-ann"]
    with principal_context.acting_as("prn_fred"):
        assert S.can_see("cinema") and not S.can_see("a-library-made-after-the-grant")


def test_a_named_library_created_after_the_grant_resolves_for_a_wildcard_friend(registry):
    conn = ScopeConn(existing=("a-library-made-after-the-grant",))
    assert _scope(conn, "prn_ann", corpus_id="a-library-made-after-the-grant").corpus_ids == ("a-library-made-after-the-grant",)


def test_the_grant_is_normalised_and_another_friends_library_is_never_grantable(registry):
    doc = W.read_registry(registry)
    ann = next(r for r in doc["principals"] if r["principal_id"] == "prn_ann")
    assert ann["corpus_ids"] == ["*", "fr-ann"] and ann["writable_corpus_ids"] == ["fr-ann"]
    assert W.set_friend_corpora(registry, "fred", ["cinema", "*", "mythos"])["corpus_ids"] == ["*", "fr-fred"]
    rec = W.set_friend_corpora(registry, "fred", ["mythos", "cinema"])
    assert rec["corpus_ids"] == ["cinema", "fr-fred", "mythos"] and rec["all_libraries"] is False
    with pytest.raises(W.AccountError) as err:
        W.set_friend_corpora(registry, "fred", ["fr-bob"])
    assert err.value.code == "PRIVATE_LIBRARY"
    with pytest.raises(W.AccountError):
        W.add_friend(registry, "carol", GOOD, corpus_ids=["fr-ann"])


def test_the_owner_puts_an_existing_friend_on_every_library(registry, capsys):
    rec = W.set_friend_all_libraries(registry, "fred")
    assert rec["corpus_ids"] == ["*", "fr-fred"] and rec["all_libraries"] is True
    W.set_friend_corpora(registry, "fred", ["cinema"])
    spec = importlib.util.spec_from_file_location("web_accounts_cli", ROOT / "scripts" / "web_accounts.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    assert cli.main(["--file", str(registry), "set-libraries", "--username", "fred", "--all"]) == 0
    assert json.loads(capsys.readouterr().out)["libraries_set"]["corpus_ids"] == ["*", "fr-fred"]
    for bad in ([], ["--all", "--corpus", "cinema"]):
        with pytest.raises(SystemExit):
            cli.main(["--file", str(registry), "set-libraries", "--username", "fred", *bad])
    from orchestrator import mcp_principals as P
    p = P.principal_from_record(next(r for r in W.read_registry(registry)["principals"] if r["principal_id"] == "prn_fred"))
    assert p.corpus_ids == frozenset({"*", "fr-fred"})                     # Server A's store loads the wildcard record


def test_an_adapter_start_without_libraries_is_let_through_and_named_ones_are_judged(registry):
    """Coordinator 2026-11-01: the adapter runtime defaults corpus_ids to the caller's searchable libraries within its grant."""
    with principal_context.acting_as("prn_fred"):
        S.require_adapter_start("ecommerce.product_research", {"seed": "x"}, None)          # none named: through
        S.require_adapter_start("ecommerce.product_research", None, {})
        S.require_adapter_start("ecommerce.product_research", {}, {"corpus_ids": ["cinema"]})
        for payload, opts in (({"corpus_ids": ["mythos"]}, None), ({}, {"corpus_ids": ["cinema", "fr-bob"]})):
            with pytest.raises(HTTPException) as err:
                S.require_adapter_start("ecommerce.product_research", payload, opts)
            assert err.value.detail["error_code"] == "CORPUS_NOT_ALLOWED"
        with pytest.raises(HTTPException) as err:
            S.require_adapter_start("trail.product_discovery", {}, {})
        assert err.value.detail["error_code"] == "ADAPTER_NOT_ALLOWED"
    with principal_context.acting_as("prn_ann"):                                            # the wildcard is honoured
        S.require_adapter_start("ecommerce.product_research", {}, {"corpus_ids": ["a-library-made-after-the-grant", "fr-ann"]})
        with pytest.raises(HTTPException):
            S.require_adapter_start("ecommerce.product_research", {}, {"corpus_ids": ["fr-bob"]})


# ---------------------------------------------------------------- 5. the private library exists from friend creation
class _FakeTx:
    def __init__(self):
        self.calls = []

    def __call__(self):
        outer = self

        class Conn:
            def execute(self, sql, params=None):
                outer.calls.append((" ".join(sql.split()), params))
        return contextlib.nullcontext(Conn())


def test_ensure_private_library_writes_one_idempotent_production_row(monkeypatch):
    from polymath_shared import db
    fake = _FakeTx()
    monkeypatch.setattr(db, "tx", fake)
    assert W.ensure_private_library("fr-ann") is False and fake.calls == []        # the test session switched it off
    monkeypatch.setenv("POLYMATH_PRIVATE_LIBRARY_AUTOCREATE", "1")
    assert W.ensure_private_library("fr-ann") is True
    sql, params = fake.calls[0]
    assert "INSERT INTO corpora" in sql and "ON CONFLICT (corpus_id) DO NOTHING" in sql
    assert params[0] == params[1] == "fr-ann" and params[-2:] == ("production", True)
    for bad in ("cinema", "fr-", "fr-Not Valid", "*"):
        with pytest.raises(W.AccountError):
            W.ensure_private_library(bad)


def test_friend_creation_and_sign_up_create_the_private_library_and_a_wrong_code_creates_nothing(tmp_path, monkeypatch):
    from polymath_shared import db
    fake = _FakeTx()
    monkeypatch.setattr(db, "tx", fake)
    monkeypatch.setenv("POLYMATH_PRIVATE_LIBRARY_AUTOCREATE", "1")
    reg = tmp_path / "p.json"
    W.add_friend(reg, "ann", GOOD, corpus_ids=["*"])
    code = W.rotate_invite(reg)
    with pytest.raises(W.AccountError):
        W.register_friend(reg, "eve", GOOD, "wrong-code-0000")
    W.register_friend(reg, "dan", GOOD, code, corpus_ids=["*"])
    assert [p[0] for _, p in fake.calls] == ["fr-ann", "fr-dan"]


def test_a_database_failure_at_friend_creation_never_fails_the_account(tmp_path, monkeypatch):
    def broken(_cid):
        raise RuntimeError("db down")
    monkeypatch.setattr(W, "ensure_private_library", broken)
    rec = W.add_friend(tmp_path / "p.json", "ann", GOOD)
    assert rec["writable_corpus_ids"] == ["fr-ann"]


def test_friend_creation_writes_a_real_corpora_row_rolled_back(tmp_path, monkeypatch):
    """Against the real schema, inside one transaction that is rolled back: the row the private library gets."""
    conn = _pg()
    if conn is None:
        pytest.skip("Postgres unreachable")
    from polymath_shared import db
    name = f"zz-parity-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(db, "tx", lambda: contextlib.nullcontext(conn))
    monkeypatch.setenv("POLYMATH_PRIVATE_LIBRARY_AUTOCREATE", "1")
    try:
        W.add_friend(tmp_path / "p.json", name, GOOD, corpus_ids=["*"])
        row = conn.execute("SELECT purpose, query_enabled, name FROM corpora WHERE corpus_id = %s", (f"fr-{name}",)).fetchone()
        assert row == ("production", True, f"fr-{name}")
        assert W.ensure_private_library(f"fr-{name}") is True                          # idempotent: a second call is a no-op
        assert conn.execute("SELECT count(*) FROM corpora WHERE corpus_id = %s", (f"fr-{name}",)).fetchone()[0] == 1
    finally:
        conn.rollback()
        conn.close()


def test_the_owner_backfills_every_friends_private_library(registry, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(W, "ensure_private_library", lambda cid: calls.append(cid) or True)
    spec = importlib.util.spec_from_file_location("web_accounts_cli", ROOT / "scripts" / "web_accounts.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    assert cli.main(["--file", str(registry), "ensure-libraries"]) == 0
    assert sorted(calls) == ["fr-ann", "fr-bob", "fr-fred"]
    assert json.loads(capsys.readouterr().out)["private_libraries"] == {c: "exists" for c in ("fr-ann", "fr-bob", "fr-fred")}


# ---------------------------------------------------------------- 6a. /ready includes Postgres
def _ready_client():
    from orchestrator.api import health
    app = FastAPI()
    app.include_router(health.router)
    return health, TestClient(app)


def test_ready_reports_postgres_and_is_not_ready_without_it(monkeypatch):
    health, client = _ready_client()
    monkeypatch.setattr(health, "postgres_ready", lambda: {"ok": True, "latency_ms": 1.0})
    body = client.get("/ready").json()
    assert body["ready"] is True and body["postgres"]["ok"] is True and body["sidecars"] == {}
    monkeypatch.setattr(health, "postgres_ready", lambda: {"ok": False, "error_code": "POSTGRES_UNAVAILABLE", "error": "PoolTimeout"})
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["ready"] is False and r.json()["postgres"]["error_code"] == "POSTGRES_UNAVAILABLE"
    assert '"ready":false' in r.text                                     # scripts/bounce_fleet.sh greps the body


def test_the_postgres_probe_never_raises_and_never_carries_the_dsn(monkeypatch):
    health, _ = _ready_client()
    from polymath_shared import db

    class Pool:
        def connection(self, timeout=None):
            raise RuntimeError("connection to postgresql://polymath:hunter2-secret@127.0.0.1:5432/polymath failed")  # not-a-connection: a fake error text
    monkeypatch.setattr(db, "get_pool", lambda: Pool())
    out = health.postgres_ready()
    assert out["ok"] is False and out["error"] == "RuntimeError" and "hunter2" not in json.dumps(out)


def test_the_postgres_probe_against_the_real_database():
    conn = _pg()
    if conn is None:
        pytest.skip("Postgres unreachable")
    conn.close()
    health, _ = _ready_client()
    out = health.postgres_ready()
    assert out["ok"] is True and out["latency_ms"] >= 0


# ---------------------------------------------------------------- 6b. JSON logs with the §8 fields
@pytest.fixture
def json_logs():
    from orchestrator import json_logging as J
    root = logging.getLogger()
    saved = (list(root.handlers), root.level, {n: list(logging.getLogger(n).handlers) for n in J.UVICORN_LOGGERS})
    buf = io.StringIO()
    yield J, buf
    root.handlers, root.level = saved[0], saved[1]
    for n, hs in saved[2].items():
        logging.getLogger(n).handlers = hs


def test_log_lines_are_json_with_the_section_8_fields_and_no_secrets(json_logs):
    J, buf = json_logs
    owner_key = "owner-main-key-0123456789abcdef"
    handler = J.configure_orchestrator_logging(buf, force=True, secrets=[owner_key])
    assert handler is not None
    log = logging.getLogger("orchestrator.test")
    log.warning("auth %s bearer pmk_0123abcd_%s, Authorization: Bearer abcdefghijklmnop, dsn postgresql://polymath:pw-123456@db/x, "
                "link https://mcp.example/k/%s/mcp, invite_code=k7mp-4xwq-9nfr, key sk-abcdefghijklmnopqrstu",
                owner_key, "s" * 40, owner_key, extra={"event": "test.event", "run_id": "run_1", "error_code": "X", "duration_ms": 3.5})
    line = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert set(J.REQUIRED_FIELDS) <= set(line)
    assert line["service"] == "orchestrator" and line["event"] == "test.event" and line["run_id"] == "run_1"
    assert line["level"] == "WARNING" and line["trace_id"] is None and line["duration_ms"] == 3.5
    text = json.dumps(line)
    for secret in (owner_key, "s" * 40, "abcdefghijklmnop", "pw-123456", "k7mp-4xwq-9nfr", "sk-abcdefghijklmnopqrstu"):
        assert secret not in text, secret
    assert "postgresql://polymath:<redacted>@db/x" in line["message"]


def test_a_long_message_and_a_traceback_are_cut_and_scrubbed(json_logs):
    J, buf = json_logs
    J.configure_orchestrator_logging(buf, force=True, secrets=["secret-value-xyz-123"])
    log = logging.getLogger("orchestrator.test")
    log.info("source text: " + "x" * 10_000)
    try:
        raise ValueError("boom secret-value-xyz-123 " + "y" * 9000)
    except ValueError:
        log.exception("failed")
    first, second = (json.loads(l) for l in buf.getvalue().strip().splitlines()[-2:])
    assert len(first["message"]) < J.MAX_MESSAGE_CHARS + 200 and "characters cut" in first["message"]
    assert "secret-value-xyz-123" not in second["exception"] and len(second["exception"]) < J.MAX_EXCEPTION_CHARS + 200


def test_logging_is_idempotent_covers_uvicorn_and_never_takes_over_someone_elses_setup(json_logs):
    J, buf = json_logs
    J.configure_orchestrator_logging(buf, force=True, secrets=[])
    J.configure_orchestrator_logging(buf, force=True, secrets=[])
    ours = [h for h in logging.getLogger().handlers if getattr(h, J._MARK, False)]
    assert len(ours) == 1 and all(logging.getLogger(n).handlers == ours for n in J.UVICORN_LOGGERS)
    logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1", "GET", "/corpora?key=abc123secret", "1.1", 200)
    access = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert access["event"] == "uvicorn.access" and "abc123secret" not in access["message"]
    logging.getLogger().addHandler(logging.NullHandler())                    # someone else configured logging (pytest does)
    assert J.configure_orchestrator_logging(io.StringIO(), secrets=[]) is None


def test_secret_values_skip_paths_and_short_values():
    from orchestrator import json_logging as J
    env = {"POLYMATH_MCP_API_KEY": "k" * 48, "POLYMATH_KEY_FILE": "/Users/x/keys/owner.key", "X_TOKEN": "short",
           "OPENCODE_API_KEY": "env:OTHER", "POLYMATH_PG_DSN": "postgresql://u:p@h/d", "PLAIN": "not-a-secret-name"}
    assert set(J.secret_values(env)) == {"k" * 48, "postgresql://u:p@h/d"}


# ---------------------------------------------------------------- 7. the acceptance harness expects friend parity
def _harness():
    spec = importlib.util.spec_from_file_location("hosted_mcp_acceptance", ROOT / "scripts" / "hosted_mcp_acceptance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeServerA:
    """Server A as seen by the harness: `parity=True` = the F14 contract (a web friend with the wildcard, its private library,
    upload / history / supplier / product / deep-research tools); `parity=False` = the pre-F14 conservative friend profile.
    Records every call so the test can prove nothing was ingested and no model or supplier was called."""

    KNOWLEDGE = ("list_corpora", "polymath_search", "polymath_explore", "polymath_answer", "polymath_compare", "corpus_status",
                 "list_documents", "document_status", "capabilities")
    ADAPTER = ("adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status", "adapter_result", "adapter_cancel")
    #: PRODUCT-DECISION-REPORT-V1: the decision report tools, in a friend's surface since B5
    REPORT = ("product_report_start", "product_report_status", "product_report_compile", "product_report_list")
    LIBS = ("cinema", "commerce-v1", "mythos", "added-after-grant")

    def __init__(self, parity: bool):
        self.parity, self.calls = parity, []

    def tools(self, who):
        if who == "owner":
            return [*self.KNOWLEDGE, *self.ADAPTER, "upload_text", "upload_document", "recent_queries", "research_acquire",
                    "product_search", "supplier_parse", "supplier_search", "supplier_product", "supplier_freight",
                    "supplier_warehouses", "polymath_deep_research", *self.REPORT]
        base = [*self.KNOWLEDGE, *self.ADAPTER]
        return base + (["upload_text", "recent_queries", "product_search", "supplier_parse", "supplier_search", "supplier_product",
                        "supplier_freight", "supplier_warehouses", "polymath_deep_research", *self.REPORT] if self.parity else [])

    def libs(self, who):
        if who == "owner":
            return [*self.LIBS, "fr-ann", "fr-bob"]
        if who == "a":
            return [*self.LIBS, "fr-ann"] if self.parity else ["commerce-v1"]
        return [*self.LIBS, "fr-bob"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        who = {"Bearer owner-key": "owner", "Bearer a-key": "a", "Bearer b-key": "b"}.get(request.headers.get("authorization"))
        msg = json.loads(request.content)
        rid = msg.get("id")
        if msg["method"] == "initialize":
            return self._ok(rid, {"protocolVersion": "2025-06-18"}, raw=True)
        if msg["method"] == "tools/list":
            return self._ok(rid, {"tools": [{"name": n} for n in self.tools(who)]}, raw=True)
        name, args = msg["params"]["name"], msg["params"].get("arguments") or {}
        self.calls.append((who, name, args))
        if name not in self.tools(who):
            return self._deny(rid, "tool_not_permitted" if name in ("upload_document", "research_acquire") else "insufficient_scope")
        return self.call(who, name, args, rid)

    def call(self, who, name, args, rid):
        cid = args.get("corpus_id")
        if name in ("polymath_search", "corpus_status", "recent_queries", "polymath_deep_research") and cid not in self.libs(who):
            return self._deny(rid, "corpus_not_allowed")
        if name == "polymath_search":
            return self._ok(rid, {"evidence_rows": [{"id": "ev_1", "text": f"a row from {cid}"}]})
        if name == "corpus_status":
            return self._ok(rid, {"corpus": {"corpus_id": cid, "documents": 0, "query_ready": False}})
        if name == "recent_queries":
            return self._ok(rid, {"corpus_id": cid, "count": 0, "queries": []})
        if name == "polymath_deep_research":
            return self._ok(rid, {"report": "a report that should never have been written"})
        if name == "upload_text":
            if who != "owner" and cid != "fr-ann":
                return self._deny(rid, "corpus_not_writable")
            if not str(args.get("source_name", "")).endswith((".md", ".txt")):
                return self._ok(rid, {"error": "source_name needs one of ['.md', '.txt']", "status": 422})
            return self._ok(rid, {"run_id": "run_ingested"})
        if name == "list_corpora":
            return self._ok(rid, {"corpora": [{"corpus_id": c} for c in self.libs(who)]})
        if name == "adapter_list":
            return self._ok(rid, {"adapters": [{"adapter_id": "polymath.knowledge_brief"}]})
        if name == "adapter_start":
            return self._ok(rid, {"run_id": "adr_friend_a"})
        if name in ("adapter_next", "adapter_status", "adapter_result", "adapter_submit", "adapter_cancel"):
            if who == "b" or args.get("run_id") != "adr_friend_a":
                return self._deny(rid, "run_not_accessible")
            if name == "adapter_next":
                return self._ok(rid, {"kind": "step"})
            return self._ok(rid, {"run_id": "adr_friend_a", "status": "cancelled" if name == "adapter_cancel" else "awaiting"})
        return self._ok(rid, {"error": f"unexpected tool {name}", "status": 500})

    @staticmethod
    def _ok(rid, payload, raw=False):
        result = payload if raw else {"content": [{"type": "text", "text": json.dumps(payload)}], "structuredContent": payload}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": rid, "result": result})

    @staticmethod
    def _deny(rid, reason):
        return httpx.Response(403, json={"jsonrpc": "2.0", "id": rid, "error": {"code": -32003, "message": "forbidden",
                                                                               "data": {"status": 403, "reason": reason}}})


def _parity_run(parity: bool, new_corpus: str | None = "added-after-grant", server_cls: type | None = None):
    harness, server = _harness(), (server_cls or FakeServerA)(parity)
    friends = {"a_key": "a-key", "b_key": "b-key", "corpus": "commerce-v1", "denied_corpus": "fr-bob", "query": "what sells",
               "start": {"adapter_id": "polymath.knowledge_brief", "input": {}, "request_options": {}}, "polls": 1, "poll_s": 0,
               "private": None, "new_corpus": new_corpus}
    rep = harness.Report()
    asyncio.run(harness._principals(rep, "http://mcp.test", "owner-key", friends, httpx.MockTransport(server.handler), 10.0))
    return {c["id"]: c["status"] for c in rep.checks}, server, rep


PARITY_CHECKS = ("principal.a_tool_parity", "principal.a_private_library", "principal.a_upload_text", "principal.a_recent_queries",
                 "principal.a_deep_research_scoped", "principal.a_every_library", "principal.a_new_library",
                 "principal.a_owner_only_refused")


def test_the_harness_passes_a_friend_parity_surface_and_ingests_nothing():
    got, server, rep = _parity_run(parity=True)
    assert set(PARITY_CHECKS) <= set(got) and "principal.a_no_upload_admin" not in got
    assert {k: v for k, v in got.items()} == {k: "PASS" for k in got}, rep.checks
    sent = [(w, n, a) for w, n, a in server.calls if w == "a"]
    assert all(a.get("source_name") == _harness().PROBE_SOURCE_NAME for _, n, a in sent if n == "upload_text")   # nothing ingested
    assert not any(n == "polymath_deep_research" and a.get("corpus_id") != "fr-bob" for _, n, a in sent)     # no report run
    assert not any(n.startswith(("supplier_", "product_report_")) or n == "product_search" for _, n, _ in sent)   # no CJ / model spend
    assert set(FakeServerA.REPORT) <= set(_harness().FRIEND_PARITY_TOOLS)                   # the report tools are judged, never called


def test_the_harness_fails_the_pre_parity_friend_profile():
    got, _, _ = _parity_run(parity=False)
    for check in ("principal.a_tool_parity", "principal.a_private_library", "principal.a_upload_text", "principal.a_recent_queries",
                  "principal.a_deep_research_scoped", "principal.a_every_library", "principal.a_new_library"):
        assert got[check] == "FAIL", (check, got)
    assert got["principal.a_owner_only_refused"] == "PASS"


def test_a_friend_without_the_report_tools_fails_tool_parity():
    """PRODUCT-DECISION-REPORT-V1 (B5): the four decision report tools are part of a web friend's surface; a Server A that hides
    them from a friend fails the parity check (and only that check)."""
    class NoReports(FakeServerA):
        def tools(self, who):
            return [t for t in super().tools(who) if t not in self.REPORT]
    got, server, rep = _parity_run(parity=True, server_cls=NoReports)
    assert got["principal.a_tool_parity"] == "FAIL", rep.checks
    detail = next(c["detail"] for c in rep.checks if c["id"] == "principal.a_tool_parity")
    assert all(t in detail for t in FakeServerA.REPORT), detail
    assert {k: v for k, v in got.items() if k != "principal.a_tool_parity"} == {k: "PASS" for k in got if k != "principal.a_tool_parity"}


def test_a_new_library_is_skipped_not_passed_without_one_named():
    got, _, _ = _parity_run(parity=True, new_corpus=None)
    assert got["principal.a_new_library"] == "SKIP"
