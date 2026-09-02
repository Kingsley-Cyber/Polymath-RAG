"""parent-enrichment-v1 compiler — transport-agnostic (plan §2.1).

`compile_parents(complete, parents, ...)` never imports a client: the
caller supplies `complete(items) -> [(id, raw_text, error_class|None)]`
(the shape `LLMExtractionClient.complete_batched` already returns), so
the same compiler runs against the pinned cross-provider group, a local
batch endpoint, or a test double. The input ceiling is enforced BEFORE
any call (ENRICH_INPUT_OVER_CEILING is a durable skip, never a silent
truncation)."""
from __future__ import annotations

import logging

log = logging.getLogger("polymath.enrich.compiler")

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
    # ENRICH-HARD-CASE-V1: which compiler contract produced the output
    # (persisted verbatim — a minimal escape never masquerades as full)
    contract: str = "parent-enrichment-v1"
    prompt_version: str = ""


def call_budget(bounds, n_parents: int) -> int:
    """ENRICH-BUDGET-V2: output budget for a call carrying n parents —
    30 % headroom per parent + 300 for the envelope, capped at 8000."""
    return min(int(bounds.max_tokens * max(1, n_parents) * 1.3) + 300, 8000)


def _looks_truncated(raw: str, max_tokens: int) -> bool:
    """A response that already spans ~3 chars per budgeted token almost
    certainly ended on the cap (finish_reason is not on this seam)."""
    return len(raw) >= 3 * max_tokens


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
        items.append((p.parent_id, SYSTEM_PROMPT, user, call_budget(bounds, 1)))

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


def compile_with_semantic_failover(
    complete_primary,
    complete_fallback,
    parents: list[ParentInput],
    bounds: EnrichmentBounds,
    input_token_ceiling: int,
) -> tuple[list[CompiledParent], int]:
    """SEMANTIC-FAILOVER-V1 (roadmap A3): a valid HTTP response carrying
    garbage no longer stops dead. Parents whose FIRST compile fails with
    a model-repairable class (SEMANTIC_FAILOVER_ELIGIBLE — plus any
    transport error class the primary surfaced) get EXACTLY ONE retry
    through `complete_fallback` (the other group lane), re-gated
    identically. Never more than one cross-lane retry — no model-repair
    loop. Source conditions (input over ceiling) never retry.

    Returns (compiled, semantic_failovers) — the count is surfaced, per
    the silent-fallback accounting law."""
    from polymath_shared.latent.gate import (
        SEMANTIC_FAILOVER_INELIGIBLE,
    )

    compiled = compile_parents(complete_primary, parents, bounds,
                               input_token_ceiling)
    if complete_fallback is None:
        return compiled, 0
    by_id = {cp.parent_id: cp for cp in compiled}
    retry = [p for p in parents
             if by_id[p.parent_id].status == "INVALID"
             and by_id[p.parent_id].error_class
             not in SEMANTIC_FAILOVER_INELIGIBLE]
    if not retry:
        return compiled, 0
    second = compile_parents(complete_fallback, retry, bounds,
                             input_token_ceiling)
    recovered = 0
    for cp in second:
        prior = by_id[cp.parent_id]
        if cp.status == "READY":
            recovered += 1
            by_id[cp.parent_id] = cp
        else:
            # keep the fallback's disposition but remember both lanes
            cp.detail = (f"primary={prior.error_class}; "
                         f"fallback={cp.error_class}"
                         + (f" ({cp.detail})" if cp.detail else ""))
            by_id[cp.parent_id] = cp
    return [by_id[p.parent_id] for p in parents], recovered


MINIMAL_CONTRACT = "parent-enrichment-minimal-v1"


def compile_minimal_parents(
    complete,
    parents: list[ParentInput],
    bounds: EnrichmentBounds,
    input_token_ceiling: int,
) -> list[CompiledParent]:
    """The bounded ENRICH-HARD-CASE escape pass: the MINIMAL contract
    (abstraction + transfer only) through one lane. Same transport
    shape, its own prompt + gate, tight output budget."""
    from polymath_shared.latent.gate import sanitize_minimal_enrichment
    from polymath_shared.latent.prompt import (
        MINIMAL_PROMPT_VERSION,
        MINIMAL_SYSTEM_PROMPT,
    )
    out: dict[str, CompiledParent] = {}
    items = []
    for p in parents:
        sh = source_hash(p.children)
        ids = [cid for cid, _, _ in p.children]
        wire = [(i, text) for i, (_, _, text) in enumerate(p.children)]
        user = render_parent_input(p.parent_id, wire)
        cp = CompiledParent(
            parent_id=p.parent_id, status="PENDING",
            source_hash=sh, source_child_ids=ids,
            child_ref_map={i: cid for i, (cid, _, _)
                           in enumerate(p.children)},
            contract=MINIMAL_CONTRACT,
            prompt_version=MINIMAL_PROMPT_VERSION)
        if _estimate_tokens(MINIMAL_SYSTEM_PROMPT + user) > input_token_ceiling:
            cp.status, cp.error_class = "INVALID", "ENRICH_INPUT_OVER_CEILING"
            out[p.parent_id] = cp
            continue
        out[p.parent_id] = cp
        items.append((p.parent_id, MINIMAL_SYSTEM_PROMPT, user,
                      min(bounds.max_tokens, 400)))
    if items:
        for pid, raw, err in complete(items):
            cp = out[pid]
            cp.raw_head = (raw or "")[:200]
            if err:
                cp.status, cp.error_class = "INVALID", err
                continue
            gate, output = sanitize_minimal_enrichment(raw, bounds)
            if gate.ok:
                cp.status, cp.output = "READY", output
            else:
                cp.status = "INVALID"
                cp.error_class, cp.detail = gate.error_class, gate.detail
    for cp in out.values():
        if cp.status == "PENDING":
            cp.status, cp.error_class = "INVALID", "ENRICH_NO_RESPONSE"
    return [out[p.parent_id] for p in parents]


def compile_with_hard_case_escape(
    complete_primary,
    complete_fallback,
    complete_escape,
    parents: list[ParentInput],
    bounds: EnrichmentBounds,
    input_token_ceiling: int,
) -> tuple[list[CompiledParent], int, int, int]:
    """ENRICH-HARD-CASE-V1 state machine (owner design 2026-09-01):

        lane A -> reject -> lane B (semantic failover, unchanged)
                 -> reject -> ONE minimal escape on a THIRD lane
                             -> reject -> ENRICH_HARD_CASE (terminal
                                by row-truth; sweeps stop retrying)

    Source conditions (over ceiling) never reach the escape. Returns
    (compiled, semantic_failovers, hard_recovered, hard_terminal) —
    every count surfaced, per the silent-fallback accounting law."""
    from polymath_shared.latent.gate import (
        SEMANTIC_FAILOVER_INELIGIBLE,
    )
    compiled, failovers = compile_with_semantic_failover(
        complete_primary, complete_fallback, parents, bounds,
        input_token_ceiling)
    if complete_escape is None:
        return compiled, failovers, 0, 0
    by_id = {cp.parent_id: cp for cp in compiled}
    escape = [p for p in parents
              if by_id[p.parent_id].status == "INVALID"
              and by_id[p.parent_id].error_class
              not in SEMANTIC_FAILOVER_INELIGIBLE]
    if not escape:
        return compiled, failovers, 0, 0
    third = compile_minimal_parents(complete_escape, escape, bounds,
                                    input_token_ceiling)
    hard_recovered = hard_terminal = 0
    for cp in third:
        prior = by_id[cp.parent_id]
        if cp.status == "READY":
            hard_recovered += 1
            by_id[cp.parent_id] = cp
        else:
            hard_terminal += 1
            prior.error_class = "ENRICH_HARD_CASE"
            prior.detail = (f"{prior.detail}; "
                            f"escape={cp.error_class}").strip("; ")
    return ([by_id[p.parent_id] for p in parents], failovers,
            hard_recovered, hard_terminal)


def compile_parents_microbatched(
    complete,
    parents: list[ParentInput],
    bounds: EnrichmentBounds,
    input_token_ceiling: int,
    max_per_call: int = 8,
    on_compiled=None,
    max_concurrency: int = 1,
) -> list[CompiledParent]:
    """ENRICH-MICROBATCH-V1 (owner 2026-09-01): token-aware batches of
    item-isolated parents through ONE call each; per-item validation
    via sanitize_microbatch (which reuses the per-parent gate); split
    ladder 8→4→2→1 on envelope-level failure (transport error or an
    unparseable envelope) so one pathological section degrades to the
    proven single-parent path instead of poisoning its batchmates.
    Partial acceptance is intrinsic: every item gets its own
    CompiledParent, and callers persist READY ones regardless of what
    happened to their batchmates.

    MICROBATCH-CONCURRENCY-V1 (2026-09-01, from the live E2E: 884
    parents took 2h49m at ~5.3/min because batches ran strictly one
    after another while five pinned lanes sat idle): max_concurrency>1
    runs whole batches concurrently. Safe by construction — each
    parent belongs to exactly ONE batch, so out[] writes are disjoint;
    a batch's split ladder stays sequential inside its own thread; the
    returned list keeps input order regardless of completion order.
    Default 1 preserves the qualified sequential behavior."""
    from polymath_shared.latent.prompt import (
        MICROBATCH_PROMPT_VERSION,
        MICROBATCH_SYSTEM_PROMPT,
        render_microbatch_input,
    )

    # per-parent scaffolding + individual ceiling checks (single-parent
    # semantics preserved exactly)
    meta: dict[str, dict] = {}
    eligible: list[ParentInput] = []
    out: dict[str, CompiledParent] = {}
    for p in parents:
        sh = source_hash(p.children)
        ids = [cid for cid, _, _ in p.children]
        wire = [(i, text) for i, (_, _, text) in enumerate(p.children)]
        cp = CompiledParent(
            parent_id=p.parent_id, status="PENDING",
            source_hash=sh, source_child_ids=ids,
            child_ref_map={i: cid for i, (cid, _, _)
                           in enumerate(p.children)},
            prompt_version=MICROBATCH_PROMPT_VERSION)
        est = _estimate_tokens(render_microbatch_input(
            [(p.parent_id, wire)]))
        if est > input_token_ceiling:
            cp.status = "INVALID"
            cp.error_class = "ENRICH_INPUT_OVER_CEILING"
            cp.detail = f"input over {input_token_ceiling} tokens"
        out[p.parent_id] = cp
        meta[p.parent_id] = {"wire": wire, "est": est,
                             "refs": [i for i, _ in wire], "p": p}
        if cp.status == "PENDING":
            eligible.append(p)

    # token-aware packing (batch input stays under the ceiling too)
    batches: list[list[ParentInput]] = []
    buf: list[ParentInput] = []
    buf_est = _estimate_tokens(MICROBATCH_SYSTEM_PROMPT)
    for p in eligible:
        est = meta[p.parent_id]["est"]
        if buf and (len(buf) >= max_per_call
                    or buf_est + est > input_token_ceiling):
            batches.append(buf)
            buf, buf_est = [], _estimate_tokens(MICROBATCH_SYSTEM_PROMPT)
        buf.append(p)
        buf_est += est
    if buf:
        batches.append(buf)

    def _emit(batch: list[ParentInput]) -> None:
        # PER-BATCH PERSIST SEAM (owner 2026-09-01 "fix the per batch
        # persist"): hand each batch's compiled parents to the caller
        # THE MOMENT they gate — a crash or bounce mid-document keeps
        # every batch already landed (measured: four bounces each threw
        # away a whole document's compiled-but-unpersisted work).
        if on_compiled is None:
            return
        for p in batch:
            try:
                on_compiled(out[p.parent_id])
            except Exception:
                pass                        # persistence is the caller's
                                            # duty; never kill the compile

    def _run_batch(batch: list[ParentInput]) -> None:
        if len(batch) == 1:
            # ladder floor: the proven single-parent compiler
            single = compile_parents(complete, batch, bounds,
                                     input_token_ceiling)
            out[batch[0].parent_id] = single[0]
            _emit(batch)
            return
        user = render_microbatch_input(
            [(p.parent_id, meta[p.parent_id]["wire"]) for p in batch])
        # ENRICH-BUDGET-V2 (measured 2026-09-02 with per-call logging):
        # at 700*n+200 the verbose lanes (gemini-lite, qwen3.7, nemotron)
        # hit finish=length on nearly every batch, the truncated envelope
        # failed the gate, the ladder split, and single-parent retries
        # truncated again — 29 of 54 parents ground for 20+ minutes. A
        # 30 % headroom per parent plus a one-shot doubling on a likely
        # truncation (raw already ~3 chars per budgeted token) ends it.
        max_tokens = call_budget(bounds, len(batch))
        rows = complete([(batch[0].parent_id, MICROBATCH_SYSTEM_PROMPT,
                          user, max_tokens)])
        raw, err = "", "ENRICH_NO_RESPONSE"
        for _bid, r, e in rows:
            raw, err = r, e
            break
        if not err and raw and _looks_truncated(raw, max_tokens) and max_tokens < 8000:
            retry_tokens = min(max_tokens * 2, 8000)
            log.warning("microbatch retry: %d parents, likely truncated "
                        "(raw_len=%d at %d tokens) -> %d tokens",
                        len(batch), len(raw), max_tokens, retry_tokens,
                        extra={"error_code": "ENRICH_BATCH_TRUNCATED"})
            rows = complete([(batch[0].parent_id, MICROBATCH_SYSTEM_PROMPT,
                              user, retry_tokens)])
            for _bid, r, e in rows:
                if not e and r:
                    raw, err, max_tokens = r, e, retry_tokens
                break
        if err or not raw:
            # ENRICH-CALL-VISIBILITY (2026-09-02): the ladder was silent —
            # 29 parents ground through splits for 20 min with no log line.
            log.warning("microbatch split: %d parents, transport err=%s raw_len=%d",
                        len(batch), err or "EMPTY", len(raw or ""),
                        extra={"error_code": "ENRICH_BATCH_SPLIT"})
            half = len(batch) // 2               # split ladder
            _run_batch(batch[:half])
            _run_batch(batch[half:])
            return
        from polymath_shared.latent.gate import sanitize_microbatch
        expected = {p.parent_id: meta[p.parent_id]["refs"] for p in batch}
        gated = sanitize_microbatch(raw, expected, bounds)
        envelope_dead = all(
            g.error_class == "ENRICH_UNPARSEABLE"
            for g, _o in gated.values())
        if envelope_dead and len(batch) > 1:
            log.warning("microbatch split: %d parents, envelope unparseable "
                        "(raw_len=%d head=%r)", len(batch), len(raw), raw[:80],
                        extra={"error_code": "ENRICH_BATCH_SPLIT"})
            half = len(batch) // 2
            _run_batch(batch[:half])
            _run_batch(batch[half:])
            return
        for p in batch:
            gate, output = gated[p.parent_id]
            cp = out[p.parent_id]
            cp.raw_head = (raw or "")[:200]
            cp.gist_coverage = gate.gist_coverage
            if gate.ok:
                cp.status, cp.output = "READY", output
            else:
                cp.status = "INVALID"
                cp.error_class, cp.detail = gate.error_class, gate.detail
        n_ok = sum(1 for p in batch if out[p.parent_id].status == "READY")
        log.info("microbatch gated: %d parents -> %d READY, %d INVALID (%s)",
                 len(batch), n_ok, len(batch) - n_ok,
                 ",".join(sorted({out[p.parent_id].error_class or "" for p in batch
                                  if out[p.parent_id].status != "READY"})) or "-")
        _emit(batch)

    if max_concurrency > 1 and len(batches) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(
                max_workers=min(max_concurrency, len(batches))) as pool:
            list(pool.map(_run_batch, batches))
    else:
        for batch in batches:
            _run_batch(batch)
    for cp in out.values():
        if cp.status == "PENDING":
            cp.status, cp.error_class = "INVALID", "ENRICH_NO_RESPONSE"
    return [out[p.parent_id] for p in parents]


def compile_microbatched_with_hard_case(
    complete_primary,
    complete_fallback,
    complete_escape,
    parents: list[ParentInput],
    bounds: EnrichmentBounds,
    input_token_ceiling: int,
    max_per_call: int = 8,
    on_compiled=None,
    max_concurrency: int = 1,
) -> tuple[list[CompiledParent], int, int, int]:
    """Microbatch first; every INVALID-but-model-repairable parent then
    walks the EXISTING single-parent ladder (semantic failover on the
    other lane → cross-family minimal escape → typed terminal). One
    contract, one failure taxonomy, two granularities.
    max_concurrency applies to the first (microbatch) pass only — the
    repair ladder is the rare tail and stays sequential."""
    from polymath_shared.latent.gate import SEMANTIC_FAILOVER_INELIGIBLE

    compiled = compile_parents_microbatched(
        complete_primary, parents, bounds, input_token_ceiling,
        max_per_call=max_per_call, on_compiled=on_compiled,
        max_concurrency=max_concurrency)
    by_id = {cp.parent_id: cp for cp in compiled}
    retry = [p for p in parents
             if by_id[p.parent_id].status == "INVALID"
             and by_id[p.parent_id].error_class
             not in SEMANTIC_FAILOVER_INELIGIBLE]
    if not retry:
        return compiled, 0, 0, 0
    second, failovers, hard_rec, hard_term = compile_with_hard_case_escape(
        complete_fallback or complete_primary,
        complete_fallback, complete_escape, retry, bounds,
        input_token_ceiling)
    for cp in second:
        prior = by_id[cp.parent_id]
        if cp.status == "READY":
            by_id[cp.parent_id] = cp
        else:
            cp.detail = (f"microbatch={prior.error_class}; "
                         f"{cp.detail}").strip("; ")
            by_id[cp.parent_id] = cp
    recovered = sum(1 for p in retry
                    if by_id[p.parent_id].status == "READY")
    return ([by_id[p.parent_id] for p in parents], failovers,
            recovered, hard_term)
