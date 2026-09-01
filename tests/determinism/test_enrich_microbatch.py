"""ENRICH-MICROBATCH-V1 exit gate: envelope discipline (ref-set
equality, no invented/duplicate refs), partial acceptance (a bad item
never re-buys its batchmates), the 8→4→2→1 split ladder down to the
proven single-parent path, per-item ceiling checks, token-aware
packing, and hard-case integration."""
from __future__ import annotations

import json

from polymath_shared.latent.compiler import (
    ParentInput,
    compile_microbatched_with_hard_case,
    compile_parents_microbatched,
)
from polymath_shared.latent.contract import EnrichmentBounds
from polymath_shared.latent.gate import sanitize_microbatch

BOUNDS = EnrichmentBounds()


def _item(ref, refs):
    return {"parent_ref": ref,
            "summary": "A section about lifecycle policies and tiers.",
            "children": [{"ref": i, "gist": f"Gist for passage {i}."}
                         for i in refs],
            "abstraction": "Automated policies move resources between "
                           "cost tiers as value decays over time.",
            "mechanisms": ["Rules watch age and trigger transitions."],
            "affordances": ["Cut storage cost without manual sweeps."],
            "questions": ["How do libraries archive unused items?"]}


def _parent(pid, n_children=2, words=6):
    return ParentInput(pid, [(f"{pid}_c{i}", i,
                              " ".join(["text"] * words) + f" {i}")
                             for i in range(n_children)])


def _envelope(refs_by_parent, drop=(), dupe=(), invent=()):
    items = [_item(r, refs) for r, refs in refs_by_parent.items()
             if r not in drop]
    items += [_item(r, refs_by_parent[r]) for r in dupe]
    items += [_item(r, [0]) for r in invent]
    return json.dumps({"items": items})


# ---------------------------------------------------------------- gate

def test_envelope_ref_discipline():
    expected = {"P0": [0, 1], "P1": [0, 1]}
    raw = _envelope(expected, drop=("P1",), invent=("P9",))
    out = sanitize_microbatch(raw, expected, BOUNDS)
    assert out["P0"][0].ok
    assert out["P1"][0].error_class == "ENRICH_NO_RESPONSE"   # missing
    assert set(out) == {"P0", "P1"}                # invented P9 ignored


def test_duplicate_ref_first_wins():
    expected = {"P0": [0, 1]}
    out = sanitize_microbatch(_envelope(expected, dupe=("P0",)),
                              expected, BOUNDS)
    assert out["P0"][0].ok


def test_unparseable_envelope_fails_every_ref():
    expected = {"P0": [0], "P1": [0]}
    out = sanitize_microbatch("total garbage", expected, BOUNDS)
    assert all(g.error_class == "ENRICH_UNPARSEABLE"
               for g, _ in out.values())


def test_item_validation_is_the_single_parent_gate():
    expected = {"P0": [0, 1, 2, 3]}
    bad = json.dumps({"items": [{**_item("P0", [0]),  # 25% coverage
                                 }]})
    out = sanitize_microbatch(bad, expected, BOUNDS)
    assert out["P0"][0].error_class == "ENRICH_GISTS_BELOW_FLOOR"


# ------------------------------------------------------------- compiler

def _ok_transport(items):
    """Answers microbatch prompts with an envelope and single-parent
    prompts (the ladder floor) with the bare per-parent object."""
    out = []
    for item_id, system, user, _mt in items:
        if "ITEM " in user:
            refs = {}
            for block in user.split("ITEM ")[1:]:
                ref = block.split("\n", 1)[0].strip()
                n = block.count("\n[")
                refs[ref] = list(range(max(n, 1)))
            out.append((item_id, json.dumps(
                {"items": [_item(r, rs) for r, rs in refs.items()]}),
                None))
        else:
            n = max(user.count("\n["), user.count("["), 1)
            bare = {k: v for k, v in _item("X", [0, 1]).items()
                    if k != "parent_ref"}
            out.append((item_id, json.dumps(bare), None))
    return out


def test_microbatch_happy_path_one_call_many_parents():
    calls = []

    def transport(items):
        calls.append(len(items))
        return _ok_transport(items)

    parents = [_parent(f"P{i}") for i in range(6)]
    out = compile_parents_microbatched(transport, parents, BOUNDS, 6000)
    assert [cp.status for cp in out] == ["READY"] * 6
    assert sum(calls) == 1                      # ONE call, six parents
    assert all(cp.prompt_version == "parent-enrichment-microbatch-v1"
               for cp in out)


def test_partial_acceptance_bad_item_keeps_batchmates():
    def transport(items):
        rows = []
        for item_id, _s, user, _mt in items:
            refs = {}
            for block in user.split("ITEM ")[1:]:
                ref = block.split("\n", 1)[0].strip()
                refs[ref] = [0, 1]
            items_out = []
            for r, rs in refs.items():
                it = _item(r, rs)
                if r == "P2":
                    it["abstraction"] = " "     # EMPTY -> per-item fail
                items_out.append(it)
            rows.append((item_id, json.dumps({"items": items_out}), None))
        return rows

    parents = [_parent(f"P{i}") for i in range(4)]
    out = compile_parents_microbatched(transport, parents, BOUNDS, 6000)
    by = {cp.parent_id: cp for cp in out}
    assert by["P0"].status == by["P1"].status == by["P3"].status == "READY"
    assert by["P2"].status == "INVALID"
    assert by["P2"].error_class == "ENRICH_EMPTY"


def test_split_ladder_reaches_single_parent_path():
    calls = []

    def transport(items):
        calls.append(items[0][1][:30])          # system prompt head
        _id, system, user, _mt = items[0]
        if "SEVERAL INDEPENDENT" in system and user.count("ITEM ") > 1:
            return [(items[0][0], "garbage envelope", None)]
        return _ok_transport(items) if "SEVERAL" in system else [
            (items[0][0], json.dumps(_item("X", [0, 1])), None)]

    parents = [_parent(f"P{i}") for i in range(4)]
    out = compile_parents_microbatched(transport, parents, BOUNDS, 6000)
    # 4 -> 2/2 (garbage) -> singles via the SINGLE-parent compiler
    assert all(cp.status == "READY" for cp in out)
    assert len(calls) >= 6                      # 1 + 2 + 4 ladder calls


def test_ceiling_checked_per_parent_not_per_batch():
    huge = ParentInput("P_big", [("c", 0, "word " * 40_000)])
    ok = _parent("P_ok")
    out = compile_parents_microbatched(_ok_transport, [huge, ok],
                                       BOUNDS, 6000)
    by = {cp.parent_id: cp for cp in out}
    assert by["P_big"].error_class == "ENRICH_INPUT_OVER_CEILING"
    assert by["P_ok"].status == "READY"


def test_on_compiled_fires_per_batch_before_return():
    landed = []

    def transport(items):
        return _ok_transport(items)

    parents = [_parent(f"P{i}") for i in range(10)]   # 2 batches of 8+2
    compile_parents_microbatched(
        transport, parents, BOUNDS, 6000,
        on_compiled=lambda cp: landed.append(cp.parent_id))
    assert sorted(landed) == sorted(p.parent_id for p in parents)


def test_on_compiled_survives_callback_errors():
    def transport(items):
        return _ok_transport(items)

    def boom(cp):
        raise RuntimeError("persist store down")

    parents = [_parent(f"P{i}") for i in range(3)]
    out = compile_parents_microbatched(transport, parents, BOUNDS, 6000,
                                       on_compiled=boom)
    assert all(cp.status == "READY" for cp in out)   # compile unharmed


def test_hard_case_integration_routes_item_failures():
    def bad_batch(items):                       # every item comes back empty
        rows = []
        for item_id, _s, user, _mt in items:
            refs = [b.split("\n", 1)[0].strip()
                    for b in user.split("ITEM ")[1:]]
            if refs:                             # microbatch call
                rows.append((item_id, json.dumps({"items": [
                    {**_item(r, [0, 1]), "abstraction": " "}
                    for r in refs]}), None))
            else:                                # single-parent call
                rows.append((item_id, "junk", None))
        return rows

    def escape(items):
        return [(i, json.dumps({
            "abstraction": "Everything decays toward the cheapest tier "
                           "that still meets its access needs.",
            "transfer": "Applies to storage, staffing and inventory."}),
                 None) for i, *_ in items]

    parents = [_parent(f"P{i}") for i in range(2)]
    out, _fo, recovered, term = compile_microbatched_with_hard_case(
        bad_batch, bad_batch, escape, parents, BOUNDS, 6000)
    assert recovered == 2 and term == 0
    assert all(cp.status == "READY" for cp in out)
    assert all(cp.contract == "parent-enrichment-minimal-v1"
               for cp in out)
