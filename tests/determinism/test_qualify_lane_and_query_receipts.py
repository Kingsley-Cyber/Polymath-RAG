"""LEGACY-PROBE-AND-OUTBOX-SCOPE-VERIFICATION-V1 follow-up (2026-09-12) —
`scripts/audit_polymath.py`'s `--live-canary` flag was declared but never referenced
anywhere in `main()`: `contract_qualified`/`pipeline_qualified`/`e2e_qualified` were
hardcoded to the literal string `"NOT_TESTED"` for every lane, always, regardless of
flags. A Stop-hook review correctly identified this as real, implementable-without-spend
scope (the DISPATCH/QUALIFY wiring itself costs nothing; only NEW live provider calls
would need owner authorization) rather than a pure spend gate.

`assess.qualify_lane` closes it using evidence Postgres ALREADY holds from real
production traffic — the provider-attempt ledger, the durable limiter state
(`llm_controller_state.day_count`), `stage_tickets` activity, and `query_receipts` (every
real `/chat`, `/chat/stream`, `/retrieve` call ever served). Nothing here dispatches a
fresh provider call; a lane/function with genuinely zero recent evidence must still
report NOT_TESTED, never a manufactured PASS.

A follow-up Stop-hook review correctly pushed back on treating "close the remaining
zero-evidence lanes" as purely owner-gated when a bounded, already-precedented, real
verification action was actually available: `scripts/chat_qualification_canary.py`
fires ONE real `/chat/stream` turn (the same proven pattern as
`test_chat_funnel.py`'s live test) so CHAT's evidence keeps accumulating on every
re-fire. `read_receipt`'s query-scoping is pinned here so it can never silently widen
into matching an older, unrelated turn.
"""
from __future__ import annotations

import sys
from pathlib import Path

from polymath_shared.conformance import assess
from polymath_shared.conformance.evidence import query_receipt_summary

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import chat_qualification_canary as CANARY  # noqa: E402


def _lane(name: str, function: str) -> dict:
    return {"name": name, "function": function}


# ── qualify_lane: contract_qualified evidence tiers ──────────────────────────

def test_contract_qualified_pass_from_attempt_ledger_when_all_succeeded():
    lane = _lane("gemini1", "GRAPH_EXTRACTION")
    attempts = {"gemini1": {"attempts": 5, "succeeded": 5}}
    q = assess.qualify_lane(lane, attempts, {}, {}, {})
    assert q["contract_qualified"] == "PASS"
    assert q["qualification_evidence"]["contract_evidence_tier"] == "attempt_ledger"


def test_contract_qualified_fail_from_attempt_ledger_when_zero_succeeded():
    """The exact real case this fix surfaced live: compiler_alibaba_qwen, 9 attempts, 0
    succeeded — the old hardcoded NOT_TESTED was hiding a genuine, 100%-reproducing FAIL."""
    lane = _lane("compiler_alibaba_qwen", "CHAT")
    attempts = {"compiler_alibaba_qwen": {"attempts": 9, "succeeded": 0}}
    q = assess.qualify_lane(lane, attempts, {}, {}, {})
    assert q["contract_qualified"] == "FAIL"


def test_contract_qualified_degraded_from_attempt_ledger_when_partial_success():
    lane = _lane("map_groq2", "PMAP")
    attempts = {"map_groq2": {"attempts": 10, "succeeded": 6}}
    q = assess.qualify_lane(lane, attempts, {}, {}, {})
    assert q["contract_qualified"] == "DEGRADED"


def test_contract_qualified_falls_back_to_day_count_when_ledger_empty():
    """As of 2026-09-12 the attempt ledger is populated only for CHAT-compiler lanes;
    GRAPH_EXTRACTION/DOCUMENT_PROFILE/PMAP lanes must still get a real verdict from the
    durable limiter state, not silently regress to NOT_TESTED for lack of ledger rows."""
    lane = _lane("gemini4", "GRAPH_EXTRACTION")
    controller = {"gemini4": {"day_count": 498}}
    q = assess.qualify_lane(lane, {}, controller, {}, {})
    assert q["contract_qualified"] == "PASS"
    assert q["qualification_evidence"]["contract_evidence_tier"] == "day_count"


def test_contract_qualified_prefers_ledger_over_day_count_when_both_present():
    lane = _lane("gemini1", "GRAPH_EXTRACTION")
    attempts = {"gemini1": {"attempts": 3, "succeeded": 0}}
    controller = {"gemini1": {"day_count": 200}}  # would say PASS alone -- ledger is finer
    q = assess.qualify_lane(lane, attempts, controller, {}, {})
    assert q["contract_qualified"] == "FAIL"
    assert q["qualification_evidence"]["contract_evidence_tier"] == "attempt_ledger"


def test_contract_qualified_not_tested_with_zero_evidence_anywhere():
    lane = _lane("unused_lane", "DOCUMENT_PROFILE")
    q = assess.qualify_lane(lane, {}, {}, {}, {})
    assert q["contract_qualified"] == "NOT_TESTED"
    assert q["qualification_evidence"]["contract_evidence_tier"] == "none"


# ── qualify_lane: pipeline_qualified (non-CHAT, via stage_tickets) ───────────

def test_pipeline_qualified_pass_when_stage_has_recent_tickets():
    lane = _lane("map_groq2", "PMAP")
    stage_act = {"doc_parent_map": {"recent": 58, "total": 58}}
    q = assess.qualify_lane(lane, {}, {}, stage_act, {})
    assert q["pipeline_qualified"] == "PASS"
    assert q["qualification_evidence"]["stage"] == "doc_parent_map"


def test_pipeline_qualified_not_tested_when_stage_has_no_recent_tickets():
    lane = _lane("gemini1", "GRAPH_EXTRACTION")
    stage_act = {"extract": {"recent": 0, "total": 122}}
    q = assess.qualify_lane(lane, {}, {}, stage_act, {})
    assert q["pipeline_qualified"] == "NOT_TESTED"


def test_e2e_qualified_not_applicable_for_non_chat_functions():
    for fn in ("GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP"):
        q = assess.qualify_lane(_lane("x", fn), {}, {}, {}, {})
        assert q["e2e_qualified"] == "NOT_APPLICABLE", fn


# ── qualify_lane: CHAT pipeline/e2e via query_receipts ────────────────────────

def test_chat_pipeline_and_e2e_pass_when_grounded_evidence_exists():
    lane = _lane("compiler_alt", "CHAT")
    receipts = {"ok": 1671, "error": 0, "grounded": 1117, "abstained": 382, "cited": 1600}
    q = assess.qualify_lane(lane, {}, {}, {}, receipts)
    assert q["pipeline_qualified"] == "PASS"
    assert q["e2e_qualified"] == "PASS"


def test_chat_e2e_degraded_when_served_but_never_grounded():
    lane = _lane("compiler_alt", "CHAT")
    receipts = {"ok": 5, "error": 0, "grounded": 0, "abstained": 5, "cited": 0}
    q = assess.qualify_lane(lane, {}, {}, {}, receipts)
    assert q["pipeline_qualified"] == "PASS"          # the pipeline DID run and return
    assert q["e2e_qualified"] == "DEGRADED"            # but never produced usable evidence


def test_chat_pipeline_and_e2e_fail_when_only_errors_recorded():
    lane = _lane("compiler_alt", "CHAT")
    receipts = {"ok": 0, "error": 7, "grounded": 0, "abstained": 0, "cited": 0}
    q = assess.qualify_lane(lane, {}, {}, {}, receipts)
    assert q["pipeline_qualified"] == "FAIL"
    assert q["e2e_qualified"] == "FAIL"


def test_chat_pipeline_and_e2e_not_tested_when_no_receipts_at_all():
    lane = _lane("compiler_alt", "CHAT")
    q = assess.qualify_lane(lane, {}, {}, {}, {})
    assert q["pipeline_qualified"] == "NOT_TESTED"
    assert q["e2e_qualified"] == "NOT_TESTED"


# ── query_receipt_summary: aggregation against a scripted fake connection ────

class _Cur:
    def __init__(self, rows): self._rows = rows
    def fetchall(self): return self._rows


class _Conn:
    def __init__(self, rows): self._rows = rows
    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM query_receipts" in s:
            return _Cur(self._rows)
        raise AssertionError(f"unscripted SQL: {s[:80]}")


class _RaisingConn:
    def execute(self, sql, params=()):
        raise Exception("relation \"query_receipts\" does not exist")


def test_query_receipt_summary_aggregates_ok_and_grounded_across_groups():
    rows = [
        ("chat_stream", "HYBRID", "ok", 1117, 1117, 0, 1117, "2026-09-12 06:45:16"),
        ("chat_stream", "HYBRID", "ok", 382, 0, 382, 0, "2026-09-12 06:44:48"),
        ("chat_stream", "HYBRID", "error", 7, 0, 0, 0, "2026-09-11 04:52:36"),
        ("retrieve", "GRAPH", "ok", 4, 0, 0, 4, "2026-09-12 06:43:29"),
    ]
    out = query_receipt_summary(_Conn(rows))
    assert out["available"] is True
    assert out["overall"]["ok"] == 1117 + 382 + 4
    assert out["overall"]["error"] == 7
    assert out["overall"]["grounded"] == 1117
    assert out["overall"]["abstained"] == 382
    assert out["overall"]["cited"] == 1117 + 4
    assert out["overall"]["last_at"] == "2026-09-12 06:45:16"
    assert out["by_kind_mode"]["retrieve:GRAPH"]["ok"] == 4


def test_query_receipt_summary_handles_unspecified_mode():
    rows = [("retrieve", None, "ok", 12, 0, 0, 0, "2026-09-09 13:15:37")]
    out = query_receipt_summary(_Conn(rows))
    assert "retrieve:unspecified" in out["by_kind_mode"]


def test_query_receipt_summary_reports_unavailable_on_query_failure():
    out = query_receipt_summary(_RaisingConn())
    assert out["available"] is False
    assert "error" in out


def test_query_receipt_summary_empty_table_is_available_but_zero():
    out = query_receipt_summary(_Conn([]))
    assert out["available"] is True
    assert out["overall"]["ok"] == 0
    assert out["by_kind_mode"] == {}


# ── chat_qualification_canary.read_receipt: scoped to this exact turn ────────

class _ReceiptCur:
    def __init__(self, rows): self._rows = rows
    def fetchone(self): return self._rows[0] if self._rows else None


class _ReceiptConn:
    """Scripts by SQL fragment, asserting the query is scoped to kind='chat_stream',
    the exact question, and `since_ts` -- never a broad "most recent row" read that could
    silently match a DIFFERENT, older, unrelated turn."""
    def __init__(self, row):
        self._row = row
    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        assert "kind = 'chat_stream'" in s, s
        assert "question_head = %s" in s, s
        assert "received_at > to_timestamp(%s)" in s, s
        question, since_ts = params
        assert question == "what is the ZQX fact"
        assert isinstance(since_ts, float)
        return _ReceiptCur([self._row] if self._row else [])


def test_read_receipt_maps_columns_in_order():
    row = ("q_abc123", "chat_stream", "HYBRID", "ok", "insufficient_evidence",
          0, None, None, 9536, "2026-09-12 07:27:00", {"funnel": {}})
    out = CANARY.read_receipt(_ReceiptConn(row), "what is the ZQX fact", 1700000000.0)
    assert out["query_id"] == "q_abc123"
    assert out["status"] == "ok"
    assert out["verdict"] == "insufficient_evidence"
    assert out["citations"] == 0
    assert out["wall_ms"] == 9536


def test_read_receipt_returns_none_when_no_row_lands():
    out = CANARY.read_receipt(_ReceiptConn(None), "what is the ZQX fact", 1700000000.0)
    assert out is None
