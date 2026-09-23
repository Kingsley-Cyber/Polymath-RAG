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


def test_local_4b_extractor_retired_and_its_memory_given_to_the_query_path():
    """Owner 2026-09-22 (FLEET-MEMORY-REBALANCE-V1): the local Qwen3.5-4B extraction sidecar is retired — under
    CLOUD-FIRST-V1 (floor 0 B) extraction never reaches it, yet it held 2.76 GB and 11.5 GB of the budget. The
    reranker (which OOM'd at ~33 pairs under 3.5 GB) gets 6.0 GB and the embedder 4.5 GB; the fleet still fits."""
    sys.path.insert(0, str(ROOT / "shared"))
    sys.path.insert(0, str(ROOT / "control"))
    from control.process_supervisor import FLEET
    from control.fleet_autopilot import LANES
    from polymath_shared import runtime_budget as rb

    names = {e["name"] if isinstance(e, dict) else (e[0] if isinstance(e, (tuple, list)) else e) for e in FLEET}
    assert "local_extractor" not in names, "the 4B extractor is back in FLEET"
    assert all("local_extractor" not in slots for _lane, _stages, slots in LANES), "the autopilot would wake the 4B"
    b = rb.budget()
    assert "local_extractor" not in (b.get("sidecars") or {})
    assert all("local_extractor" not in (p.get("slots") or []) for p in (b.get("profiles") or {}).values())
    assert float(b["sidecars"]["sidecar_reranker"]["mps_gb"]) == 6.0
    assert float(b["sidecars"]["sidecar_embedder"]["mps_gb"]) == 4.5
    assert int(b["sidecars"]["sidecar_embedder"]["max_batch_texts"]) == 8
    assert int(b["sidecars"]["sidecar_embedder"]["max_batch_tokens"]) == 8192     # the token bound (memory) is unchanged
    assert rb.plan()["fits"] and all(rb.plan(",".join(rb.profile_slots(p)))["fits"] for p in b["profiles"])
