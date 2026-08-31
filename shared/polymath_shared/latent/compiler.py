"""parent-enrichment-v1 compiler — transport-agnostic (plan §2.1).

`compile_parents(complete, parents, ...)` never imports a client: the
caller supplies `complete(items) -> [(id, raw_text, error_class|None)]`
(the shape `LLMExtractionClient.complete_batched` already returns), so
the same compiler runs against the pinned cross-provider group, a local
batch endpoint, or a test double. The input ceiling is enforced BEFORE
any call (ENRICH_INPUT_OVER_CEILING is a durable skip, never a silent
truncation)."""
from __future__ import annotations

from dataclasses import dataclass, field

from polymath_shared.latent.contract import (
    EnrichmentBounds,
    EnrichmentOutput,
)
from polymath_shared.latent.gate import sanitize_enrichment, source_hash
from polymath_shared.latent.prompt import SYSTEM_PROMPT, render_parent_input


@dataclass
class ParentInput:
    parent_id: str
    # ordered (chunk_id, chunk_index, text); wire refs are the ordinals
    children: list[tuple[str, int, str]]


@dataclass
class CompiledParent:
    parent_id: str
    status: str                       # READY | INVALID
    source_hash: str
    source_child_ids: list[str]
    output: EnrichmentOutput | None = None
    error_class: str | None = None
    detail: str = ""
    gist_coverage: float = 0.0
    raw_head: str = ""
    child_ref_map: dict = field(default_factory=dict)   # ref -> chunk_id


def _estimate_tokens(text: str) -> int:
    from polymath_shared.llm_extraction.client import estimate_input_tokens
    return estimate_input_tokens(text)


def compile_parents(
    complete,
    parents: list[ParentInput],
    bounds: EnrichmentBounds,
    input_token_ceiling: int,
) -> list[CompiledParent]:
    out: dict[str, CompiledParent] = {}
    items = []
    ref_maps: dict[str, dict] = {}
    refs_by_parent: dict[str, list[int]] = {}
    for p in parents:
        sh = source_hash(p.children)
        ids = [cid for cid, _, _ in p.children]
        wire = [(i, text) for i, (_, _, text) in enumerate(p.children)]
        ref_maps[p.parent_id] = {i: cid for i, (cid, _, _)
                                 in enumerate(p.children)}
        refs_by_parent[p.parent_id] = [i for i, _ in wire]
        user = render_parent_input(p.parent_id, wire)
        if _estimate_tokens(SYSTEM_PROMPT + user) > input_token_ceiling:
            out[p.parent_id] = CompiledParent(
                parent_id=p.parent_id, status="INVALID",
                source_hash=sh, source_child_ids=ids,
                error_class="ENRICH_INPUT_OVER_CEILING",
                detail=f"input over {input_token_ceiling} tokens",
                child_ref_map=ref_maps[p.parent_id])
            continue
        out[p.parent_id] = CompiledParent(
            parent_id=p.parent_id, status="PENDING",
            source_hash=sh, source_child_ids=ids,
            child_ref_map=ref_maps[p.parent_id])
        items.append((p.parent_id, SYSTEM_PROMPT, user, bounds.max_tokens))

    if items:
        for pid, raw, err in complete(items):
            cp = out[pid]
            if err:
                cp.status, cp.error_class = "INVALID", err
                cp.raw_head = (raw or "")[:200]
                continue
            gate, output = sanitize_enrichment(
                raw, refs_by_parent[pid], bounds)
            cp.gist_coverage = gate.gist_coverage
            cp.raw_head = (raw or "")[:200]
            if gate.ok:
                cp.status, cp.output = "READY", output
            else:
                cp.status = "INVALID"
                cp.error_class, cp.detail = gate.error_class, gate.detail
    for cp in out.values():
        if cp.status == "PENDING":     # transport never returned it
            cp.status, cp.error_class = "INVALID", "ENRICH_NO_RESPONSE"
    return [out[p.parent_id] for p in parents]
