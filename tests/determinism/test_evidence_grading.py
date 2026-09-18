"""CONSTRAINT-AWARE-RETRIEVAL-V1 (CA4) — evidence support-role grading + the epistemic gate.

grade_evidence: DIRECT (required-need + relevant + satisfies HARD source), PARTIAL (need + relevant
but not the named source), RELATED (bridge-only or not relevant); multi-signal, deterministic.
The epistemic verdict drives render_answer's answerability gate — an answer needs >=1 DIRECT/PARTIAL
chunk, else it states the gap (fixes the unsupported-hallucination case) — while a bundle WITHOUT the
epistemic key is byte-identical. Pure shared/ — executed path is this worktree.
"""
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.query_constraints import (  # noqa: E402
    Constraint, EVIDENCE_ROLES, grade_evidence)


def _plan(origins=(("q0", "USER"), ("p0", "PROFILE")), constraints=()):
    return SimpleNamespace(queries=[SimpleNamespace(id=i, origin=o) for i, o in origins],
                           explicit_constraints=list(constraints))


def _c(cid, doc, rr, qids):
    return {"chunk_id": cid, "doc_id": doc, "rerank_score": rr, "query_ids": qids}


# --- unconstrained: DIRECT = user-need + relevant; RELATED = bridge-only or not relevant ---------
def test_direct_when_user_need_and_relevant():
    ev = [_c("c1", "docA", 5.0, ["q0"]), _c("c2", "docB", -1.0, ["q0"]), _c("c3", "docC", 3.0, ["p0"])]
    roles, ep = grade_evidence(ev, _plan())
    assert roles == {"c1": "DIRECT", "c2": "RELATED", "c3": "RELATED"}   # c2 not relevant; c3 profile-only
    assert ep["directly_established"] is True and ep["establishes_need"] is True
    assert (ep["n_direct"], ep["n_related"]) == (1, 2)


def test_profile_only_chunk_is_related_even_if_relevant():
    roles, _ = grade_evidence([_c("c1", "docA", 9.0, ["p0"])], _plan())
    assert roles["c1"] == "RELATED"


# --- HARD constraint: source=DIRECT, relevant-non-source=PARTIAL --------------------------------
def test_hard_source_direct_nonsource_partial():
    cons = [Constraint(kind="SOURCE", value="Murch", strength="HARD", resolved_targets=["murch"])]
    ev = [_c("c1", "murch", 5.0, ["q0"]),      # the named source, relevant, user need -> DIRECT
          _c("c2", "rabiger", 7.0, ["q0"]),    # relevant to the need but NOT the source -> PARTIAL
          _c("c3", "edhooks", -2.0, ["q0"])]   # not relevant -> RELATED
    roles, ep = grade_evidence(ev, _plan(constraints=cons))
    assert roles == {"c1": "DIRECT", "c2": "PARTIAL", "c3": "RELATED"}
    assert ep["directly_established"] is True and ep["n_partial"] == 1


def test_soft_constraint_does_not_gate_direct():
    # a SOFT constraint must not turn a relevant non-source chunk into PARTIAL — only HARD does
    cons = [Constraint(kind="SOURCE", value="Murch", strength="SOFT", resolved_targets=["murch"])]
    roles, _ = grade_evidence([_c("c1", "rabiger", 5.0, ["q0"])], _plan(constraints=cons))
    assert roles["c1"] == "DIRECT"


# --- the hallucination case: only adjacent RELATED material -> establishes_need False ------------
def test_out_of_domain_all_related_does_not_establish():
    ev = [_c("c1", "docA", -5.0, ["q0"]), _c("c2", "docB", -8.0, ["q0", "p0"]), _c("c3", "docC", -3.0, ["p0"])]
    roles, ep = grade_evidence(ev, _plan())
    assert set(roles.values()) == {"RELATED"}
    assert ep["directly_established"] is False and ep["establishes_need"] is False


def test_partial_still_establishes_need():
    cons = [Constraint(kind="SOURCE", value="Murch", strength="HARD", resolved_targets=["murch"])]
    # no source chunk retrieved, but a relevant non-source (PARTIAL) exists -> need IS established
    roles, ep = grade_evidence([_c("c1", "rabiger", 5.0, ["q0"])], _plan(constraints=cons))
    assert roles["c1"] == "PARTIAL"
    assert ep["directly_established"] is False and ep["establishes_need"] is True


def test_no_plan_queries_treats_as_user_need():
    roles, _ = grade_evidence([_c("c1", "docA", 5.0, [])], _plan(origins=()))
    assert roles["c1"] == "DIRECT"


def test_roles_vocabulary():
    cons = [Constraint(kind="SOURCE", value="X", strength="HARD", resolved_targets=["x"])]
    roles, _ = grade_evidence([_c("c1", "x", 5.0, ["q0"]), _c("c2", "y", 5.0, ["q0"]), _c("c3", "z", 5.0, ["p0"])],
                              _plan(constraints=cons))
    assert set(roles.values()) <= set(EVIDENCE_ROLES)


# --- the render_answer epistemic gate (reusing the synthesis test fixture) -----------------------
def test_epistemic_gate_blocks_when_need_not_established():
    import test_answer_synthesis as tas
    from polymath_shared.answer_synthesis import grounded_answer
    QUERY = tas.QUERY
    base = tas._bundle()
    assert grounded_answer(base, QUERY)["meta"]["abstained"] is False       # normally supported
    blocked = tas._bundle(); blocked["epistemic"] = {"establishes_need": False, "directly_established": False}
    assert grounded_answer(blocked, QUERY)["meta"]["abstained"] is True     # gate -> states the gap
    ok = tas._bundle(); ok["epistemic"] = {"establishes_need": True, "directly_established": True}
    assert grounded_answer(ok, QUERY)["meta"]["abstained"] is False         # DIRECT/PARTIAL present -> unchanged
