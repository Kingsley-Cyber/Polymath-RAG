"""I4R rescue lane: syntax-aligned, GLiNER-verified argument repair.

Division of labor (I4R authorization, 2026-08-16): spaCy identifies
WHERE semantic certainty is missing; GLiNER is re-queried about THAT
exact phrase; the rule pack defines legal structure; deterministic
code decides whether a fact exists. There is NO deterministic
promotion anywhere — every expanded or re-typed argument is confirmed
by the same pinned GLiNER model at the same frozen threshold, or the
fact abstains.

This module owns I4R-A (boundary reconciliation). Missing-argument
rescue (I4R-B) and type reconciliation (I4R-C) extend the same query
machinery; frame arbitration (I4R-D) lives in the rule pack +
compiler.

All offsets: EntitySpans are CHUNK-relative; syntax-evidence-v1 token
and noun-chunk offsets are SENTENCE-relative and are converted using
the slice's sentence_start.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

log = logging.getLogger("rescue")

RESCUE_CONTRACT = "rescue-v1"
RESCUE_THRESHOLD = 0.5  # frozen entity threshold (I4 frozen posture)

# Leading tokens never part of an entity surface ("the gateway" -> "gateway").
TRIM_DEPS = ("det", "poss", "nmod:poss")


@dataclass(frozen=True)
class RescueQuery:
    """Deterministic rescue request identity (user-specified): the
    identity covers contract + kind + query-policy version + model
    revision + threshold + exact target text + ORDERED labels, and is
    recorded in provenance."""

    kind: str
    text: str
    labels: tuple[str, ...]
    threshold: float
    model_revision: str
    query_policy_version: str

    @property
    def identity(self) -> str:
        payload = "|".join((
            RESCUE_CONTRACT, self.kind, self.query_policy_version,
            self.model_revision,
            f"{self.threshold:g}", self.text, ",".join(self.labels),
        ))
        return hashlib.sha256(payload.encode()).hexdigest()

    def payload(self) -> dict:
        return {"text": self.text, "labels": list(self.labels),
                "threshold": self.threshold}


def _trimmed_noun_chunks(syntax: dict, text: str) -> list[tuple[int, int, str]]:
    """Noun chunks as (sentence-relative start, end, surface) with
    leading determiners/possessives trimmed. Invariant preserved:
    text[start:end] == surface for the TRIMMED span."""
    tokens = sorted(syntax.get("tokens", []), key=lambda t: t["char_start"])
    out: list[tuple[int, int, str]] = []
    for chunk in syntax.get("noun_chunks", []):
        start, end = chunk["char_start"], chunk["char_end"]
        inside = [t for t in tokens if t["char_start"] >= start and t["char_end"] <= end]
        while inside and inside[0]["dep"] in TRIM_DEPS:
            inside.pop(0)
        if inside:
            start = inside[0]["char_start"]
        if end <= start:
            continue
        surface = text[start:end]
        if surface and text[start:end] == surface:
            out.append((start, end, surface))
    return out


def boundary_candidates(sl, revision: str) -> list[tuple[object, RescueQuery, int, int]]:
    """Per slice: GLiNER spans strictly inside a larger (trimmed) NP
    become boundary rescue candidates.

    Query labels resolve through the semantic query policy
    (semantic-query-policy-v1) for the entity's ORIGINAL canonical
    type — provider aliases, if a future policy version introduces
    them, live in the policy, never in this code. Acceptance requires
    the returned raw label to map back to the same canonical type.

    Returns (entity, query, chunk-relative target start, end) tuples.
    Clean alignment (span == trimmed NP) and no-NP spans are retained
    untouched — only the contraction class is rescued."""
    from polymath_shared.query_policy import QUERY_POLICY_VERSION, query_labels_for

    syntax = getattr(sl, "syntax", None)
    if not syntax:
        return []
    candidates = []
    for entity in sl.entities:
        es, ee = entity.start, entity.end
        labels = query_labels_for(entity.core_type.value)
        best = None
        for (cs, ce, surface) in _trimmed_noun_chunks(syntax, sl.text):
            chunk_cs, chunk_ce = sl.sentence_start + cs, sl.sentence_start + ce
            if chunk_cs <= es and ee <= chunk_ce and (chunk_ce - chunk_cs) > (ee - es):
                if best is None or (chunk_ce - chunk_cs) < (best[3] - best[2]):
                    best = (entity, surface, chunk_cs, chunk_ce)
        if best is not None:
            entity, surface, chunk_cs, chunk_ce = best
            candidates.append((entity, RescueQuery(
                kind="boundary",
                text=surface,
                labels=tuple(labels),
                threshold=RESCUE_THRESHOLD,
                model_revision=revision,
                query_policy_version=QUERY_POLICY_VERSION,
            ), chunk_cs, chunk_ce))
    return candidates


def _accepted(spans: list[dict], query: RescueQuery) -> dict | None:
    """Exact-full-span-only acceptance: the model must return the
    ENTIRE supplied string with a raw label that maps (through the
    query policy) to a queried canonical type. Partial results are
    rejections; nothing is promoted deterministically."""
    from polymath_shared.query_policy import canonical_of

    target_len = len(query.text)
    for span in spans:
        if (span.get("start") == 0 and span.get("end") == target_len
                and span.get("label") in query.labels):
            return span
    return None


# Dependency relations that fill predicate argument slots. Covers both
# the UD scheme (obj/obl/obl:agent/nsubj:pass) and spaCy's English
# ClearNLP scheme (dobj/pobj/agent); prepositional objects (pobj) hang
# off the preposition, so the trigger->prep->pobj chain is walked too.
ARGUMENT_DEPS = frozenset({
    "nsubj", "nsubj:pass", "obj", "iobj", "dobj", "obl", "obl:agent", "pobj", "agent",
})
PREP_DEPS = frozenset({"prep", "case"})


def _tokens(syntax: dict) -> list[dict]:
    return sorted(syntax.get("tokens", []), key=lambda t: t["char_start"])


def _trigger_tokens(sl, tokens: list[dict]) -> list[dict]:
    """Tokens overlapping this slice's evidence (trigger) spans."""
    out = []
    for ev in sl.evidence:
        s = ev.start - sl.sentence_start
        e = ev.end - sl.sentence_start
        for tok in tokens:
            if tok["char_start"] < e and tok["char_end"] > s:
                out.append(tok)
    return out


def missing_argument_candidates(sl, revision: str, label_set: tuple[str, ...]):
    """I4R-B: trigger-governed grammatical slots with NO GLiNER entity.

    For each evidence (trigger) token, tokens whose dependency head is
    the trigger and whose relation fills an argument slot (nsubj/obj/
    obl/…) identify the argument position; the trimmed noun chunk
    containing such a token is a rescue candidate when NO existing
    entity overlaps it. Free-floating noun chunks never qualify.

    Per the temporal-durability directive (§10), the query uses the
    NORMAL policy vocabulary (the pass-1 label set), never slot-forced
    types; the returned canonical type is validated by the predicate
    signature downstream — rules constrain acceptance, they do not
    manufacture compatibility."""
    from polymath_shared.query_policy import QUERY_POLICY_VERSION

    syntax = getattr(sl, "syntax", None)
    if not syntax:
        return []
    tokens = _tokens(syntax)
    chunks = _trimmed_noun_chunks(syntax, sl.text)
    triggers = {t["i"] for t in _trigger_tokens(sl, tokens)}
    # argument tokens: direct children in argument deps, plus
    # prepositional objects reached through trigger-governed preps
    argument_tokens: list[dict] = []
    for tok in tokens:
        if tok["head_i"] in triggers and tok["dep"] in ARGUMENT_DEPS:
            argument_tokens.append(tok)
        elif tok["head_i"] in triggers and tok["dep"] in PREP_DEPS:
            for tok2 in tokens:
                if tok2["head_i"] == tok["i"] and tok2["dep"] in ARGUMENT_DEPS:
                    argument_tokens.append(tok2)
    candidates = []
    seen_np: set[tuple[int, int]] = set()
    for tok in argument_tokens:
        # the trimmed NP containing this argument token
        np = None
        for (cs, ce, surface) in chunks:
            if cs <= tok["char_start"] and tok["char_end"] <= ce:
                if np is None or (ce - cs) < (np[1] - np[0]):
                    np = (cs, ce, surface)
        if np is None or np[:2] in seen_np:
            continue
        cs, ce, surface = np
        # Quantified NPs ("two new surgeons") are descriptions, not
        # referential entity endpoints — excluded from rescue on
        # syntax alone (I4R-B B07 audit; nummod/quantmod children).
        inside = [t for t in tokens if t["char_start"] >= cs and t["char_end"] <= ce]
        if any(t["dep"] in ("nummod", "quantmod") for t in inside):
            continue
        chunk_cs, chunk_ce = sl.sentence_start + cs, sl.sentence_start + ce
        # only MISSING arguments: skip any NP an entity already covers
        if any(e.start < chunk_ce and e.end > chunk_cs for e in sl.entities):
            continue
        # the NP must not itself be the trigger surface
        if any(ev.start < chunk_ce and ev.end > chunk_cs for ev in sl.evidence):
            continue
        seen_np.add(np[:2])
        candidates.append((RescueQuery(
            kind="missing_argument",
            text=surface,
            labels=tuple(label_set),
            threshold=RESCUE_THRESHOLD,
            model_revision=revision,
            query_policy_version=QUERY_POLICY_VERSION,
        ), chunk_cs, chunk_ce))
    return candidates


def _gliner_revision() -> str:
    from polymath_shared.clients import GlinerClient

    client = GlinerClient()
    try:
        m = client.manifest()
        return m.get("identity", {}).get("model", {}).get("revision", "unknown")
    finally:
        client.close()


def apply_boundary(ordered_slices: list) -> dict:
    """I4R-A: collect + dedup boundary queries for the whole document,
    run ONE batched /rescue call (bounded), apply results per slice.

    Accepted -> the slice's argument-binding entity list carries the
    EXPANDED span (same core type, rescued score, chunk-relative
    offsets of the trimmed NP). Refused -> BOUNDARY_UNRESOLVED: the
    original proposal stays a durable mention (already persisted in
    pass A) but is REMOVED from this sentence's argument binding —
    unresolved argument identity means no edge."""
    from polymath_shared.clients import GlinerClient
    from polymath_shared.contracts import CoreType, EntitySpan

    revision = _gliner_revision()
    per_slice: list[list] = []
    queries: dict[str, RescueQuery] = {}
    for row, sl in ordered_slices:
        found = boundary_candidates(sl, revision)
        per_slice.append(found)
        for entity, query, _cs, _ce in found:
            queries.setdefault(query.identity, query)

    results: dict[str, list[dict]] = {}
    report_queries = []
    if queries:
        ordered = list(queries.values())
        client = GlinerClient()
        try:
            client.verify_pin()
            spans_by_query = []
            for i in range(0, len(ordered), 256):
                spans_by_query.extend(client.infer_rescue_batch(
                    [q.payload() for q in ordered[i:i + 256]]))
        finally:
            client.close()
        results = {q.identity: spans for q, spans in zip(ordered, spans_by_query)}
        for q in ordered:
            hit = _accepted(results.get(q.identity, []), q)
            report_queries.append({
                "identity": q.identity, "kind": q.kind, "text": q.text,
                "labels": list(q.labels), "threshold": q.threshold,
                "query_policy_version": q.query_policy_version,
                "raw_predictions": [
                    {"raw_label": s.get("label"), "text": s.get("text"),
                     "score": round(float(s.get("score", 0.0)), 4)}
                    for s in results.get(q.identity, [])
                ],
                "outcome": "accepted" if hit else "refused",
                "accepted_raw_label": hit.get("label") if hit else None,
                "score": round(float(hit["score"]), 4) if hit else None,
                "accept_reason": "exact_full_span_same_canonical_type" if hit else "no_full_span_prediction",
            })

    accepted = refused = 0
    for (row, sl), found in zip(ordered_slices, per_slice):
        if not found:
            continue
        outcomes = {}
        for entity, query, chunk_cs, chunk_ce in found:
            hit = _accepted(results.get(query.identity, []), query)
            outcomes[id(entity)] = (hit, chunk_cs, chunk_ce)
            if hit:
                accepted += 1
            else:
                refused += 1
        new_entities = []
        for entity in sl.entities:
            outcome = outcomes.get(id(entity))
            if outcome is None:
                new_entities.append(entity)
                continue
            hit, chunk_cs, chunk_ce = outcome
            if hit is None:
                continue  # BOUNDARY_UNRESOLVED: no argument binding here
            new_entities.append(EntitySpan(
                doc_id=entity.doc_id,
                chunk_id=entity.chunk_id,
                start=chunk_cs,
                end=chunk_ce,
                text=sl.text[chunk_cs - sl.sentence_start:chunk_ce - sl.sentence_start],
                core_type=CoreType(entity.core_type.value),
                score=float(hit["score"]),
                extractor_version=entity.extractor_version,
                raw_label=hit.get("label"),
                pass_kind="boundary_rescue",
            ))
        object.__setattr__(sl, "entities", new_entities)

    return {
        "contract": RESCUE_CONTRACT,
        "query_policy_version": _policy_version(),
        "stages": ["boundary"],
        "queries": report_queries,
        "counts": {"candidates": len(queries), "accepted": accepted, "refused": refused},
    }


def _policy_version() -> str:
    from polymath_shared.query_policy import QUERY_POLICY_VERSION

    return QUERY_POLICY_VERSION


def apply_missing_arguments(ordered_slices: list, label_set: tuple[str, ...]) -> dict:
    """I4R-B: query the normal policy vocabulary for trigger-governed
    NPs with no entity; accepted full-span predictions become entity
    spans (pass_kind=missing_argument_rescue) that the existing
    candidate/type-compatibility machinery then validates — predicate
    signatures constrain acceptance, they never force the query."""
    from polymath_shared.clients import GlinerClient
    from polymath_shared.contracts import CoreType, EntitySpan
    from polymath_shared.query_policy import canonical_of

    revision = _gliner_revision()
    per_slice: list[list] = []
    queries: dict[str, RescueQuery] = {}
    for row, sl in ordered_slices:
        found = missing_argument_candidates(sl, revision, label_set)
        per_slice.append(found)
        for query, _cs, _ce in found:
            queries.setdefault(query.identity, query)

    results: dict[str, list[dict]] = {}
    report_queries = []
    if queries:
        ordered = list(queries.values())
        client = GlinerClient()
        try:
            client.verify_pin()
            spans_by_query = []
            for i in range(0, len(ordered), 256):
                spans_by_query.extend(client.infer_rescue_batch(
                    [q.payload() for q in ordered[i:i + 256]]))
        finally:
            client.close()
        results = {q.identity: spans for q, spans in zip(ordered, spans_by_query)}
        for q in ordered:
            hit = _accepted(results.get(q.identity, []), q)
            canonical = canonical_of(hit["label"]) if hit else None
            report_queries.append({
                "identity": q.identity, "kind": q.kind, "text": q.text,
                "labels": list(q.labels), "threshold": q.threshold,
                "query_policy_version": q.query_policy_version,
                "raw_predictions": [
                    {"raw_label": s.get("label"), "text": s.get("text"),
                     "score": round(float(s.get("score", 0.0)), 4)}
                    for s in results.get(q.identity, [])
                ],
                "outcome": "accepted" if (hit and canonical) else "refused",
                "accepted_raw_label": hit.get("label") if hit else None,
                "canonical_type": canonical,
                "score": round(float(hit["score"]), 4) if hit else None,
                "accept_reason": ("exact_full_span_canonical_mappable" if (hit and canonical)
                                  else ("unmappable_label" if hit else "no_full_span_prediction")),
            })

    added = 0
    for (row, sl), found in zip(ordered_slices, per_slice):
        if not found:
            continue
        hits = {q.identity: _accepted(results.get(q.identity, []), q)
                for q, _cs, _ce in found}
        new_entities = list(sl.entities)
        for query, chunk_cs, chunk_ce in found:
            hit = hits[query.identity]
            if hit is None:
                continue
            canonical = canonical_of(hit.get("label", ""))
            if canonical is None:
                continue
            new_entities.append(EntitySpan(
                doc_id=row["doc_id"],
                chunk_id=row["chunk_id"],
                start=chunk_cs,
                end=chunk_ce,
                text=sl.text[chunk_cs - sl.sentence_start:chunk_ce - sl.sentence_start],
                core_type=CoreType(canonical),
                score=float(hit["score"]),
                extractor_version="gliner-2pass-v1",
                raw_label=hit.get("label"),
                pass_kind="missing_argument_rescue",
            ))
            added += 1
        object.__setattr__(sl, "entities", new_entities)

    return {
        "contract": RESCUE_CONTRACT,
        "query_policy_version": _policy_version(),
        "stages": ["missing_argument"],
        "queries": report_queries,
        "counts": {"candidates": len(queries), "accepted": added, "refused": len(queries) - added},
    }


def apply_rescue(ordered_slices: list, stages: tuple[str, ...],
                 label_set: tuple[str, ...] = ()) -> dict:
    """Entry point from the extract worker. Every enabled stage requires
    syntax evidence on every slice; missing evidence fails LOUDLY (no
    silent rescue-free extraction)."""
    for _row, sl in ordered_slices:
        if getattr(sl, "syntax", None) is None:
            raise RuntimeError(
                "rescue enabled but syntax evidence is missing — "
                "POLYMATH_SYNTAX_PROVIDER must be spacy"
            )
    report = {"contract": RESCUE_CONTRACT,
              "query_policy_version": _policy_version(),
              "stages": list(stages)}
    if "boundary" in stages:
        report["boundary"] = apply_boundary(ordered_slices)
    if "missing_argument" in stages:
        report["missing_argument"] = apply_missing_arguments(ordered_slices, label_set)
    return report
