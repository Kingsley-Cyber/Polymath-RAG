---
change_id: ENRICHMENT-AUDIT-OWNER-INTENT
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents and one read-only evidence script. The enrichment audit gains a full field inventory (§8), the owner's statement of intent with the code-level root cause (§9), and fixes revised to wire the fields in (§6). No code, flag, schema or data change."
last_reviewed: 2026-09-23
---

# ENRICHMENT-SURFACES-AUDIT addendum — every field, the owner's intent, and why enrichment chunks die at the judge

## Contract
The owner, same day, after reading the audit (11.415):
1. "For the 4 list the skeleton you found, it's more than see also."
2. "The purpose of them is for them to be used at query time in some form or way to create the conditional rank system to
   win and to bring about different abstract level of information winning upon retrieval and synthesis, and allow more
   bridges and hops, so the compiler bridging must use it in some form or fashion.
3. "GNN is excluded since it's its own thing; however, for graph, see more can be used for hops or traversals.
4. "I think it got complicated due to the subqueries being added in the equations, and the coding session didn't know how
   to handle dropped chunks when ranked against my original queries, even if the chunks retrieved actually reflected
   information subdued and latent but actually relevant to my query."

## Changes
- `docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md`:
  - §8: field inventory of the v3.2 profile (9 fields), the parent skeleton (12 fields), the pMAP and the vNext atoms;
  - §9: the owner's intent, the code path that drops enrichment chunks, and the survival gradient;
  - §6: revised to wire the fields in: no field is removed, and the root cause comes first;
  - §1: the lift row now names only the lift-only inputs (aliases, exact identifiers, terms). pMAP hooks, topics and
    headings also reach answers by other paths;
  - status line and reruns updated.
- NEW `docs/wiki/experiments/enrichment-surfaces-2026-09-23/field_inventory.py` / `.json`: profile and pMAP field totals for a
  corpus.
- `receipt_audit.py` / `.json`: adds `pre_rerank_alone` per lane (pool entries no other lane found). All other numbers are
  unchanged (rerun).
- Register 11.416; scaffold `TREE` entries for the 3 new files; CONTINUITY CURRENT block updated.

## Proof
- EXECUTED (read-only, $0): `field_inventory.py` (cinema: 67 / 67 v3.2 profiles, 5,151 list items; 11,993 maps, 35,838 hooks,
  41,350 exact identifiers, 1,023 maps with `A1`-shaped ids), and the `receipt_audit.py` rerun (pool → evidence survival per
  lane).
- READ (anchors re-read at `7eb767d`; the code is unchanged since):
  - `identity` = `one` + "Topics: …" (`compiler.py:909-912`); `theme` = `summary` (`:914-917`);
  - representations carry no `terms` (`:936-944`);
  - `profile_nominate` defaults to `ANSWER_SURFACES`, and none of its three callers passes `surfaces`
    (`ui.py:1724`, `chat_retrieval.py:329`, `:355`);
  - `EXPLORATION_SURFACES` has no production reader;
  - the pMAP vector text = signature + hooks + compact heading (`parent_map_projection.py:64-75`);
  - enrichment lanes D–I attach `query_ids=[ctx.query_id]` (`candidate_engine.py:814, 846, 863, 882, 900, 919`);
  - `lineage_class` puts q0's lanes in Q0 (`ranked_fusion.py:82`);
  - winners are preserved per query (`:159`);
  - one judge call against `result.context.query` (`candidate_engine.py:1447`);
  - the WLK2C conditional pass covers the bridge pool only (`ui.py:2140-2206`).
- Guards: see the commit.

## Rejected claims
- "Profile topics are dead": they are pooled into the `identity` vector text, so they route as one string per document. Only
  `terms` is lift-only. The 11.415 §1 row was corrected.
- "Stop producing the unread fields" (an option in the 11.415 fix 4): withdrawn. The owner's intent is query-time use, so the
  fixes wire them in.
- "The conditional rank system is missing": it exists (LATENT-QUERY-FUSION-V2 fusion + WLK2C). It keys lineage by query, and
  enrichment lanes run under q0's identity, so they never enter it.

## Open contract gaps
- None changed (documents and a read-only script): NOT_AFFECTED.
- The seven fixes in report §6 are DEFERRED to the owner's word, one slice each. Fix 4's multi-hop part touches the deferred
  "Graph traversal / bounded multi-hop" item and is BLOCKED until the owner lifts that deferral; the one-hop part is not.
