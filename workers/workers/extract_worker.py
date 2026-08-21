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
import time
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
) -> list[EvidenceSpan]:
    """ADR-0008: pass 2 = GLiNER coarse proposals (may abstain) +
    lexical trigger localization. The compiler decides either way."""
    from workers.evidence_proposer import (
        localize_trigger,
        merge_gliner_proposals,
        propose_evidence,
    )

    anchors = propose_evidence(chunk_text, chunk_id, pack)
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
    for idx, (row, sl) in enumerate(ordered_slices):
        conn.execute(
            """
            INSERT INTO sentence_slices (doc_id, chunk_id, slice_index,
                                         chunk_start, chunk_end, in_context)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (doc_id, chunk_id, slice_index) DO UPDATE
                SET chunk_start = EXCLUDED.chunk_start,
                    chunk_end = EXCLUDED.chunk_end,
                    in_context = EXCLUDED.in_context
            """,
            (doc_id, row["chunk_id"], idx, sl.sentence_start, sl.sentence_end),
        )


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
    client = SpacySyntaxClient()
    try:
        client.verify_pin()
        response = client.syntax(sentences)
    finally:
        client.close()

    expected_ids = [s["sentence_id"] for s in sentences]
    returned_ids = [r["sentence_id"] for r in response["results"]]
    if returned_ids != expected_ids:
        raise RuntimeError(
            "syntax sidecar returned mismatched sentence identity/order"
        )
    by_id = {r["sentence_id"]: r for r in response["results"]}
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
                entities, rejected = _entity_spans(
                    gliner, row["text"], row["chunk_id"], doc_id, profile_dict,
                    envelope=envelope, trace=trace, raw_sink=raw_entity_sink
                )
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
                evidence = _evidence_spans(
                    gliner, row["text"], row["chunk_id"], pack, proposal_mode,
                    raw_sink=raw_predicate_sink
                )
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
                sentences = _sentences_of(row["text"])
                slices = _slices(sentences, entities, evidence, corpus_id)
                for sl in slices:
                    ordered_slices.append((row, sl))

            doc_entity_history: list[EntitySpan] = []
            # SYNTAX-BOOTSTRAP: after the GLiNER passes and before
            # build_candidates — annotate the same slices (one batched
            # call) when the provider is enabled; disabled records and
            # changes nothing.
            _raw.bulk_write(conn, "raw_entity_proposals", _raw_rows_entity)
            _raw.bulk_write(conn, "raw_predicate_evidence", _raw_rows_predicate)
            syntax_runtime = _syntax_evidence(ordered_slices)
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
                rescue_report = apply_rescue(
                    ordered_slices, rescue_stages, rescue_label_set, _pack())
                writer.artifact({"rescue": rescue_report})

            # SENTENCE-SLICE-MANIFEST-V1 (row 54): record WHICH slices the
            # interpreter saw, in what order, under which contract — before
            # interpreting. Slice membership depends on GLiNER evidence-trigger
            # placement, which is not otherwise recoverable, so reprocessing
            # had to guess at it: a narrower guess loses antecedents, a wider
            # one invents them. Persisting the view is what makes
            # re-derivation reproduce interpretation instead of approximating
            # it.
            _persist_slice_manifest(conn, doc_id, ordered_slices)
            # S4c: THE admission boundary. It sits after syntax (S4a) AND
            # after rescue, because rescue is proposal generation too — a
            # rescued span is a candidate endpoint and must be interpreted
            # by the same authority, exactly once, not left unadmitted.
            from polymath_shared.execution import SEMANTIC_CONTRACT_V2

            identities = _allocate_identities(
                ordered_slices, corpus_id, doc_id,
                contract_version=SEMANTIC_CONTRACT_V2)
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
            _persist_mentions(
                conn, corpus_id, doc_id,
                [span for _row, _sl in ordered_slices for span in _sl.entities],
                ordered_slices=ordered_slices, identities=identities)
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
                    if active_pipeline() == "kimi_v1":
                        decision = compile_relation_kimi(candidate, sl.parse, pack, syntax=sl.syntax)
                    else:
                        decision = compile_relation(candidate, sl.parse, pack, syntax=sl.syntax)
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
                        _persist_decision(conn, row, candidate, decision,
                                          corpus_id=corpus_id,
                                          identities=identities)
                        if trace.enabled:
                            trace.record(
                                event_type="fact", decision="FACT_ACCEPTED",
                                reason_code="FACT_ACCEPTED", doc_id=doc_id,
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
        conn.execute(
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
            """,
            (mention_id, corpus_id, span.doc_id or doc_id,
             span.chunk_id, span.start, span.end, span.text,
             norm_surface, span.core_type.value, span.score,
             span.extractor_version, identity.admission_class, entity_id,
             span.raw_label, QUERY_POLICY_VERSION, span.pass_kind,
             adm.proposal_surface, adm.referential_surface,
             adm.anchor_kind, adm.decision_status, adm.reference_basis,
             adm.admission_reason, adm.semantic_contract),
        )
        # Same rule as reprocessing: an inheriting reference does not describe
        # the identity it borrowed. Under ON CONFLICT DO NOTHING this was
        # ORDER-dependent — whichever mention landed first defined the class —
        # so an anchor preceded by its own reference would have been mislabelled.
        if identity.durable and adm.reference_basis != "ANTECEDENT_RESOLVED":
            conn.execute(
                """
                INSERT INTO entities (entity_id, core_type, normalized_surface,
                                      admission_class)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (entity_id) DO NOTHING
                """,
                # the entity's own surface — the envelope is a reference TO
                # the entity, not the entity's name
                (entity_id, span.core_type.value,
                 normalized_for_lookup(span.text),
                 identity.admission_class),
            )


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
        if identity.admission.reference_basis == "ANTECEDENT_RESOLVED":
            # This endpoint BORROWED its identity from an anchor (row 48).
            # The anchor already described the entity when its own mention was
            # persisted; describing it again from the reference would restamp
            # a GLOBAL anchor with the reference's DOCUMENT_SCOPED scope.
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
         fact.rule_version, json.dumps(fact.provenance)),
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


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 4) -> None:
    from polymath_shared.worker_runtime import run_worker

    run_worker('extract', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)

if __name__ == "__main__":
    run_forever()
