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
        # ACRONYM-EVIDENCE-FLOOR (2026-09-12): require MORE THAN ONE all-caps
        # occurrence. A single one is weak evidence of acronym identity — emphasis, a
        # shouted heading, a banner.
        #
        # The comment above this block used to justify itself with "MEASURED in this
        # corpus: US appears 49x, IT 6x, WHO 10x". RE-MEASURED 2026-09-12 against the
        # live database, that is STALE and no longer true of any corpus present:
        #     us -> 0 mentions · who -> 0 · one -> 0 · it -> 1 ("IT")
        #     they -> 1 ("THEY") · you -> 1 ("YOU")
        # i.e. every surface the safeguard was protecting now has exactly ONE all-caps
        # mention, so "protect anything seen once in caps" was protecting styling, not
        # acronyms. That is what kept a closed-class pronoun alive as a fact endpoint
        # and made `test_no_active_fact_has_a_pronoun_endpoint` fail permanently: the
        # gate reported a violation this tool then refused to act on, so the two never
        # converged.
        #
        # RESIDUAL AMBIGUITY, stated rather than hidden: with only one occurrence,
        # "IT" cannot be distinguished from the pronoun "it" shouted in a heading.
        # This floor makes the tool WILLING to retire it; `--apply` (owner-gated) is
        # still what actually retires anything, so the judgement stays with the owner
        # and the affected surfaces are printed below before any write happens.
        ACRONYM_MIN_MENTIONS = 2
        acronymic = {
            r[0] for r in conn.execute(
                """SELECT normalized_surface FROM mentions
                    WHERE surface = upper(surface) AND length(surface) > 1
                      AND surface ~ '^[A-Z]+$'
                    GROUP BY normalized_surface
                   HAVING COUNT(*) >= %s""", (ACRONYM_MIN_MENTIONS,)).fetchall()}
        singletons = [
            r[0] for r in conn.execute(
                """SELECT normalized_surface FROM mentions
                    WHERE surface = upper(surface) AND length(surface) > 1
                      AND surface ~ '^[A-Z]+$'
                    GROUP BY normalized_surface
                   HAVING COUNT(*) < %s""", (ACRONYM_MIN_MENTIONS,)).fetchall()]
        print(f"protected acronym surfaces : {len(acronymic)}"
              f" (>= {ACRONYM_MIN_MENTIONS} all-caps mentions;"
              f" e.g. {sorted(acronymic & {'us','it','who','one'})})")
        unprotected = sorted(s for s in singletons if is_unresolved_pronoun(s))
        if unprotected:
            print(f"single-occurrence all-caps pronouns (NOT treated as acronyms): "
                  f"{unprotected}")

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

        # PROTECTION must be PROVEN, not assumed. `acronymic` is the set that keeps
        # "US", "IT", "WHO" from being deleted as pronouns. If that query silently
        # returns nothing — a renamed table, a changed column, an empty `mentions` — the
        # protection vanishes and every acronym-shaped endpoint joins `doomed`. Unlike
        # the claim_sets census, an empty result here does not block a deletion, it
        # ENABLES a larger one, so it must be checked before `--apply`, never after.
        mention_rows = conn.execute("SELECT count(*) FROM mentions").fetchone()[0]
        if mention_rows and not acronymic:
            print(f"\nREFUSING: `mentions` holds {mention_rows} rows but the acronym "
                  f"protection set is EMPTY. That is a broken protection query, not a "
                  f"corpus without acronyms — applying now would delete every "
                  f"acronym-shaped endpoint as a pronoun.")
            return 1
        if not mention_rows:
            print("\nREFUSING: `mentions` is empty, so nothing can be protected from "
                  "this pass. Retirement needs evidence, and there is none here.")
            return 1

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
