"""Owner directive 2026-08-30: the GLiNER and spaCy sidecars must never
boot again — their GPU residency cost the batched 4B ~3x decode throughput
and both are retired dependencies in llm_live."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_gliner_and_spacy_absent_from_fleet_and_profiles():
    supervisor = (ROOT / "control" / "control" / "process_supervisor.py").read_text()
    budget = (ROOT / "config" / "runtime_budget.yaml").read_text()
    # FLEET universe must not contain the slots
    for name in ("sidecar_gliner", "sidecar_spacy"):
        assert f'"{name}"' not in supervisor, f"{name} reappeared in FLEET"
    # no profile may list them
    for line in budget.splitlines():
        if line.strip().startswith("slots:"):
            assert "sidecar_gliner" not in line and "sidecar_spacy" not in line, \
                f"legacy sidecar in profile: {line.strip()}"
