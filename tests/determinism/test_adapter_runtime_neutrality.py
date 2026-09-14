"""Plan §9 / final acceptance: the runtime contains NO adapter-name conditional path implementing Trail semantics.
Manifests carry the semantics; service/transitions/manifest/contracts/store/worker never branch on an adapter id."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import list_manifests  # noqa: E402

RUNTIME = [ROOT / "shared/polymath_shared/adapter" / f for f in ("service.py", "transitions.py", "manifest.py", "contracts.py", "store.py", "trail_client.py", "hypotheses.py")] + \
          [ROOT / "workers/workers/adapter_step_worker.py", ROOT / "orchestrator/orchestrator/api/adapter.py"]
ADAPTER_IDS = ("trail.product_discovery", "substack.article_development", "polymath.knowledge_brief")
# hypotheses are GENERIC engine state since ADR-0019 (HypothesisStateV1), not a domain word
DOMAIN_WORDS = ("product_territory", "workaround", "narrative_role", "counterargument", "thesis", "article")


def test_runtime_never_branches_on_an_adapter_id_or_domain_vocabulary():
    for path in RUNTIME:
        src = path.read_text()
        code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#") and '"""' not in l)
        for aid in ADAPTER_IDS:
            assert aid not in code, f"{path.name} mentions adapter id {aid!r}"
        for w in DOMAIN_WORDS:
            assert re.search(rf"\b{w}\b", code) is None, f"{path.name} hard-codes domain word {w!r}"


def test_both_workload_adapters_share_the_closed_vocabulary_and_differ_in_semantics():
    ms = {m.adapter_id: m for m in list_manifests()}
    trail, sub = ms["trail.product_discovery"], ms["substack.article_development"]
    assert {s["type"] for s in trail.steps.values()} >= {"EXTERNAL_OPERATION", "AGENT_REASON", "BRANCH", "COMPILE_RESULT"}
    assert {s["type"] for s in sub.steps.values()} >= {"POLYMATH_COMPILE_PLAN", "POLYMATH_RETRIEVE", "POLYMATH_GRAPH_EXPAND", "AGENT_REASON", "VALIDATE", "BRANCH", "COMPILE_RESULT"}
    assert not any(s["type"] == "EXTERNAL_OPERATION" for s in sub.steps.values())          # Trail-free
    trail_words = {"activity", "task", "context", "friction", "workaround", "product_territory", "candidate"}
    sub_text = str(sub.raw).lower()
    assert not any(w in sub_text for w in ("registry_record_id", "product_territory", "workaround")), "substack must not import Trail ontology"
    assert all(w in sub_text for w in ("claim", "mechanism", "tension", "counterargument", "analogy", "implication", "narrative_role", "article"))


# ─────────────────────────────────────────────────────────── ADR-0019 §6: source scalability is enforced in code
SOURCE_NAMES = ("reddit", "youtube", "tiktok", "facebook", "amazon", "walmart", "etsy", "ebay", "homedepot", "home_depot", "lowes",
                "alibaba", "cj_dropshipping", "cjdropshipping", "1688", "searxng", "google", "exa", "camofox", "playwright", "crawl4ai")
HARNESS_IDS = ("hermes", "claude-code", "claude_code", "codex", "opencode")


def test_runtime_and_manifests_never_name_a_source_or_a_harness():
    """Adding a website is registry data on the Trail side; the Polymath runtime, the worker and every manifest stay source- and
    harness-neutral. (The acceptance script and tests may name harness ids as data; the runtime may not.)"""
    files = RUNTIME + [ROOT / "orchestrator/orchestrator/api/adapter.py"] + sorted((ROOT / "config/adapters").glob("*.json"))
    for path in files:
        code = path.read_text().lower()
        for w in SOURCE_NAMES + HARNESS_IDS:
            assert re.search(rf"(?<![a-z0-9_]){re.escape(w)}(?![a-z0-9_])", code) is None, f"{path.name} names {w!r}"
