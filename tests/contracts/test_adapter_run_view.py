"""TRAIL-INTERFACE-V1 T1 — the Research section's read model: runs are listed newest first and scoped to their principal, a
run's outcome is one readable line built from TrailSignal's record COUNTS, progress covers every manifest step, the web
boundary opens both routes to signed-in users (ownership stays in the route), and the view recompiles output through the
fixed readers."""
from __future__ import annotations

from polymath_shared.adapter import run_view, store
from polymath_shared.adapter.transitions import RunState

from orchestrator import web_boundary as B


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    """Records the SQL and parameters; answers with the given rows."""

    def __init__(self, rows=()):
        self.rows, self.calls = list(rows), []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))
        return _Rows(self.rows)


def _row(**over):
    base = {"run_id": "adr_1", "adapter_id": "ecommerce.product_research", "adapter_version": "0.7.0", "status": "completed",
            "current_step_id": None, "steps_accepted": 40, "harness_action_count": 5, "input": {"seed": "  cold hands\nwhile filming "},
            "gap": None, "failure": None, "agent_identity": "claude-code", "owner_principal_id": None, "created_at": None,
            "updated_at": None, "terminal_at": None, "scores": 0, "refusals": 6}
    base.update(over)
    return tuple(base[k] for k in store.RUN_LIST_COLS)


def test_a_friend_lists_only_their_own_runs():
    conn = _Conn([_row()])
    runs = run_view.list_runs(conn, "prn_fred", limit=10)
    sql, params = conn.calls[0]
    assert "r.owner_principal_id = %s" in sql and params[0] == "prn_fred"
    assert runs[0]["title"] == "cold hands while filming" and runs[0]["outcome"] == "TrailSignal refused all 6 scores"


def test_the_owner_lists_every_run_newest_first_with_filters_and_a_cursor():
    conn = _Conn([_row()])
    run_view.list_runs(conn, None, status="completed", adapter_id="ecommerce.product_research", limit=5000, before="adr_0")
    sql, params = conn.calls[0]
    assert "owner_principal_id =" not in sql
    assert "ORDER BY r.created_at DESC" in sql and "r.status = %s" in sql and "r.adapter_id = %s" in sql
    assert params == ("completed", "ecommerce.product_research", "adr_0", 200)          # the limit is capped


def test_outcomes_read_like_sentences_and_never_carry_a_score_value():
    assert run_view.outcome_of("awaiting_agent", None, None, None) == "Waiting for your agent"
    assert run_view.outcome_of("awaiting_harness", None, None, None) == "Waiting for web research"
    assert run_view.outcome_of("terminal_gap", None, None, {"code": "TRAIL_REFUSED"}) == "Stopped: TRAIL_REFUSED"
    assert run_view.outcome_of("completed", 2, 1, None) == "2 scored, 1 refused"
    assert run_view.outcome_of("completed", 0, 1, None) == "TrailSignal refused the score"
    assert run_view.outcome_of("completed", 0, 0, None) == "Completed, nothing scored"
    assert run_view.outcome_of("completed", None, None, None) == "Completed"


def test_titles_come_from_the_input_and_are_bounded():
    assert run_view.title_of({"seed_idea": "Why notation matters"}) == "Why notation matters"
    assert run_view.title_of({"question": "x" * 300}).endswith("…") and len(run_view.title_of({"question": "x" * 300})) == 140
    assert run_view.title_of({}) == "Untitled run" and run_view.title_of(None) == "Untitled run"


def test_progress_covers_every_manifest_step_in_order():
    steps = {"A": {"type": "VALIDATE", "title": "Understand"}, "B": {"type": "AGENT_REASON", "title": "Plan"},
             "C": {"type": "EXTERNAL_OPERATION"}, "D": {"type": "COMPILE_RESULT"}}
    stored = [{"step_id": "A", "status": "executed"}, {"step_id": "B", "status": "accepted"}, {"step_id": "B", "status": "accepted"},
              {"step_id": "C", "status": "issued"}]
    state = RunState(run_id="adr_1", adapter_id="x", status="awaiting_harness", current_step_id="C")
    rows = run_view.progress_of(steps, stored, state)
    assert [(r["step_id"], r["state"], r["visits"]) for r in rows] == [
        ("A", "done", 1), ("B", "done", 2), ("C", "waiting_harness", 1), ("D", "pending", 0)]
    assert rows[3]["title"] == "D"                                              # a step without a title shows its id


def test_the_web_boundary_opens_both_routes_to_signed_in_users():
    assert B.classify("GET", "/adapter/runs") == B.USER
    assert B.classify("GET", "/adapter/adr_1/view") == B.USER
    assert B.classify("POST", "/adapter/runs") is None                          # nothing else under that path


def test_the_gates_come_from_every_qualify_step_once():
    steps = [
        {"step_id": "R_qualify", "output": {"operation_kind": "opportunity.qualify",
                                             "qualifications": [{"record_id": "q_m1", "stage": "market_delta"}]}},
        {"step_id": "V_score", "output": {"operation_kind": "opportunity.score", "qualifications": []}},      # unfilled
        {"step_id": "U_qualify", "output": {"operation_kind": "opportunity.qualify",
                                             "qualifications": [{"record_id": "q_s1", "stage": "supply"}, {"record_id": "q_m1", "stage": "market_delta"}]}},
        {"step_id": "old", "output": {"operation_kind": "opportunity.qualify", "qualification": {"record_id": "q_legacy", "stage": "supply"}}},
        {"step_id": "W", "output": {"interpretation": "agent text"}},
    ]
    assert [q["record_id"] for q in run_view.all_qualifications(steps)] == ["q_m1", "q_s1", "q_legacy"]
