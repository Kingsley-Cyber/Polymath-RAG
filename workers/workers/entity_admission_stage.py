"""ENTITY-KNOWLEDGE-ADMISSION-V1 wired into the ingest path.

The gate chain E1–E7 was built, tested, qualified and frozen, and then
had zero production callers. Reports describing "entity admission" were
describing a shadow harness while production admitted everything. This
module is the missing call site.

What a REJECT does, and does not do
-----------------------------------
It does NOT delete a mention, remove a raw proposal, or touch evidence.
The architecture's boundary is:

    filtering decides what becomes KNOWLEDGE
    it never decides whether EVIDENCE survives

So a refusal DEMOTES the interpretation to MENTION_ONLY by clearing
`durable` on the allocated identity. `_persist_mentions` already writes
`entity_id = identity.entity_id if identity.durable else None`, and
`MentionIdentity.admission_class` already reports MENTION_ONLY when not
durable, so demotion needs no new persistence path and no new column.

The surface stays readable, searchable and attributable at its exact
character offsets. It stops being a durable identity and stops being
projected as a graph node. `Figure 4-7` remains something the corpus
says; it stops being something the graph claims exists.

Shadow first
------------
Wiring and enforcing are separate. With `enforce=False` the chain runs,
records every decision, and changes nothing — so its production
behaviour can be measured against the same corpus before it governs.
That is the same discipline fact admission used, and it is what makes
the cutover a flag rather than a rewrite.
"""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import Any

from polymath_shared.entity_knowledge_admission import (
    ENTITY_ADMISSION_CONTRACT,
    EntityContext,
    admit_entity,
    policy,
)
from polymath_shared.fact_admission import EndpointAdmission
from polymath_shared.identity_allocation import span_identity_key

log = logging.getLogger("entity-admission-stage")

#: Governing is opt-in. Absent the flag the chain records and abstains.
ENFORCE_ENV = "POLYMATH_ENTITY_ADMISSION_ENFORCE"


def enforcing() -> bool:
    return os.environ.get(ENFORCE_ENV, "0") == "1"


def _region_policy_version() -> str | None:
    try:
        from polymath_shared.source_region import REGION_POLICY_VERSION
        return REGION_POLICY_VERSION
    except Exception:
        return None


def apply_entity_admission(
    conn,
    corpus_id: str,
    doc_id: str,
    ordered_slices: list[tuple[dict, Any]],
    identities: dict,
    *,
    enforce: bool | None = None,
    mention_id_for=None,
) -> dict[str, Any]:
    """Run E1–E7 over this document's spans; record, and optionally govern.

    Returns counts for the stage receipt. Mutates `identities` in place
    only when governing, and only ever by clearing `durable` — never by
    removing an entry, because a missing entry would make
    `_persist_mentions` refuse the span entirely and that would lose
    evidence.
    """
    if enforce is None:
        enforce = enforcing()

    pol = policy()
    rows: list[tuple] = []
    passed = rejected = demoted = 0
    by_gate: dict[str, int] = {}
    # Verdicts keyed exactly as FACT-ADMISSION-V1 expects them, so F3 can
    # attribute a refusal to the ENTITY layer instead of reporting "the
    # relation gate failed" for an endpoint that was never admissible.
    verdicts: dict[tuple, Any] = {}

    for row, sl in ordered_slices:
        chunk_id = row.get("chunk_id")
        # E3 indexes chunk_text with char_start/char_end DIRECTLY, and
        # SentenceSlice documents its offsets as "absolute in the chunk"
        # while `sl.text` is only the sentence. Passing the slice text
        # made every span past the first sentence read as out of range:
        # a shadow run refused 359 spans as E_SPAN_OUT_OF_RANGE, `Nir
        # Eyal` and `Barnes & Nobles` among them. The gate was right and
        # the caller was wrong -- which is the whole reason this stage
        # runs in shadow before it governs.
        chunk_text = row.get("text") or getattr(sl, "text", None)
        parse = getattr(sl, "parse", None)
        sentence_start = getattr(sl, "sentence_start", 0) or 0
        region = row.get("region") or getattr(sl, "region", None)

        for span in getattr(sl, "entities", []) or []:
            key = span_identity_key(span, corpus_id)
            identity = identities.get(key)
            if identity is None:
                # Not interpreted at the admission boundary; persistence
                # will refuse it loudly. Not this stage's call to make.
                continue

            ctx = EntityContext(
                entity_id=identity.entity_id,
                surface=span.text,
                normalized_surface=getattr(span, "normalized_surface", None)
                or span.text.strip().lower(),
                core_type=span.core_type.value if span.core_type else None,
                admission_class=identity.admission_class,
                doc_id=span.doc_id or doc_id,
                chunk_id=span.chunk_id or chunk_id,
                char_start=span.start,
                char_end=span.end,
                score=span.score,
                chunk_text=chunk_text,
                region=region,
                anchor_kind=getattr(identity.admission, "anchor_kind", None),
                decision_status=getattr(identity.admission, "decision_status", None),
                parse=parse,
                sentence_start=sentence_start,
            )

            decision = admit_entity(ctx)
            is_reject = decision.outcome != "PASS"

            did_demote = False
            if is_reject:
                rejected += 1
                by_gate[decision.gate or "?"] = by_gate.get(decision.gate or "?", 0) + 1
                if enforce and identity.durable:
                    # The ONLY mutation this stage performs. Frozen
                    # dataclass, so replace rather than mutate: the span
                    # keeps its mention row, loses its durable identity.
                    identities[key] = replace(identity, durable=False)
                    did_demote = True
                    demoted += 1
            else:
                passed += 1

            verdicts[(identity.entity_id, span.start, span.chunk_id or chunk_id)] = (
                EndpointAdmission(admitted=not is_reject,
                                  reason=decision.reason if is_reject else None))

            mid = (mention_id_for(span) if mention_id_for
                   else f"{span.chunk_id or chunk_id}:{span.start}:{span.end}")
            rows.append((
                identity.entity_id, mid, corpus_id, span.doc_id or doc_id,
                span.chunk_id or chunk_id, span.text,
                span.core_type.value if span.core_type else None,
                "REJECT" if is_reject else "PASS",
                decision.gate, decision.reason,
                not enforce, did_demote,
                ENTITY_ADMISSION_CONTRACT, pol["policy_version"],
                _region_policy_version(),
            ))

    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO entity_admission_decisions
                    (entity_id, mention_id, corpus_id, doc_id, chunk_id,
                     surface, core_type, outcome, gate, reason, shadow,
                     demoted, contract_version, policy_version,
                     region_policy_version)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (mention_id, contract_version, policy_version)
                DO UPDATE SET outcome = EXCLUDED.outcome,
                              gate = EXCLUDED.gate,
                              reason = EXCLUDED.reason,
                              shadow = EXCLUDED.shadow,
                              demoted = EXCLUDED.demoted,
                              decided_at = now()
                """,
                rows,
            )

    summary = {
        "contract": ENTITY_ADMISSION_CONTRACT,
        "policy_version": pol["policy_version"],
        "enforced": bool(enforce),
        "considered": passed + rejected,
        "passed": passed,
        "rejected": rejected,
        "demoted": demoted,
        "by_gate": by_gate,
        # Consumed by the fact stage in the same document pass; never
        # persisted, because the durable record is the decisions table.
        "verdicts": verdicts,
    }
    if rejected:
        log.info("entity admission: %d/%d refused (%s)%s",
                 rejected, passed + rejected,
                 ", ".join(f"{g}={n}" for g, n in sorted(by_gate.items())),
                 "" if enforce else " [shadow: nothing demoted]")
    return summary
