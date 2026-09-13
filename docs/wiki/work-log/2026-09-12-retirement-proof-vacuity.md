---
title: "WORK LOG — the DROP-authorising proof could be satisfied by an absent measurement"
change_id: RETIREMENT-PROOF-VACUITY-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.244
architecture_impact: "hardens the two retirement scripts' pre-conditions. retire_claim_sets.py refuses when write statistics are absent and self-tests its code census against a positive control; retire_pronoun_facts.py refuses when its acronym protection set is empty. Both remain dry-run by default and owner-gated at --execute/--apply. No schema or data change."
---

> 11.243 asked whether the verifier could pass on nothing. The same question, asked of
> the script that authorises `DROP TABLE`, had worse answers.

## Contract

§1 (destructive production schema deletion is owner-gated) and §18 (a missing measurement
is `NOT_TESTED`, never green). An owner authorising a DROP is relying on this script's
verdict; that verdict must not be satisfiable by an absence.

## Changes

**`retire_claim_sets.py` — two ways a MISSING measurement read as a PERMISSIVE one.**

1. **Absent write statistics read as "never written".**
   ```python
   never_written = (not ws.get("present_in_stats")) or (ins == 0 and upd == 0 and del == 0)
   ```
   A table vanishes from `pg_stat_user_tables` after `pg_stat_reset()`, on a replica, or
   for a schema the query does not cover. "We have no evidence of writes" was being read
   as "there were none" — on the one verdict that authorises an irreversible DROP. It now
   returns `UNPROVEN` and refuses, naming the three causes.

2. **An empty census read as "nothing references this table".** The census runs
   `git grep -lEi` and treats zero hits as proof of no readers. A pattern the local grep
   cannot parse, a wrong cwd, or a renamed pattern produces exactly the same empty
   result. There is now a **positive control**: the identical pattern shape must find
   `chunks`, which the repository certainly references. If the control finds nothing the
   census machinery is broken, its empty result for `claim_sets` proves nothing, and the
   script exits rather than reporting a clean census.

**`retire_pronoun_facts.py` — the mirror risk.** Here an empty result does not block a
deletion, it **enables a larger one**: `acronymic` is the set protecting "US", "IT",
"WHO" from being deleted as pronouns, and if that query silently returns nothing, every
acronym-shaped endpoint joins `doomed`. The script now refuses when `mentions` holds rows
but the protection set is empty ("that is a broken protection query, not a corpus without
acronyms"), and refuses when `mentions` is empty at all — checked **before** the `--apply`
branch, since a check after it protects nothing.

## Proof

`tests/determinism/test_retirement_proofs_not_vacuous.py`, 7 tests:

- absent stats → `holds=False`, verdict names `pg_stat_user_tables`;
- real stats showing zero writes → still `holds=True` (strictness does not cost the real
  case);
- any lifetime write → `PROOF NO LONGER HOLDS`;
- a census that finds nothing → `SystemExit("self-test FAILED")`;
- the positive control really is present in this repo (a control that has drifted is not
  a control);
- the pronoun refusal exists **and precedes** the `--apply` branch, asserted on source
  order;
- both scripts still exit 0 and announce `DRY RUN` when run with no flags.

Live, unchanged where it should be: `claim_sets` → `exists True · rows 0 · lifetime
ins/upd/del 0/0/0 · code references NONE · DEAD_PROVEN still holds`.

## Rejected claims

- **"No stats row means the table is untouched — that is why there are no stats."**
  Rejected: `pg_stat_user_tables` lists every table in the schema regardless of activity,
  with zeros. Absence means the statistics are gone, not that the writes were.
- **"The census is fine, it found the right answer today."** Rejected as reasoning from
  the outcome. It found the right answer because the pattern happens to work here; the
  control is what makes that checkable on the day it stops.

## Open contract gaps

- Neither script's **rollback** path is tested end to end; `retire_claim_sets.py` prints
  restore DDL but nothing exercises it. It is complete-by-inspection for an empty table,
  which is weaker than a test.
