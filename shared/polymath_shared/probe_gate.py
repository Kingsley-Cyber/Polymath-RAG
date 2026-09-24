"""PROBE-GATE-V1 — a vague probe earns nothing, decided before retrieval (owner design note, 2026-09-23: "A vague bridge
earns nothing"; SKELETON-ROUTING-V1 §9.4).

Every plan gains probes the user never wrote: PROFILE probes (a question from a nominated book's profile), BRIDGE probes
(a nominated book's concept, reworded as a question) and CORPUS_EXPLORE probes. Some miss the question entirely. Measured
on five live plans (2026-09-24): "How do television techniques influence film editing and audience perception?" rode a
question about building suspense without dialogue. An off-topic probe spends candidate slots, judged seats and
cross-encoder time, and never reaches the final evidence (all four off-topic probes: 0 final chunks).

One cross-encoder call scores each such probe against the user's RESOLVED question — the full question with its context,
not the compact retrieval query: the compact form had dropped the context and inverted the verdicts (a useful bridge fell
from 0.99 to 0.22, an off-topic probe rose from 0.04 to 0.77; measured). The four off-topic probes scored 0.02–0.08; every
probe that contributed evidence scored ≥ 0.31, so the floor (0.2) sits in a wide gap. A probe below the floor is dropped
before retrieval. The user's own facets (USER origin) are never gated. Fail-open: any error or timeout keeps every probe.
No LLM; one bounded call of ≤ 10 short pairs.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable

#: the probe origins the gate may drop (the user's own facets are never gated)
GATED_ORIGINS = frozenset({"PROFILE", "BRIDGE", "CORPUS_EXPLORE"})
#: σ floor; measured gap 2026-09-24: off-topic 0.02–0.08, contributing ≥ 0.31
DEFAULT_FLOOR = 0.2
PROBE_GATE_VERSION = "probe-gate-v1"


def _sig(x) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(x)))))


def gate_probes(question: str, probes: Iterable[tuple[str, str, str]], rerank: Callable[[str, list[dict]], list[dict]], *,
                floor: float = DEFAULT_FLOOR, timeout_s: float | None = 3.0) -> tuple[set[str], dict]:
    """`probes` = (id, origin, text). Returns (the ids to drop, the receipt). Only GATED_ORIGINS are scored; a probe the
    judge did not score is kept. `timeout_s` bounds the one judge call (None = no bound); past it, nothing is dropped."""
    t0 = time.perf_counter()
    gated = [(pid, origin, text) for pid, origin, text in probes if origin in GATED_ORIGINS and (text or "").strip()]
    receipt: dict = {"version": PROBE_GATE_VERSION, "floor": floor, "scored": len(gated), "dropped": [], "scores": {}}
    if not gated or floor <= 0 or not (question or "").strip():
        receipt["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return set(), receipt
    rows = [{"chunk_id": pid, "doc_id": "", "parent_id": "", "source_name": "", "text": text} for pid, _o, text in gated]
    try:
        if timeout_s is None:
            out = rerank(question, rows)
        else:
            from concurrent.futures import ThreadPoolExecutor
            ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="probe-gate")
            try:
                out = ex.submit(rerank, question, rows).result(timeout=timeout_s)
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
    except Exception as exc:  # noqa: BLE001 — fail-open: a judge outage never drops a probe
        receipt.update({"error": f"{type(exc).__name__}", "ms": round((time.perf_counter() - t0) * 1000, 1)})
        return set(), receipt
    scores = {r.get("chunk_id"): r.get("rerank_score") for r in (out or [])}
    dropped: set[str] = set()
    for pid, origin, _text in gated:
        s = scores.get(pid)
        if s is None:
            continue
        p = round(_sig(s), 4)
        receipt["scores"][pid] = {"origin": origin, "score": p}
        if p < floor:
            dropped.add(pid)
    receipt["dropped"] = sorted(dropped)
    receipt["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return dropped, receipt
