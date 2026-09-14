"""HARNESS-RESEARCH-MIGRATION-V1 R4 — dead-code guard (plan §9 test J, §12): the retired Trail-owned live-web acquisition path
of the product-discovery adapter cannot come back into the active runtime, manifests, contracts or tests. History (work-logs,
register, CONTINUITY, the E0 matrix, the plan) keeps the names; nothing executable does."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RETIRED = ("_exec_discover", "_exec_acquire_extract", "_hypothesis_queries", "_leads_from_prior", "discovery_request", "crawl_request",
           "batch_request", "extraction_request", "page_request", "page_all", "outputs_of", "D_discover", "E_acquire", "F_normalize",
           "G_gates", "H_gap_loop", "I_score", "J_interpret", "trail_record_ids", "TRAIL_NO_LEADS", "TRAIL_DISCOVERY_", "TRAIL_ACQUISITION_",
           "commerce.research", "scrape.submit+extract.submit")
SCAN = [ROOT / "shared/polymath_shared/adapter", ROOT / "workers/workers/adapter_step_worker.py", ROOT / "orchestrator/orchestrator/api/adapter.py",
        ROOT / "orchestrator/orchestrator/mcp_server.py", ROOT / "config/adapters", ROOT / "contracts/adapter/v1", ROOT / "tests", ROOT / "scripts/adapter_mcp_acceptance.py"]


def _files():
    for base in SCAN:
        if base.is_file():
            yield base
        else:
            yield from (p for p in base.rglob("*") if p.suffix in (".py", ".json") and p.is_file())


def test_retired_acquisition_path_is_unreachable_from_the_active_runtime():
    offenders = []
    for path in _files():
        if path.name == "test_retired_paths.py":
            continue
        text = path.read_text(errors="ignore")
        for sym in RETIRED:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(sym)}(?![A-Za-z0-9_])", text):
                offenders.append(f"{path.relative_to(ROOT)}: {sym}")
    assert not offenders, "retired symbols are back: " + "; ".join(offenders[:20])


def test_active_manifest_needs_no_trail_acquisition_and_declares_the_three_stages():
    import json
    m = json.loads((ROOT / "config/adapters/trail.product_discovery.json").read_text())
    ops = {s["external"]["operation_kind"] for s in m["steps"] if s["type"] == "EXTERNAL_OPERATION"}
    assert ops.isdisjoint({"discover.submit", "crawl.submit", "scrape.submit", "extract.submit"})
    kinds = [s["harness"]["action_kind"] for s in m["steps"] if s["type"] == "HARNESS_ACTION"]
    assert kinds == ["AGENT_RESEARCH", "PRODUCT_REALITY_CHECK", "SUPPLIER_RESEARCH"]
    stages = [s["config"]["stage"] for s in m["steps"] if s["type"] == "EXTERNAL_OPERATION" and s["external"]["operation_kind"] == "evidence.admit"]
    assert stages == ["field_evidence", "product_reality", "supply"]         # plan §9 test H: distinct admission stages per typed step
