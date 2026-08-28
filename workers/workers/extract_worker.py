"""extract worker: GLiNER pass 1 + pass 2 -> compiler -> facts. One durable stage.

Consumes `chunked.v1` outbox events. Flow per document:

  for each child chunk:
    pass 1: entity spans (chunk label set from the document profile)
    pass 2: evidence spans (18-class evidence inventory)
    per sentence: candidates (workers.candidates) -> compiler
    ACCEPT/QUALIFY -> facts + evidence rows; REJECT/AMBIGUOUS/UNSUPPORTED
    -> audit rows only (never invented edges, docx: silence is valid).

Entity, fact, and evidence rows commit in ONE Postgres transaction with
the receipt (AGENTS.md rule 5). GLiNER proposes; the compiler decides.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from dataclasses import dataclass, field

import psycopg
from psycopg import Connection

from polymath_shared.clients import GlinerClient
from polymath_shared.contracts import (
    CoreType,
    EntitySpan,
    EvidenceSpan,
    ExtractionManifest,
)
from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
)
from polymath_shared.query_policy import QUERY_POLICY_VERSION, policy_identity
from polymath_shared.rulepack import compile_relation, compile_relation_kimi, load_rule_pack
from workers.candidates import SentenceSlice
from workers.kimi_candidates import active_pipeline, build_candidates_dispatch as build_candidates
from workers.evidence_proposer import EXTRACTOR_VERSION as EVIDENCE_EXTRACTOR_VERSION
from workers.profile_router import chunk_label_set
from workers.summarizer import split_sentences
from workers.syntax import parse_sentence, parser_identity

STAGE = "extract"
EVENT_TYPE = "chunked.v1"

EXTRACTOR_VERSION = "gliner-2pass-v1"
ONTOLOGY_VERSION = "core-v1"
RULE_PACK_VERSION = "1.0.0"
# Q1-R: the rule-pack release the extract stage compiles against.
# Packed into the stage contract so a pack promotion re-runs extraction.
_ACTIVE_PACK_VERSION = "1.0.1"  # overwritten at runtime from settings


def active_pack_version() -> str:
    from polymath_shared.settings import get_settings

    return get_settings().worker.rule_pack_version

ENTITY_THRESHOLD = 0.5
EVIDENCE_THRESHOLD = 0.4

log = logging.getLogger("extract")

_rule_pack = None


def _gliner_pin() -> dict:
    """I3R-R7: the actual immutable GLiNER identity from the sidecar's
    /manifest (canonical production configuration source) — never a
    template placeholder."""
    try:
        from polymath_shared.clients import GlinerClient

        client = GlinerClient()
        try:
            m = client.manifest()
            model = (m.get("identity") or {}).get("model") or {}
            model_id = model.get("id") or "unknown"
            revision = model.get("revision") or "unknown"
            if str(model_id).startswith("__PIN_") or str(revision).startswith("__PIN_"):
                raise RuntimeError("GLiNER sidecar manifest is unpinned")
            return {"model_id": model_id, "revision": revision}
        finally:
            client.close()
    except Exception:
        # Fail LOUD at artifact time instead of recording placeholders:
        # a run whose extractor cannot resolve the pin records nothing.
        raise RuntimeError("could not resolve the GLiNER pin from the sidecar manifest")


_GLINER_PIN = _gliner_pin()


def _pack() -> dict:
    global _rule_pack
    if _rule_pack is None:
        _rule_pack = load_rule_pack(pack_version=active_pack_version())
    return _rule_pack


def _core_type(label: str, pack: dict) -> str | None:
    for core in pack["core_types"]:
        if label == core:
            return core
    return None


@dataclass
class _Sentences:
    texts: list[str]
    offsets: list[tuple[int, int]]


def _sentences_of(chunk_text: str) -> _Sentences:
    texts = split_sentences(chunk_text)
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for sentence in texts:
        start = chunk_text.find(sentence, cursor)
        end = start + len(sentence)
        offsets.append((start, end))
        cursor = end
    return _Sentences(texts=texts, offsets=offsets)


def _map_label(label: str, pack: dict) -> str | None:
    """Pass-1 raw label -> canonical core type, resolved through the
    semantic query policy (semantic-query-policy-v1). Domain labels map
    through the policy's module table; core labels pass through. The
    compiler and predicates never see provider aliases."""
    from polymath_shared.query_policy import canonical_of

    if _core_type(label, pack):
        return label
    return canonical_of(label)


def _entity_spans(
    gliner: GlinerClient,
    chunk_text: str,
    chunk_id: str,
    doc_id: str,
    profile: dict,
    envelope=None,
    trace=None,
    raw_sink: list | None = None,
    precomputed: dict | None = None,
) -> tuple[list[EntitySpan], list[dict]]:
    from polymath_shared.contracts import DocumentProfile
    from polymath_shared.query_policy import provider_passes

    base_labels = DocumentProfile(**profile).label_set if profile.get("label_set") else []
    spans: list[EntitySpan] = []
    rejected: list[dict] = []
    # EXTRACTION-CONTEXT-V1: when an envelope is supplied, GLiNER reads
    # the envelope text and predictions are mapped back to source
    # coordinates; only focal-owned predictions become EntitySpans.
    inference_text = envelope.envelope_text if envelope else chunk_text
    focal_offset = envelope.focal_envelope_start if envelope else 0
    proposals: dict[tuple[int, int], dict] = {}
    for pass_labels in provider_passes():
        labels = list(dict.fromkeys(list(base_labels) + list(pass_labels)))
        if not labels:
            continue
        if precomputed is not None:
            # PHASE B2: provider output supplied by the batched transport.
            # Everything below — raw capture, dedupe, envelope
            # classification, label mapping — is IDENTICAL to the per-call
            # path; only where the bytes traveled changed.
            if tuple(labels) not in precomputed:
                # A label-composition mismatch between the batch builder and
                # this function would otherwise yield silently EMPTY provider
                # results — a masked defect. Fail loudly instead.
                raise RuntimeError(
                    f"batched pass-1 has no result for label composition "
                    f"{labels!r}; batch builder and _entity_spans disagree")
            result = {"spans": precomputed[tuple(labels)]}
        else:
            result = gliner.entity_pass(inference_text, labels, threshold=ENTITY_THRESHOLD)
        if raw_sink is not None:
            # V5 L1: the provider's observations EXACTLY as returned —
            # before dedupe, before label mapping, before envelope
            # classification, before rescue. Paired with the composed label
            # list so the ledger records what was actually asked.
            for item in result.get("spans", []):
                raw_sink.append((dict(item), tuple(labels)))
        for item in result.get("spans", []):
            key = (item["start"], item["end"])
            current = proposals.get(key)
            if current is None or item["score"] > current["score"]:
                proposals[key] = item
    from polymath_shared.extraction_context import classify_prediction
    for item in proposals.values():
        if envelope is not None:
            classification, src_start, src_end = classify_prediction(
                envelope, item["start"], item["end"])
            if trace and trace.enabled:
                trace.record(
                    event_type="context", decision=classification,
                    reason_code=classification, doc_id=doc_id, chunk_id=chunk_id,
                    surface=item["text"][:80],
                    detail={"envelope_offsets": [item["start"], item["end"]],
                            "source_offsets": [src_start, src_end],
                            "raw_label": item["label"],
                            "score": round(item["score"], 4),
                            "policy": envelope.policy})
            if classification != "CONTEXT_PREDICTION_FOCAL":
                rejected.append({"span": item, "reason": classification})
                continue
            # remap to FOCAL-CHUNK-RELATIVE offsets (EntitySpan contract):
            # chunk_relative = source_offset - focal.char_start
            item = dict(item)
            item["start"] = src_start - envelope.focal_source_start
            item["end"] = src_end - envelope.focal_source_start
        core_type = _map_label(item["label"], _pack())
        if core_type is None:
            rejected.append({"span": item, "reason": "no core mapping for label"})
            continue
        spans.append(EntitySpan(
            doc_id=doc_id,
            chunk_id=chunk_id,
            start=item["start"],
            end=item["end"],
            text=item["text"],
            core_type=CoreType(core_type),
            score=item["score"],
            extractor_version=EXTRACTOR_VERSION,
            raw_label=item["label"],
            pass_kind="discovery",
        ))
    return spans, rejected


def _evidence_spans(
    gliner: GlinerClient,
    chunk_text: str,
    chunk_id: str,
    pack: dict,
    mode: str,
    raw_sink: list | None = None,
    scientific_lane_prioritized: bool = True,
) -> list[EvidenceSpan]:
    """ADR-0008: pass 2 = GLiNER coarse proposals (may abstain) +
    lexical trigger localization. The compiler decides either way.

    EXTRACTION-ELIGIBILITY-V1 (owner invariant): classification may
    PRIORITIZE; evidence determines ELIGIBILITY. The document-level
    router never vetoes this lane — when the router deprioritizes it
    (scientific_lane_prioritized=False), the cheap deterministic
    trigger localization still runs, and any chunk with LOCAL
    relational evidence proceeds through the identical discovery path.
    Chunks with no local evidence skip the expensive GLiNER evidence
    pass — that is the cost optimization the router is allowed to be.
    (The prior hard veto measured: PROCEDURAL 4→0, CONCEPTUAL 6→0,
    NARRATIVE 2→0 eligible relation spans — SMART verification P0.)"""
    from workers.evidence_proposer import (
        localize_trigger,
        merge_gliner_proposals,
        propose_evidence,
    )

    anchors = propose_evidence(chunk_text, chunk_id, pack)
    if not scientific_lane_prioritized and not anchors:
        # Deprioritized lane AND no local relational evidence: nothing
        # here qualifies for the compiler — skip the expensive pass.
        return []
    if mode == "hybrid":
        result = gliner.evidence_pass(chunk_text, threshold=EVIDENCE_THRESHOLD)
        if raw_sink is not None:
            for item in result.get("spans", []):
                raw_sink.append((dict(item), ()))
        proposals = merge_gliner_proposals(chunk_text, chunk_id, result.get("spans", []))
        # Localize each proposal to a compiled trigger; unlocalizable
        # proposals compile to UNSUPPORTED downstream.
        proposals = [localize_trigger(p, pack) for p in proposals]
        merged = {s.text: s for s in anchors}
        for p in proposals:
            key = p.text
            if key not in merged:
                merged[key] = p
        return sorted(merged.values(), key=lambda s: (s.start, s.end))
    return anchors


def _slices(
    sentences: _Sentences,
    entities: list[EntitySpan],
    evidence: list[EvidenceSpan],
    corpus_id: str = "eval",
) -> list[SentenceSlice]:
    slices: list[SentenceSlice] = []
    for sentence_idx, (text, (start, end)) in enumerate(zip(sentences.texts, sentences.offsets)):
        ent = [e for e in entities if e.start >= start and e.end <= end]
        ev = [v for v in evidence if v.start >= start and v.end <= end]
        if ent or ev:
            parse = parse_sentence(text)
            if parse is not None:
                parse["_sentence_offsets"] = [start, end]
                # S4b: NO allocation here. `_slices` runs BEFORE syntax
                # exists, so it cannot be an admission authority under a
                # syntax-dependent contract. Parse entity ids are attached
                # at the post-syntax boundary from the single identities
                # map (see _allocate_identities).
            slices.append(SentenceSlice(
                text=text, sentence_start=start, sentence_end=end,
                entities=ent, evidence=ev, parse=parse,
            ))
    return slices


def _allocate_parse_entity(span, corpus_id: str, parse: dict,
                           identities: dict | None = None) -> str | None:
    """S4b — CONSUMER, not an authority.

    Parse-record entity ids must be IDENTICAL to candidate ids because the
    compiler compares them in `_oriented_pair`. This function previously
    RE-DERIVED admission for the same span, which is a second semantic
    authority over one mention: two independent admissions of one span can
    disagree, and under admission-harbor-v2 it would also need syntax the
    parse record does not carry.

    THE INVARIANT: admission is computed ONCE per mention interpretation.
    Every downstream representation carries the resulting identity; none
    recomputes it.

    `identities` maps a span key to the id already allocated at the
    admission boundary. A miss returns None — the parse record simply
    carries no entity_id — rather than inventing one.
    """
    if not identities:
        return None
    identity = identities.get(_span_identity_key(span, corpus_id))
    return identity.entity_id if identity is not None else None


def _persist_slice_manifest(conn: Connection, doc_id: str,
                            ordered_slices: list[tuple[dict, SentenceSlice]]) -> None:
    """SENTENCE-SLICE-MANIFEST-V1 — the interpreter's view, made durable.

    `slice_index` is the position in DOCUMENT order, which is the order the
    discourse consumer accumulated context in; reproducing the set without
    the order would still change resolution.
    """
    conn.execute("DELETE FROM sentence_slices WHERE doc_id = %s", (doc_id,))
    with conn.cursor() as _cur:                       # PHASE B6: bulk write
        _cur.executemany(
            """
            INSERT INTO sentence_slices (doc_id, chunk_id, slice_index,
                                         chunk_start, chunk_end, in_context)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (doc_id, chunk_id, slice_index) DO UPDATE
                SET chunk_start = EXCLUDED.chunk_start,
                    chunk_end = EXCLUDED.chunk_end,
                    in_context = EXCLUDED.in_context
            """,
            [(doc_id, row["chunk_id"], idx, sl.sentence_start, sl.sentence_end)
             for idx, (row, sl) in enumerate(ordered_slices)])


def _allocate_identities(ordered_slices, corpus_id: str, doc_id: str, *,
                         contract_version: str) -> dict:
    """S4b/S4c — THE single admission authority for a document.

    `contract_version` is REQUIRED and never inferred. Production pins
    admission-harbor-v2; an explicitly pinned historical replay is the only
    other legitimate value. There is no default, because a default is how a
    fallback gets in.

    Runs at the post-syntax boundary (S4a) and interprets each proposed span
    EXACTLY ONCE under the pinned semantic contract. Every downstream
    representation — parse records, relation candidates, persisted mentions,
    fact endpoints — reads its identity from this map rather than re-deriving
    admission. Two independent admissions of one span can disagree; that is a
    second semantic authority, which wiring invariant 1 forbids.

    Discourse state accumulates in document order, so a reference is resolved
    against what the document has actually established BEFORE it, never after.
    """
    from polymath_shared.admission_interpreter import interpret_admission
    from polymath_shared.execution import SEMANTIC_CONTRACT_V2
    from dataclasses import replace

    from polymath_shared.identity_allocation import (
        allocate_identity, normalized_for_lookup, span_identity_key,
    )
    from polymath_shared.layout_evidence import in_heading

    reads_coordinates = contract_version == SEMANTIC_CONTRACT_V2

    # CONCEPT-EVIDENCE-V1 reads definitional patterns from the whole
    # document, not the sentence: "X is defined as ..." may be chunks away.
    chunk_text: dict[str, str] = {}
    for row, _sl in ordered_slices:
        chunk_text.setdefault(row["chunk_id"], row.get("text") or "")
    document_text = "\n".join(chunk_text.values())
    # LAYOUT-EVIDENCE-V1 (row 53): heading status is READ from persisted
    # layout evidence, never re-derived here. Chunk text is assembled with
    # `" ".join(sentences)` and has no line structure left, so detecting
    # headings from it marked whole chunks as headings and withdrew identity
    # from every span inside them.
    #
    # NULL layout_map means the chunk predates layout evidence. The rule then
    # ABSTAINS — absent evidence is not evidence of absence, and asserting
    # "no headings" would silently re-enable the typography defect.
    chunk_headings: dict[str, list[tuple[int, int]]] = {}
    for row, _sl in ordered_slices:
        cid = row["chunk_id"]
        if cid in chunk_headings:
            continue
        raw = row.get("layout_map")
        chunk_headings[cid] = [tuple(r) for r in raw] if raw else []

    out: dict = {}
    context: list[str] = []
    context_syntax: list[dict | None] = []
    anchors: list[tuple[str, str]] = []
    # ANTECEDENT-IDENTITY-INHERITANCE-V1: the identity each admitted anchor
    # holds, so a reference that resolves to one can inherit it rather than
    # mint a second id from its own descriptive surface.
    anchor_identity: dict[str, str] = {}

    for _row, sl in ordered_slices:
        for span in sl.entities:
            key = span_identity_key(span, corpus_id)
            if key in out:
                continue
            # `sl.syntax` is annotated over `sl.text`, so its token offsets
            # are SENTENCE-relative while span offsets are chunk-absolute.
            # A silent frame mismatch would select the wrong tokens and thus
            # decide identity from the wrong evidence — fail loudly instead.
            #
            # This is a precondition of V2 SPECIFICALLY: it is the contract
            # that reads span coordinates to select tokens. The historical
            # interpreter reads only the surface, so enforcing coordinate
            # agreement during a pinned replay would reject fixtures on a
            # dimension that contract never consulted.
            rel_start = span.start - sl.sentence_start
            rel_end = span.end - sl.sentence_start
            if reads_coordinates and sl.text[rel_start:rel_end] != span.text:
                raise RuntimeError(
                    "span/sentence coordinate frame mismatch at "
                    f"{span.chunk_id}[{span.start}:{span.end}]: "
                    f"sentence yields {sl.text[rel_start:rel_end]!r}, "
                    f"span carries {span.text!r}")
            result = interpret_admission(
                contract_version=contract_version,
                proposal_surface=span.text,
                core_type=span.core_type.value,
                span=(rel_start, rel_end),
                sentence_text=sl.text,
                syntax=sl.syntax,
                document_text=document_text,
                discourse_context=list(context),
                discourse_syntax=list(context_syntax),
                admitted_anchors=list(anchors),
                # carried for an explicitly pinned historical replay; the
                # V2 interpreter ignores both.
                extraction_score=span.score,
                sentence_initial=rel_start <= len(
                    sl.text[: len(sl.text) - len(sl.text.lstrip())]),
                heading_context=in_heading(
                    chunk_headings.get(span.chunk_id, []),
                    span.start, span.end),
            )
            inherited = None
            if result.reference_basis == "ANTECEDENT_RESOLVED":
                inherited = anchor_identity.get(
                    normalized_for_lookup(result.resolves_to or ""))
                if inherited is None:
                    # The antecedent carries no durable identity — a generic
                    # population, or a noun phrase never admitted in its own
                    # right. Keep the record truthful: eligibility is
                    # inherited too, so it is False here.
                    result = replace(
                        result, graph_eligible=False,
                        admission_reason=(
                            f"{result.admission_reason}; antecedent carries no "
                            "durable identity to inherit"))
            identity = allocate_identity(
                result, corpus_id=corpus_id, doc_id=span.doc_id or doc_id,
                chunk_id=span.chunk_id, span_start=span.start,
                span_end=span.end, inherit_entity_id=inherited)
            out[key] = identity
            # Only a durable IDENTITY anchor can serve as an antecedent.
            # A resolved LOCAL_REFERENCE must not become one, or reference
            # chains would manufacture identity by recurrence.
            if identity.durable and result.anchor_kind == "IDENTITY":
                # KNOWN LIMITATION (ledger row 70): this passes an entity id
                # where discourse-reference-v1 expects a CORE TYPE, so E4b
                # never fires in production though it passes in tests. Fixed
                # on candidate/rescue-discourse-v1-failed; not promoted,
                # because correcting it revived E4b and it then resolved
                # `vision system` -> `Siemens PLCs`.
                anchors.append((result.referential_surface, identity.entity_id))
            if identity.durable:
                # Any durable admission can be the antecedent a later
                # reference inherits from — concepts included.
                anchor_identity.setdefault(
                    normalized_for_lookup(result.proposal_surface),
                    identity.entity_id)
                anchor_identity.setdefault(
                    normalized_for_lookup(result.referential_surface),
                    identity.entity_id)
        context.append(sl.text)
        context_syntax.append(sl.syntax)
    return out


def _span_identity_key(span, corpus_id: str) -> tuple:
    """Re-export of the shared key so extract_worker and candidates cannot
    drift apart on what counts as "the same span"."""
    from polymath_shared.identity_allocation import span_identity_key

    return span_identity_key(span, corpus_id)


def _fill_parse_entities(parse: dict, entities: list[EntitySpan],
                         corpus_id: str = "eval",
                         identities: dict | None = None) -> None:
    """Q1-R v1.1.0: link the syntactic record's subject/agent/object to
    pass-1 entity ids by deterministic surface match, so the compiler's
    voice normalization (_oriented_pair) can orient passive facts by
    semantic role. Without this link the passive path was dead in
    production (the frozen harness was the only supplier of entity_id)."""
    for slot in ("subject", "agent", "object"):
        record = parse.get(slot)
        if not record:
            continue
        token_text = (record.get("token_text") or "").strip()
        head_text = (record.get("head_text") or "").strip()
        if not token_text:
            continue
        match = None
        for span in entities:
            span_text = span.text.strip()
            if span_text == token_text or span_text == head_text:
                match = span
                break
        if match is None:
            for span in entities:
                if token_text.lower() in span.text.lower():
                    match = span
                    break
        if match is not None:
            allocated = _allocate_parse_entity(match, corpus_id, parse,
                                               identities)
            if allocated is not None:
                record["entity_id"] = allocated


# ADR-0016 Phase 5: which pipeline step owns each outcome. A code missing
# here degrades to argument_binding, preserving pre-Phase-5 behaviour.
_STAGE_BY_CODE = {
    "SUBJECT_ENDPOINT_UNAVAILABLE": "argument_binding",
    "OBJECT_ENDPOINT_UNAVAILABLE": "argument_binding",
    "SUBJECT_MENTION_ONLY": "admission",
    "ARGUMENT_BINDING_AMBIGUOUS": "argument_binding",
    "COORDINATION_AMBIGUOUS": "argument_binding",
    "OBJECT_TYPE_INCOMPATIBLE": "candidate_generation",
    "CANDIDATE_CREATED": "candidate_generation",
    "UD_SUBJECT_BOUND": "ud_binding",
    "UD_OBJECT_BOUND": "ud_binding",
    "UD_OBLIQUE_BOUND": "ud_binding",
    "UD_NO_ARGUMENT_IN_SLOT": "ud_binding",
    "ROLE_ARG0_ASSIGNED": "role_assignment",
    "ROLE_ARG1_ASSIGNED": "role_assignment",
    "ROLE_ARG2_ASSIGNED": "role_assignment",
    "ROLE_ASSIGNED": "role_assignment",
    "ROLE_NO_ROLESET": "role_assignment",
    "ROLE_ORIENTATION_INCOMPLETE": "role_assignment",
    "TYPE_PRECHECK_PASS": "type_precheck",
    "TYPE_PRECHECK_FAIL": "type_precheck",
    "TYPE_PRECHECK_IMPOSSIBLE": "type_precheck",
    "TYPE_PRECHECK_NO_VIABLE_PAIR": "type_precheck",
}
# Progress events carry their own event_type so summary mode (terminal
# decisions only) drops them and the first-loss funnel never sees them.
_EVENT_TYPE_BY_STAGE = {
    "ud_binding": "binding",
    "role_assignment": "role",
    "type_precheck": "type_precheck",
}


class _SliceObserver:
    """Adapts build_candidates' outcome callbacks into trace events."""

    def __init__(self, collector, row, sl, sentence_id):
        self._c = collector
        self._row = row
        self._sl = sl
        self._sid = sentence_id
        self.created = 0
        self.losses: list[str] = []

    def record_candidate_outcome(self, sl, evidence, code, detail=None):
        if not self._c.enabled:
            return
        from polymath_shared.observability import (
            STEP_CODES, binding_discipline,
        )
        detail = detail or {}
        stage = _STAGE_BY_CODE.get(code, "argument_binding")
        step = code in STEP_CODES
        if code == "CANDIDATE_CREATED":
            event_type = "candidate"
        elif step:
            event_type = _EVENT_TYPE_BY_STAGE.get(stage, "binding")
        else:
            event_type = "first_loss"
        # Directive Phase 17: every event that names a binding mechanism
        # also names its discipline tier, so the trace reads in either
        # vocabulary without renaming BindingSource.
        if "binding_source" in detail and "binding_discipline" not in detail:
            detail = {**detail,
                      "binding_discipline": binding_discipline(detail["binding_source"])}
        self._c.record(
            event_type=event_type,
            decision=code, reason_code=code,
            doc_id=self._row["doc_id"], chunk_id=self._row["chunk_id"],
            sentence_id=self._sid,
            surface=str(detail.get("subject") or detail.get("object") or evidence.text or "")[:80],
            char_start=evidence.start, char_end=evidence.end,
            detail={"first_loss_stage": stage,
                    "trigger": evidence.text, "trigger_predicate_id": getattr(evidence, "trigger_predicate_id", None),
                    "evidence_class": evidence.evidence_class, **detail},
        )
        if code == "CANDIDATE_CREATED":
            self.created += 1
        elif not step:
            self.losses.append(code)


def _acceptance_block(admitted_facts, durable_surfaces) -> dict:
    """ACCEPTANCE-HARNESS-V1 against optional frozen human labels
    (POLYMATH_ACCEPTANCE_LABELS=<path>.json). Absent labels leave the
    gate shape with AWAITING_HUMAN_LABELS."""
    import json as _j

    from polymath_shared.acceptance_harness import score_acceptance

    path = os.environ.get("POLYMATH_ACCEPTANCE_LABELS")
    if not path or not Path(path).exists():
        return {"contract": "acceptance-harness-v1",
                "status": "AWAITING_HUMAN_LABELS"}
    labels = _j.loads(Path(path).read_text())
    scored = score_acceptance(
        labels, admitted_entities=durable_surfaces,
        admitted_facts=admitted_facts, admitted_events=[])
    scored["status"] = "SCORED"
    scored["labels_path"] = path
    return scored


def _syntax_evidence(
    ordered_slices: list[tuple[dict, SentenceSlice]],
) -> dict | None:
    """SYNTAX-BOOTSTRAP: optional spaCy syntax annotation of the SAME
    sentence slices GLiNER just proposed over — attached per slice for a
    future reconciliation layer; nothing downstream consumes it in this
    gate.

    provider=disabled (production default): returns None before any
    client is constructed — the extraction path is byte-identical.
    provider=spacy: one batched syntax-evidence-v1 call for the whole
    document; an unavailable sidecar raises and fails the stage LOUDLY
    (no silent fallback, no different syntax logic)."""
    from polymath_shared.settings import get_settings

    provider = get_settings().sidecars.syntax_provider
    if provider not in ("disabled", "spacy"):
        raise ValueError(f"unknown syntax provider: {provider}")
    if provider == "disabled" or not ordered_slices:
        return None

    from polymath_shared.clients import SpacySyntaxClient

    sentences = [
        {"sentence_id": f"{row['chunk_id']}:{idx}", "text": sl.text}
        for idx, (row, sl) in enumerate(ordered_slices)
    ]
    # The sidecar accepts at most 512 sentences per request; a book-sized
    # document exceeds that in one batched call (observed: 1242 sentences ->
    # 422). Batch client-side, preserving order, verifying identity/order
    # PER BATCH exactly as before — same sentences, same pinned model, same
    # per-sentence results, so this is transport, not semantics.
    SYNTAX_BATCH = 512
    client = SpacySyntaxClient()
    results: list[dict] = []
    try:
        client.verify_pin()
        for i in range(0, len(sentences), SYNTAX_BATCH):
            batch = sentences[i:i + SYNTAX_BATCH]
            response = client.syntax(batch)
            expected_ids = [s["sentence_id"] for s in batch]
            returned_ids = [r["sentence_id"] for r in response["results"]]
            if returned_ids != expected_ids:
                raise RuntimeError(
                    "syntax sidecar returned mismatched sentence identity/order"
                )
            results.extend(response["results"])
    finally:
        client.close()

    by_id = {r["sentence_id"]: r for r in results}
    for idx, (row, sl) in enumerate(ordered_slices):
        # SentenceSlice is frozen; attach through the dataclass escape
        # hatch. The field is read by nothing on the candidate path.
        object.__setattr__(sl, "syntax", by_id[f"{row['chunk_id']}:{idx}"])
    return {
        "contract": response["contract"],
        "provider": "spacy",
        "model_release": response.get("model_release"),
        "runtime": response.get("runtime"),
        "sentences": len(sentences),
        "batches": (len(sentences) + SYNTAX_BATCH - 1) // SYNTAX_BATCH,
    }


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    doc_id = payload["doc_id"]
    profile_dict = payload.get("profile", {})
    from polymath_shared.settings import get_settings

    proposal_mode = get_settings().worker.evidence_proposal_mode
    if proposal_mode not in ("lexical", "hybrid"):
        raise ValueError(f"unknown evidence proposal mode: {proposal_mode}")

    from polymath_shared.observability import (
        TraceCollector, extraction_contracts, trace_mode,
    )

    trace = TraceCollector(trace_mode(), run_id, extraction_contracts())

    rescue_stages = get_settings().rescue_policy.enabled_stages()
    if rescue_stages and get_settings().sidecars.syntax_provider != "spacy":
        raise RuntimeError(
            "POLYMATH_RESCUE enabled but POLYMATH_SYNTAX_PROVIDER != spacy — "
            "rescue requires syntax evidence; refusing to extract without it"
        )

    pack = _pack()
    parser_name, parser_version = parser_identity()

    # KNOWLEDGE-ROUTER v1.1 as a PRIORITY signal (owner correction,
    # EXTRACTION-ELIGIBILITY-V1): a routed 'disabled' scientific lane
    # DEPRIORITIZES relation discovery (chunks without local trigger
    # evidence skip the expensive GLiNER evidence pass) but never
    # vetoes it — local content evidence always reaches the compiler.
    # Entity pass-1/proposals are unaffected (admission still runs).
    scientific_lane_prioritized = True
    if os.environ.get("POLYMATH_PREDICATE_V2") == "enforce":
        from polymath_shared.knowledge_router.classifier import (
            classify_document)
        _doc_text = "\n".join(
            c[0] for c in (conn.cursor().execute(
                "SELECT text FROM chunks WHERE doc_id=%s "
                "ORDER BY chunk_index", (doc_id,)).fetchall()))
        _prof = classify_document(_doc_text)
        scientific_lane_prioritized = "scientific_predicate" not in \
            _prof["routing"]["disabled"]
    manifest = ExtractionManifest(
        run_id=run_id,
        gliner_model=_GLINER_PIN["model_id"],
        gliner_revision=_GLINER_PIN["revision"],
        parser=parser_name,
        parser_version=parser_version,
        ontology_version=ONTOLOGY_VERSION,
        rule_pack_version=active_pack_version(),
        thresholds={"entity": ENTITY_THRESHOLD, "evidence": EVIDENCE_THRESHOLD},
        query_policy=QUERY_POLICY_VERSION,
    )

    contract_payload = {
        "extractor_version": EXTRACTOR_VERSION,
        "evidence_proposer": EVIDENCE_EXTRACTOR_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "rule_pack_version": RULE_PACK_VERSION,
        "active_pack_version": active_pack_version(),
        "parser_version": parser_version,
        "admission_policy": "entity-admission-v1.1",
        "identity_contract": "entity-identity-v2",
        "thresholds": {"entity": ENTITY_THRESHOLD, "evidence": EVIDENCE_THRESHOLD},
        "evidence_proposal_mode": proposal_mode,
        "binding_gates": "endpoint-binding-v1",
        "provenance_contract": "exact-evidence-v1",
        "gliner_pin": _GLINER_PIN,
        # Temporal durability (semantic-query-policy-v1): the extraction
        # contract identity includes EVERY input that can change semantic
        # output — provider-facing vocabulary policy, syntax contract,
        # rescue policy — including their disabled state, so any
        # interpretation is reproducibly attributable years later.
        "query_policy": policy_identity(),
        "syntax_contract": {
            "provider": get_settings().sidecars.syntax_provider,
            "contract": "syntax-evidence-v1",
        },
        "rescue_policy": {
            "contract": "rescue-v1",
            "stages": list(rescue_stages),
        },
    }
    contract = stage_contract_hash(STAGE, contract_payload)

    corpus_row = conn.execute(
        "SELECT r.corpus_id FROM runs r WHERE r.run_id = %s", (run_id,)
    ).fetchone()
    corpus_id = corpus_row[0] if corpus_row else "unknown"

    with stage_transaction(
        conn, run_id=run_id, stage=STAGE, contract_hash=contract
    ) as writer:
        writer.artifact({"manifest": manifest.model_dump()})

        # Postgres is the authority: consume the chunks the intake stage
        # committed (materialized for native formats, I0/ADR 0010),
        # never re-derive text from event bytes.
        chunk_rows = conn.execute(
            """
            SELECT chunk_id, doc_id, parent_id, tier, text, summary,
                   char_start, char_end, layout_map
              FROM chunks
             WHERE doc_id = %s
             ORDER BY chunk_index
            """,
            (doc_id,),
        ).fetchall()
        chunks = [
            {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2], "tier": r[3],
             "text": r[4], "summary": r[5], "char_start": r[6], "char_end": r[7],
             "layout_map": r[8]}
            for r in chunk_rows
        ]
        child_chunks = [row for row in chunks if row["tier"] == "child"]

        gliner = GlinerClient()
        gliner.verify_pin()
        audit: list[dict] = []

        # I3R-R3: two-pass extraction — pass A gathers the full document
        # entity stream (the bounded local-reference resolver needs
        # earlier-sentence history), pass B builds candidates with that
        # history. Extraction candidates remain derived from the current
        # document proposal stream only.
        try:
            ordered_slices: list[tuple[dict, SentenceSlice]] = []
            # PHASE B1: wall-clock attribution. Pure observability — a perf
            # dict in the stage artifact; no semantic effect.
            import time as _t
            _perf = {"entity_pass_s": 0.0, "evidence_pass_s": 0.0,
                     "slices_s": 0.0, "syntax_s": 0.0, "rescue_s": 0.0,
                     "admission_s": 0.0, "persist_mentions_s": 0.0,
                     "candidates_compile_s": 0.0, "l1_l4_writes_s": 0.0,
                     "fact_admission_s": 0.0,
                     "provider_calls": 0, "stage_t0": _t.perf_counter()}
            # EXTRACTION-AUDIT-V1: per-stage counts for the durable audit
            # report (timings come from _perf, monotonic perf_counter).
            _counts = {"gliner_entity_proposals": 0, "gliner_entity_rejected": 0,
                       "evidence_spans": 0, "mentions_persisted": 0}
            _decision_counts: dict = {}
            _event_facts = 0
            _event_candidates: list = []
            _admitted_facts: list = []
            _durable_surfaces: list = []
            # V5 L1 (raw-evidence-ledger-v1): provider observations captured
            # per chunk, bulk-written once per document inside this stage
            # transaction — so raw evidence commits with the stage receipt
            # and rolls back with the stage. (chunk_id, item, labels) tuples.
            raw_entity_sink: list = []
            raw_predicate_sink: list = []
            _raw_rows_entity: list = []
            _raw_rows_predicate: list = []
            from polymath_shared import raw_evidence as _raw

            _gl_model = (gliner.manifest().get("identity", {}) or {}).get("model", {})
            _contract_cache: dict = {}

            def _raw_contract(labels, task):
                key = (tuple(labels), task)
                if key not in _contract_cache:
                    _contract_cache[key] = _raw.provider_contract(
                        provider="gliner",
                        model_id=str(_gl_model.get("id")),
                        revision=str(_gl_model.get("revision")),
                        task=task,
                        threshold=ENTITY_THRESHOLD if task == "entity" else EVIDENCE_THRESHOLD,
                        labels=list(labels))
                return _contract_cache[key]
            # EXTRACTION-CONTEXT-V1: build the envelope per focal chunk
            from polymath_shared.extraction_context import active_policy, build_envelope
            context_active = active_policy() != "C0_FOCAL_ONLY"
            doc_text_cache: dict[str, str] = {}
            child_siblings = sorted(child_chunks, key=lambda r: r["char_start"])
            # PHASE B2: one batched provider call set per label composition
            # for the WHOLE document (chunk-level batching; C0 policy = no
            # envelopes on the batched path). Per-chunk calls remain the
            # automatic path whenever envelopes are active.
            _batched_pass1: dict = {}
            if not context_active:
                from polymath_shared.query_policy import provider_passes as _pp
                from polymath_shared.contracts import DocumentProfile as _DP
                _base = _DP(**profile_dict).label_set if profile_dict.get("label_set") else []
                _texts = [r["text"] for r in child_chunks]
                _gbatch = int(os.environ.get("POLYMATH_GLINER_BATCH", "32"))
                _t_batch = _t.perf_counter()
                for _pl in _pp():
                    _labels = list(dict.fromkeys(list(_base) + list(_pl)))
                    if not _labels or not _texts:
                        continue
                    _rows = gliner.entity_pass_batch(
                        _texts, _labels, threshold=ENTITY_THRESHOLD, batch=_gbatch)
                    for _r_, _row_ in zip(child_chunks, _rows):
                        _batched_pass1.setdefault(_r_["chunk_id"], {})[tuple(_labels)] = _row_
                _perf["entity_pass_s"] += _t.perf_counter() - _t_batch
                _perf["provider_calls"] += (len(_texts) + _gbatch - 1) // _gbatch
            for row in child_chunks:
                envelope = None
                if context_active:
                    doc_key = row["doc_id"]
                    if doc_key not in doc_text_cache:
                        doc_row = conn.execute(
                            "SELECT text FROM documents WHERE doc_id=%s", (doc_key,)
                        ).fetchone()
                        # documents table may not have text; reconstruct from chunks
                        if doc_row and doc_row[0]:
                            doc_text_cache[doc_key] = doc_row[0]
                        else:
                            doc_text_cache[doc_key] = "\n".join(
                                r["text"] for r in sorted(child_chunks, key=lambda x: x["char_start"]))
                    envelope = build_envelope(row, child_siblings,
                                              doc_text_cache[doc_key])
                _pt = _t.perf_counter()
                entities, rejected = _entity_spans(
                    gliner, row["text"], row["chunk_id"], doc_id, profile_dict,
                    envelope=envelope, trace=trace, raw_sink=raw_entity_sink,
                    precomputed=_batched_pass1.get(row["chunk_id"])
                )
                _counts["gliner_entity_proposals"] += len(entities)
                if rejected:
                    _counts["gliner_entity_rejected"] += len(rejected)
                if not _batched_pass1:
                    _perf["entity_pass_s"] += _t.perf_counter() - _pt
                    _perf["provider_calls"] += 1
                audit.extend(rejected)
                # S4a EXTRACT-STAGE ORDERING: mention persistence is DEFERRED
                # until syntax exists. A mention carries a semantic admission
                # decision, and admission-harbor-v2 cannot decide without
                # syntax-evidence-v1 — persisting here would have committed a
                # decision the contract forbids making.
                if trace.enabled:
                    trace.record(
                        event_type="discovery", decision="GLINER_PROPOSED",
                        reason_code="GLINER_PROPOSED", doc_id=doc_id,
                        chunk_id=row["chunk_id"],
                        detail={"proposals": len(entities), "rejected_labels": len(rejected)})
                    for ent in entities:
                        trace.record(
                            event_type="admission",
                            decision="ADMITTED_MENTION_ONLY",  # corrected below by class
                            reason_code="ADMITTED_MENTION_ONLY", doc_id=doc_id,
                            chunk_id=row["chunk_id"], surface=ent.text,
                            char_start=ent.start, char_end=ent.end,
                            detail={"core_type": ent.core_type.value, "raw_label": ent.raw_label,
                                    "score": ent.score, "pass_kind": ent.pass_kind})
                _pt = _t.perf_counter()
                evidence = _evidence_spans(
                    gliner, row["text"], row["chunk_id"], pack, proposal_mode,
                    raw_sink=raw_predicate_sink,
                    scientific_lane_prioritized=scientific_lane_prioritized)
                _counts["evidence_spans"] += len(evidence)
                _perf["evidence_pass_s"] += _t.perf_counter() - _pt
                # drain this chunk's raw observations into ledger rows
                _raw_rows_entity.extend(
                    _raw.proposal_row(doc_id, row["chunk_id"], item,
                                      _raw_contract(labels, "entity"))
                    for item, labels in raw_entity_sink)
                raw_entity_sink.clear()
                _raw_rows_predicate.extend(
                    _raw.evidence_row(doc_id, row["chunk_id"], item,
                                      _raw_contract(labels, "evidence"))
                    for item, labels in raw_predicate_sink)
                raw_predicate_sink.clear()
                _pt = _t.perf_counter()
                sentences = _sentences_of(row["text"])
                slices = _slices(sentences, entities, evidence, corpus_id)
                _perf["slices_s"] += _t.perf_counter() - _pt
                for sl in slices:
                    ordered_slices.append((row, sl))

            doc_entity_history: list[EntitySpan] = []
            _l4_rows: list = []
            # SYNTAX-BOOTSTRAP: after the GLiNER passes and before
            # build_candidates — annotate the same slices (one batched
            # call) when the provider is enabled; disabled records and
            # changes nothing.
            _raw.bulk_write(conn, "raw_entity_proposals", _raw_rows_entity)
            _raw.bulk_write(conn, "raw_predicate_evidence", _raw_rows_predicate)
            _pt = _t.perf_counter()
            syntax_runtime = _syntax_evidence(ordered_slices)
            _perf["syntax_s"] = _t.perf_counter() - _pt
            if syntax_runtime is not None:
                writer.artifact({"syntax": syntax_runtime})
            # S4a: the semantic dependency boundary. Every slice now carries
            # its syntax, so a mention may be persisted WITH an admission
            # decision. Batching is unchanged — `ordered_slices` already
            # accumulated the whole document before this point, so deferring
            # mention writes to the same boundary alters no memory profile.
            # S4b: allocate ONCE, then hand the same identities to every
            # downstream representation.
            # I4R rescue lane (flag-gated; default off = no-op): syntax
            # says where semantic certainty is missing; GLiNER is
            # re-queried about that exact phrase; deterministic code
            # applies exact-full-span-only acceptance.
            if rescue_stages:
                from workers.rescue import apply_rescue

                # Normal policy vocabulary for missing-argument queries
                # (temporal-durability §10): the pass-1 label set, never
                # slot-forced types.
                from polymath_shared.contracts import DocumentProfile

                rescue_label_set = tuple(
                    DocumentProfile(**profile_dict).label_set
                ) if profile_dict.get("label_set") else ()
                _pt = _t.perf_counter()
                rescue_report = apply_rescue(
                    ordered_slices, rescue_stages, rescue_label_set, _pack())
                _perf["rescue_s"] = _t.perf_counter() - _pt
                writer.artifact({"rescue": rescue_report})
                # V5 L2: persist every rescue decision as a span hypothesis,
                # idempotently, inside this stage transaction.
                _hyp_rows = [
                    _raw.hypothesis_row(doc_id, h)
                    for lane in rescue_report.values() if isinstance(lane, dict)
                    for h in lane.get("hypotheses", [])
                ]
                _raw.bulk_write(conn, "span_hypotheses", _hyp_rows)

            # SENTENCE-SLICE-MANIFEST-V1 (row 54): record WHICH slices the
            # interpreter saw, in what order, under which contract — before
            # interpreting. Slice membership depends on GLiNER evidence-trigger
            # placement, which is not otherwise recoverable, so reprocessing
            # had to guess at it: a narrower guess loses antecedents, a wider
            # one invents them. Persisting the view is what makes
            # re-derivation reproduce interpretation instead of approximating
            # it.
            _persist_slice_manifest(conn, doc_id, ordered_slices)
            # V5 P4: EVIDENCE-COMPLETE. Raw capture, syntax, slice manifest
            # and rescue hypotheses are all durable — seal the document's
            # evidence bundle manifest before anything settles.
            _bundle = _raw.write_bundle(conn, doc_id)
            # S4c: THE admission boundary. It sits after syntax (S4a) AND
            # after rescue, because rescue is proposal generation too — a
            # rescued span is a candidate endpoint and must be interpreted
            # by the same authority, exactly once, not left unadmitted.
            from polymath_shared.execution import SEMANTIC_CONTRACT_V2

            _pt = _t.perf_counter()
            identities = _allocate_identities(
                ordered_slices, corpus_id, doc_id,
                contract_version=SEMANTIC_CONTRACT_V2)
            _perf["admission_s"] = _t.perf_counter() - _pt

            # ENTITY-KNOWLEDGE-ADMISSION-V1 (E1-E7). Runs AFTER identity
            # allocation, because the gates judge a SETTLED class and a
            # decided admission -- never a raw provider label -- and BEFORE
            # `_fill_parse_entities` and `_persist_mentions`, so a refused
            # entity never reaches argument binding or the graph.
            #
            # A refusal demotes to MENTION_ONLY; it never drops the span.
            # `_persist_mentions` still writes the mention row, so the
            # surface stays readable and attributable at its offsets. Only
            # the durable identity is withheld.
            _pt = _t.perf_counter()
            from workers.entity_admission_stage import apply_entity_admission

            _entity_admission = apply_entity_admission(
                conn, corpus_id, doc_id, ordered_slices, identities,
                mention_id_for=lambda s: "mention_" + _mention_suffix(s, doc_id))
            _perf["entity_admission_s"] = _t.perf_counter() - _pt
            _counts["entity_admission_considered"] = int(
                _entity_admission.get("considered", 0))
            _counts["entity_admission_refused"] = int(
                _entity_admission.get("rejected", 0))

            # FACT-ADMISSION-V1 (F1-F8): the last court before a claim
            # becomes asserted knowledge. Carries the ENTITY verdicts so
            # F3 can refuse an endpoint that was never admissible and
            # attribute the refusal to the entity layer -- "You acquired
            # Hooked" is refused for `You`, not for `acquired`.
            from workers.fact_admission_stage import FactAdmissionStage

            _fact_stage = FactAdmissionStage(
                corpus_id, doc_id,
                entity_verdicts=_entity_admission.get("verdicts"))

            for _row, _sl in ordered_slices:
                if _sl.parse is not None:
                    _fill_parse_entities(_sl.parse, _sl.entities, corpus_id,
                                         identities)
            # S4c: persist the FINAL proposal set — the slices as they stand
            # after rescue — not the pre-rescue snapshot. Rescue rebuilds
            # `sl.entities` (boundary correction, type reconciliation), so the
            # earlier snapshot holds spans the pipeline has since superseded.
            # Persisting those would store a mention row for a span no
            # candidate, parse record or fact endpoint refers to, and it could
            # only be admitted by interpreting it a SECOND time — the very
            # divergence this cutover removes.
            _pt = _t.perf_counter()
            _mention_spans = [span for _row, _sl in ordered_slices
                              for span in _sl.entities]
            _counts["mentions_persisted"] = len(_mention_spans)
            _durable_surfaces = sorted({s.text for s in _mention_spans})
            _persist_mentions(
                conn, corpus_id, doc_id,
                _mention_spans,
                ordered_slices=ordered_slices, identities=identities)
            _perf["persist_mentions_s"] = _t.perf_counter() - _pt
            _pt = _t.perf_counter()
            for slice_idx, (row, sl) in enumerate(ordered_slices):
                slice_observer = _SliceObserver(
                    trace, row, sl, f"{row['chunk_id']}:{slice_idx}")
                candidates = build_candidates(
                    [sl],
                    doc_id=doc_id,
                    corpus_id=corpus_id,
                    ontology_profile=profile_dict.get("profile_id", "core"),
                    extractor_version=EXTRACTOR_VERSION,
                    rule_pack=pack,
                    doc_entities_history=doc_entity_history,
                    observer=slice_observer,
                    identities=identities,
                )
                doc_entity_history.extend(
                    sorted(sl.entities, key=lambda e: (e.start, e.end)))
                for candidate in candidates:
                    if active_pipeline() in ("kimi_v1", "kimi_v2"):
                        decision = compile_relation_kimi(candidate, sl.parse, pack, syntax=sl.syntax)
                    else:
                        decision = compile_relation(candidate, sl.parse, pack, syntax=sl.syntax)
                    # V5 L4 (I7): every candidate's disposition is durable —
                    # refused relation evidence survives outside the trace.
                    _l4_rows.append(_raw.relation_candidate_row(
                        doc_id, row["chunk_id"], candidate, decision))
                    _decision_counts[decision.decision] = (
                        _decision_counts.get(decision.decision, 0) + 1)
                    if decision.fact is not None and (
                            decision.fact.qualifiers.get("temporal_surface")
                            or decision.fact.predicate == "occurred_at"):
                        _event_facts += 1
                    # Phase 6b: event candidate generation on ACCEPTED
                    # scientific-action facts.
                    if (decision.decision == "ACCEPT"
                            and decision.fact is not None):
                        from polymath_shared.event_reification import (
                            event_candidate,
                        )
                        _admitted_facts.append({
                            "subject": candidate.subject.span.text,
                            "predicate": decision.fact.predicate,
                            "object": candidate.object.span.text,
                            "chunk_id": row.get("chunk_id"),
                            "provenance": {
                                "trigger_surface":
                                    decision.fact.provenance.get(
                                        "trigger_surface"),
                                "evidence_start": candidate.evidence.start,
                            }})
                        _ec = event_candidate(
                            decision.fact.predicate,
                            decision.fact.subject_id,
                            decision.fact.object_id,
                            decision.fact.qualifiers,
                            subject_surface=candidate.subject.span.text,
                            object_surface=candidate.object.span.text)
                        if _ec:
                            _event_candidates.append(_ec)
                    if trace.enabled:
                        reason = str(decision.reason or "")
                        code = ("NEGATED" if "negated" in reason else
                                "CONDITIONAL" if "conditional" in reason else
                                "MODAL" if any(w in reason for w in ("speculative", "hypothetical", "modal")) else
                                "FRAME_MISMATCH" if reason.startswith("frame_violation") else
                                "TYPE_SIGNATURE_MISMATCH" if reason.startswith("type_violation") else
                                "AMBIGUOUS_PREDICATE" if decision.decision == "AMBIGUOUS" else
                                "UNSUPPORTED_PREDICATE" if decision.decision == "UNSUPPORTED" else
                                "E3B_REJECTED" if reason.startswith("binding:") else
                                "COMPILER_ACCEPTED" if decision.decision in ("ACCEPT", "QUALIFY") else
                                "COMPILER_REJECTED")
                        trace.record(
                            event_type="compiler", decision=decision.decision,
                            reason_code=code, doc_id=doc_id, chunk_id=row["chunk_id"],
                            sentence_id=f"{row['chunk_id']}:{slice_idx}",
                            surface=str(candidate.subject.span.text)[:80],
                            detail={"predicate": getattr(decision, "rule_id", None),
                                    "reason": reason[:200],
                                    "subject": candidate.subject.span.text,
                                    "object": candidate.object.span.text})
                    if decision.decision in ("ACCEPT", "QUALIFY") and decision.fact:
                        # The compiler decided the trigger MEANS this
                        # predicate. Admission decides whether the claim may
                        # be ASSERTED. The candidate row above is already
                        # durable, so a refusal withholds the assertion
                        # without losing the evidence.
                        _pf = _t.perf_counter()
                        _may_assert = _fact_stage.admits(
                            row=row, candidate=candidate, decision=decision,
                            sl=sl, identities=identities)
                        _perf["fact_admission_s"] += _t.perf_counter() - _pf
                        if _may_assert:
                            _persist_decision(conn, row, candidate, decision,
                                              corpus_id=corpus_id,
                                              identities=identities)
                        if trace.enabled:
                            # Report the ASSERTION, not the proposal: a fact
                            # the admission chain withheld must not appear in
                            # the trace as FACT_ACCEPTED.
                            trace.record(
                                event_type="fact",
                                decision=("FACT_ACCEPTED" if _may_assert
                                          else "FACT_WITHHELD"),
                                reason_code=("FACT_ACCEPTED" if _may_assert
                                             else "FACT_ADMISSION_REFUSED"),
                                doc_id=doc_id,
                                chunk_id=row["chunk_id"],
                                sentence_id=f"{row['chunk_id']}:{slice_idx}",
                                surface=decision.fact.subject_id,
                                detail={"fact_id": decision.fact.fact_id,
                                        "predicate": decision.fact.predicate})
                    else:
                        audit.append({
                            "decision": decision.decision,
                            "reason": decision.reason,
                            "alternatives": decision.alternatives,
                            "subject": candidate.subject.span.text,
                            "object": candidate.object.span.text,
                            "evidence_class": candidate.evidence.evidence_class,
                        })
            _perf["candidates_compile_s"] = _t.perf_counter() - _pt
            _pt = _t.perf_counter()
            _raw.bulk_write(conn, "relation_candidates", _l4_rows)
            _fact_admission = _fact_stage.flush(conn)
            _perf["l1_l4_writes_s"] += _t.perf_counter() - _pt
            _perf["total_s"] = _t.perf_counter() - _perf.pop("stage_t0")
            _perf = {k: (round(v, 2) if isinstance(v, float) else v)
                     for k, v in _perf.items()}
            _perf["chunks"] = len(child_chunks)
            _perf["slices"] = len(ordered_slices)

            # EXTRACTION-AUDIT-V1: durable per-document audit report.
            # Monotonic timings only (perf_counter), integer milliseconds,
            # counts for every stage boundary — the phase's auditable
            # record, queryable via artifacts(run_id, stage='extract').
            timing_ms = {
                "total_ms": int(round(_perf.get("total_s", 0) * 1000)),
                "gliner_ms": int(round((_perf.get("entity_pass_s", 0.0)
                                        + _perf.get("evidence_pass_s", 0.0)) * 1000)),
                "spacy_ms": int(round(_perf.get("syntax_s", 0.0) * 1000)),
                "rescue_ms": int(round(_perf.get("rescue_s", 0.0) * 1000)),
                "entity_admission_ms": int(round(_perf.get("entity_admission_s", 0.0) * 1000)),
                "persist_mentions_ms": int(round(_perf.get("persist_mentions_s", 0.0) * 1000)),
                "predicate_compile_ms": int(round(_perf.get("candidates_compile_s", 0.0) * 1000)),
                "fact_admission_ms": int(round(_perf.get("fact_admission_s", 0.0) * 1000)),
                "writes_ms": int(round(_perf.get("l1_l4_writes_s", 0.0) * 1000)),
            }
            # KNOWLEDGE-ARTIFACT-PERSISTENCE-V1: procedures/concepts as
            # durable first-class objects, gated by router lanes only.
            try:
                _artifact_counts = _persist_knowledge_artifacts(
                    conn, corpus_id=corpus_id, doc_id=doc_id,
                    doc_text="\n".join(r["text"] for r in child_chunks),
                    chunk_ids=[r["chunk_id"] for r in child_chunks],
                    durable_surfaces=_durable_surfaces)
                extraction_audit_extra = {
                    "artifacts": _artifact_counts}
            except Exception as exc:
                extraction_audit_extra = {"artifacts_error": str(exc)[:200]}
                _artifact_counts = {"procedures": 0, "concepts": 0}

            extraction_audit = {
                "contract": "extraction-audit-v1",
                "run_id": run_id,
                "corpus_id": corpus_id,
                "document_id": doc_id,
                "relation_pipeline": active_pipeline(),
                "bytes": sum(len(r["text"]) for r in child_chunks),
                "timing_ms": timing_ms,
                "counts": {
                    "chunks": len(child_chunks),
                    "sentences": len(ordered_slices),
                    **_counts,
                    **_artifact_counts,
                    "relation_candidates_by_decision": dict(_decision_counts),
                    "facts_passed": _fact_stage.passed,
                    "facts_qualified": _fact_stage.qualified,
                    "facts_rejected": _fact_stage.rejected,
                    "facts_withheld": getattr(_fact_stage, "withheld", 0),
                },
            }
            writer.artifact({"extraction_audit": extraction_audit,
                             **extraction_audit_extra})
            # SEMANTIC-REPLAY-BENCHMARK-V1: the machine-comparable record
            # for corpus-level regression. Contract versions + counts +
            # rejection histograms, deterministic JSON.
            from polymath_shared.query_policy import active_policy_version
            from polymath_shared.execution import SEMANTIC_CONTRACT_V2
            replay_benchmark = {
                "contract": "semantic-replay-benchmark-v1",
                "run_id": run_id,
                "corpus_id": corpus_id,
                "document_id": doc_id,
                "pipeline_version": f"{EXTRACTOR_VERSION}+{active_pipeline()}",
                "build_sha": os.environ.get("POLYMATH_BUILD_SHA"),
                "entity_contract_version": SEMANTIC_CONTRACT_V2,
                "predicate_pack_version": pack.get("pack", {}).get("version"),
                "vocabulary_version": active_policy_version(),
                "counts": {
                    "fact_count": _fact_stage.passed,
                    "fact_qualified": _fact_stage.qualified,
                    "event_count": _event_facts,
                    "events": [],
                    "relation_candidates": sum(_decision_counts.values()),
                    "mentions_persisted": _counts.get(
                        "mentions_persisted", 0),
                },
                "rejection_histogram": {
                    "entity_admission": dict(_entity_admission.get(
                        "by_gate", {})) if _entity_admission else {},
                    "compiler_decisions": dict(_decision_counts),
                    "fact_admission_gates": dict(_fact_stage.by_gate),
                    "fact_admission_reasons": {
                        f"{r[5]}:{r[6]}": sum(
                            1 for x in _fact_stage.rows
                            if x[5] == r[5] and x[6] == r[6])
                        for r in set(_fact_stage.rows)},
                },
            }
            from polymath_shared.event_reification import admit_event
            admitted_events = []
            for ec in _event_candidates:
                ok, reason = admit_event(ec)
                if ok:
                    ec["admitted"] = True
                    ec["admission_reason"] = reason
                    admitted_events.append(ec)
                else:
                    ec["admitted"] = False
                    ec["admission_reason"] = reason
            replay_benchmark["counts"]["event_count"] = len(admitted_events)
            replay_benchmark["acceptance"] = _acceptance_block(
                _admitted_facts, _durable_surfaces)
            replay_benchmark["events"] = {
                "admitted": admitted_events,
                "rejected": [ec for ec in _event_candidates
                             if not ec.get("admitted")],
            }
            writer.artifact({"replay_benchmark": replay_benchmark})
            import json as _json
            log.info("extract audit %s", _json.dumps(extraction_audit),
                     extra={"run_id": run_id, "stage": "extract"})
            writer.artifact({"perf": _perf})
            log.info("extract perf", extra={"run_id": run_id, "stage": "extract",
                                            "detail": None})
        finally:
            gliner.close()

        writer.artifact({"audit": audit})
        if trace.enabled:
            trace.count("chunks", len(child_chunks))
            trace.count("slices", len(ordered_slices))
            trace.count("candidates_compiled", len(candidates) if 'candidates' in dir() else 0)
            funnel = trace.funnel()  # BEFORE flush (flush clears events)
            written = trace.flush(conn)
            writer.artifact({"trace": {
                "observer_contract_version": "extraction-observability-v1",
                "mode": trace.mode, "events_written": written,
                **funnel,
            }})
        # No outbox event: the control census schedules the projection
        # stages from the extract receipt (per-stage event types).
        writer.run_status("reconciling")


def _persist_mentions(conn: Connection, corpus_id: str, doc_id: str,
                      spans: list[EntitySpan],
                      ordered_slices: list[tuple[dict, SentenceSlice]] | None = None,
                      identities: dict | None = None,
                      ) -> None:
    """I3R-R4 / S4c: persist every accepted GLiNER proposal as a durable
    mention carrying the SINGLE admission decision made for it.

    This is a consumer, not an authority. A span with no entry in the
    identities map was never interpreted, which means the caller changed the
    ordering — refuse rather than interpret it a second time here.
    """
    from polymath_shared.identity_allocation import (
        normalized_for_lookup, span_identity_key,
    )

    if identities is None:
        raise RuntimeError(
            "_persist_mentions requires the identities map (S4c): mentions "
            "must carry the admission decided at the post-syntax boundary, "
            "never a second one computed here")

    # PHASE B6: one executemany for the whole document instead of one
    # INSERT per span (a book = ~8k round-trips inside the txn). Same rows,
    # same transaction, same conflict semantics.
    _mention_rows = []
    _entity_rows = []
    for span in spans:
        identity = identities.get(span_identity_key(span, corpus_id))
        if identity is None:
            raise RuntimeError(
                f"no admission for span {span.text!r} at {span.chunk_id}"
                f"[{span.start}:{span.end}] — persistence ran before or "
                "outside the single admission boundary")
        adm = identity.admission
        norm_surface = normalized_for_lookup(span.text)
        entity_id = identity.entity_id if identity.durable else None
        mention_id = "mention_" + _mention_suffix(span, doc_id)
        _mention_rows.append(
            (mention_id, corpus_id, span.doc_id or doc_id,
             span.chunk_id, span.start, span.end, span.text,
             norm_surface, span.core_type.value, span.score,
             span.extractor_version, identity.admission_class, entity_id,
             span.raw_label, QUERY_POLICY_VERSION, span.pass_kind,
             adm.proposal_surface, adm.referential_surface,
             adm.anchor_kind, adm.decision_status, adm.reference_basis,
             adm.admission_reason, adm.semantic_contract))
        # Same rule as reprocessing: an inheriting reference does not describe
        # the identity it borrowed. Under ON CONFLICT DO NOTHING this was
        # ORDER-dependent — whichever mention landed first defined the class —
        # so an anchor preceded by its own reference would have been mislabelled.
        if identity.durable and adm.reference_basis != "ANTECEDENT_RESOLVED":
            # the entity's own surface — the envelope is a reference TO
            # the entity, not the entity's name
            _entity_rows.append(
                (entity_id, span.core_type.value,
                 normalized_for_lookup(span.text), identity.admission_class))

    with conn.cursor() as _cur:
        _cur.executemany(
            """
            INSERT INTO mentions (mention_id, corpus_id, doc_id, chunk_id,
                                  char_start, char_end, surface,
                                  normalized_surface, core_type,
                                  gliner_score, extractor_version,
                                  admission_class, entity_id,
                                  raw_label, query_policy_version, pass_kind,
                                  proposal_surface, referential_surface,
                                  anchor_kind, decision_status,
                                  reference_basis, admission_reason,
                                  semantic_contract)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (mention_id) DO NOTHING
            """, _mention_rows)
        if _entity_rows:
            _cur.executemany(
                """
                INSERT INTO entities (entity_id, core_type, normalized_surface,
                                      admission_class)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (entity_id) DO NOTHING
                """, _entity_rows)


def _mention_suffix(span: EntitySpan, doc_id: str) -> str:
    """Evidence identity of the mention ROW — always span-stable, never the
    durable entity id. Keeping these apart is what lets one entity own many
    mentions without the rows colliding."""
    from polymath_shared.identity import content_hash

    return content_hash({
        "doc": span.doc_id or doc_id, "chunk": span.chunk_id,
        "type": span.core_type.value, "start": span.start, "end": span.end,
    })


def _evidence_offsets(chunk_row: dict, candidate, decision) -> dict:
    """I3R-R6 exact-evidence-v1 provenance record. All span offsets are
    CHUNK-RELATIVE so that chunk_text[start:end] == surface verifiably.

    The semantic subject/object are taken from the compiler decision's
    fact so that passive paraphrases label the actual agent/patient,
    not the surface word order."""
    chunk_start = int(chunk_row.get("char_start") or 0)
    chunk_end = int(chunk_row.get("char_end") or 0)
    ev = candidate.evidence
    fact = decision.fact
    # Match the semantic subject_id / object_id to the candidate spans.
    # The compiler may have inverted passive pairs, so we compare by
    # resolved entity identity (not by surface position).
    if fact.subject_id == candidate.subject.resolved_entity_id:
        subj, obj = candidate.subject.span, candidate.object.span
    else:
        subj, obj = candidate.object.span, candidate.subject.span
    # span offsets are CHUNK-RELATIVE (GLiNER spans are chunk-based);
    # chunk_char_start/end locate the chunk within the document.
    return {
        "provenance_contract": "exact-evidence-v1",
        "chunk_char_start": chunk_start,
        "chunk_char_end": chunk_end,
        "sentence_index": getattr(candidate, "sentence_index", 0),
        "evidence_surface": ev.text,
        "evidence_start": ev.start,
        "evidence_end": ev.end,
        "trigger_lemma": ev.trigger_lemma,
        "subject_surface": subj.text,
        "subject_start": subj.start,
        "subject_end": subj.end,
        "object_surface": obj.text,
        "object_start": obj.start,
        "object_end": obj.end,
    }


_BUNDLE_STAMP: dict | None = None


def _bundle_hash() -> str:
    global _BUNDLE_STAMP
    if _BUNDLE_STAMP is None:
        from polymath_shared.execution_bundle import (
            bundle_id, compute_execution_bundle)
        _BUNDLE_STAMP = bundle_id(compute_execution_bundle())
    return _BUNDLE_STAMP


def _stamped_provenance(provenance: dict) -> dict:
    """EXECUTION-BUNDLE-FENCE-V1: every accepted fact records the exact
    code+configuration bundle that produced it. Computed once per
    process; the claim gate guarantees it cannot go stale mid-flight."""
    global _BUNDLE_STAMP
    if _BUNDLE_STAMP is None:
        from polymath_shared.execution_bundle import (
            bundle_id, compute_execution_bundle)
        _BUNDLE_STAMP = bundle_id(compute_execution_bundle())
    out = dict(provenance or {})
    out.setdefault("generated_by_bundle_hash", _bundle_hash())
    return out


def _persist_knowledge_artifacts(conn: Connection, *, corpus_id: str,
                                 doc_id: str, doc_text: str,
                                 chunk_ids: list[str],
                                 durable_surfaces: list[str]) -> dict:
    """KNOWLEDGE-ARTIFACT-PERSISTENCE-V1: compile Procedure/Concept
    artifacts as first-class objects. They are NOT facts and never touch
    the entity graph here; retrieval projection is the projector's job.
    Content-addressed ids make replay idempotent.

    EXTRACTION-ELIGIBILITY-V1: the compilers are the LOCAL-EVIDENCE
    detectors — cheap, deterministic, self-gating (no procedural or
    conceptual evidence → no artifact). Document-level classification
    is recorded as routing metadata but never vetoes a compiler:
    eligible content always gets evaluated."""
    from polymath_shared.knowledge_router.classifier import classify_document
    from polymath_shared.knowledge_objects.concept import compile_concepts
    from polymath_shared.knowledge_objects.procedure import compile_procedure

    routing = classify_document(doc_text)["routing"]
    counts = {"procedures": 0, "concepts": 0,
              "routing_disabled": sorted(routing.get("disabled") or [])}

    # SEMANTIC-LANE-LIVENESS-V1: record the OPPORTUNITY, not just the
    # output. An artifact count alone cannot tell "12 of 12 opportunities
    # captured" from "12 of 400", which is precisely how a lane can look
    # alive while being deeply lossy. Counters are diagnostic and share
    # the compilers' own helpers, so they cannot drift from what the
    # compilers actually evaluate.
    from polymath_shared.knowledge_objects import concept as _concept_mod
    from polymath_shared.knowledge_objects import procedure as _procedure_mod
    from workers.summarizer import split_sentences as _split

    _doc_sentences = _split(doc_text)
    _proc_opportunities = _procedure_mod.count_opportunities(doc_text)
    _concept_opportunities = _concept_mod.count_opportunities(_doc_sentences)

    # procedure lane: always evaluated; the compiler self-gates on
    # local procedural evidence
    proc = compile_procedure(
        document_id=doc_id, corpus_id=corpus_id, text=doc_text,
        admitted_entities=durable_surfaces,
        source_chunk_ids=chunk_ids)
    if proc:
        conn.execute(
            """
            INSERT INTO procedure_artifacts
                (procedure_id, document_id, corpus_id, title, goal,
                 steps_json, tools_json, confidence, source_chunk_ids,
                 generated_by_bundle_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (procedure_id) DO NOTHING
            """,
            (proc["artifact_id"], doc_id, corpus_id,
             proc.get("title", ""), proc.get("goal", ""),
             json.dumps(proc.get("steps", [])),
             json.dumps(proc.get("tools", [])),
             float(proc.get("confidence", 0.0)), list(chunk_ids),
             _bundle_hash()))
        counts["procedures"] = 1

    # concept lane: always evaluated; the compiler self-gates on
    # local definitional evidence
    from workers.summarizer import split_sentences
    concepts = compile_concepts(
        document_id=doc_id, corpus_id=corpus_id,
        sentences=split_sentences(doc_text),
        admitted_entities=durable_surfaces,
        source_chunk_ids=chunk_ids)
    for c in concepts:
        conn.execute(
            """
            INSERT INTO concept_artifacts
                (concept_id, document_id, corpus_id, name, description,
                 domain, related_entities, source_sentence, confidence,
                 supporting_chunks, generated_by_bundle_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (concept_id) DO NOTHING
            """,
            (c["artifact_id"], doc_id, corpus_id, c["name"],
             c.get("description", ""), c.get("domain", "general"),
             json.dumps(c.get("related_entities", [])),
             c.get("source_sentence", ""),
             float(c.get("confidence", 0.0)), list(chunk_ids),
             _bundle_hash()))
        counts["concepts"] += 1

    _record_lane_attempt(conn, doc_id=doc_id, corpus_id=corpus_id,
                         lane="procedure",
                         opportunities=_proc_opportunities,
                         accepted=counts["procedures"], capped=False)
    _record_lane_attempt(conn, doc_id=doc_id, corpus_id=corpus_id,
                         lane="concept",
                         opportunities=_concept_opportunities,
                         accepted=counts["concepts"],
                         # compile_concepts caps at max_concepts=10;
                         # equality means the cap truncated real recall
                         capped=counts["concepts"] >= 10)
    counts["procedure_opportunities"] = _proc_opportunities
    counts["concept_opportunities"] = _concept_opportunities
    return counts


def _record_lane_attempt(conn: Connection, *, doc_id: str, corpus_id: str,
                         lane: str, opportunities: int, accepted: int,
                         capped: bool) -> None:
    """SEMANTIC-LANE-LIVENESS-V1 durable disposition.

    NO_OPPORTUNITY is a CORRECT outcome and must stay distinguishable
    from a lane that saw evidence and produced nothing (GATED) -- the
    latter is the dead-feature signal."""
    if opportunities <= 0:
        disposition = "NO_OPPORTUNITY"
    elif accepted > 0:
        disposition = "ACCEPTED"
    else:
        disposition = "GATED"
    conn.execute(
        """
        INSERT INTO knowledge_lane_attempts
            (doc_id, corpus_id, lane, opportunities, accepted, capped,
             disposition, bundle_hash)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (doc_id, lane) DO UPDATE SET
            opportunities = EXCLUDED.opportunities,
            accepted = EXCLUDED.accepted,
            capped = EXCLUDED.capped,
            disposition = EXCLUDED.disposition,
            bundle_hash = EXCLUDED.bundle_hash,
            created_at = now()
        """,
        (doc_id, corpus_id, lane, opportunities, accepted, capped,
         disposition, _bundle_hash()))


def _persist_decision(conn: Connection, chunk_row: dict, candidate, decision,
                      corpus_id: str = "eval", identities: dict | None = None) -> None:
    """S4c: fact endpoints are written from the SAME admission the mention
    carries. Re-deciding here is what previously let an endpoint disagree
    with its own mention row."""
    from polymath_shared.identity_allocation import (
        normalized_for_lookup, span_identity_key,
    )

    fact = decision.fact
    for entity_id, span in (
        (fact.subject_id, candidate.subject.span),
        (fact.object_id, candidate.object.span),
    ):
        identity = (identities or {}).get(span_identity_key(span, corpus_id))
        if identity is None:
            raise RuntimeError(
                f"fact endpoint {span.text!r} has no admission in the "
                "identities map — the compiler produced an endpoint the "
                "admission boundary never interpreted")
        if (identity.admission.reference_basis == "ANTECEDENT_RESOLVED"
                and identity.durable):
            # This endpoint BORROWED a durable identity from an anchor
            # (row 48). The anchor already described the entity when its own
            # mention was persisted; describing it again from the reference
            # would restamp a GLOBAL anchor with the reference's
            # DOCUMENT_SCOPED scope.
            #
            # A NON-durable resolved reference is different: it inherited
            # NOTHING, its id is its own span-scoped mention_ identity, and
            # no anchor ever writes that entities row — skipping here left a
            # parked fact pointing at a missing row (FK violation, found by
            # the first book-scale ingest). It falls through and records its
            # own MENTION_ONLY entity row, exactly like every other parked
            # endpoint.
            continue
        conn.execute(
            """
            INSERT INTO entities (entity_id, core_type, normalized_surface, admission_class)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (entity_id) DO NOTHING
            """,
            (entity_id, span.core_type.value,
             normalized_for_lookup(span.text),
             identity.admission_class),
        )
    conn.execute(
        """
        INSERT INTO facts (fact_id, predicate, subject_id, object_id, qualifiers,
                           decision, rule_id, rule_version, provenance)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fact_id) DO NOTHING
        """,
        (fact.fact_id, fact.predicate, fact.subject_id, fact.object_id,
         json.dumps(fact.qualifiers), fact.decision, fact.rule_id,
         fact.rule_version, json.dumps(_stamped_provenance(fact.provenance))),
    )

    from polymath_shared.identity import evidence_id

    ev_id = evidence_id(
        fact.fact_id, chunk_row["doc_id"], chunk_row["chunk_id"],
        {"chunk": chunk_row["char_start"]}, fact.rule_id,
    )
    offsets = _evidence_offsets(chunk_row, candidate, decision)
    conn.execute(
        """
        INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id, span_offsets,
                              rule_id, gliner_scores, extractor_version, rule_version,
                              provenance_contract)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (evidence_id) DO NOTHING
        """,
        (ev_id, fact.fact_id, chunk_row["doc_id"], chunk_row["chunk_id"],
         json.dumps(offsets),
         fact.rule_id, json.dumps({}), EXTRACTOR_VERSION, fact.rule_version,
         "exact-evidence-v1"),
    )


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:
    """LONG-STAGE-LEASE-CORRECTNESS-V1: claim depth 1.

    A worker executes tickets serially, so claiming ahead bought nothing
    but made "held" differ from "being processed" -- and a stage running
    past claim_ttl_s let the reaper expire the queued ones. Parallelism
    comes from running several workers of a type.
    """
    from polymath_shared.worker_runtime import run_worker

    run_worker('extract', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)

if __name__ == "__main__":
    run_forever()
