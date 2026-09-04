# Evidence Judgment (web_research output standard)
You are hunting REAL USER LANGUAGE: "I wish", "I hate", "I ended up", "I had to",
"does anyone know", "too bulky", "doesn't work when", "looking for", "what do you use".
Each observation (schema observation.json): id, gap_id (which gap it addresses), source
(distinct URL/thread), quote_ref (short verbatim quote), community, problem, workaround,
desired_outcome, purchase_language (true only for buying intent), contradicts (true if it
argues AGAINST the gap). Behavior beats opinion. Adaptations beat wishes. Absence of
complaints across multiple communities is evidence AGAINST — submit it as contradicts=true.
Never fabricate quotes; every quote_ref must be recoverable from its source.

## Allocation (docs/20 §1)
The envelope carries `research_allocation`: live hypotheses ranked with the
starved ones first (open gaps below the independent-thread bar, nothing
contradicted). Work the queries in `allocation_rank` order — they are
interleaved across hypotheses on purpose. Stop a gap at three independent
threads and move to the next hypothesis; do not spend the round on the
branch whose evidence is easiest to find. A hypothesis that ends the round
starved cannot be rejected at challenge, so leaving it starved only buys
another round.
