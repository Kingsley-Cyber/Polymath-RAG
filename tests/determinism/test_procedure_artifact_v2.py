"""PROCEDURE-ARTIFACT-V2 (P3).

V1 emitted at most ONE artifact per document. On sentinel_procedures.md
— three plainly separate tasks — it produced a single artifact holding
5 of the 20 real steps, with the goal "Select the key".

MEASURED: two defects, neither of them granularity.

  1. SENTENCE SHREDDING — split_step_sentences splits on every newline,
     so a hard-wrapped line became two "sentences" ("Select the key" /
     "you intend to replace."). Wrapping is presentation, not structure.

  2. WHITELIST RECALL — a step was recognised only if its verb was in a
     hand-written list, so generate/revoke/detach/attach/boot/capture/
     collect/record/notify/hand/confirm/close were invisible. An
     open-class verb list can never be completed.

V2 fixes both and the granularity falls out: the goal sentences that
mark each task ("To rotate an API credential, …") are exactly the ones
the step detector declines to call steps.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.knowledge_objects.procedure import (  # noqa: E402
    MIN_STEPS,
    NON_VERB_OPENERS,
    PROCEDURE_CONTRACT_V2,
    compile_procedure,
    compile_procedures,
    is_imperative_v2,
    segment_tasks,
    split_step_sentences_v2,
)

SENTINEL = ROOT / "eval" / "v5" / "killchain" / "sentinel"
PROCEDURES = (SENTINEL / "sentinel_procedures.md").read_text()

#: The three tasks a human reads in sentinel_procedures.md, and a
#: distinctive marker from each.
TASKS = {
    "rotate": ["credential console", "Generate a replacement key",
               "Revoke the previous key"],
    "restore": ["known good snapshot", "Detach the compromised volume",
                "Boot the host in isolation"],
    "containment": ["isolating the affected host", "Capture a memory image",
                    "Close the containment phase"],
}


def artifacts():
    return compile_procedures(document_id="doc_p3", corpus_id="c",
                              text=PROCEDURES)


# ==================================================== THE ACCEPTANCE
def test_three_coherent_artifacts():
    arts = artifacts()
    assert len(arts) == 3, (
        f"expected one artifact per task, got {len(arts)}: "
        f"{[a['goal'] for a in arts]}")


def test_step_sets_are_disjoint():
    arts = artifacts()
    seen: set[str] = set()
    for a in arts:
        steps = set(a["steps"])
        assert not (steps & seen), f"step shared between tasks: {steps & seen}"
        seen |= steps
    assert len(seen) == 20, f"expected all 20 source steps, got {len(seen)}"


def test_no_unrelated_task_contamination():
    """Each artifact must match exactly ONE ground-truth task."""
    for a in artifacts():
        hit = {name for name, markers in TASKS.items()
               if any(any(m in s for s in a["steps"]) for m in markers)}
        assert len(hit) == 1, (
            f"artifact goal={a['goal']!r} mixes tasks {sorted(hit)}")


def test_every_task_is_recovered():
    found = set()
    for a in artifacts():
        for name, markers in TASKS.items():
            if any(any(m in s for s in a["steps"]) for m in markers):
                found.add(name)
    assert found == set(TASKS), f"tasks missing: {set(TASKS) - found}"


def test_no_invented_steps():
    """The compiler SELECTS; it never rewrites. Every step must appear
    verbatim in the source once soft wraps are repaired."""
    flat = re.sub(r"\s+", " ", PROCEDURES)
    for a in artifacts():
        for step in a["steps"]:
            assert re.sub(r"\s+", " ", step) in flat, f"invented step: {step!r}"


def test_steps_keep_source_order():
    flat = re.sub(r"\s+", " ", PROCEDURES)
    for a in artifacts():
        positions = [flat.index(re.sub(r"\s+", " ", s)) for s in a["steps"]]
        assert positions == sorted(positions), (
            f"steps reordered in {a['goal']!r}")


def test_goals_come_from_goal_markers_not_the_first_step():
    goals = {a["goal"] for a in artifacts()}
    assert "rotate an API credential" in goals
    assert "restore a host from backup" in goals
    assert "Select the key" not in goals, (
        "the v1 goal defect is back: goal is a mid-task step")


def test_ids_are_deterministic_and_distinct():
    a, b = artifacts(), artifacts()
    assert [x["artifact_id"] for x in a] == [x["artifact_id"] for x in b], (
        "artifact ids are not deterministic — replay would duplicate")
    assert len({x["artifact_id"] for x in a}) == 3, "two tasks share an id"


def test_artifacts_declare_their_contract():
    for a in artifacts():
        assert a["provenance"]["contract"] == PROCEDURE_CONTRACT_V2


# ================================================ SEGMENTATION CHOICE
def test_local_task_beats_document_and_section_segmentation():
    """The promotion evidence. DOCUMENT and PARENT_NEIGHBOURHOOD collapse
    all three tasks into one; SECTION splits on headings and so merges
    the two tasks that share a section. Only local task segmentation
    separates them — with the SAME step detector, so the difference is
    the unit and nothing else."""
    def steps_in(seg):
        return [s for s in split_step_sentences_v2(seg) if is_imperative_v2(s)]

    whole = [steps_in(PROCEDURES)]
    sections, cur = [], []
    for line in PROCEDURES.split("\n"):
        if line.startswith("#"):
            sections.append("\n".join(cur)); cur = []
        else:
            cur.append(line)
    sections.append("\n".join(cur))
    section_groups = [steps_in(s) for s in sections if s.strip()]

    def coherent(groups):
        groups = [g for g in groups if len(g) >= MIN_STEPS]
        mixed = sum(1 for g in groups
                    if len({n for n, ms in TASKS.items()
                            if any(any(m in s for s in g) for m in ms)}) > 1)
        return len(groups), mixed

    assert coherent(whole) == (1, 1), "DOCUMENT segmentation stopped merging"
    assert coherent(section_groups)[1] >= 1, (
        "SECTION segmentation stopped merging the shared-section tasks")
    assert coherent([t["steps"] for t in segment_tasks(PROCEDURES)]) == (3, 0)


# ======================================================== PRECISION
@pytest.mark.parametrize("name", ["sentinel_facts.md",
                                  "sentinel_boilerplate.md",
                                  "sentinel_transcript.md"])
def test_non_procedural_documents_yield_no_artifact(name):
    """Recall must not have been bought with precision. None of these
    are runbooks; none may compile into a procedure."""
    text = (SENTINEL / name).read_text()
    assert compile_procedures(document_id="d", corpus_id="c",
                              text=text) == []


def test_declaratives_are_never_steps():
    """The subject-detection rules, stated as behaviour."""
    for s in ("Nessus scans network hosts for known vulnerabilities.",
              "Nmap discovers open ports on a target host.",
              "Nessus was developed by Tenable.",
              "Dana Reyes, CISSP, MCSE, is a technical consultant.",
              "Port scanning is the technique of probing a host.",
              "The scanner produces a report for each host.",
              "A vulnerability scanner is a tool that inspects hosts."):
        assert not is_imperative_v2(s, frozenset({"nessus", "nmap"})), \
            f"declarative read as a step: {s!r}"


def test_imperatives_outside_the_old_whitelist_are_steps():
    """The recall the whitelist could not reach."""
    for s in ("Generate a replacement key.", "Revoke the previous key.",
              "Detach the compromised volume.", "Boot the host in isolation.",
              "Capture a memory image before powering down.",
              "Notify the incident commander.",
              "Close the containment phase."):
        assert is_imperative_v2(s), f"imperative missed: {s!r}"


def test_structural_lines_are_never_steps():
    """Table rows, headings and code survive in chunk text only because
    of CHUNK_CONTRACT_V2 — which is also what makes them excludable."""
    text = (SENTINEL / "sentinel_transcript.md").read_text()
    for s in split_step_sentences_v2(text):
        assert not s.lstrip().startswith("|"), f"table row as sentence: {s!r}"
        assert "firewall.block" not in s, f"code as sentence: {s!r}"


def test_soft_wrapped_steps_are_repaired():
    """The shredding defect: a hard-wrapped step must come back whole."""
    steps = [s for a in artifacts() for s in a["steps"]]
    assert "Select the key you intend to replace." in steps
    assert "Capture a memory image before powering down." in steps
    assert not any(s.strip() == "you intend to replace." for s in steps)


def test_opener_set_stays_a_closed_class():
    """If this needs a domain word to work, it has become a heuristic."""
    assert len(NON_VERB_OPENERS) <= 160
    assert all(w.isalpha() and w == w.lower() for w in NON_VERB_OPENERS)


# ================================================== V1 STAYS FROZEN
def test_v1_compiler_is_unchanged():
    """V1 remains reachable and behaves exactly as before: one artifact,
    the old low-recall step set, the old wrong goal."""
    v1 = compile_procedure(document_id="doc_p3", corpus_id="c",
                           text=PROCEDURES)
    assert v1 is not None
    assert v1["goal"] == "Select the key"
    assert len(v1["steps"]) == 5


# ==================================================== CALLSITE PIN
def test_callsite_pin_worker_persists_every_task():
    """PIN. A compiler that can emit three artifacts is worthless if the
    worker still writes one. The v1 call site assigned
    `counts["procedures"] = 1` — a literal that cannot count."""
    src = (ROOT / "workers" / "workers" / "extract_worker.py").read_text()
    start = src.index("def _persist_knowledge_artifacts")
    body = src[start:src.index("\ndef ", start + 1)]
    assert "for proc in compile_procedures(" in body, (
        "the worker no longer iterates tasks — only one procedure "
        "artifact per document can reach the ledger")
    assert 'counts["procedures"] += 1' in body, (
        "procedure count is not accumulated per artifact")
    assert 'counts["procedures"] = 1' not in body, (
        "the v1 constant count is back")
    assert "_procedure_mod.count_opportunities_v2(" in body, (
        "opportunity counting drifted from the v2 compiler; accepted "
        "could exceed opportunities")
