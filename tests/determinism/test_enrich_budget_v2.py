"""ENRICH-BUDGET-V2: verbose lanes hit finish=length at 700*n+200 and the
ladder split truncated envelopes into more truncated envelopes (measured
2026-09-02 with per-call logging: 29 of 54 parents ground for 20+ min).
Pins: 30 % headroom per parent + 300 envelope, cap 8000; a likely-truncated
envelope is retried ONCE with a doubled budget before any split."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "tests" / "determinism"))

from polymath_shared.latent.compiler import (ParentInput, _looks_truncated, call_budget,
                                             compile_parents_microbatched)
from polymath_shared.latent.contract import PRODUCTION_BOUNDS, QUALIFICATION_BOUNDS
from test_enrich_microbatch import _item, _parent   # the suite's envelope helpers


def test_call_budget_headroom_and_cap():
    assert call_budget(QUALIFICATION_BOUNDS, 1) == int(700 * 1.3) + 300
    assert call_budget(PRODUCTION_BOUNDS, 4) == int(900 * 4 * 1.3) + 300
    assert call_budget(PRODUCTION_BOUNDS, 8) == 8000            # capped
    assert call_budget(PRODUCTION_BOUNDS, 0) == call_budget(PRODUCTION_BOUNDS, 1)


def test_looks_truncated_is_a_chars_per_token_heuristic():
    assert _looks_truncated("x" * 6000, 3000) is True      # 2 chars/token = at the cap
    assert _looks_truncated("x" * 2000, 3000) is False


def test_valid_long_envelope_is_not_re_asked():
    """The doubled re-ask fires only when the envelope is DEAD — a complete,
    parseable envelope that happens to be long costs exactly one call."""
    parents = [_parent(f"Q{i}", n_children=2) for i in range(3)]
    calls = []

    def transport(items):
        out = []
        for item_id, system, user, max_tokens in items:
            calls.append(max_tokens)
            refs = {p.parent_id: [0, 1] for p in parents}
            env = json.dumps({"items": [_item(r, rs) for r, rs in refs.items()]})
            out.append((item_id, env + " " * (2 * max_tokens), None))   # long but valid
        return out

    out = compile_parents_microbatched(transport, parents, PRODUCTION_BOUNDS, 6000)
    assert [cp.status for cp in out] == ["READY"] * 3 and len(calls) == 1


def test_likely_truncated_envelope_is_retried_with_a_bigger_budget_before_splitting():
    parents = [_parent(f"P{i}", n_children=2) for i in range(4)]
    calls = []

    def transport(items):
        out = []
        for item_id, system, user, max_tokens in items:
            calls.append((len(items), max_tokens))
            first_budget = call_budget(PRODUCTION_BOUNDS, 4)
            if max_tokens == first_budget:
                # an envelope cut off at the cap: long, unparseable
                out.append((item_id, "{\"items\": [" + "x" * (2 * first_budget), None))
            else:
                # the doubled budget: a complete, valid microbatch envelope
                refs = {p.parent_id: [0, 1] for p in parents}
                out.append((item_id, json.dumps({"items": [_item(r, rs) for r, rs in refs.items()]}), None))
        return out

    out = compile_parents_microbatched(transport, parents, PRODUCTION_BOUNDS, 6000)
    assert [cp.status for cp in out] == ["READY"] * 4
    assert len(calls) == 2, f"expected one retry and no split, got {calls}"
    assert calls[1][1] == min(call_budget(PRODUCTION_BOUNDS, 4) * 2, 8000)
