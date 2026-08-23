"""PREDICATE-COMPILER-V2: syntax-grounded candidate generation.

Owner decision record 2026-08-22: association-based intake is replaced,
not filtered. Predicate occurrences originate at spaCy tokens whose
lemma is licensed by the authored registry; arguments bind only through
dependency structure; a missing parse or a missing dependency-bound
entity emits no candidate. Proximity recall, definite-description
resolution, and chunk-wide pairing do not exist on this path.

Binding sources are UD_DEPENDENCY (verbal triggers) and
NOMINAL_DEPENDENCY (nominal triggers confirmed by a prep>pobj subtree).
Every emitted candidate satisfies v2_binding_refusal() is None by
construction.
"""
from __future__ import annotations

from polymath_shared.contracts import (
    BindingSource,
    EntityCandidate,
    EvidenceSpan,
    RelationCandidate,
)
from polymath_shared.rulepack.lexical_evidence import (
    build_lexical_semantic_evidence,
)
from polymath_shared.rulepack.negation import analyze_scope
from polymath_shared.scientific_concept import (
    is_temporal_surface,
    normalize_temporal,
)
from polymath_shared.rulepack.role_assignment import (
    assign_roles,
    get_role_inventory,
)
from workers.candidates import (
    SentenceSlice,
    _allocate,
    _lookup_for,
    _role_assignments,
    _type_compatible,
)
from workers.kimi_candidates import (
    _propagate_shared_arguments,
    _syntax_tokens,
    _token_to_entity,
)
from polymath_shared.discourse_bridge import (
    find_appos_entity_head,
    is_pronoun_token,
    resolve_anaphora,
)

VERBAL_POS = frozenset({"VERB", "AUX"})
NOMINAL_POS = frozenset({"NOUN"})
SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "nsubj:pass"})
OBJECT_DEPS = frozenset({"dobj", "obj", "iobj"})
COPULA_OBJECT_DEPS = frozenset({"attr", "acomp", "oprd"})
PREP_DEPS = frozenset({"prep", "agent"})
PREP_OBJECT_DEPS = frozenset({"pobj", "obl"})
CONJ_DEP = "conj"

# SCIENTIFIC-KAG-V1 phase 5: authored infinitive-control frames.
# The EMBEDDED verb is the predicate occurrence; its subject is supplied
# by the matrix clause under a licensed control verb. Fail-closed on
# ambiguity: zero or several controllers yields no candidate.
SUBJECT_CONTROL_VERBS = frozenset({
    "use", "leverage", "attempt", "try", "begin", "continue", "fail",
    "help",
})
OBJECT_CONTROL_VERBS = frozenset({
    "allow", "enable", "permit", "require", "cause",
})
CONTROL_EMBEDDED_DEPS = frozenset({"xcomp", "ccomp", "advcl"})


def _v2_registry(rule_pack: dict) -> tuple[dict[str, str], dict[str, str]]:
    verbs: dict[str, str] = {}
    nouns: dict[str, str] = {}
    for rule_id in rule_pack["predicate_order"]:
        ev = rule_pack["predicates"][rule_id]["evidence"]
        for lemma in ev.get("verbs", []):
            verbs.setdefault(lemma.lower(), rule_id)
        for noun in ev.get("nouns", []):
            nouns.setdefault(noun.lower(), rule_id)
    return verbs, nouns


def _children(tokens: list[dict], head_i: int) -> list[dict]:
    return [t for t in tokens if t["head_i"] == head_i]


def _conj_expansion(tokens: list[dict], heads: list[dict]) -> list[dict]:
    out = list(heads)
    seen = {t["i"] for t in out}
    for head in heads:
        for tok in _children(tokens, head["i"]):
            if tok["dep"] == CONJ_DEP and tok["i"] not in seen:
                out.append(tok)
                seen.add(tok["i"])
    return out


def _entity_pairs(tok_list: list[dict], sl: SentenceSlice,
                  anaphora: dict | None = None) -> tuple[list[tuple], bool]:
    pairs: list[tuple] = []
    used_anaphora = False
    for tok in tok_list:
        ent = None
        if is_pronoun_token(tok) and anaphora:
            key = (sl.entities[0].chunk_id,
                   sl.sentence_start + tok["char_start"],
                   sl.sentence_start + tok["char_end"])
            # A resolved pronoun outranks its own noisy GLiNER proposal.
            ent = anaphora.get(key)
            used_anaphora = True
        if ent is None:
            ent = _token_to_entity(tok, sl.entities, sl)
        if ent is None:
            # Phase 5.5 discourse bridge: (a) controlled anaphora — a
            # pronoun span resolved to a prior durable subject; (b)
            # definitional apposition — a token inside an appos subtree
            # describes, and binds through, the entity head it apposes.
            if anaphora:
                key = (sl.entities[0].chunk_id,
                       sl.sentence_start + tok["char_start"],
                       sl.sentence_start + tok["char_end"])
                ent = anaphora.get(key)
            if ent is None:
                # Scientific-register compound-NP heads: a generic head
                # token ("model") whose compound child names the entity
                # ("BERT") binds through the child — dependency evidence
                # only, never surface guessing.
                for child in (getattr(sl, "syntax", None) or {}).get(
                        "tokens", []):
                    if (child.get("head_i") == tok.get("i")
                            and child.get("dep") == "compound"):
                        ent = _token_to_entity(child, sl.entities, sl)
                        if ent is not None:
                            break
            if ent is None:
                head_tok = find_appos_entity_head(
                    {"head_i": tok.get("head_i"), "i": tok.get("i"),
                     "dep": tok.get("dep")}, sl)
                if head_tok is not None:
                    ent = _token_to_entity(head_tok, sl.entities, sl)
        if ent is not None and all(ent is not e for _, e in pairs):
            pairs.append((tok, ent))
    return pairs, used_anaphora


TEMPORAL_OBJECT_TYPES = frozenset(
    {"Date", "TimePeriod", "Version", "TimeReference"})


def _pobj_phrase(tokens: list[dict], pobj: dict) -> str:
    """The temporal NP surface: the pobj plus its nummod children."""
    parts = [pobj] + [t for t in _children(tokens, pobj["i"])
                      if t["dep"] == "nummod"]
    parts.sort(key=lambda t: t["char_start"])
    return " ".join(t["text"] for t in parts)


def _control_controller(
    tokens: list[dict], tok: dict, sl: SentenceSlice,
) -> tuple[dict, BindingSource, str] | None:
    """Infinitive-control resolution for an embedded predicate token.

    Returns (controller_token, binding_source, matrix_lemma) or None.
    Deterministic and fail-closed: the controller is the unique
    entity-bearing argument child of the matrix verb that sits BETWEEN
    the matrix verb and this token — which selects the object controller
    for allow-class verbs and excludes the matrix's own subject."""
    if tok.get("dep") not in CONTROL_EMBEDDED_DEPS:
        return None
    head_i = tok.get("head_i")
    matrix = next((t for t in tokens if t["i"] == head_i), None)
    if matrix is None or matrix is tok:
        return None
    m_lemma = (matrix.get("lemma") or "").lower()
    m_pos = matrix.get("pos", "")
    if m_pos not in VERBAL_POS:
        return None

    if m_lemma in SUBJECT_CONTROL_VERBS:
        ctrl = [t for t in _children(tokens, matrix["i"])
                if t["dep"] in SUBJECT_DEPS]
        source = BindingSource.CONTROL_SUBJECT
        frame = "subject"
    elif m_lemma in OBJECT_CONTROL_VERBS:
        lo, hi = sorted((matrix["i"], tok["i"]))
        ctrl = [t for t in _children(tokens, matrix["i"])
                if t["dep"] in (SUBJECT_DEPS | OBJECT_DEPS)
                and lo < t["i"] < hi]
        source = BindingSource.CONTROL_OBJECT
        frame = "object"
    else:
        return None

    entity_ctrl = [t for t in ctrl if _token_to_entity(t, sl.entities, sl)]
    if len(entity_ctrl) != 1:
        return None
    return entity_ctrl[0], source, f"{m_lemma}:{frame}"


def build_candidates_kimi_v2(
    slices: list[SentenceSlice],
    *,
    doc_id: str,
    corpus_id: str = "eval",
    ontology_profile: str,
    extractor_version: str,
    rule_pack: dict,
    enrich: bool = True,
    doc_entities_history=None,
    observer=None,
    identities: dict | None = None,
) -> list[RelationCandidate]:
    verb_registry, noun_registry = _v2_registry(rule_pack)
    candidates: list[RelationCandidate] = []
    anaphora = resolve_anaphora(slices)

    for sl in slices:
        tokens = _syntax_tokens(sl)
        if not tokens or not sl.entities:
            continue
        chunk_id = sl.entities[0].chunk_id
        sentence_id = f"{chunk_id}#s{sl.sentence_index}"
        rel_start = sl.sentence_start

        for tok in tokens:
            lemma = (tok.get("lemma") or "").lower()
            pos = tok.get("pos", "")
            nominal = pos in NOMINAL_POS
            if nominal:
                predicate_id = noun_registry.get(lemma)
            elif pos in VERBAL_POS:
                predicate_id = verb_registry.get(lemma)
            else:
                predicate_id = None
            if predicate_id is None:
                continue
            if observer:
                observer.record_candidate_outcome(
                    sl, None, "V2_PREDICATE_TOKEN", {
                        "token_i": tok["i"], "lemma": lemma, "pos": pos,
                        "predicate": predicate_id, "kimi_v2": True})

            evidence_class = rule_pack["predicates"][predicate_id][
                "evidence"]["classes"][0]

            subj_toks = [t for t in _children(tokens, tok["i"])
                         if t["dep"] in SUBJECT_DEPS]
            obj_deps = OBJECT_DEPS | (COPULA_OBJECT_DEPS if pos == "AUX"
                                      else set())
            obj_toks = [t for t in _children(tokens, tok["i"])
                        if t["dep"] in obj_deps]
            binding_source = (BindingSource.NOMINAL_DEPENDENCY if nominal
                              else BindingSource.UD_DEPENDENCY)

            # Voice is read from the UD tree itself (auxpass / nsubj:pass),
            # never fabricated: a passive without its by-agent yields an
            # oblique-bound object exactly like an active dobj would not.
            children = _children(tokens, tok["i"])
            voice = ("passive"
                     if any(t["dep"] in ("auxpass", "aux:pass")
                            for t in children)
                     or any(t["dep"] in ("nsubjpass", "nsubj:pass")
                            for t in subj_toks)
                     else "active")

            dep_path_parts: list[str] = []
            temporal_surface: str | None = None
            temporal_toks: list[dict] = []
            control_note = None

            # Phase 6: prep>pobj complements are partitioned for EVERY
            # verbal trigger (active or passive) — a temporal phrase
            # ("in March 2023", "in 2024") is an event attribute, never
            # the primary object. Non-temporal pobjs bind as objects only
            # where the architecture allows it: passives, nominal
            # predicates, and control-framed infinitives.
            _allow_pobj_objects = (
                nominal or voice == "passive" or bool(control_note))
            for prep in _children(tokens, tok["i"]):
                if prep["dep"] not in PREP_DEPS:
                    continue
                pobjs = [t for t in _children(tokens, prep["i"])
                         if t["dep"] in PREP_OBJECT_DEPS]
                for p in pobjs:
                    phrase = _pobj_phrase(tokens, p)
                    if is_temporal_surface(phrase):
                        temporal_toks.append(p)
                        if temporal_surface is None:
                            temporal_surface = phrase
                        continue
                    if _allow_pobj_objects:
                        obj_toks.append(p)
                if pobjs and obj_toks:
                    dep_path_parts.append(
                        f"{prep['dep']}.{prep['text'].lower()}>"
                        f"{pobjs[0]['dep']}")


            subj_toks = _conj_expansion(tokens, subj_toks)
            obj_toks = _conj_expansion(tokens, obj_toks)

            # Phase 5: infinitive-control. Only when the embedded verb has
            # NO subject of its own; its own explicit arguments always win.
            if not subj_toks and not nominal:
                ctrl = _control_controller(tokens, tok, sl)
                if ctrl is not None:
                    subj_toks = [ctrl[0]]
                    binding_source = ctrl[1]
                    control_note = ctrl[2]
                    dep_path_parts.insert(
                        0, f"control[{ctrl[2]}]")
                    # A controlled infinitive takes its object through the
                    # same prep>pobj subtree ("enables B to train on D").
                    if not obj_toks:
                        for prep in _children(tokens, tok["i"]):
                            if prep["dep"] not in PREP_DEPS:
                                continue
                            for gc in _children(tokens, prep["i"]):
                                if gc["dep"] not in PREP_OBJECT_DEPS:
                                    continue
                                phrase = _pobj_phrase(tokens, gc)
                                if is_temporal_surface(phrase):
                                    temporal_toks.append(gc)
                                    if temporal_surface is None:
                                        temporal_surface = phrase
                                else:
                                    obj_toks.append(gc)
                elif observer:
                    observer.record_candidate_outcome(
                        sl, None, "V2_CONTROL_AMBIGUOUS", {
                            "token_i": tok["i"], "lemma": lemma,
                            "kimi_v2": True})

            # Phase 6: an intransitive event predicate whose only
            # complement is temporal ("occurred in 2024") binds the DATE
            # as the knowledge-object endpoint.
            rule_obj_core = {
                core for sig in rule_pack["predicates"][predicate_id][
                    "signatures"]
                for core in (sig.get("object_core") or [])}
            if (not obj_toks and temporal_toks
                    and rule_obj_core & TEMPORAL_OBJECT_TYPES):
                obj_toks.extend(temporal_toks)

            _propagate_shared_arguments(
                tokens, tok["i"],
                {"subject": subj_toks, "object": obj_toks})
            if not subj_toks or not obj_toks:
                if observer:
                    observer.record_candidate_outcome(
                        sl, None, "V2_NO_DEPENDENT_IN_SLOT", {
                            "slot": "subject" if not subj_toks else "object",
                            "token_i": tok["i"], "lemma": lemma,
                            "binding_source": binding_source.value,
                            "kimi_v2": True})
                continue

            subject_pairs, subj_via_anaphora = _entity_pairs(
                subj_toks, sl, anaphora)
            object_pairs, _obj_via_anaphora = _entity_pairs(
                obj_toks, sl, anaphora)
            if not subject_pairs or not object_pairs:
                if observer:
                    observer.record_candidate_outcome(
                        sl, None, "V2_ARGUMENT_NOT_AN_ENTITY", {
                            "subjects": len(subject_pairs),
                            "objects": len(object_pairs),
                            "token_i": tok["i"], "kimi_v2": True})
                continue

            scope = analyze_scope(sl.text, tok["char_start"],
                                  tok["char_end"])
            trig_abs_start = rel_start + tok["char_start"]
            trig_abs_end = rel_start + tok["char_end"]

            # Lexical enrichment needs only the trigger identity; the
            # per-pair candidate evidence span is widened below to attest
            # trigger plus arguments (what F8 support verifies).
            probe = EvidenceSpan(
                chunk_id=chunk_id,
                start=trig_abs_start,
                end=trig_abs_end,
                text=tok["text"],
                evidence_class=evidence_class,
                trigger_lemma=lemma,
                trigger_lexical_class="NOUN" if nominal else "VERB",
                trigger_predicate_id=predicate_id,
                trigger_match_source="nouns" if nominal else "verbs",
                score=1.0,
                extractor_version=extractor_version,
            )
            lexical = (_lookup_for(rule_pack, probe) if enrich else {
                "roleset": None, "vn_classes": [], "fn_frames": [],
                "semlink_resolved": False,
            })

            for subj_tok, subject_span in subject_pairs:
                for obj_tok, object_span in object_pairs:
                    if (subject_span.text == object_span.text
                            and subject_span.core_type
                            == object_span.core_type):
                        continue
                    evidence = EvidenceSpan(
                        chunk_id=chunk_id,
                        start=min(subject_span.start, object_span.start,
                                  trig_abs_start),
                        end=max(subject_span.end, object_span.end,
                                trig_abs_end),
                        text=sl.text[
                            min(subject_span.start, object_span.start,
                                trig_abs_start) - rel_start:
                            max(subject_span.end, object_span.end,
                                trig_abs_end) - rel_start],
                        evidence_class=evidence_class,
                        trigger_lemma=lemma,
                        trigger_lexical_class="NOUN" if nominal else "VERB",
                        trigger_predicate_id=predicate_id,
                        trigger_match_source="nouns" if nominal else "verbs",
                        score=1.0,
                        extractor_version=extractor_version,
                    )
                    forward_ok = _type_compatible(
                        subject_span.core_type.value,
                        object_span.core_type.value,
                        evidence_class, rule_pack)
                    reverse_ok = _type_compatible(
                        object_span.core_type.value,
                        subject_span.core_type.value,
                        evidence_class, rule_pack)
                    if not (forward_ok or reverse_ok):
                        if observer:
                            observer.record_candidate_outcome(
                                sl, evidence, "TYPE_PRECHECK_FAIL", {
                                    "subject": subject_span.text,
                                    "object": object_span.text,
                                    "kimi_v2": True})
                        continue

                    subject_id = _allocate(subject_span, sl, doc_id,
                                           corpus_id, identities)
                    object_id = _allocate(object_span, sl, doc_id,
                                          corpus_id, identities)

                    role_inv = get_role_inventory(
                        lexical, lexical.get("roleset"))
                    subj_dep = subj_tok["dep"]
                    if subj_dep == "nsubjpass":
                        subj_dep = "nsubj:pass"
                    agent_span = None
                    if voice == "passive":
                        for child in _children(tokens, tok["i"]):
                            if child["dep"] not in PREP_DEPS:
                                continue
                            for gc in _children(tokens, child["i"]):
                                if gc["dep"] in PREP_OBJECT_DEPS:
                                    agent_span = _token_to_entity(
                                        gc, sl.entities, sl)

                    role_result = assign_roles(
                        roleset=lexical.get("roleset"),
                        role_inventory=role_inv,
                        voice=voice,
                        subject_dep=subj_dep,
                        object_dep=obj_tok["dep"],
                        subject_entity=subject_span,
                        object_entity=object_span,
                        agent_entity=agent_span,
                    )
                    lse = build_lexical_semantic_evidence(
                        evidence=evidence,
                        subject=subject_span,
                        object=object_span,
                        lexical=lexical,
                        role_result=role_result,
                        tokens=tokens,
                        trigger_head=tok,
                        subj_dep=subj_tok["dep"],
                        obj_dep=obj_tok["dep"],
                        binding_source=binding_source.value,
                        rule_pack=rule_pack,
                    )

                    if subj_via_anaphora:
                        binding_source = BindingSource.DISCOURSE_ANAPHORA
                        dep_path_parts.insert(0, "anaphora")
                    if not dep_path_parts:
                        dep_path_parts.append(
                            f"{subj_tok['dep']}+{obj_tok['dep']}")
                    candidates.append(RelationCandidate(
                        sentence_text=sl.text,
                        sentence_start=rel_start,
                        sentence_index=sl.sentence_index,
                        evidence=evidence,
                        subject=EntityCandidate(span=subject_span,
                                                resolved_entity_id=subject_id),
                        object=EntityCandidate(span=object_span,
                                               resolved_entity_id=object_id),
                        roles=_role_assignments(subject_span, object_span,
                                                sl.parse),
                        roleset=lexical["roleset"],
                        verbnet_classes=lexical["vn_classes"],
                        framenet_frames=lexical["fn_frames"],
                        semlink_resolved=lexical["semlink_resolved"],
                        semlink_mapping={
                            "roleset": lexical.get("roleset"),
                            "vn_classes": lexical.get("vn_classes", []),
                            "fn_frames": lexical.get("fn_frames", []),
                            "semlink_pb_vn": lexical.get("semlink_pb_vn", {}),
                        },
                        scope=scope,
                        ontology_profile=ontology_profile,
                        assigned_roles=role_result["assigned"],
                        lexical_semantic_evidence=lse,
                        document_id=doc_id,
                        sentence_id=sentence_id,
                        trigger_token_id=tok["i"],
                        subject_token_id=subj_tok["i"],
                        object_token_id=obj_tok["i"],
                        dependency_path="+".join(dep_path_parts),
                        binding_source=binding_source,
                        temporal_surface=temporal_surface,
                    ))
    return candidates
