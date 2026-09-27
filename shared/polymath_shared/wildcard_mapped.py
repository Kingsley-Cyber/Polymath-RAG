"""FACET-RETRIEVAL-V1 F3 — WILDCARD's mapped subqueries (register 11.545; docs/wiki/plans/FACET-RETRIEVAL-V1.md §3.3).

The owner (2026-09-27): "wildcard should use its lanes to create better mapped subqueries". Pass 1 runs the facets' queries;
WILDCARD's lanes — the atom frontier, the see-also blends, the top latent candidates (the parents the finish will validate
as bridges) — return what the library holds around the question. This module turns those findings into a SECOND pass of
subqueries mapped to the library: ≤ MAPPED_PER_FACET per facet, ≤ MAPPED_TOTAL in total, origin WILDCARD, `facet_id`
set, each a SHORT natural query built from the atom / see-also / latent text (an enrichment surface, never a raw chunk),
gated against the ORIGINAL question by the reranker (`probe_gate.gate_probes`, floor MAPPED_GATE_FLOOR, fail-open and
counted). The route (`chat_retrieval._retrieve_wildcard`) then hands the kept ones to `chat_retrieve_v2`, which retrieves
and fuses them exactly like the plan's subqueries, so F2's facet seats and per-document quotas apply to their evidence.

Pure: no I/O. `POLYMATH_WILDCARD_MAPPED=0` restores the pre-F3 WILDCARD composition byte for byte (the route never
builds the seam).
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Sequence

from polymath_shared.chat_plan import _content_words, _has_instruction_tokens
from polymath_shared.probe_gate import gate_probes

MAPPED_CONTRACT = "wildcard-mapped-v1"
MAPPED_FLAG = "POLYMATH_WILDCARD_MAPPED"
MAPPED_ORIGIN = "WILDCARD"
#: the plan's indirect probes (PROFILE / BRIDGE) are typed ENTITY; a mapped subquery is one more indirect probe
MAPPED_QUERY_TYPE = "ENTITY"
#: the fusion weight of a mapped subquery: the BRIDGE probe's (0.55) — an indirect probe, never the user's own facet (0.8+)
MAPPED_WEIGHT = 0.55
MAPPED_PER_FACET = 2
MAPPED_TOTAL = 6
#: PROBE-GATE-V1's floor (measured gap 2026-09-24: off-topic 0.02–0.08, contributing ≥ 0.31)
MAPPED_GATE_FLOOR = 0.2
MAPPED_QUERY_MAX_WORDS = 14
MAPPED_QUERY_MAX_CHARS = 120
#: a candidate whose content words overlap a plan query (or an earlier mapped query) at or above this Jaccard is the same
#: search again — dropped, counted `dropped_duplicate`
MAPPED_DUPLICATE_JACCARD = 0.6
#: the sources, in the order a facet's candidates interleave them (see-also lines are the question's own documents'
#: pointers; atoms are the corpus's concept surfaces; latent parents are the frontier the finish validates)
MAPPED_SOURCES = ("seealso", "atom", "latent")

__all__ = ["MAPPED_CONTRACT", "MAPPED_FLAG", "MAPPED_GATE_FLOOR", "MAPPED_ORIGIN", "MAPPED_PER_FACET", "MAPPED_QUERY_TYPE",
           "MAPPED_TOTAL", "MAPPED_WEIGHT", "best_facet", "build_mapped_subqueries", "gate_mapped", "mapped_enabled",
           "short_query"]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
#: discourse / boilerplate leads an enrichment surface may open with — never part of a search query
_LEAD_RES = (
    re.compile(r"^(?:(?:the|a|an|one)\s+)?(?:key\s+|core\s+|central\s+|underlying\s+|general\s+)?"
               r"(?:principle|insight|idea|lesson|pattern|takeaway|rule|abstraction|transfer|point|mechanism)"
               r"\s*(?:here\s+)?(?:is|:|—|-)\s*(?:that\s+)?", re.IGNORECASE),
    re.compile(r"^(?:in short|in other words|put simply|essentially|note that|it (?:is|seems) that|this (?:means|suggests|shows|"
               r"transfers to|applies to|implies) that|this (?:means|suggests|shows|transfers to|applies to|implies))\s*[:,]?\s*", re.IGNORECASE),
)
_TRAILING_STOP = frozenset(["a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "in", "is", "it", "of", "on", "or",
                            "that", "the", "this", "to", "was", "with", "which"])
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


def mapped_enabled(env=None) -> bool:
    """Default ON (the plan of record admits F3); `0` / `false` / `off` / `no` = the pre-F3 WILDCARD composition."""
    env = os.environ if env is None else env
    return str(env.get(MAPPED_FLAG, "1")).strip().lower() not in ("0", "false", "off", "no")


def short_query(text: str) -> str:
    """A short natural search query from an enrichment surface: the first sentence, its discourse lead stripped, at most
    MAPPED_QUERY_MAX_WORDS words / MAPPED_QUERY_MAX_CHARS characters (cut at a word, trailing stop words trimmed). "" when
    fewer than two content words remain or the text carries output instructions — never a raw chunk."""
    t = " ".join(str(text or "").split()).strip().strip('"“”\'')
    if not t:
        return ""
    first = next((s for s in _SENTENCE_SPLIT.split(t) if s.strip()), t).strip()
    for _ in range(2):
        for rx in _LEAD_RES:
            first = rx.sub("", first, count=1).strip()
    words = _TOKEN.findall(first)
    words = words[:MAPPED_QUERY_MAX_WORDS]
    out = " ".join(words)
    if len(out) > MAPPED_QUERY_MAX_CHARS:
        cut = out[:MAPPED_QUERY_MAX_CHARS]
        out = cut[: cut.rfind(" ")] if " " in cut else cut
        words = out.split()
    while words and words[-1].lower() in _TRAILING_STOP:
        words.pop()
    out = " ".join(words).strip(" ,;:-—")
    if len(_content_words(out)) < 2 or _has_instruction_tokens(out):
        return ""
    return out


def _same_stem(a: str, b: str) -> bool:
    """`emotion` ~ `emotional`, `video` ~ `videos`, `direct` ~ `directing`: equal, or one a prefix of the other with the
    shorter at least 5 characters (no stemmer; deterministic)."""
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 5 and long_.startswith(short)


def facet_overlap(text: str, facet_texts: Sequence[str]) -> int:
    """How many content words of `text` a facet's query texts share (a word counts once; stems match, see `_same_stem`)."""
    words = _content_words(text)
    have = _content_words(" ".join(str(x) for x in facet_texts))
    return sum(1 for w in words if any(_same_stem(w, h) for h in have))


def best_facet(text: str, facets: Sequence[tuple[str, Sequence[str]]], *, room: Callable[[str], bool] | None = None) -> str | None:
    """The facet whose query texts share the most content words with `text` (stems match: `emotion` ~ `emotional`); ties to
    the earlier facet; None without any overlap. `room(facet_id)` False leaves that facet out (its seats are taken — the
    next-best overlapping facet is chosen instead). Deterministic; no model."""
    best, best_n = None, 0
    for fid, texts in facets:
        if room is not None and not room(str(fid)):
            continue
        n = facet_overlap(text, texts)
        if n > best_n:
            best, best_n = str(fid), n
    return best


def _jaccard(a: set[str], b: set[str]) -> float:
    return (len(a & b) / len(a | b)) if (a or b) else 0.0


def build_mapped_subqueries(*, seealso: Iterable[dict] = (), atoms: Iterable[dict] = (), latent: Iterable[dict] = (),
                            facets: Sequence[tuple[str, Sequence[str]]] = (), plan_queries: Iterable[str] = (),
                            per_facet: int = MAPPED_PER_FACET, total: int = MAPPED_TOTAL) -> tuple[list[dict], dict]:
    """The sweep's findings → mapped subquery rows, per facet.

    `seealso`: [{text, kind, doc_id}] (lane G's blends, then its fan-out atoms, in rank order); `atoms`: [{text, atom_kind,
    doc_id, score}] (the atom frontier, best first); `latent`: [{parent_id, doc_id, abstraction, transfer, hop1}] (the
    sweep's parents, best first). `facets`: ((facet_id, (query texts…)), …) in plan order — a candidate attaches to the
    facet with the best content-word overlap that still has a seat (`attach: overlap`), else, with no overlap at all, to
    the first facet (the request's core; `attach: primary`) while it has one; a candidate no facet can seat is dropped
    (`dropped_no_room`) — a facet's seats are never filled with words that name another facet. Without facets every row
    has `facet_id: None` and the total cap alone applies. `plan_queries`: the texts already searched.

    Rows `{id, facet_id, query, from, source, attach, kept}` (`kept` is the gate's to set), ids w0…; the sources interleave
    (see-also, atom, latent, see-also, …) so one facet never takes only one lane's words; the facets are filled
    round-robin (every facet's first before any facet's second) under `per_facet` and `total`. Receipt: the candidate
    counts per source, the drops (empty, duplicate, no room) and the caps."""
    cands: dict[str, list[dict]] = {src: [] for src in MAPPED_SOURCES}
    for it in seealso or ():
        if isinstance(it, dict) and (it.get("text") or "").strip():
            cands["seealso"].append({"from": "seealso", "text": str(it["text"]),
                                     "source": {"kind": str(it.get("kind") or "SEEALSO"), "doc_id": str(it.get("doc_id") or "")}})
    for a in sorted((a for a in (atoms or ()) if isinstance(a, dict) and (a.get("text") or "").strip()),
                    key=lambda a: -float(a.get("score") or 0.0)):
        cands["atom"].append({"from": "atom", "text": str(a["text"]),
                              "source": {"kind": str(a.get("atom_kind") or "atom"), "doc_id": str(a.get("doc_id") or "")}})
    for p in sorted((p for p in (latent or ()) if isinstance(p, dict)),
                    key=lambda p: (-float(p.get("hop1") or 0.0), str(p.get("parent_id") or ""))):
        text = str(p.get("abstraction") or p.get("transfer") or "").strip()
        if text:
            cands["latent"].append({"from": "latent", "text": text,
                                    "source": {"parent_id": str(p.get("parent_id") or ""), "doc_id": str(p.get("doc_id") or "")}})
    rec: dict = {"contract": MAPPED_CONTRACT, "candidates": {src: len(v) for src, v in cands.items()},
                 "dropped_empty": 0, "dropped_duplicate": 0, "dropped_no_room": 0, "built": 0, "per_facet": per_facet,
                 "total": total, "facets": len(facets)}
    seen_words: list[set[str]] = [_content_words(q) for q in (plan_queries or ()) if str(q or "").strip()]
    seen_text: set[str] = set()
    facet_ids = [str(fid) for fid, _ in facets] or [None]
    per_facet_cap = per_facet if facets else total
    accepted: dict[str | None, list[dict]] = {fid: [] for fid in facet_ids}
    # interleave the sources per facet: the i-th of every source before the (i+1)-th of any
    order: list[dict] = []
    for i in range(max((len(v) for v in cands.values()), default=0)):
        for src in MAPPED_SOURCES:
            if i < len(cands[src]):
                order.append(cands[src][i])
    for c in order:
        q = short_query(c["text"])
        if not q:
            rec["dropped_empty"] += 1
            continue
        key = q.lower()
        words = _content_words(q)
        if key in seen_text or any(_jaccard(words, w) >= MAPPED_DUPLICATE_JACCARD for w in seen_words):
            rec["dropped_duplicate"] += 1
            continue
        if facets:
            fid = best_facet(q, facets, room=lambda f: len(accepted[f]) < per_facet_cap)
            attach = "overlap"
            if fid is None:
                if best_facet(q, facets) is not None or len(accepted[facet_ids[0]]) >= per_facet_cap:
                    rec["dropped_no_room"] += 1          # its facet(s) are seated, or the core is: never another facet's words
                    continue
                fid, attach = facet_ids[0], "primary"
        else:
            fid, attach = None, "none"
            if len(accepted[fid]) >= per_facet_cap:
                rec["dropped_no_room"] += 1
                continue
        seen_text.add(key)
        seen_words.append(words)
        accepted[fid].append({"facet_id": fid, "query": q, "from": c["from"], "source": c["source"], "attach": attach})
    rows: list[dict] = []
    for i in range(per_facet_cap):                        # round-robin: every facet's first before any facet's second
        for fid in facet_ids:
            if i < len(accepted[fid]) and len(rows) < total:
                rows.append(accepted[fid][i])
    for n, r in enumerate(rows):
        r["id"] = f"w{n}"
        r["kept"] = True
    rows = [{"id": r["id"], "facet_id": r["facet_id"], "query": r["query"], "from": r["from"], "source": r["source"],
             "attach": r["attach"], "kept": True} for r in rows]
    rec["built"] = len(rows)
    return rows, rec


def gate_mapped(question: str, rows: list[dict], rerank: Callable[[str, list[dict]], list[dict]], *,
                floor: float = MAPPED_GATE_FLOOR, timeout_s: float | None = 3.0) -> dict:
    """PROBE-GATE-V1 over the mapped rows against the ORIGINAL question (origin WILDCARD gated here — the chat plan's
    gate exempts WILDCARD probes; a mapped subquery is a search, not a bridge, and an off-topic one spends seats). Sets
    `gate_score` (σ of the judge's logit) and `kept` on every row in place. Fail-open: a judge error or timeout keeps
    every row and is counted (`error`, `kept_unscored`). Returns the small receipt (no clock reading: `ms` is popped)."""
    dropped, rec = gate_probes(question, [(str(r["id"]), MAPPED_ORIGIN, str(r.get("query") or "")) for r in rows], rerank,
                               floor=floor, timeout_s=timeout_s, gated_origins=(MAPPED_ORIGIN,))
    unscored = 0
    for r in rows:
        s = (rec.get("scores") or {}).get(str(r["id"]))
        r["gate_score"] = s.get("score") if isinstance(s, dict) else None
        r["kept"] = str(r["id"]) not in dropped
        if r["gate_score"] is None:
            unscored += 1
    out = {"version": rec.get("version"), "floor": floor, "scored": int(rec.get("scored") or 0), "dropped": sorted(dropped),
           "kept_unscored": unscored}
    if rec.get("error"):
        out["error"] = rec["error"]
    return out
