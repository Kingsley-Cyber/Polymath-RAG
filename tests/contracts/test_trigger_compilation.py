"""A trigger must be manually licensed. VerbNet may only suggest.

Gate 5 of the predicate compiler used to do `verbs.update(members)`:
every member of every cited VerbNet class entered the production trigger
set. 112 authored verbs became 337 compiled triggers -- x3.0 across 8 of
28 predicates:

    founded     7 ->  65   inheriting bake, bead, blow, author
    created     6 ->  63   inheriting bake, bead, blow
    acquired    4 ->  28   inheriting accept, borrow, grab
    similar_to  3 ->  20   inheriting banter, bargain, collaborate

"She baked a cake" could license founded(she, cake). "The teams
collaborate" produced skill--similar_to-->users.

These were never extraction failures and Fact Admission was never the
right place to fix them. The court should not have to acquit an
accusation the compiler should not have made. So these tests assert on
the COMPILED ARTIFACT: the vocabulary that actually reaches production.
"""

from __future__ import annotations

import json
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK = ROOT / "shared" / "polymath_shared" / "rulepack" / "core-predicates-v1.3.0.yaml"
ALLOWLIST = ROOT / "resources" / "predicates" / "trigger_allowlist.yaml"


def _compiled() -> dict:
    hits = sorted((ROOT / "resources" / "compiled").rglob("compiled_lexical-v1.3.0.json"))
    if not hits:
        pytest.skip("no compiled v1.3.0 artifact")
    return json.loads(hits[-1].read_text())["predicates"]


def _authored() -> dict[str, set[str]]:
    src = yaml.safe_load(PACK.read_text())
    return {p["id"]: set((p.get("evidence") or {}).get("verbs") or [])
            for p in src["predicates"]}


def _allowlist() -> dict:
    return yaml.safe_load(ALLOWLIST.read_text())


# ---------------------------------------------------------------------------
# the invariant
# ---------------------------------------------------------------------------

def test_every_compiled_trigger_is_authored_or_explicitly_allowed():
    """No trigger reaches production without a human licensing it."""
    compiled, authored, allow = _compiled(), _authored(), _allowlist()
    unlicensed: dict[str, list[str]] = {}
    for pid, spec in compiled.items():
        entry = (allow.get("predicates") or {}).get(pid) or {}
        licensed = authored.get(pid, set()) | set(entry.get("allow") or [])
        extra = sorted(set(spec.get("verbs") or []) - licensed)
        if extra:
            unlicensed[pid] = extra
    assert not unlicensed, (
        f"compiled triggers with no licence: {unlicensed}. VerbNet class "
        f"expansion has returned; a trigger must be authored or explicitly "
        f"promoted in trigger_allowlist.yaml.")


def test_denied_triggers_never_compile():
    """A verb recorded as producing false facts must stay out, forever."""
    compiled, allow = _compiled(), _allowlist()
    leaked: dict[str, list[str]] = {}
    for pid, entry in (allow.get("predicates") or {}).items():
        denied = set(entry.get("deny") or [])
        if not denied:
            continue
        got = sorted(denied & set((compiled.get(pid) or {}).get("verbs") or []))
        if got:
            leaked[pid] = got
    assert not leaked, (
        f"denied triggers present in the compiled artifact: {leaked}. These "
        f"were recorded because they produced false facts.")


def test_suggestions_are_retained_but_not_compiled():
    """Nothing is lost. The review queue survives; it just never ships."""
    compiled = _compiled()
    total_suggested = 0
    for pid, spec in compiled.items():
        sug = set(spec.get("suggested_unlicensed") or [])
        total_suggested += len(sug)
        overlap = sug & set(spec.get("verbs") or [])
        assert not overlap, (
            f"{pid}: {sorted(overlap)} is both a compiled trigger and an "
            f"unlicensed suggestion; the two sets must be disjoint")
    assert total_suggested > 0, (
        "no suggestions recorded at all — the compiler is discarding what "
        "VerbNet offered instead of queueing it for review")


def test_allowlist_policy_is_authored_only():
    assert _allowlist().get("policy") == "authored_only", (
        "trigger allowlist policy changed; only 'authored_only' prevents "
        "VerbNet from expanding production vocabulary")


def test_no_trigger_is_both_allowed_and_denied():
    for pid, entry in (_allowlist().get("predicates") or {}).items():
        overlap = set(entry.get("allow") or []) & set(entry.get("deny") or [])
        assert not overlap, f"{pid}: {sorted(overlap)} both allowed and denied"


# ---------------------------------------------------------------------------
# the named contaminations, asserted individually so a regression names itself
# ---------------------------------------------------------------------------

CONTAMINATIONS = [
    # (predicate, verb, the sentence it would have mis-licensed)
    ("founded", "bake", "She baked a cake -> founded(she, cake)"),
    ("founded", "blow", "He blew a bubble -> founded(he, bubble)"),
    ("founded", "bead", "beading -> founded"),
    ("created", "bake", "She baked a cake -> created(she, cake)"),
    ("acquired", "grab", "He grabbed a coffee -> acquired(he, coffee)"),
    ("acquired", "borrow", "She borrowed a pen -> acquired(she, pen)"),
    ("acquired", "accept", "They accepted the terms -> acquired(they, terms)"),
    ("similar_to", "collaborate", "Teams collaborate -> similar_to(a, b)"),
    ("similar_to", "communicate", "They communicated -> similar_to(a, b)"),
    ("similar_to", "disagree", "They disagreed -> similar_to(a, b)"),
    ("similar_to", "compete", "They compete -> similar_to(a, b)"),
    ("uses", "work", "She worked with users -> uses(she, users)"),
]


@pytest.mark.parametrize("predicate,verb,scenario", CONTAMINATIONS,
                         ids=[f"{p}!={v}" for p, v, _ in CONTAMINATIONS])
def test_named_contamination_cannot_return(predicate, verb, scenario):
    """Each of these was observed or is a direct consequence of the class."""
    compiled = _compiled()
    spec = compiled.get(predicate)
    if spec is None:
        pytest.skip(f"{predicate} not in pack")
    assert verb not in set(spec.get("verbs") or []), (
        f"'{verb}' is a compiled trigger for '{predicate}' again. {scenario}")


def test_compiled_vocabulary_has_not_inflated():
    """The headline number, asserted so drift is visible in one line."""
    compiled, authored = _compiled(), _authored()
    total = sum(len(s.get("verbs") or []) for s in compiled.values())
    licensed = sum(len(v) for v in authored.values())
    allow = _allowlist()
    promoted = sum(len((e.get("allow") or []))
                   for e in (allow.get("predicates") or {}).values())
    assert total <= licensed + promoted, (
        f"compiled vocabulary is {total} triggers against {licensed} "
        f"authored + {promoted} promoted. It was 337 against 112 before "
        f"VerbNet expansion was removed.")


# ---------------------------------------------------------------------------
# provenance: a fact must be auditable back to the trigger that licensed it
# ---------------------------------------------------------------------------

def test_relation_candidate_records_the_trigger_that_licensed_it():
    """`trigger_surface` was read off a field EvidenceSpan never defines.

    getattr(..., "trigger_surface", None) returned None for all 34,655
    candidates ever recorded, across every corpus, including all 8,834
    ACCEPT/QUALIFY rows. Licensing was working -- `_trigger_matches`
    tests `trigger_lemma` against the licensed arms -- but the ledger
    could not say which trigger produced any given fact. A silent
    getattr default turned a contract field into a permanent NULL, and
    an unauditable fact is not evidence-first.
    """
    src = (ROOT / "shared" / "polymath_shared" / "raw_evidence.py").read_text()
    fn = src[src.index("def relation_candidate_row"):]
    fn = fn[:fn.index("\n\n\n")] if "\n\n\n" in fn else fn
    assert "trigger_lemma" in fn, (
        "relation_candidate_row does not record trigger_lemma; the field "
        "EvidenceSpan actually defines")
    assert '"trigger_surface", None' not in fn, (
        "still reading a non-existent `trigger_surface` attribute, which "
        "silently records NULL for every candidate")


def test_evidence_span_defines_the_field_the_ledger_reads():
    """Guard the mismatch itself, not just today's symptom."""
    from polymath_shared.contracts import EvidenceSpan

    fields = set(EvidenceSpan.model_fields)
    assert "trigger_lemma" in fields, (
        f"EvidenceSpan no longer defines trigger_lemma; the ledger reads "
        f"it. Available: {sorted(fields)}")
