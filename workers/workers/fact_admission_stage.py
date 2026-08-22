"""FACT-ADMISSION-V1 wired into the ingest path — the last court.

This is the boundary the graph was missing. The pipeline behaved as:

    GLiNER -> candidate entities -> relations -> Neo4j

with no court deciding whether an intermediate evidence object had
earned the right to become knowledge. The architecture it must be is:

    GLiNER            "possible mention"
      |
    ENTITY ADMISSION  "valid identity"          E1-E7
      |
    spaCy + predicate compiler
      |                "possible relation"
    FACT ADMISSION    "asserted knowledge"      F1-F8
      |
    Neo4j             settled knowledge only

Two DIFFERENT failure modes, two different layers
-------------------------------------------------
The predicate compiler answers *does this verb actually mean this
relationship?* It is why `similar_to` must not inherit `collaborate`,
`banter` and `plot` from a VerbNet class.

F3 ENDPOINTS answers a question the compiler cannot: *are the things
being connected allowed to exist as graph nodes at all?* For

    "You acquired Hooked."

the compiler is content -- `acquired` is a licensed trigger. The entity
layer is not: `You` is a pronoun with no durable identity. Only F3 can
refuse that fact, and it refuses it for a reason attributed to the
ENTITY layer, so forensics can distinguish "the relation gate failed"
from "the endpoint was never admissible".

Neither layer subsumes the other. Both are required.

What a refusal costs
--------------------
Nothing that is evidence. The relation candidate is already persisted
as an L4 row before this runs, so a refused fact leaves behind the
complete record of what was proposed and why it was refused. What a
refusal withholds is the ASSERTION -- the T2 fact and its graph edge.

Shadow first, exactly as the entity stage: with `enforce=False` the
chain runs, records every decision, and changes nothing.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from polymath_shared.fact_admission import (
    FACT_ADMISSION_CONTRACT,
    EndpointAdmission,
    FactContext,
    admit,
    policy,
)

log = logging.getLogger("fact-admission-stage")

ENFORCE_ENV = "POLYMATH_FACT_ADMISSION_ENFORCE"


def enforcing() -> bool:
    return os.environ.get(ENFORCE_ENV, "0") == "1"


def _region_policy_version() -> str | None:
    try:
        from polymath_shared.source_region import REGION_POLICY_VERSION
        return REGION_POLICY_VERSION
    except Exception:
        return None


class FactAdmissionStage:
    """Per-document accumulator so decisions are written in one round trip."""

    def __init__(self, corpus_id: str, doc_id: str,
                 entity_verdicts: dict | None = None,
                 enforce: bool | None = None):
        self.corpus_id = corpus_id
        self.doc_id = doc_id
        self.entity_verdicts = entity_verdicts or {}
        self.enforce = enforcing() if enforce is None else enforce
        self.rows: list[tuple] = []
        self.passed = self.qualified = self.rejected = 0
        self.withheld = 0
        self.by_gate: dict[str, int] = {}

    # -- the decision -------------------------------------------------------

    def admits(self, *, row: dict, candidate, decision, sl,
               identities: dict | None = None) -> bool:
        """Run F1-F8. Returns whether the fact may be ASSERTED.

        In shadow this always returns True: the chain records what it
        would have done and the caller persists exactly as before.
        """
        fact = getattr(decision, "fact", None)
        if fact is None:
            return True

        pack = _pack()
        subj, obj = candidate.subject, candidate.object
        chunk_id = row.get("chunk_id")

        def _endpoint(entity_id, span) -> EndpointAdmission | None:
            if entity_id is None or span is None:
                return None
            return self.entity_verdicts.get(
                (entity_id, getattr(span, "start", None), chunk_id))

        ctx = FactContext(
            doc_id=self.doc_id,
            chunk_id=chunk_id,
            predicate=getattr(fact, "predicate", None) or "",
            subject_entity_id=getattr(fact, "subject_id", None),
            object_entity_id=getattr(fact, "object_id", None),
            subject_type=_type_of(subj),
            object_type=_type_of(obj),
            subject_admission_class=_class_of(subj, identities),
            object_admission_class=_class_of(obj, identities),
            subject_surface=getattr(subj.span, "text", None),
            object_surface=getattr(obj.span, "text", None),
            trigger_surface=getattr(candidate, "trigger_surface", None),
            trigger_lemma=getattr(candidate, "trigger_lemma", None),
            evidence_class=getattr(candidate, "evidence_class", None),
            subject_start=getattr(subj.span, "start", None),
            subject_end=getattr(subj.span, "end", None),
            object_start=getattr(obj.span, "start", None),
            object_end=getattr(obj.span, "end", None),
            chunk_text=row.get("text"),
            region=row.get("region"),
            parse=getattr(sl, "parse", None),
            sentence_start=getattr(sl, "sentence_start", 0) or 0,
            subject_entity_admission=_endpoint(
                getattr(fact, "subject_id", None), subj.span),
            object_entity_admission=_endpoint(
                getattr(fact, "object_id", None), obj.span),
        )

        verdict = admit(ctx, pack)
        outcome = verdict.outcome
        if outcome == "PASS":
            self.passed += 1
        elif outcome == "QUALIFY":
            self.qualified += 1
        else:
            self.rejected += 1
            self.by_gate[verdict.gate or "?"] = (
                self.by_gate.get(verdict.gate or "?", 0) + 1)

        # QUALIFY is never asserted knowledge (R4). It is retained as T1.
        may_assert = outcome == "PASS"
        withheld = self.enforce and not may_assert
        if withheld:
            self.withheld += 1

        pol = policy()
        self.rows.append((
            getattr(fact, "fact_id", None),
            getattr(candidate, "candidate_id", None) or getattr(fact, "fact_id", None),
            self.corpus_id, self.doc_id,
            outcome, verdict.gate, verdict.reason,
            bool(getattr(verdict, "flipped", False)),
            not self.enforce,
            FACT_ADMISSION_CONTRACT, pol["policy_version"],
            _region_policy_version(),
        ))
        return (not self.enforce) or may_assert

    # -- persistence --------------------------------------------------------

    def flush(self, conn) -> dict[str, Any]:
        if self.rows:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO fact_admission_decisions
                        (fact_id, candidate_id, corpus_id, doc_id, outcome,
                         gate, reason, flipped, shadow, contract_version,
                         policy_version, region_policy_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (fact_id, candidate_id, contract_version,
                                 policy_version)
                    DO UPDATE SET outcome = EXCLUDED.outcome,
                                  gate = EXCLUDED.gate,
                                  reason = EXCLUDED.reason,
                                  flipped = EXCLUDED.flipped,
                                  shadow = EXCLUDED.shadow,
                                  decided_at = now()
                    """,
                    self.rows,
                )
        total = self.passed + self.qualified + self.rejected
        summary = {
            "contract": FACT_ADMISSION_CONTRACT,
            "enforced": self.enforce,
            "considered": total,
            "passed": self.passed,
            "qualified": self.qualified,
            "rejected": self.rejected,
            "withheld_from_graph": self.withheld,
            "by_gate": self.by_gate,
        }
        if total:
            log.info("fact admission: %d/%d asserted%s (%s)",
                     self.passed, total,
                     "" if self.enforce else " [shadow: nothing withheld]",
                     ", ".join(f"{g}={n}" for g, n in sorted(self.by_gate.items()))
                     or "no refusals")
        return summary


# ---------------------------------------------------------------------------

def _pack() -> dict:
    from polymath_shared.rulepack import load_rule_pack
    return load_rule_pack()


def _type_of(endpoint) -> str | None:
    ct = getattr(getattr(endpoint, "span", None), "core_type", None)
    return getattr(ct, "value", None) if ct is not None else None


def _class_of(endpoint, identities) -> str | None:
    """The SETTLED admission class, read from the identity map.

    Never recomputed here: a second interpretation of the same span is
    the divergence the single admission boundary exists to remove.
    """
    if not identities:
        return None
    span = getattr(endpoint, "span", None)
    if span is None:
        return None
    for ident in identities.values():
        if getattr(ident, "entity_id", None) == getattr(span, "entity_id", None):
            return ident.admission_class
    return None
