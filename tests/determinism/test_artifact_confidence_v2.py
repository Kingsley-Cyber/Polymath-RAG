"""P7 ARTIFACT-CONFIDENCE-V2 — confidence is a declared non-signal.

THE PHASE ASKED: derive a defensible deterministic signal, or remove
confidence from semantic use. Length must not imply reliability.

WHAT WAS THERE, measured:

    procedure   min(1.0, 0.6 + 0.05 * len(steps))   live: 12 at 1.00, 1 at 0.85
    concept     0.9, hardcoded                      live: 121 at 0.90

The procedure value is worse than a constant — it is a LENGTH function
that saturates at 1.0 for any procedure with 8 or more steps, which
under the v1 one-artifact-per-document contract was nearly all of them.
And `ask.py` RANKED on it (`match + 0.25 * conf`), so a longer procedure
beat a shorter one for being longer. Under PROCEDURE_ARTIFACT_V2 that
becomes actively wrong: the 10-step containment task would outrank the
5-step credential rotation on length alone.

The concept value is a true constant, so it adds the same amount to
every candidate and cannot discriminate. It only looked like a signal.

THE DECISION: removed from semantic use. There is no defensible
deterministic reliability signal available here — these compilers SELECT
verbatim source sentences, so every step is exactly as reliable as the
document it came from. Confidence is now a declared non-signal: a fixed
value retained for provenance compatibility that nothing ranks or admits
on. It is not part of the artifact body hash, so identity is unchanged.

V1 stays frozen, length derivation and all.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.knowledge_objects.procedure import (  # noqa: E402
    CONFIDENCE_CONTRACT,
    DECLARED_NON_SIGNAL_CONFIDENCE,
    compile_procedure,
    compile_procedures,
)

ASK = ROOT / "orchestrator" / "orchestrator" / "api" / "ask.py"
PROC = ROOT / "shared" / "polymath_shared" / "knowledge_objects" / "procedure.py"

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

SHORT = """To rotate a key, open the console.
Select the key.
Revoke the old key.
"""

LONG = """To contain an incident, isolate the host.
Capture a memory image.
Collect the log bundles.
Record the responder actions.
Notify the incident commander.
Preserve the disk image.
Document the decision.
Hand off the case.
Confirm the handoff.
Close the phase.
"""


# ============================ NO RANKING ADVANTAGE FROM CONFIDENCE
@pytest.mark.parametrize("marker", [
    "0.25 * float(conf",
    "0.2 * float(conf",
])
def test_confidence_no_longer_contributes_to_score(marker):
    """THE ACCEPTANCE: no candidate gains ranking advantage from a
    constant — or, worse, from its own length."""
    assert marker not in ASK.read_text(), (
        f"ask.py still adds {marker} to the score; confidence is ranking "
        "again")


def test_scoring_is_term_match_only():
    src = ASK.read_text()
    assert src.count("score = round(match, 4)") >= 2, (
        "procedure and concept scoring should each be term-match only")


# ================================ LENGTH MUST NOT IMPLY RELIABILITY
def test_a_longer_procedure_gets_no_confidence_advantage():
    """The concrete regression: a 10-step task must not outscore a
    3-step task on confidence."""
    short = compile_procedures(document_id="d1", corpus_id="c", text=SHORT)
    long_ = compile_procedures(document_id="d2", corpus_id="c", text=LONG)
    assert short and long_, "fixtures did not compile"
    assert len(long_[0]["steps"]) > len(short[0]["steps"]), "fixture invalid"
    assert short[0]["confidence"] == long_[0]["confidence"], (
        f"length still moves confidence: {short[0]['confidence']} vs "
        f"{long_[0]['confidence']}")


def test_v2_confidence_is_the_declared_non_signal():
    for art in compile_procedures(document_id="d", corpus_id="c", text=LONG):
        assert art["confidence"] == DECLARED_NON_SIGNAL_CONFIDENCE


def test_v2_derivation_is_not_a_length_function():
    """Pin the mechanism, not just the value."""
    src = PROC.read_text()
    v2 = src[src.index("def compile_procedures"):]
    assert "0.05 * len(steps)" not in v2, (
        "the V2 compiler derives confidence from step count again")
    assert "DECLARED_NON_SIGNAL_CONFIDENCE" in v2


def test_contract_is_named():
    assert CONFIDENCE_CONTRACT == "artifact-confidence-v2"


# ======================================================= V1 IS FROZEN
def test_v1_keeps_its_length_derivation():
    """V1 is frozen. Its confidence stays length-derived so historical
    artifacts remain explainable."""
    src = PROC.read_text()
    v1 = src[src.index("def compile_procedure("):src.index("# " + "=" * 60)]
    assert "0.05 * len(steps)" in v1, (
        "the frozen v1 compiler changed; historical confidence values "
        "would no longer be reproducible")
    art = compile_procedure(document_id="d", corpus_id="c", text=LONG)
    assert art is not None
    # v1's confidence tracks ITS OWN step count. (It finds only 2 steps
    # on this fixture — that is the P3 whitelist-recall defect, frozen
    # along with the rest of v1.)
    assert art["confidence"] == min(1.0, 0.6 + 0.05 * len(art["steps"])), (
        "v1 confidence is no longer its length function")


def test_confidence_is_not_part_of_artifact_identity():
    """Declaring it a non-signal must not have re-identified anything."""
    a = compile_procedures(document_id="d", corpus_id="c", text=LONG)[0]
    b = compile_procedures(document_id="d", corpus_id="c", text=LONG)[0]
    assert a["artifact_id"] == b["artifact_id"]
    body_fields = {"title", "goal", "tools", "steps"}
    assert "confidence" not in body_fields


# ============================================================ LIVE
def test_stored_confidence_cannot_discriminate():
    """Whatever is stored, it must not be usable as a ranking signal —
    either it is constant, or nothing reads it."""
    try:
        import psycopg
        conn = psycopg.connect(DSN, connect_timeout=3)
    except Exception:
        pytest.skip("postgres unavailable")
    with conn:
        vals = {r[0] for r in conn.execute(
            "SELECT DISTINCT confidence FROM concept_artifacts").fetchall()}
    assert len(vals) <= 1 or "0.2 * float(conf" not in ASK.read_text(), (
        "concept confidence varies AND is used for ranking")
