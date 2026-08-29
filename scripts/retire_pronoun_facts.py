#!/usr/bin/env python
"""FACT-ENDPOINT-ELIGIBILITY-V2: retire facts with pronoun endpoints.

MEASURED before this gate: 557 of 3,184 accepted facts (17.5%) carried an
unresolved closed-class pronoun as subject or object, producing
`you --instance_of--> microsoft` and `they --uses--> ssh`.

RETIREMENT, NOT DELETION. Raw observations (mentions, span hypotheses,
relation candidates, evidence) are untouched — a pronoun remains
perfectly valid as source, mention and discourse evidence. Only the
claim that it IS a durable knowledge identity is withdrawn:

  facts.decision            ACCEPT/QUALIFY -> REJECT
  fact_admission_decisions  a row recording gate + reason (disposition
                            is retained, per contract)
  projection_receipts       active neo4j receipts deactivated so the
                            projector re-derives without them

Idempotent: re-running retires nothing new. Dry-run by default.

    python scripts/retire_pronoun_facts.py
    python scripts/retire_pronoun_facts.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.entity_admission import is_unresolved_pronoun  # noqa: E402

GATE = "FACT_ENDPOINT_ELIGIBILITY_V2"
CONTRACT_VERSION = "fact-endpoint-eligibility-v2"
POLICY_VERSION = "closed-class-pronoun-v1"
REASON = "unresolved_closed_class_pronoun_endpoint"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with tx() as conn:
        # Candidate endpoints resolved in PYTHON through the same
        # predicate admission uses — never a SQL lowercase IN-list, which
        # would also match You.com / WeWork / US / IT / WHO.
        rows = conn.execute(
            """SELECT f.fact_id, f.decision,
                      es.normalized_surface, eo.normalized_surface
                 FROM facts f
                 JOIN entities es ON es.entity_id = f.subject_id
                 JOIN entities eo ON eo.entity_id = f.object_id""").fetchall()

        # PRECISION: entities store only the NORMALIZED (lowercased)
        # surface, so "US" (the country) and "IT" (information
        # technology) arrive here as "us"/"it" and would be destroyed by
        # a naive check. Mentions retain the raw casing, so they are the
        # authority on acronym identity. MEASURED in this corpus: US
        # appears 49x, IT 6x, WHO 10x with capitalised surfaces.
        acronymic = {
            r[0] for r in conn.execute(
                """SELECT DISTINCT normalized_surface FROM mentions
                    WHERE surface = upper(surface) AND length(surface) > 1
                      AND surface ~ '^[A-Z]+$'""").fetchall()}
        print(f"protected acronym surfaces : {len(acronymic)}"
              f" (e.g. {sorted(acronymic & {'us','it','who','one'})})")

        doomed = []
        for fact_id, decision, s_norm, o_norm in rows:
            endpoints = [e for e in (s_norm, o_norm)
                         if e not in acronymic and is_unresolved_pronoun(e)]
            if endpoints and decision != "REJECT":
                doomed.append(fact_id)

        total = len(rows)
        print(f"facts examined            : {total}")
        print(f"pronoun-endpoint facts    : {len(doomed)}")
        print(f"already retired           : "
              f"{sum(1 for r in rows if r[1] == 'REJECT')}")

        if not args.apply:
            print("\nDRY RUN — pass --apply to retire")
            return 0
        if not doomed:
            print("\nnothing to retire")
            return 0

        # 1. record the disposition BEFORE mutating the fact row
        conn.execute(
            """INSERT INTO fact_admission_decisions
                   (fact_id, candidate_id, corpus_id, doc_id, outcome,
                    gate, reason, flipped, shadow,
                    contract_version, policy_version)
               SELECT DISTINCT ON (f.fact_id)
                      f.fact_id, f.fact_id, d.corpus_id, ev.doc_id,
                      'REJECT', %s, %s, true, false, %s, %s
                 FROM facts f
                 JOIN evidence ev ON ev.fact_id = f.fact_id
                 JOIN documents d ON d.doc_id = ev.doc_id
                WHERE f.fact_id = ANY(%s)
                ORDER BY f.fact_id
               ON CONFLICT DO NOTHING""",
            (GATE, REASON, CONTRACT_VERSION, POLICY_VERSION, doomed))
        # 2. withdraw the durable claim
        retired = conn.execute(
            "UPDATE facts SET decision='REJECT' WHERE fact_id = ANY(%s)",
            (doomed,)).rowcount
        # 3. deactivate derived graph receipts so the projector re-derives
        cleared = conn.execute(
            """UPDATE projection_receipts SET active = false
                WHERE projection='neo4j' AND entity_kind='fact'
                  AND active AND entity_id = ANY(%s)""",
            (doomed,)).rowcount

    print(f"\nretired facts             : {retired}")
    print(f"neo4j receipts deactivated: {cleared}")
    print("raw observations (mentions/candidates/evidence): UNTOUCHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
