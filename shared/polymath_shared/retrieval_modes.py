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

from polymath_shared.pass1 import PASS1_DEFAULT_PLAN, Pass1RetrievalPlan

RETRIEVAL_MODE_CONTRACT = "retrieval-mode-v1"

MODE_FAST = "FAST"
MODE_LEGACY = "LEGACY"

EXPOSED_MODES = (MODE_FAST, MODE_LEGACY)

DEFAULT_MODE = MODE_LEGACY  # frozen regression default; FAST is explicit


def mode_plan(mode: str) -> Pass1RetrievalPlan:
    """Deterministic mapping from a production mode to a retrieval plan."""
    if mode == MODE_FAST:
        return PASS1_DEFAULT_PLAN
    raise ValueError(f"mode {mode!r} has no pass-1 plan")


def validate_mode(mode: str | None) -> str:
    if mode is None or mode == "":
        return DEFAULT_MODE
    if mode not in EXPOSED_MODES:
        raise ValueError(
            f"unknown retrieval mode {mode!r}; exposed modes: {list(EXPOSED_MODES)}"
        )
    return mode
