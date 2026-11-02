"""PRODUCT-DECISION-REPORT-V1 (B4b): the decision reports' store (shared/polymath_shared/product_search/report_store.py) on the REAL
migration 0068 — run ONLY on the sealed harness's throwaway Postgres (POLYMATH_TEST_DSN on a port other than the fleet's 5432, whose
`documents` table is near-empty; never the fleet's database). Every test runs in one transaction that is rolled back: nothing stays.

Covered: the migration (the plan's columns, with `upload_tokens` for the plan's single hash; the keys and indexes, the CHECKs,
replay-safe), the upload tokens (each returned once, only hashes stored, at most 30 held — the least recently minted-or-used dropped,
a token in use never; concurrent mints lose none; every token ends with the report's 6 h expiry), privacy (the owner sees every report, a principal only its own; "not yours" and "no such
report" are one answer), the upload capability (wrong / another report's / malformed / expired), idempotent uploads and the caps
(2 MB, 300 packets), compare-and-set status transitions and rounds, the saved columns, the cascade, and the pure helpers on stored
rows (round targets, parsed per candidate, upload counts)."""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import threading
from urllib.parse import urlsplit

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "orchestrator"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

psycopg = pytest.importorskip("psycopg")

from polymath_shared.product_search import report_store as S

MIGRATION = ROOT / "stores" / "postgres" / "migrations" / "0068_product_reports.sql"


def sealed_dsn() -> str | None:
    dsn = os.environ.get("POLYMATH_TEST_DSN")
    if not dsn or (urlsplit(dsn).port or 5432) == 5432:
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            if conn.execute("SELECT to_regclass('product_reports')").fetchone()[0] is None:
                return None
            if int(conn.execute("SELECT count(*) FROM documents").fetchone()[0]) >= 1000:
                return None
    except Exception:  # noqa: BLE001
        return None
    return dsn


DSN = sealed_dsn()
pytestmark = pytest.mark.skipif(DSN is None, reason="needs the sealed Postgres (POLYMATH_TEST_DSN, never the fleet's database)")


def test_the_store_under_test_is_this_checkout():
    assert pathlib.Path(S.__file__).resolve().is_relative_to(ROOT), S.__file__


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=False) as c:
        try:
            yield c
        finally:
            c.rollback()                                     # nothing a test writes survives it


def _new(conn, owner=None, **kw):
    return S.create(conn, owner_principal_id=owner, request={"products_from": "caller", "ship_to": "US"},
                    candidates={"status": "ready", "source": "caller",
                                "items": [{"candidate_id": "c1", "title": "Pet feeder", "search_terms": ["pet feeder"]}]}, **kw)


# ───────────────────────────────────────────────────────────────── the migration
def test_the_migration_holds_the_plans_columns_and_is_replay_safe(conn):
    cols = {t: [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s "
                                            "ORDER BY ordinal_position", (t,)).fetchall()]
            for t in ("product_reports", "product_report_uploads")}
    assert cols["product_reports"] == ["report_id", "owner_principal_id", "status", "request", "candidates", "host", "model", "html",
                                       "verdicts", "upload_tokens", "upload_expires_at", "round", "compile_started_at", "created_at",
                                       "updated_at"]
    assert cols["product_report_uploads"] == ["report_id", "packet_id", "round", "source", "kind", "received_at", "bytes", "sha256",
                                              "status", "parsed", "refused"]
    pk = conn.execute("""SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                          WHERE i.indrelid = 'product_report_uploads'::regclass AND i.indisprimary ORDER BY a.attname""").fetchall()
    assert [r[0] for r in pk] == ["packet_id", "report_id"]
    idx = {r[0]: r[1] for r in conn.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'product_reports'")}
    assert "(owner_principal_id, created_at DESC)" in idx["product_reports_owner_created_idx"]
    assert "(created_at DESC)" in idx["product_reports_created_idx"]
    text = MIGRATION.read_text()
    assert "Rollback" in text and "DROP TABLE IF EXISTS product_report_uploads" in text
    alters = [line for line in text.splitlines() if "ALTER TABLE" in line and not line.lstrip().startswith("--")]
    assert alters == ["ALTER TABLE product_reports ADD COLUMN IF NOT EXISTS compile_started_at TIMESTAMPTZ;"]   # NEW-4, additive
    conn.execute(text)                                        # replay: every statement is IF NOT EXISTS
    conn.execute(text)
    row, _token = _new(conn)
    assert row["status"] == "collecting" and row["round"] == 1


_A64 = "a" * 64


@pytest.mark.parametrize("sql,args", [
    ("UPDATE product_reports SET status = 'done' WHERE report_id = %s", None),
    ("UPDATE product_reports SET round = 3 WHERE report_id = %s", None),
    ("UPDATE product_reports SET upload_tokens = '[]' WHERE report_id = %s", None),                         # none held
    ("UPDATE product_reports SET upload_tokens = '{}' WHERE report_id = %s", None),                         # not a list
    ("UPDATE product_reports SET upload_tokens = '[{\"sha256\": \"abc\"}]' WHERE report_id = %s", None),    # not a sha256
    ("UPDATE product_reports SET upload_tokens = '[{\"minted_at\": \"x\"}]' WHERE report_id = %s", None),   # no sha256
    (("UPDATE product_reports SET upload_tokens = (SELECT jsonb_agg(jsonb_build_object('sha256', repeat('a', 64))) "
      "FROM generate_series(1, 31)) WHERE report_id = %s"), None),                                          # over the cap
    (("INSERT INTO product_reports (report_id, request, upload_tokens, upload_expires_at) VALUES ('rpt_short', '{}', "
      f"'[{{\"sha256\": \"{_A64}\"}}]', now())"), ()),
    (("INSERT INTO product_report_uploads (report_id, packet_id, round, source, kind, bytes, sha256, status) "
      "VALUES (%s, 'p', 1, 'reddit', 'search', 2097153, repeat('a', 64), 'OK')"), None),
])
def test_the_checks_refuse_what_the_store_never_writes(conn, sql, args):
    row, _ = _new(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(sql, (row["report_id"],) if args is None else args)


# ───────────────────────────────────────────────────────────────── the token
def test_create_returns_the_token_once_and_stores_only_its_sha256(conn):
    t0 = S.now()
    row, token = _new(conn, owner="prn_alice", at=t0)
    assert S.REPORT_ID_RE.match(row["report_id"]) and S.TOKEN_RE.match(token)
    raw = conn.execute("SELECT row_to_json(r)::text FROM product_reports r WHERE report_id = %s", (row["report_id"],)).fetchone()[0]
    assert token not in raw and S.token_sha256(token) in raw
    assert row["upload_tokens"] == [{"sha256": S.token_sha256(token), "minted_at": S.stamp(t0), "used_at": None}]
    assert row["upload_expires_at"] - row["created_at"] == S.UPLOAD_TTL == dt.timedelta(hours=6)
    assert row["owner_principal_id"] == "prn_alice" and row["candidates"]["items"][0]["candidate_id"] == "c1"
    other, token2 = _new(conn)
    assert other["report_id"] != row["report_id"] and token2 != token


def test_the_capability_opens_only_its_own_report_until_it_expires(conn):
    a, ta = _new(conn)
    b, tb = _new(conn)
    assert S.by_capability(conn, a["report_id"], ta)["report_id"] == a["report_id"]

    def refused(rid, tok, **kw):
        with pytest.raises(S.UploadRefused) as e:
            S.by_capability(conn, rid, tok, **kw)
        return e.value.status, e.value.code
    assert refused(a["report_id"], S.new_upload_token()) == (403, "UPLOAD_TOKEN_INVALID")      # wrong
    assert refused(a["report_id"], tb) == (403, "UPLOAD_TOKEN_INVALID")                        # another report's
    assert refused(a["report_id"], "x" * 10) == (403, "UPLOAD_TOKEN_INVALID")                  # malformed
    assert refused("rpt_" + "0" * 24, ta) == (403, "UPLOAD_TOKEN_INVALID")                     # no such report
    assert refused("../etc", ta) == (403, "UPLOAD_TOKEN_INVALID")
    later = S.now() + dt.timedelta(hours=6, seconds=1)
    assert refused(a["report_id"], ta, at=later) == (410, "UPLOAD_EXPIRED")
    assert [S.capability_state(a, t) for t in (None, tb, ta)] == ["absent", "invalid", "valid"]
    assert S.capability_state(a, ta, later) == "expired"
    locked = S.by_capability(conn, b["report_id"], tb, for_update=True)
    assert "html" not in locked and [e["sha256"] for e in locked["upload_tokens"]] == [S.token_sha256(tb)]


# ───────────────────────────────────────────────────────────────── privacy and the list
def test_the_owner_reaches_every_report_and_a_principal_only_its_own(conn):
    mine, _ = _new(conn)
    alice, _ = _new(conn, owner="prn_alice_store")
    bob, _ = _new(conn, owner="prn_bob_store")
    assert S.get(conn, alice["report_id"], principal_id=None)["report_id"] == alice["report_id"]          # the owner: any
    assert S.get(conn, alice["report_id"], principal_id="prn_alice_store")["owner_principal_id"] == "prn_alice_store"
    for rid, who in ((alice["report_id"], "prn_bob_store"), (mine["report_id"], "prn_alice_store"),       # NULL owner: never "open"
                     ("rpt_" + "e" * 24, "prn_bob_store"), ("not-an-id", None)):
        with pytest.raises(S.UnknownReport):
            S.get(conn, rid, principal_id=who)
    ids = [r["report_id"] for r in S.list_for(conn, "prn_alice_store")]
    assert ids == [alice["report_id"]]
    everyone = S.list_for(conn, None, limit=200)
    assert {mine["report_id"], alice["report_id"], bob["report_id"]} <= {r["report_id"] for r in everyone}
    assert all(set(r) == {"report_id", "owner_principal_id", "status", "request", "candidates", "round", "created_at", "updated_at",
                          "upload_expires_at", "compiled", "compiled_at", "uploads"} for r in everyone)


def test_the_list_is_newest_first_with_a_cursor(conn):
    t = S.now()
    rows = [_new(conn, owner="prn_carol_store", at=t + dt.timedelta(seconds=i))[0]["report_id"] for i in range(3)]
    listed = [r["report_id"] for r in S.list_for(conn, "prn_carol_store")]
    assert listed == rows[::-1]
    assert [r["report_id"] for r in S.list_for(conn, "prn_carol_store", before=rows[2])] == rows[1::-1]
    assert [r["report_id"] for r in S.list_for(conn, "prn_carol_store", limit=1)] == [rows[2]]


# ───────────────────────────────────────────────────────────────── uploads
def _up(conn, rid, packet, raw=b"text", round_=1, source="reddit", **kw):
    return S.add_upload(conn, rid, packet_id=packet, round_=round_, source=source, kind="search", raw=raw, status=kw.pop("status", "OK"),
                        parsed=kw.pop("parsed", {"candidate_id": "c1", "records": [{"title": raw.decode()[:20]}], "next_targets": []}),
                        refused=kw.pop("refused", []), **kw)


def test_an_upload_is_idempotent_per_packet_and_a_reupload_replaces(conn):
    row, _ = _new(conn)
    rid = row["report_id"]
    first = _up(conn, rid, "r1-c1-reddit", b"first", status="BLOCKED", refused=[{"code": "BLOCKED"}])
    again = _up(conn, rid, "r1-c1-reddit", b"second, longer")          # a re-upload replaces (here: OK over BLOCKED; see NEW-1)
    assert first["replaced"] is False and again["replaced"] is True and again["uploads"] == 1
    ups = S.uploads(conn, rid)
    assert len(ups) == 1 and ups[0]["bytes"] == len(b"second, longer") and ups[0]["status"] == "OK"
    assert ups[0]["sha256"] == S.content_sha256(b"second, longer") and ups[0]["refused"] == []
    assert ups[0]["parsed"]["records"] == [{"title": "second, longer"}]
    _up(conn, rid, "r2-c1-amazon-0", round_=2, source="amazon", status="BLOCKED")
    assert [u["packet_id"] for u in S.uploads(conn, rid, round_=2)] == ["r2-c1-amazon-0"]
    assert S.upload_counts(S.uploads(conn, rid)) == {"total": 2, "by_round": {"1": 1, "2": 1},
                                                     "by_source": {"amazon": {"BLOCKED": 1}, "reddit": {"OK": 1}}}


def test_the_upload_caps_are_two_megabytes_and_three_hundred_packets(conn):
    row, _ = _new(conn)
    rid = row["report_id"]
    with pytest.raises(S.UploadRefused) as e:
        _up(conn, rid, "big", b"x" * (S.MAX_UPLOAD_BYTES + 1))
    assert (e.value.status, e.value.code) == (413, "UPLOAD_TOO_LARGE")
    assert _up(conn, rid, "p000", b"x" * S.MAX_UPLOAD_BYTES)["bytes"] == S.MAX_UPLOAD_BYTES
    with pytest.raises(S.UploadRefused) as e:
        _up(conn, rid, "../bad packet")
    assert e.value.code == "UNKNOWN_PACKET"
    for i in range(1, S.MAX_UPLOADS):
        _up(conn, rid, f"p{i:03d}", b"y")
    with pytest.raises(S.UploadRefused) as e:
        _up(conn, rid, "p300", b"y")
    assert (e.value.status, e.value.code) == (409, "UPLOAD_LIMIT_REACHED")
    assert _up(conn, rid, "p007", b"replaced at the cap")["replaced"] is True      # a re-upload never counts again
    assert len(S.uploads(conn, rid)) == S.MAX_UPLOADS


# ───────────────────────────────────────────────────────────────── status, rounds, the saved columns
def test_status_moves_only_along_the_transitions_as_compare_and_set(conn):
    row, _ = _new(conn)
    rid = row["report_id"]
    assert row["compile_started_at"] is None
    for current, wanted in (("collecting", "compiling"), ("compiling", "failed"), ("failed", "compiling"),
                            ("compiling", "compiled"), ("compiled", "compiling"), ("compiling", "compiled")):
        S.transition(conn, rid, wanted, current=current)
        assert S.get(conn, rid, principal_id=None)["status"] == wanted
    with pytest.raises(S.BadTransition):
        S.transition(conn, rid, "collecting", current="compiled")                    # an illegal edge
    with pytest.raises(S.BadTransition):
        S.transition(conn, rid, "compiling", current="failed")                       # the row no longer holds `failed`
    assert S.get(conn, rid, principal_id=None)["status"] == "compiled"
    at = S.now() - dt.timedelta(seconds=42)                                          # C9: the move to `compiling` is stamped
    S.transition(conn, rid, "compiling", current="compiled", at=at)
    assert S.get(conn, rid, principal_id=None)["compile_started_at"] == at
    S.transition(conn, rid, "failed", current="compiling")
    assert S.get(conn, rid, principal_id=None)["compile_started_at"] == at           # other moves keep it


def test_rounds_advance_once_and_the_saved_columns_round_trip(conn):
    row, _ = _new(conn)
    rid = row["report_id"]
    assert S.advance_round(conn, rid, current=1) is True
    assert S.advance_round(conn, rid, current=1) is False and S.advance_round(conn, rid, current=2) is False
    S.save_candidates(conn, rid, {"status": "ready", "items": [{"candidate_id": "c1", "title": "x", "search_terms": ["x"]}]})
    S.save_host(conn, rid, {"status": "done", "data": {"cj": {"c1": {"status": "OK"}}}})
    S.save_model(conn, rid, {"compiled_at": "2026-11-02T10:00:00Z", "decision": {"products": []}})
    S.save_verdicts(conn, rid, {"by": "agent", "items": {"c1": "worth a test order"}})
    S.save_html(conn, rid, "<!doctype html><p>report</p>")
    got = S.get(conn, rid, principal_id=None, with_html=True)
    assert got["round"] == 2 and got["host"]["data"]["cj"]["c1"]["status"] == "OK" and got["model"]["decision"] == {"products": []}
    assert got["verdicts"]["items"] == {"c1": "worth a test order"} and got["html"] == "<!doctype html><p>report</p>"
    assert "html" not in S.get(conn, rid, principal_id=None)
    assert S.html_of(conn, rid, principal_id=None) == "<!doctype html><p>report</p>"
    listed = next(r for r in S.list_for(conn, None, limit=200) if r["report_id"] == rid)
    assert listed["compiled"] is True and listed["compiled_at"] == "2026-11-02T10:00:00Z"
    S.save_verdicts(conn, rid, None)
    assert S.get(conn, rid, principal_id=None)["verdicts"] is None


def test_deleting_a_report_deletes_its_uploads(conn):
    row, _ = _new(conn)
    _up(conn, row["report_id"], "r1-c1-reddit")
    conn.execute("DELETE FROM product_reports WHERE report_id = %s", (row["report_id"],))
    assert conn.execute("SELECT count(*) FROM product_report_uploads WHERE report_id = %s", (row["report_id"],)).fetchone()[0] == 0


def test_round_targets_and_parsed_records_are_read_back_per_candidate(conn):
    row, _ = _new(conn)
    rid = row["report_id"]
    t1 = {"url": "https://www.amazon.com/dp/B01", "source": "amazon", "kind": "page", "why": "top"}
    t2 = {"url": "https://www.alibaba.com/product-detail/x_1.html", "source": "alibaba", "kind": "page", "why": "supplier"}
    _up(conn, rid, "r1-c2-amazon", source="amazon", parsed={"candidate_id": "c2", "records": [{"asin": "B01"}], "next_targets": [t1]})
    _up(conn, rid, "r1-c1-amazon", source="amazon", parsed={"candidate_id": "c1", "records": [{"asin": "B01"}], "next_targets": [t1, t1]})
    _up(conn, rid, "r1-c1-alibaba", source="alibaba", parsed={"candidate_id": "c1", "records": [], "next_targets": [t2, {"why": "no url"}]})
    _up(conn, rid, "r2-c1-amazon-0", round_=2, source="amazon", parsed={"candidate_id": "c1", "records": [{"asin": "B01", "page": 1}],
                                                                       "next_targets": [t2]})
    _up(conn, rid, "r1-c9-reddit", parsed={"candidate_id": "c9", "records": [{"title": "not a candidate"}], "next_targets": []})
    ups = S.uploads(conn, rid)
    assert S.round_targets(ups, 1) == [{**t2, "candidate_id": "c1"}, {**t1, "candidate_id": "c1"}, {**t1, "candidate_id": "c2"},
                                       ]
    by = S.parsed_by_candidate(ups, ["c1", "c2"])
    assert set(by) == {"c1", "c2"} and set(by["c1"]) == {"reddit", "amazon", "ebay", "alibaba"}
    assert by["c1"]["amazon"] == [{"asin": "B01"}, {"asin": "B01", "page": 1}] and by["c2"]["amazon"] == [{"asin": "B01"}]
    assert by["c1"]["reddit"] == [] and json.dumps(by).count("not a candidate") == 0


# ───────────────────────────────────────────────────────────────── the minted tokens
def test_every_minted_token_opens_the_report_and_only_its_hash_is_kept(conn):
    row, first = _new(conn)
    rid = row["report_id"]
    minted = [S.mint_token(conn, rid) for _ in range(3)]
    raw = conn.execute("SELECT upload_tokens::text FROM product_reports WHERE report_id = %s", (rid,)).fetchone()[0]
    assert all(t not in raw and S.token_sha256(t) in raw for t in (first, *minted)) and len(set(minted)) == 3
    for t in (first, *minted):                                                    # any held token opens the report
        assert S.by_capability(conn, rid, t)["report_id"] == rid
    other, _ = _new(conn)
    with pytest.raises(S.UploadRefused) as e:
        S.by_capability(conn, other["report_id"], minted[0])                     # never another report
    assert e.value.code == "UPLOAD_TOKEN_INVALID"
    with pytest.raises(S.UploadRefused) as e:
        S.by_capability(conn, rid, minted[2], at=S.now() + dt.timedelta(hours=6, seconds=1))   # the report's expiry ends them all
    assert e.value.code == "UPLOAD_EXPIRED"
    with pytest.raises(S.UnknownReport):
        S.mint_token(conn, "rpt_" + "0" * 24)


def test_at_most_thirty_are_held_and_the_least_recently_active_goes_first(conn):
    row, first = _new(conn)
    rid = row["report_id"]
    t0 = S.now()
    minted = [S.mint_token(conn, rid, at=t0 + dt.timedelta(seconds=i + 1)) for i in range(S.MAX_TOKENS - 1)]
    assert len(S.get(conn, rid, principal_id=None)["upload_tokens"]) == S.MAX_TOKENS == 30
    S.by_capability(conn, rid, first, for_update=True)
    S.mark_used(conn, rid, first, at=t0 + dt.timedelta(seconds=100))             # the first token: in use by a running script
    newer = [S.mint_token(conn, rid, at=t0 + dt.timedelta(seconds=200 + i)) for i in range(2)]
    held = [e["sha256"] for e in S.get(conn, rid, principal_id=None)["upload_tokens"]]
    assert len(held) == 30 and held[0] == S.token_sha256(first)                  # kept, and mint order is kept
    assert S.token_sha256(minted[0]) not in held and S.token_sha256(minted[1]) not in held
    assert held[-2:] == [S.token_sha256(t) for t in newer]
    with pytest.raises(S.UploadRefused) as e:
        S.by_capability(conn, rid, minted[0])
    assert e.value.code == "UPLOAD_TOKEN_INVALID"                                 # a dropped token: the one answer
    used = next(e for e in S.get(conn, rid, principal_id=None)["upload_tokens"] if e["sha256"] == S.token_sha256(first))
    assert used["used_at"] == S.stamp(t0 + dt.timedelta(seconds=100))


def test_concurrent_mints_never_lose_a_token():
    """Two status calls mint at once: the row lock serialises them, so both tokens are held (none overwritten)."""
    with psycopg.connect(DSN, autocommit=False) as setup:
        row, first = _new(setup)
        setup.commit()
    rid, got, errors = row["report_id"], [], []
    started = threading.Barrier(2)

    def mint():
        try:
            with psycopg.connect(DSN, autocommit=False) as c:
                started.wait(5)
                got.append(S.mint_token(c, rid))
                c.commit()
        except Exception as exc:  # noqa: BLE001 — reported below
            errors.append(exc)
    threads = [threading.Thread(target=mint) for _ in range(2)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)
        assert not errors and len(got) == 2
        with psycopg.connect(DSN) as c:
            held = [e["sha256"] for e in S.get(c, rid, principal_id=None)["upload_tokens"]]
        assert sorted(held) == sorted(S.token_sha256(t) for t in (first, *got))
    finally:
        with psycopg.connect(DSN) as c:
            c.execute("DELETE FROM product_reports WHERE report_id = %s", (rid,))


# ───────────────────────────────────────────────────────────────── review-fix round
def test_a_status_caller_without_a_token_gets_at_most_one_mint_a_minute(conn):
    """Contract C1 (R3 #2): `mint_token(every_s=...)` refuses while the report's newest token is younger than that, naming when a
    mint is allowed again; the start's token counts."""
    t0 = S.now()
    row, _first = _new(conn, at=t0)
    rid = row["report_id"]
    with pytest.raises(S.MintTooSoon) as e:
        S.mint_token(conn, rid, at=t0 + dt.timedelta(seconds=30), every_s=S.MINT_EVERY_S)
    assert e.value.mint_after == t0 + dt.timedelta(seconds=S.MINT_EVERY_S) == S.last_minted(S.get(conn, rid, principal_id=None)) + \
        dt.timedelta(seconds=60)
    later = S.mint_token(conn, rid, at=t0 + dt.timedelta(seconds=61), every_s=S.MINT_EVERY_S)
    assert len(S.get(conn, rid, principal_id=None)["upload_tokens"]) == 2 and S.by_capability(conn, rid, later)
    with pytest.raises(S.MintTooSoon):
        S.mint_token(conn, rid, at=t0 + dt.timedelta(seconds=100), every_s=S.MINT_EVERY_S)
    assert S.mint_token(conn, rid, at=t0 + dt.timedelta(seconds=100))              # without `every_s`: no limit (the store's own)


def test_a_nul_character_is_stripped_before_every_write(conn):
    """C9 (R3 #3): Postgres refuses U+0000 in jsonb and text; every JSON value and the HTML lose it before the write."""
    row, _ = S.create(conn, owner_principal_id=None, request={"message": "pet\u0000 products", "k\u0000": ["a\u0000"]},
                      candidates={"status": "ready", "items": [{"candidate_id": "c1", "title": "pet\u0000feeder",
                                                                "search_terms": ["pet feeder"]}]})
    rid = row["report_id"]
    assert row["request"] == {"message": "pet products", "k": ["a"]} and row["candidates"]["items"][0]["title"] == "petfeeder"
    S.save_verdicts(conn, rid, {"by": "agent", "items": {"c1": "good\u0000margin"}})
    S.save_model(conn, rid, {"decision": {"note": "x\u0000y"}})
    S.save_html(conn, rid, "<p>a\u0000b</p>")
    _up(conn, rid, "r1-c1-reddit", parsed={"candidate_id": "c1", "records": [{"title": "t\u0000t"}], "next_targets": []},
        refused=[{"code": "X", "why": "w\u0000"}])
    got = S.get(conn, rid, principal_id=None, with_html=True)
    assert got["verdicts"]["items"]["c1"] == "goodmargin" and got["model"]["decision"]["note"] == "xy" and got["html"] == "<p>ab</p>"
    up = S.uploads(conn, rid)[0]
    assert up["parsed"]["records"] == [{"title": "tt"}] and up["refused"] == [{"code": "X", "why": "w"}]


def test_the_uploads_digest_is_the_set_of_packets_and_their_contents(conn):
    """R3 #4: a compile records the (packet_id, sha256) set it read; any new or replaced packet changes it, order never does."""
    row, _ = _new(conn)
    rid = row["report_id"]
    _up(conn, rid, "r1-c1-reddit", b"one")
    _up(conn, rid, "r1-c1-amazon", b"two")
    first = S.uploads_digest(S.uploads(conn, rid))
    assert first == S.uploads_digest(list(reversed(S.uploads(conn, rid))))
    _up(conn, rid, "r1-c1-amazon", b"two, replaced")
    assert S.uploads_digest(S.uploads(conn, rid)) != first
    _up(conn, rid, "r1-c1-amazon", b"two")
    assert S.uploads_digest(S.uploads(conn, rid)) == first                           # the same content again: the same set
    _up(conn, rid, "r1-c1-alibaba", b"")                                             # an EMPTY packet counts too
    assert S.uploads_digest(S.uploads(conn, rid)) != first


def test_an_oversize_packet_row_holds_no_body(conn):
    """C10: the OUTPUT_TOO_LARGE row the route records for an upload over 2 MiB — no body, so the CHECKs hold."""
    row, _ = _new(conn)
    rid = row["report_id"]
    res = _up(conn, rid, "r1-c1-amazon", b"", status="OUTPUT_TOO_LARGE",
              parsed={"candidate_id": "c1", "records": [], "next_targets": []},
              refused=[{"code": "OUTPUT_TOO_LARGE", "why": "2097153 bytes"}])
    assert res["bytes"] == 0 and S.uploads(conn, rid)[0]["status"] == "OUTPUT_TOO_LARGE"


def test_a_touch_and_a_mint_at_once_lose_neither():
    """C1: reusing a token touches its last use (`mark_used`) while another caller mints: both lock the row, so the touch never
    writes back a list without the new token."""
    with psycopg.connect(DSN, autocommit=False) as setup:
        row, first = _new(setup)
        setup.commit()
    rid, got, errors = row["report_id"], [], []
    started = threading.Barrier(2)

    def touch():
        try:
            with psycopg.connect(DSN, autocommit=False) as c:
                started.wait(5)
                S.mark_used(c, rid, first)
                c.commit()
        except Exception as exc:  # noqa: BLE001 — reported below
            errors.append(exc)

    def mint():
        try:
            with psycopg.connect(DSN, autocommit=False) as c:
                started.wait(5)
                got.append(S.mint_token(c, rid))
                c.commit()
        except Exception as exc:  # noqa: BLE001 — reported below
            errors.append(exc)
    threads = [threading.Thread(target=touch), threading.Thread(target=mint)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)
        assert not errors and len(got) == 1
        with psycopg.connect(DSN) as c:
            held = {e["sha256"]: e for e in S.get(c, rid, principal_id=None)["upload_tokens"]}
        assert set(held) == {S.token_sha256(first), S.token_sha256(got[0])} and held[S.token_sha256(first)]["used_at"]
    finally:
        with psycopg.connect(DSN) as c:
            c.execute("DELETE FROM product_reports WHERE report_id = %s", (rid,))


# ───────────────────────────────────────────────────────────────── review-fix round 2
def test_an_ok_packet_is_never_replaced_by_a_worse_one(conn):
    """NEW-1: the ON CONFLICT update only runs when the stored row is not OK or the new one is OK; the answer says so."""
    row, _ = _new(conn)
    rid = row["report_id"]
    first = _up(conn, rid, "r1-c1-reddit", b"good")
    assert first["kept_earlier"] is False and first["replaced"] is False
    for status, raw in (("EMPTY", b""), ("BLOCKED", b"blocked"), ("OUTPUT_TOO_LARGE", b""), ("UNRECOGNISED", b"?")):
        res = _up(conn, rid, "r1-c1-reddit", raw, status=status, parsed={"candidate_id": "c1", "records": [], "next_targets": []})
        assert (res["kept_earlier"], res["replaced"]) == (True, False), status
        kept = S.uploads(conn, rid)[0]
        assert (kept["status"], kept["sha256"], kept["parsed"]["records"]) == ("OK", S.content_sha256(b"good"), [{"title": "good"}])
    res = _up(conn, rid, "r1-c1-reddit", b"better")                              # OK replaces OK
    assert (res["kept_earlier"], res["replaced"]) == (False, True) and S.uploads(conn, rid)[0]["sha256"] == S.content_sha256(b"better")
    _up(conn, rid, "r1-c1-amazon", b"", status="EMPTY", parsed={"candidate_id": "c1", "records": [], "next_targets": []})
    res = _up(conn, rid, "r1-c1-amazon", b"blocked", status="BLOCKED")           # a non-OK row is replaced by anything
    assert (res["kept_earlier"], res["replaced"]) == (False, True)
    res = _up(conn, rid, "r1-c1-amazon", b"now it reads")
    assert (res["kept_earlier"], res["replaced"]) == (False, True)
    assert {u["packet_id"]: u["status"] for u in S.uploads(conn, rid)} == {"r1-c1-amazon": "OK", "r1-c1-reddit": "OK"}


def test_a_database_that_ran_the_earlier_draft_of_0068_gets_compile_started_at(conn):
    """NEW-4: 0068 was edited in place; its closing ALTER brings a database that ran the draft without `compile_started_at` to
    the same shape (the test transaction is rolled back)."""
    conn.execute("ALTER TABLE product_reports DROP COLUMN compile_started_at")
    assert conn.execute("SELECT count(*) FROM information_schema.columns WHERE table_name = 'product_reports' "
                        "AND column_name = 'compile_started_at'").fetchone()[0] == 0
    conn.execute(MIGRATION.read_text())
    assert conn.execute("SELECT data_type FROM information_schema.columns WHERE table_name = 'product_reports' "
                        "AND column_name = 'compile_started_at'").fetchone()[0] == "timestamp with time zone"
    row, _ = _new(conn)
    S.transition(conn, row["report_id"], "compiling", current="collecting")
    assert S.get(conn, row["report_id"], principal_id=None)["compile_started_at"] is not None
