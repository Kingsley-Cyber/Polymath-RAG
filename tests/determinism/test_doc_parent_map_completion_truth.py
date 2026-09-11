"""COMPLETION-TRUTH-V1 (D-3) — `MappingOutcome.complete` is CURRENT DURABLE STATE.

Reproduces the defect U2-PERSISTENCE-CANARY-V1 measured live on 2026-09-10: a cinema
document with 5 eligible parents, all 5 mapped and projected, 0 unresolved, but TWO
stale historical batch rows that never dispatched (`raw_response_hash IS NULL`). The
old predicate `not unresolved and batches_partial == 0` reported INCOMPLETE, the stage
raised `DOC_PARENT_MAP_INCOMPLETE: unresolved=0 partial=2`, and the ticket re-armed —
a successful document reporting failure.

Provider-free and DB-free: `complete` is a pure property over the outcome.
"""
from __future__ import annotations

from workers.doc_parent_map_worker import MappingOutcome


def _outcome(**kw) -> MappingOutcome:
    base = dict(doc_id="doc_test", map_contract="map-compiler-v1",
                eligible_parents=5, excluded_parents=0, batches_total=1,
                batches_done=1, batches_partial=0, parents_mapped=5)
    base.update(kw)
    return MappingOutcome(**base)


def test_stale_non_dispatched_batches_do_not_block_completion() -> None:
    """THE REGRESSION: 5 eligible · 5 mapped · 0 unresolved · 2 stale rows -> COMPLETE."""
    o = _outcome(parents_mapped=5, unresolved_parent_ids=(), batches_partial=2, batches_done=1)
    assert o.unresolved_parent_ids == ()
    assert o.batches_partial == 2          # the stale rows are still RECORDED …
    assert o.complete is True              # … but they are not the completion authority


def test_unresolved_parents_still_mean_incomplete() -> None:
    """The other direction must not regress: real unmapped parents -> INCOMPLETE."""
    o = _outcome(parents_mapped=3, unresolved_parent_ids=("P4", "P5"), batches_partial=0)
    assert o.complete is False


def test_unresolved_incomplete_even_when_every_batch_is_done() -> None:
    """A clean batch ledger cannot mask an unmapped eligible parent."""
    o = _outcome(parents_mapped=4, unresolved_parent_ids=("P5",),
                 batches_partial=0, batches_done=3)
    assert o.complete is False


def test_zero_eligible_parents_is_complete() -> None:
    """Nothing eligible is vacuously complete (the stage short-circuits this case)."""
    o = _outcome(eligible_parents=0, parents_mapped=0, unresolved_parent_ids=())
    assert o.complete is True


def test_completion_is_independent_of_every_diagnostic_counter() -> None:
    """Only unresolved decides. Refusals/429s/failures are diagnostics on the receipt.

    A run CAN legitimately end complete while having seen transport noise earlier —
    what matters is whether any eligible parent is still unmapped in durable state.
    """
    o = _outcome(unresolved_parent_ids=(), batches_partial=7, limiter_refusals=926,
                 http_429=11, http_failures=3, empty_completions=2, compiler_invalid=4)
    assert o.complete is True
    o2 = _outcome(unresolved_parent_ids=("P1",), batches_partial=0, limiter_refusals=0)
    assert o2.complete is False


def test_parents_newly_mapped_is_unaffected_by_the_fix() -> None:
    o = _outcome(parents_mapped=5, parents_already_mapped=2, unresolved_parent_ids=())
    assert o.parents_newly_mapped == 3
