"""R1C retrieval-mode contract: versioned production modes.

FAST is the promoted Pass-1 semantic route and maps deterministically
to the qualified pass1-retrieval-v1 plan (R1B). LEGACY is the frozen
pre-R1A lane-based route, retained explicitly for regression/rollback
(G1/G2 golden contracts). HYBRID/GRAPH are NOT exposed yet.

One engine rule: production FAST and qualification both call
polymath_shared.pass1.pass1_retrieve with the SAME versioned plan —
no duplicate retrieval implementation exists.
"""
from __future__ import annotations

from polymath_shared.hybrid import HYBRID_DEFAULT_PLAN, HybridRetrievalPlan
from polymath_shared.pass1 import PASS1_DEFAULT_PLAN, Pass1RetrievalPlan

RETRIEVAL_MODE_CONTRACT = "retrieval-mode-v1"

MODE_FAST = "FAST"
MODE_HYBRID = "HYBRID"
MODE_GRAPH = "GRAPH"
MODE_LEGACY = "LEGACY"

EXPOSED_MODES = (MODE_FAST, MODE_HYBRID, MODE_GRAPH, MODE_LEGACY)

DEFAULT_MODE = MODE_LEGACY  # frozen regression default; FAST/HYBRID are explicit

# R1D qualification verdict: lexical PROMOTED (material doc/recall gains);
# MMR REJECTED (damages supporting-child recall at every lambda < 1.0 on
# the frozen grid). Production HYBRID therefore = FAST + lexical,
# lambda 1.0 (relevance-only), documented as the promoted operating point.
HYBRID_PROMOTED_PLAN = HybridRetrievalPlan(mmr_enabled=False, mmr_lambda=1.0)


def mode_plan(mode: str) -> Pass1RetrievalPlan:
    """Deterministic mapping from a production mode to a retrieval plan."""
    if mode == MODE_FAST:
        return PASS1_DEFAULT_PLAN
    raise ValueError(f"mode {mode!r} has no pass-1 plan")


def hybrid_mode_plan(mode: str) -> HybridRetrievalPlan:
    if mode in (MODE_HYBRID, MODE_GRAPH):
        return HYBRID_PROMOTED_PLAN
    raise ValueError(f"mode {mode!r} has no hybrid plan")


# R1F: GRAPH = promoted HYBRID + the already-qualified evidence-authorized
# corpus-authorized canonical bidirectional hop1 graph expansion
# (D2 machinery: 8 seeds / 20 facts, HIGH_MEDIUM, SPO preserved).
GRAPH_PLAN_VERSION = "graph-retrieval-v1"
GRAPH_MAX_SEEDS = 8
GRAPH_MAX_FACTS = 20


def validate_mode(mode: str | None) -> str:
    if mode is None or mode == "":
        return DEFAULT_MODE
    if mode not in EXPOSED_MODES:
        raise ValueError(
            f"unknown retrieval mode {mode!r}; exposed modes: {list(EXPOSED_MODES)}"
        )
    return mode
