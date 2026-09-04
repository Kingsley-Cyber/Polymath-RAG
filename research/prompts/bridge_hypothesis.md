# Bridge Hypothesis (hypothesize)
Using the selected lenses and corpus evidence, construct 2-4 EXPLICIT bridge paths from
the abstract signal toward a physical product mechanism. Every hop must be written out.
Each hypothesis (schema: hypothesis.json): id, source, path[] (each hop a short phrase),
target_mechanism, evidence_boundary.first_inference_at (the FIRST hop that is inference,
not evidence), gaps[] (plain questions real communities could answer), status=WORKING_HYPOTHESIS.
Registry motifs (reasoning_motifs.yaml) are allowed directions, not answers. Paths outside
the registry CSVs are allowed and encouraged when the lens supports them.
Forbidden: single-hop jumps (signal → product). That is the exact failure this skill exists to prevent.

## Hardened contract (2026-08-09)
Every hypothesis MUST also carry: `alternatives[]` (>=1 competing explanation you
genuinely entertained), `falsifiers[]` (>=1 observation that would kill the
bridge), a path of >=3 hops (no direct source->product jumps), and enough gaps
to cover speculation past the evidence boundary. The validator rejects anything
less BEFORE it enters state — write them properly the first time.

## Hop provenance (docs/19)
Add `hop_refs`: {"0": [corpus row ids], "1": [...]} for every hop BEFORE the
evidence boundary — the ids of the corpus_evidence (or observation) rows that
back that hop. When policy `bridge.require_hop_refs` is on the validator
rejects an evidence-side hop with no ref or with an unknown id.

## OpportunityGenesis (docs/17)

Tag each hypothesis with `genesis`: PROBLEM_LED | SHIFT_LED | TREND_LED |
DEMAND_REROUTE | CAPABILITY_LED | WORKAROUND_LED | COMMUNITY_LED |
SUPPLY_TRANSFER_LED. Do not force everything through market→problem→solution:
demand can already exist and be rerouted; a shift/trend generates hypotheses
only through its BEHAVIORAL consequences. Genesis controls emphasis, never
evidence authority.
