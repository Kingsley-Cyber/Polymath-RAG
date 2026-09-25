"""AUTORESEARCH-SOURCES-AND-HARNESS-V1, slice R6 — the deploy live check ($0: no model call, no run started).
Run from the main checkout after the merge + bounce, with the main .env loaded (POLYMATH_MCP_API_KEY):
  1. MCP Server A (loopback) publishes the operating guide: prompt `run_governed_research` + the four resources, byte-equal to
     `polymath_shared.adapter.harness_guide` and to the repository files; the source table carries the two comment rows;
  2. adapter_list: ecommerce.product_research 0.7.0 PREFERRED, trail.product_discovery 2.2.1 LEGACY; adapter_start's description
     says corpus_ids is required for a non-admin key;
  3. the pinned TrailSignal core (the same files the fleet imports) ADMITS a TikTok comment and an Instagram reel comment as field
     evidence, keeps a Creative Center link on the trend row, and refuses a short link in the field stage.
Writes live_check.json next to this file; exit 0 only when every check holds."""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "shared"))
import mcp_call  # noqa: E402
from polymath_shared.adapter import harness_guide as HG  # noqa: E402


async def _mcp() -> dict:
    c = await mcp_call._session()
    try:
        _, prompt = await c.rpc("prompts/get", {"name": HG.PROMPT_NAME, "arguments": {}})
        texts = {}
        for uri in HG.RESOURCE_URIS:
            _, body = await c.rpc("resources/read", {"uri": uri})
            texts[uri] = "".join(item.get("text", "") for item in (body.get("result") or {}).get("contents") or [])
        _, listed = await c.rpc("tools/call", {"name": "adapter_list", "arguments": {}})
        _, tools = await c.rpc("tools/list", {})
    finally:
        await c.close()
    msgs = ((prompt.get("result") or {}).get("messages") or [])
    prompt_text = " ".join(str((m.get("content") or {}).get("text") or "") for m in msgs)
    adapters = mcp_call._structured(listed.get("result") or {})
    by_id = {a["adapter_id"]: a for a in (adapters or {}).get("adapters", [])}
    start_desc = next((t.get("description") or "" for t in (tools.get("result") or {}).get("tools") or [] if t.get("name") == "adapter_start"), "")
    return {"prompt_has_guide": HG.GUIDE.strip()[:200] in prompt_text,
            "resources_equal_the_repository": texts[HG.GUIDE_URI] == HG.GUIDE and all(texts[u] == (ROOT / rel).read_text(encoding="utf-8") for u, rel in HG.FILES.items()),
            "source_table_has_comment_rows": all(r in texts[HG.SOURCES_URI] for r in ("src-tiktok-comments", "src-instagram-comments")),
            "preferred_adapter": [by_id.get("ecommerce.product_research", {}).get("adapter_version"), str(by_id.get("ecommerce.product_research", {}).get("description", ""))[:9]],
            "legacy_adapter": [by_id.get("trail.product_discovery", {}).get("adapter_version"), str(by_id.get("trail.product_discovery", {}).get("description", ""))[:6]],
            "start_says_corpus_ids_required": "REQUIRED for a non-admin key" in start_desc}


def _admission() -> dict:
    sys.path.insert(0, str(ROOT / "governance" / "trail"))
    import embedded as E
    now = datetime.now(timezone.utc)
    snap = E.compile_registry_snapshot(E.ROOT / "data", E.ROOT / "config", E.ROOT / "data" / "source_capabilities.csv", compiled_at=now)
    roles = {r.source_id: r for r in snap.source_roles}
    from trail_signal.contexts.evidence.domain.admission import route_source, ReceiptSource  # noqa: E402

    def route(url: str) -> str | None:
        policy = type("P", (), {"source_roles": [type("R", (), {"enabled": r.enabled, "domains_or_patterns": r.domains_or_patterns,
                                                                  "source_class": r.source_class, "source_id": r.source_id})() for r in snap.source_roles]})()
        hit = route_source(policy, ReceiptSource(source_id="s", url=url, source_class="video_platform", retrieved_at=now - timedelta(hours=1),
                                                 published_at_if_known=None))
        return hit.source_id if hit else None
    comment_row = roles.get("src-tiktok-comments")
    return {"snapshot_id": snap.snapshot_id,
            "tiktok_comment_routes": route("https://www.tiktok.com/@creator/video/7400000000000000001"),
            "instagram_reel_routes": route("https://www.instagram.com/reel/C0ABCDEFGHI/"),
            "creative_center_routes": route("https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"),
            "short_link_routes": route("https://vm.tiktok.com/ZMabcdefg/"),
            "comment_row_serves_field_evidence": bool(comment_row and "field_evidence" in [s.value for s in comment_row.supported_research_stages]),
            "comment_row_roles": sorted(comment_row.supported_evidence_roles) if comment_row else None}


def main() -> int:
    mcp = asyncio.run(_mcp())
    adm = _admission()
    checks = {
        "prompt_has_guide": mcp["prompt_has_guide"], "resources_equal_the_repository": mcp["resources_equal_the_repository"],
        "source_table_has_comment_rows": mcp["source_table_has_comment_rows"],
        "preferred_adapter": mcp["preferred_adapter"] == ["0.7.0", "PREFERRED"], "legacy_adapter": mcp["legacy_adapter"] == ["2.2.1", "LEGACY"],
        "start_says_corpus_ids_required": mcp["start_says_corpus_ids_required"],
        "tiktok_comment_admitted_as_field_evidence": adm["tiktok_comment_routes"] == "src-tiktok-comments" and adm["comment_row_serves_field_evidence"],
        "instagram_reel_routes_to_comments": adm["instagram_reel_routes"] == "src-instagram-comments",
        "creative_center_unchanged": adm["creative_center_routes"] == "src-tiktok-creative",
        "short_link_stays_on_the_trend_row": adm["short_link_routes"] == "src-tiktok-creative",
    }
    report = {"mcp": mcp, "admission": adm, "checks": checks}
    (HERE / "live_check.json").write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps(report, indent=1, default=str))
    ok = all(checks.values())
    print("ALL CHECKS PASS" if ok else "A CHECK FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
