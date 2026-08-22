"""POLYMATH-FACT-ADMISSION-V1 — the deterministic L4→L5 boundary.

The relation compiler answers "does some rule map this candidate onto a
predicate?". That is a MAPPING question. This module answers the
ADMISSION question:

    is there deterministic evidence that this document ASSERTS this
    relation, between these two referents, in this direction?

Measured need (FINAL_FORENSIC_REPORT.md §7): 38% of projected edges were
WRONG under strict span attestation. Five mechanisms explained nearly all
of them, and each has a gate here:

    structure/reference-region relations   -> F2
    pronoun / non-durable endpoints        -> F3
    part_of / include direction inversion  -> F7
    predicate misfire (use -> acquired)    -> F5
    modal prose becoming asserted fact     -> F4

Governing rulings (from the authorizing directive):

  R1  Raw GLiNER type is EVIDENCE, never signature authority. Every
      type read here is the SETTLED semantic class carried on the
      entity row, so provider typing cannot re-enter as truth through
      the back door.

  R2  No lexical stoplist decides endpoints. An endpoint fails because
      of its SEMANTIC STATE (durable + graph-eligible) or its
      GRAMMATICAL STATE (its head token is a pronoun — a POS fact from
      the parser, not a hand-maintained word list). Harbor minting
      durable identities for "we"/"they" is a separate upstream defect;
      this layer still fails closed.

  R3  Predicate licensing consults the compiled lexical authorities
      (rule-pack evidence blocks, VerbNet / PropBank / FrameNet via
      `lexical_lookup`) rather than growing a private verb dictionary.
      The only enumerations here are closed grammatical classes (English
      modal auxiliaries) and declarative ontology metadata in
      fact_admission_policy.yaml.

  R4  QUALIFY is not canonical truth. It stays durable, queryable
      evidence and MUST NOT project to Neo4j as an asserted fact.

Every gate is a pure function of persisted evidence. Same candidate +
same policy + same pack => same decision, always, with a reason code.
"""

from __future__ import annotations

import functools
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

FACT_ADMISSION_CONTRACT = "fact-admission-v1"

_POLICY_PATH = pathlib.Path(__file__).with_name("fact_admission_policy.yaml")


@functools.lru_cache(maxsize=1)
def policy() -> dict[str, Any]:
    return yaml.safe_load(_POLICY_PATH.read_text())


# ---------------------------------------------------------------------------
# decision surface
# ---------------------------------------------------------------------------

PASS = "PASS"
REJECT = "REJECT"
QUALIFY = "QUALIFY"


@dataclass(frozen=True)
class GateVerdict:
    outcome: str                      # PASS | REJECT | QUALIFY
    reason: Optional[str] = None      # stable reason code
    detail: Optional[str] = None      # human-readable, never parsed
    # F7 may license an orientation flip; the chain applies it.
    flip: bool = False


@dataclass(frozen=True)
class AdmissionDecision:
    outcome: str
    reason: Optional[str]
    gate: Optional[str]
    detail: Optional[str] = None
    flipped: bool = False
    contract: str = FACT_ADMISSION_CONTRACT
    policy_version: str = ""
    trace: tuple[tuple[str, str, Optional[str]], ...] = ()


@dataclass
class FactContext:
    """Everything a gate may read. Assembled once per candidate.

    Nothing here is derived inside a gate: gates are pure over this
    record, which is what makes the chain replayable and cheap
    (no document rescanning — the 289M-regex lesson).
    """
    # provenance
    doc_id: str
    chunk_id: str
    predicate: str
    # endpoints (settled state, R1)
    subject_entity_id: Optional[str]
    object_entity_id: Optional[str]
    subject_type: Optional[str] = None          # SETTLED core type
    object_type: Optional[str] = None
    subject_admission_class: Optional[str] = None
    object_admission_class: Optional[str] = None
    subject_surface: Optional[str] = None
    object_surface: Optional[str] = None
    # evidence
    trigger_surface: Optional[str] = None
    trigger_lemma: Optional[str] = None
    evidence_class: Optional[str] = None
    subject_start: Optional[int] = None
    subject_end: Optional[int] = None
    object_start: Optional[int] = None
    object_end: Optional[int] = None
    evidence_start: Optional[int] = None
    evidence_end: Optional[int] = None
    # source
    chunk_text: Optional[str] = None
    region: Optional[str] = None                 # precomputed by region.py
    # syntax (optional; absent => affected gates abstain, never guess)
    parse: Optional[dict] = None                 # syntax-evidence-v1 tokens
    scope: dict = field(default_factory=dict)    # persisted ScopeFlags
    sentence_start: int = 0


# ---------------------------------------------------------------------------
# F1 — provenance
# ---------------------------------------------------------------------------

_REQUIRED = ("doc_id", "chunk_id", "predicate",
             "subject_entity_id", "object_entity_id")


def f1_provenance(ctx: FactContext, pack: dict) -> GateVerdict:
    """A fact with no traceable origin cannot be audited, so it cannot
    be asserted. Fails closed on any missing required provenance."""
    for name in _REQUIRED:
        if not getattr(ctx, name, None):
            return GateVerdict(REJECT, "MISSING_INPUT", f"missing {name}")
    if ctx.chunk_text is None:
        return GateVerdict(REJECT, "MISSING_INPUT", "no source text")
    spans = (ctx.subject_start, ctx.subject_end,
             ctx.object_start, ctx.object_end)
    if any(s is None for s in spans):
        return GateVerdict(REJECT, "MISSING_INPUT", "no endpoint offsets")
    if not ctx.trigger_surface and not ctx.trigger_lemma:
        return GateVerdict(REJECT, "MISSING_INPUT", "no predicate evidence")
    return GateVerdict(PASS)


# ---------------------------------------------------------------------------
# F2 — region
# ---------------------------------------------------------------------------

def f2_region(ctx: FactContext, pack: dict) -> GateVerdict:
    """Structurally unsafe regions may hold evidence; they may not
    manufacture canonical relations.

    An index line ("process, 484"), a reference entry ("Nakamura, H.,
    Tanaka, A., …"), a figure caption and a bare heading are all real
    text that retrieval must keep — and all three produced wrong edges
    in the forensic sample. Region licensing is policy data
    (fact_admission_policy.yaml), versioned so a later release can
    license, say, tables without touching this code.
    """
    region = ctx.region or "BODY_PROSE"
    spec = policy()["regions"].get(region)
    if spec is None:
        return GateVerdict(REJECT, "REGION_UNKNOWN", region)
    if not spec.get("licenses_relations", False):
        return GateVerdict(REJECT, spec.get("reason", "REGION"), region)
    return GateVerdict(PASS)


# ---------------------------------------------------------------------------
# F3 — endpoint eligibility
# ---------------------------------------------------------------------------

_PRONOUN_POS = {"PRON"}


def _head_pos(ctx: FactContext, start: int, end: int) -> Optional[str]:
    """POS of the span's head token, from the persisted parse.

    Returns None when no parse covers the span — in which case the
    caller ABSTAINS from the grammatical test rather than guessing.
    """
    if not ctx.parse:
        return None
    tokens = ctx.parse.get("tokens") or []
    s = start - ctx.sentence_start
    e = end - ctx.sentence_start
    inside = [t for t in tokens
              if t.get("char_start") is not None
              and s <= t["char_start"] < e]
    if not inside:
        return None
    ids = {t.get("i") for t in inside}
    for tok in inside:                       # head = points outside the span
        if tok.get("head_i") not in ids or tok.get("head_i") == tok.get("i"):
            return tok.get("pos")
    return inside[-1].get("pos")


def f3_endpoints(ctx: FactContext, pack: dict) -> GateVerdict:
    """Both endpoints must denote something the graph can name.

    Two independent requirements, neither of them a word list (R2):

      SEMANTIC   the endpoint holds a durable identity and is
                 graph-eligible under the entity-admission boundary
                 (admission_class != MENTION_ONLY).

      GRAMMATICAL the endpoint's head token is not a pronoun. Harbor
                 currently mints CORPUS_SCOPED identities for "we" /
                 "they" / "you" (recorded upstream defect
                 ENTITY-ADMISSION-PRONOUN-CONCEPT-LEAK), so semantic
                 state alone does not stop them. A pronoun is not a
                 nameable referent, and POS is a parser fact.
    """
    from polymath_shared.neo4j_eligibility import fact_eligible_from_classes

    for side, eid, cls in (("SUBJ", ctx.subject_entity_id, ctx.subject_admission_class),
                           ("OBJ", ctx.object_entity_id, ctx.object_admission_class)):
        if not eid or eid.startswith("mention_"):
            return GateVerdict(REJECT, f"ENDPOINT_{side}_NOT_DURABLE",
                               f"{side} carries no durable identity")
        if cls == "MENTION_ONLY":
            return GateVerdict(REJECT, f"ENDPOINT_{side}_INELIGIBLE",
                               f"{side} is not graph-eligible")
    if not fact_eligible_from_classes(ctx.subject_admission_class,
                                      ctx.object_admission_class):
        return GateVerdict(REJECT, "ENDPOINT_INELIGIBLE", "endpoint pair ineligible")
    if ctx.subject_entity_id == ctx.object_entity_id:
        return GateVerdict(REJECT, "ENDPOINT_SELF_EDGE", "subject == object")

    for side, (s, e) in (("SUBJ", (ctx.subject_start, ctx.subject_end)),
                         ("OBJ", (ctx.object_start, ctx.object_end))):
        pos = _head_pos(ctx, s, e)
        if pos in _PRONOUN_POS:
            return GateVerdict(REJECT, f"ENDPOINT_{side}_PRONOMINAL",
                               f"{side} head token is a pronoun")
    return GateVerdict(PASS)


# ---------------------------------------------------------------------------
# F4 — assertion status
# ---------------------------------------------------------------------------

def _trigger_token(ctx: FactContext) -> Optional[dict]:
    if not ctx.parse or ctx.evidence_start is None:
        return None
    tokens = ctx.parse.get("tokens") or []
    s = ctx.evidence_start - ctx.sentence_start
    e = (ctx.evidence_end or ctx.evidence_start) - ctx.sentence_start
    return next((t for t in tokens
                 if t.get("char_start") is not None and s <= t["char_start"] < e), None)


def _clause_head(ctx: FactContext, trig: dict) -> Optional[dict]:
    """Nearest VERB/AUX at or above the trigger: the clause whose
    modality governs whether the trigger reports or proposes."""
    tokens = ctx.parse.get("tokens") or []
    by_i = {t.get("i"): t for t in tokens}
    tok, seen = trig, set()
    while tok is not None and tok.get("i") not in seen:
        seen.add(tok.get("i"))
        if tok.get("pos") in {"VERB", "AUX"}:
            return tok
        if tok.get("head_i") == tok.get("i"):
            return tok
        tok = by_i.get(tok.get("head_i"))
    return trig


def _governors_above(ctx: FactContext, tok: dict) -> list[dict]:
    """Tokens strictly above `tok` in the dependency chain."""
    tokens = ctx.parse.get("tokens") or []
    by_i = {t.get("i"): t for t in tokens}
    out, seen, cur = [], {tok.get("i")}, by_i.get(tok.get("head_i"))
    while cur is not None and cur.get("i") not in seen:
        seen.add(cur.get("i"))
        out.append(cur)
        if cur.get("head_i") == cur.get("i"):
            break
        cur = by_i.get(cur.get("head_i"))
    return out


def f4_assertion(ctx: FactContext, pack: dict) -> GateVerdict:
    """Did the document ASSERT this, or merely entertain it?

    Two layers, both clause-local (never a document-global keyword sweep):

      1. the persisted ScopeFlags the compiler already computed
         (negation / speculation / conditional / hypothetical /
         question), which are respected as-is;
      2. dependency-scoped modality the compiler misses. "an architect
         might make a decision to use React.js" produced an asserted
         `acquired` edge in the forensic sample: the modal `might` and
         the attitude verb `decide` both sit on the clause that governs
         the trigger, so the clause proposes rather than reports.
    """
    scope = ctx.scope or {}
    if scope.get("negated"):
        return GateVerdict(REJECT, "NEG_SCOPE", "negated clause")
    # Lexical contrast lives in the clause, not necessarily on the trigger
    # token: "varz is quite dissimilar to SNMP" carries the copula as its
    # trigger, so only scanning the window catches it.
    contrastive = {str(x).lower() for x in policy().get("contrastive_markers", [])}
    window = ""
    if ctx.chunk_text and ctx.subject_start is not None and ctx.object_start is not None:
        lo = min(ctx.subject_start, ctx.object_start,
                 ctx.evidence_start if ctx.evidence_start is not None else ctx.subject_start)
        hi = max(ctx.subject_end or 0, ctx.object_end or 0,
                 ctx.evidence_end or 0)
        window = ctx.chunk_text[lo:hi].lower()
    forms = {f for f in ((ctx.trigger_surface or "").lower().strip(),
                         (ctx.trigger_lemma or "").lower().strip()) if f}
    if forms & contrastive or any(
            re.search(rf"\b{re.escape(m)}\b", window) for m in contrastive):
        return GateVerdict(REJECT, "CONTRASTIVE",
                           "clause asserts contrast, not the relation")
    if scope.get("question"):
        return GateVerdict(REJECT, "INTERROGATIVE", "question framing")
    if scope.get("hypothetical") or scope.get("conditional"):
        return GateVerdict(REJECT, "MODALITY", "hypothetical/conditional clause")

    trig = _trigger_token(ctx)
    if trig is not None and ctx.parse:
        pol = policy()
        tokens = ctx.parse.get("tokens") or []
        head = _clause_head(ctx, trig)
        head_i = head.get("i") if head else None
        for tok in tokens:
            if tok.get("head_i") != head_i or tok.get("dep") not in {"aux", "auxpass"}:
                continue
            lemma = (tok.get("lemma") or tok.get("text") or "").lower()
            if lemma in pol["epistemic_modals"]:
                return GateVerdict(REJECT, "MODALITY",
                                   f"epistemic modal '{lemma}' governs the clause")
            if lemma in pol["deontic_modals"]:
                return GateVerdict(QUALIFY, "MODALITY_DEONTIC",
                                   f"modal '{lemma}' governs the clause")
        # An attitude verb ABOVE the trigger's clause makes the clause a
        # proposal, not a report: "decided to use", "considered adopting".
        for gov in _governors_above(ctx, head or trig):
            lemma = (gov.get("lemma") or "").lower()
            if lemma in pol["irrealis_governors"]:
                return GateVerdict(REJECT, "IRREALIS",
                                   f"attitude verb '{lemma}' governs the clause")
            for tok in tokens:
                if (tok.get("head_i") == gov.get("i")
                        and tok.get("dep") in {"aux", "auxpass"}
                        and (tok.get("lemma") or "").lower() in pol["epistemic_modals"]):
                    return GateVerdict(
                        REJECT, "MODALITY",
                        f"epistemic modal governs the matrix clause "
                        f"'{gov.get('lemma')}'")

    if scope.get("speculative"):
        return GateVerdict(QUALIFY, "SPECULATIVE", "speculative clause")
    if scope.get("attributed"):
        return GateVerdict(QUALIFY, "ATTRIBUTED", "attributed claim")
    return GateVerdict(PASS)


# ---------------------------------------------------------------------------
# F5 — predicate evidence license
# ---------------------------------------------------------------------------

def _pack_rule(pack: dict, predicate: str) -> Optional[dict]:
    return (pack.get("predicates") or {}).get(predicate)


def _trigger_forms(ctx: FactContext) -> set[str]:
    forms = set()
    for raw in (ctx.trigger_lemma, ctx.trigger_surface):
        if raw:
            forms.add(raw.strip().lower())
    return forms


def _class_expanded(rule: dict) -> set[str]:
    """Verbs the pack inherited from a VerbNet class rather than declaring.

    The pack expands `verbnet_classes` into `evidence.verbs` through
    `class_members`. That expansion is SENSE-BLIND: obtain-13.5.2 drags
    `make`, `source`, `receive` into `acquired`; use-105.1 drags `work`
    into `uses`. Membership in a class is weaker evidence than an
    explicit declaration, so it is tracked separately and licensed only
    with sense agreement (see `_licensed_by_rule`).
    """
    members = (rule.get("evidence") or {}).get("class_members") or {}
    out: set[str] = set()
    for verbs in members.values():
        out |= {str(v).lower() for v in verbs}
    return out


def _sense_agrees(rule: dict, form: str, pack: dict) -> bool:
    """Does the trigger's own sense inventory meet the predicate's?

    Uses only compiled authorities (PropBank rolesets, FrameNet frames).
    A predicate that declares neither cannot be tested, so it does not
    refuse on this basis.
    """
    ev = rule.get("evidence") or {}
    want_rs = {str(r).lower() for r in (ev.get("propbank_rolesets") or [])}
    want_fr = {str(f).lower() for f in (ev.get("framenet_frames") or [])}
    if not want_rs and not want_fr:
        # Nothing to test the inherited sense against. Class membership
        # alone is not evidence that this verb expresses this predicate:
        # `collaborate` sits in a VerbNet class expanded into similar_to
        # and produced similar_to(Google, NORAD) from "Google
        # collaborated with NORAD". Fail closed.
        return False
    try:
        from polymath_shared.rulepack.compiler import lexical_lookup
        entry = lexical_lookup(pack, form) or {}
    except Exception:
        return True
    got_rs = {str(r).lower() for r in (entry.get("propbank_rolesets") or [])}
    got_fr = {str(f).lower() for f in (entry.get("framenet_frames") or [])}
    return bool((want_rs & got_rs) or (want_fr & got_fr))


def _licensed_by_rule(rule: dict, forms: set[str],
                      pack: Optional[dict] = None) -> bool:
    ev = rule.get("evidence") or {}
    listed = set()
    for key in ("verbs", "nouns", "multiword"):
        listed |= {str(x).lower() for x in (ev.get(key) or [])}
    inherited = _class_expanded(rule)
    declared = listed - inherited

    hit_declared = bool(forms & declared) or any(
        any(f == part or f in part.split() for part in declared) for f in forms)
    if hit_declared:
        return True
    hit_inherited = forms & inherited
    if hit_inherited and pack is not None:
        return any(_sense_agrees(rule, f, pack) for f in hit_inherited)
    return bool(hit_inherited) and pack is None


def f5_predicate_evidence(ctx: FactContext, pack: dict) -> GateVerdict:
    """The observed lexical evidence must license THIS predicate, and
    must never be strengthened into a bigger claim.

    Consults the rule pack's own evidence block plus the compiled
    lexical authorities (VerbNet / PropBank / FrameNet) — no private
    verb dictionary (R3). Strength ordering lives in policy: a trigger
    that only licenses a weaker predicate cannot mint a stronger one,
    which is exactly the `use` -> `acquired` / `developed` misfire class.
    """
    rule = _pack_rule(pack, ctx.predicate)
    if rule is None:
        return GateVerdict(REJECT, "PRED_UNKNOWN", ctx.predicate)
    forms = _trigger_forms(ctx)
    if not forms:
        return GateVerdict(REJECT, "PRED_NO_TRIGGER", "no trigger evidence")

    if _licensed_by_rule(rule, forms, pack):
        return GateVerdict(PASS)

    # not in this predicate's own evidence: does it license a WEAKER one?
    pol = policy()
    strength = pol["predicate_strength"]
    mine = strength.get(ctx.predicate, 3)
    for other_id, other in (pack.get("predicates") or {}).items():
        if other_id == ctx.predicate:
            continue
        if _licensed_by_rule(other, forms, pack):
            if strength.get(other_id, 3) < mine:
                return GateVerdict(
                    REJECT, "PRED_STRENGTHENED",
                    f"trigger licenses '{other_id}' (strength "
                    f"{strength.get(other_id, 3)}) not '{ctx.predicate}' ({mine})")
            return GateVerdict(REJECT, "PRED_FRAME",
                               f"trigger licenses '{other_id}', not '{ctx.predicate}'")

    # compiled lexical resources are the last authority before refusal
    try:
        from polymath_shared.rulepack.compiler import lexical_lookup
        for form in forms:
            entry = lexical_lookup(pack, form) or {}
            frames = {str(f).lower() for f in (entry.get("framenet_frames") or [])}
            vn = {str(v).lower() for v in (entry.get("verbnet_classes") or [])}
            rolesets = {str(r).lower() for r in (entry.get("propbank_rolesets") or [])}
            ev = rule.get("evidence") or {}
            if (frames & {str(f).lower() for f in (ev.get("framenet_frames") or [])}
                    or vn & {str(v).lower() for v in (ev.get("verbnet_classes") or [])}
                    or rolesets & {str(r).lower() for r in (ev.get("propbank_rolesets") or [])}):
                return GateVerdict(PASS)
    except Exception:
        pass
    return GateVerdict(REJECT, "PRED_FRAME",
                       f"no lexical authority licenses '{ctx.predicate}' "
                       f"for trigger {sorted(forms)}")


# ---------------------------------------------------------------------------
# F6 — signature
# ---------------------------------------------------------------------------

def _signature_ok(rule: dict, subj_type: Optional[str], obj_type: Optional[str]) -> bool:
    for sig in rule.get("signatures") or []:
        if (subj_type in (sig.get("subject_core") or [])
                and obj_type in (sig.get("object_core") or [])):
            return True
    return False


def f6_signature(ctx: FactContext, pack: dict) -> GateVerdict:
    """(settled subject class, predicate, settled object class) must be
    licensed by the ontology. Fail-closed.

    R1 in force: the types read here come from the settled entity rows,
    never from the raw provider label on the mention.
    """
    rule = _pack_rule(pack, ctx.predicate)
    if rule is None:
        return GateVerdict(REJECT, "PRED_UNKNOWN", ctx.predicate)
    if not ctx.subject_type or not ctx.object_type:
        return GateVerdict(REJECT, "SIGNATURE_UNTYPED", "endpoint lacks settled type")
    if _signature_ok(rule, ctx.subject_type, ctx.object_type):
        return GateVerdict(PASS)
    return GateVerdict(REJECT, "SIGNATURE",
                       f"({ctx.subject_type} -> {ctx.object_type}) unlicensed "
                       f"for '{ctx.predicate}'")


# ---------------------------------------------------------------------------
# F7 — direction / inverse
# ---------------------------------------------------------------------------

def _head_token_in(ctx: FactContext, start: Optional[int],
                   end: Optional[int]) -> Optional[dict]:
    if not ctx.parse or start is None or end is None:
        return None
    tokens = ctx.parse.get("tokens") or []
    s, e = start - ctx.sentence_start, end - ctx.sentence_start
    inside = [t for t in tokens
              if t.get("char_start") is not None and s <= t["char_start"] < e]
    if not inside:
        return None
    ids = {t.get("i") for t in inside}
    for tok in inside:
        if tok.get("head_i") not in ids or tok.get("head_i") == tok.get("i"):
            return tok
    return inside[-1]


_SUBJ_DEPS = {"nsubj", "nsubjpass", "csubj"}
_OBJ_DEPS = {"dobj", "obj", "attr", "dative", "oprd", "acomp"}


def _syntactic_roles(ctx: FactContext) -> tuple[Optional[dict], Optional[dict], bool]:
    """(syntactic subject, syntactic object, is_passive) of the trigger's clause."""
    trig = _trigger_token(ctx)
    if trig is None or not ctx.parse:
        return None, None, False
    tokens = ctx.parse.get("tokens") or []
    head = _clause_head(ctx, trig)
    hi = head.get("i") if head else None
    kids = [t for t in tokens if t.get("head_i") == hi]
    passive = any(t.get("dep") in {"nsubjpass", "auxpass", "agent"} for t in kids)
    # An explicit agent phrase ("owned BY Cisco") marks a true agentive
    # passive whose surface subject is the patient. A stative passive
    # ("Manjaro is based ON Arch Linux") has no agent and keeps its
    # subject as the semantic subject — the two must not be conflated.
    passive = passive and any(t.get("dep") == "agent" for t in kids)
    subj = next((t for t in kids if t.get("dep") in _SUBJ_DEPS), None)
    obj = next((t for t in kids if t.get("dep") in _OBJ_DEPS), None)
    if obj is None:
        for t in kids:
            if t.get("dep") in {"prep", "agent"}:
                obj = next((x for x in tokens
                            if x.get("head_i") == t.get("i")
                            and x.get("dep") in {"pobj", "obj"}), None)
                if obj is not None:
                    break
    return subj, obj, passive


def _side_of(ctx: FactContext, tok: Optional[dict]) -> Optional[str]:
    """Which candidate endpoint does this token fall inside?"""
    if tok is None or tok.get("char_start") is None:
        return None
    pos = tok["char_start"] + ctx.sentence_start
    if (ctx.subject_start is not None
            and ctx.subject_start <= pos < (ctx.subject_end or ctx.subject_start)):
        return "SUBJ"
    if (ctx.object_start is not None
            and ctx.object_start <= pos < (ctx.object_end or ctx.object_start)):
        return "OBJ"
    return None


def f7_direction(ctx: FactContext, pack: dict) -> GateVerdict:
    """Orientation must be WITNESSED, never inherited from candidate order.

    Iteration 1 flipped inverse-trigger candidates unconditionally and
    produced part_of(GGG, payment), part_of(committee, League of Women
    Voters), part_of(MAC, Token Ring) — all inverted. The lesson: the
    candidate's subject/object order carries no orientation guarantee, so
    a blanket swap is exactly as arbitrary as no swap.

    Grammar decides instead. For "X includes Y" the syntactic subject is
    the WHOLE and the object is the PART, so part_of's subject must be
    the syntactic OBJECT. When the parse cannot establish the roles, the
    orientation is unwitnessed and nothing is asserted.

    Passive clauses are exempt from the contradiction check: the compiler
    already normalized voice onto (agent, patient), and re-deriving from
    the surface subject would undo that.
    """
    rule = _pack_rule(pack, ctx.predicate)
    if rule is None:
        return GateVerdict(REJECT, "PRED_UNKNOWN", ctx.predicate)
    symmetry = ((rule.get("direction") or {}).get("symmetry") or "asymmetric")
    if symmetry == "symmetric":
        return GateVerdict(PASS)

    spec = policy()["orientation"].get(ctx.predicate)
    if spec is None:
        # asymmetric predicate with no declared orientation evidence:
        # nothing licenses the order, so nothing may be asserted.
        return GateVerdict(QUALIFY, "DIRECTION_UNDECLARED",
                           f"no orientation policy for '{ctx.predicate}'")
    forms = _trigger_forms(ctx)
    canonical = {str(x).lower() for x in spec.get("canonical_triggers") or []}
    inverse = {str(x).lower() for x in spec.get("inverse_triggers") or []}

    def _hit(pool: set[str]) -> bool:
        return any(f in pool or any(f == p or f in p.split() for p in pool)
                   for f in forms)

    syn_subj, syn_obj, passive = _syntactic_roles(ctx)
    subj_side = _side_of(ctx, syn_subj)
    obj_side = _side_of(ctx, syn_obj)
    witnessed = subj_side is not None and obj_side is not None and subj_side != obj_side

    if _hit(inverse) and not _hit(canonical):
        if not witnessed:
            return GateVerdict(REJECT, "DIRECTION_UNWITNESSED",
                               "inverse trigger, but the parse does not "
                               "establish which endpoint is the whole")
        # inverse reading: syntactic SUBJECT is the whole, OBJECT is the part.
        if subj_side == "OBJ":
            return GateVerdict(PASS)          # candidate already part->whole
        if _signature_ok(rule, ctx.object_type, ctx.subject_type):
            return GateVerdict(PASS, "DIRECTION_FLIPPED",
                               "inverse trigger; grammar places the part second",
                               flip=True)
        return GateVerdict(REJECT, "DIRECTION_FLIP_UNLICENSED",
                           f"inverse trigger but ({ctx.object_type} -> "
                           f"{ctx.subject_type}) unlicensed")

    if _hit(canonical):
        if witnessed and not passive and subj_side == "OBJ":
            return GateVerdict(REJECT, "DIRECTION_CONTRADICTED",
                               "active clause places the candidate's object "
                               "in subject position")
        if passive and subj_side == "SUBJ":
            # "SpamCop currently owned by Cisco Systems" admitted
            # owns(spamcop, cisco) — inverted. In a passive the surface
            # subject is the PATIENT, so a candidate whose subject is that
            # surface subject is either already voice-normalized by the
            # compiler or inverted, and the persisted evidence cannot say
            # which. Ambiguous orientation is not asserted.
            return GateVerdict(REJECT, "DIRECTION_PASSIVE_AMBIGUOUS",
                               "passive clause: candidate subject is the "
                               "surface patient; orientation unresolvable")
        return GateVerdict(PASS)
    return GateVerdict(REJECT, "DIRECTION_UNLICENSED",
                       f"trigger {sorted(forms)} licenses neither orientation")


# ---------------------------------------------------------------------------
# F8 — direct support
# ---------------------------------------------------------------------------

# How far an argument may sit from its trigger in the dependency tree.
# 1 hop covers "Acme uses K8s"; the budget allows an intervening
# preposition, coordination or modifier ("built on top of Kubernetes",
# "RHEL, which uses Firewalld"). Beyond that the connection stops being
# a witnessed argument relation and becomes proximity.
_ARGUMENT_HOPS = 4

# Predicates asserted through a copula: the type must be the predicate
# nominal of that copula, never a noun buried inside its complement.
_COPULA_PREDICATES = {"is_a", "instance_of"}
_COPULAS = {"be", "is", "are", "was", "were"}


def _reachable_within(ctx: FactContext, start: dict, hops: int) -> set:
    """Token ids within `hops` dependency edges of `start` (undirected)."""
    tokens = ctx.parse.get("tokens") or []
    edges: dict = {}
    for t in tokens:
        i, h = t.get("i"), t.get("head_i")
        if i is None or h is None:
            continue
        edges.setdefault(i, set()).add(h)
        edges.setdefault(h, set()).add(i)
    seen, frontier = {start.get("i")}, {start.get("i")}
    for _ in range(hops):
        nxt: set = set()
        for node in frontier:
            nxt |= edges.get(node, set()) - seen
        if not nxt:
            break
        seen |= nxt
        frontier = nxt
    return seen


def f8_direct_support(ctx: FactContext, pack: dict) -> GateVerdict:
    """The cited span must actually witness the relationship.

    Span-local predicates need both endpoints and the trigger inside one
    sentence, with a parse path connecting them. Cross-sentence readings
    ("PostgreSQL is the datastore. The service relies on it.") are real
    knowledge that this version cannot verify, so they are preserved as
    QUALIFY(CROSS_SENTENCE) for a future discourse gate — never asserted,
    never destroyed.
    """
    if ctx.evidence_start is None:
        return GateVerdict(QUALIFY, "SPAN_SUPPORT", "no trigger offsets")
    lo = min(ctx.subject_start, ctx.object_start, ctx.evidence_start)
    hi = max(ctx.subject_end, ctx.object_end, ctx.evidence_end or ctx.evidence_start)
    text = ctx.chunk_text or ""
    window = text[lo:hi]
    if re.search(r"(?<=[.!?])\s+(?=[A-Z])", window) or "\n" in window.strip():
        return GateVerdict(QUALIFY, "CROSS_SENTENCE",
                           "endpoints and trigger span a sentence boundary")
    if not ctx.parse:
        return GateVerdict(QUALIFY, "SPAN_SUPPORT", "no parse to witness relation")

    trig = _trigger_token(ctx)
    subj_head = _head_token_in(ctx, ctx.subject_start, ctx.subject_end)
    obj_head = _head_token_in(ctx, ctx.object_start, ctx.object_end)
    if trig is None or subj_head is None or obj_head is None:
        return GateVerdict(QUALIFY, "SPAN_SUPPORT",
                           "parse does not cover trigger and both endpoints")

    # Both endpoints must be ARGUMENTS of the trigger, not merely present
    # in the same sentence. Iteration 1 admitted uses(amazon, riak) from
    # "Amazon used it for its Dynamo system. Riak, Cassandra ..." and
    # employs(PRC, pavlov) from a sentence where PRC employed techniques
    # and Pavlov was named earlier — pure co-occurrence, which this
    # reachability requirement is what rules out.
    # Copular typing predicates must bind the PREDICATE NOMINAL, not any
    # noun reachable through it. "SOC support is one of the primary
    # customers of an intelligence program" made instance_of(soc support,
    # intelligence): the complement head is `one`, not `intelligence`.
    if ctx.predicate in _COPULA_PREDICATES and (
            (ctx.trigger_lemma or "").lower() in _COPULAS):
        tokens = ctx.parse.get("tokens") or []
        head = _clause_head(ctx, trig)
        hi = head.get("i") if head else None
        comp = next((t for t in tokens if t.get("head_i") == hi
                     and t.get("dep") in {"attr", "acomp", "oprd"}), None)
        if comp is None:
            # No detectable predicate nominal is AMBIGUITY, not disproof:
            # the clause may be an apposition or the offsets may not align
            # with the parsed sentence. Preserve as evidence rather than
            # asserting or discarding.
            return GateVerdict(QUALIFY, "BINDING_NO_COMPLEMENT",
                               "copular clause has no detectable predicate nominal")
        if obj_head.get("i") != comp.get("i"):
            return GateVerdict(REJECT, "BINDING_COPULA_COMPLEMENT",
                               "object is not the predicate nominal")

    reach = _reachable_within(ctx, trig, _ARGUMENT_HOPS)
    missing = [name for name, tokn in (("subject", subj_head), ("object", obj_head))
               if tokn.get("i") not in reach]
    if missing:
        return GateVerdict(REJECT, "BINDING_NOT_WITNESSED",
                           f"{', '.join(missing)} is not a dependency argument "
                           f"of the trigger")
    return GateVerdict(PASS)


# ---------------------------------------------------------------------------
# the chain
# ---------------------------------------------------------------------------

GATES = (
    ("F1_PROVENANCE", f1_provenance),
    ("F2_REGION", f2_region),
    ("F3_ENDPOINTS", f3_endpoints),
    ("F4_ASSERTION", f4_assertion),
    ("F5_PREDICATE", f5_predicate_evidence),
    ("F6_SIGNATURE", f6_signature),
    ("F7_DIRECTION", f7_direction),
    ("F8_SUPPORT", f8_direct_support),
)


def admit(ctx: FactContext, pack: dict) -> AdmissionDecision:
    """Run the ordered chain. First REJECT wins; QUALIFYs accumulate and
    demote the outcome without stopping the chain, so the decision log
    records every reason a fact failed to be asserted, not just the
    first."""
    trace: list[tuple[str, str, Optional[str]]] = []
    qualified: Optional[tuple[str, str, Optional[str]]] = None
    flipped = False
    for name, gate in GATES:
        v = gate(ctx, pack)
        trace.append((name, v.outcome, v.reason))
        if v.flip:
            flipped = True
        if v.outcome == REJECT:
            return AdmissionDecision(
                outcome=REJECT, reason=v.reason, gate=name, detail=v.detail,
                flipped=flipped, policy_version=policy()["policy_version"],
                trace=tuple(trace))
        if v.outcome == QUALIFY and qualified is None:
            qualified = (name, v.reason or "QUALIFY", v.detail)
    if qualified is not None:
        return AdmissionDecision(
            outcome=QUALIFY, reason=qualified[1], gate=qualified[0],
            detail=qualified[2], flipped=flipped,
            policy_version=policy()["policy_version"], trace=tuple(trace))
    return AdmissionDecision(
        outcome=PASS, reason=None, gate=None, flipped=flipped,
        policy_version=policy()["policy_version"], trace=tuple(trace))
