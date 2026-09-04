# Challenge (challenge)
Attack every WORKING_HYPOTHESIS as a skeptic: alternative explanations, cheaper existing
solutions, "nobody actually experiences this", motivated-reasoning check on each hop.
For each: keep status WORKING_HYPOTHESIS, or set CHALLENGED (weak hop found — record it in
challenges[]), or REJECTED (bridge indefensible). After observations exist, re-judge using
ONLY curated observations: a hypothesis whose gaps are supported may become SUPPORTED;
contradicted gaps force REJECTED. Submit updated hypotheses[] + challenges[] entries
({id, hypothesis_id, argument, verdict}).

## Starvation is not refutation (docs/20 §1)
REJECTED means the evidence spoke against the hypothesis (a contradicted gap)
or the research budget is spent. A hypothesis whose gaps simply have fewer
than three independent threads and no contradiction is CHALLENGED (or HOLD),
never REJECTED — the controller refuses that verdict and names the gaps and
queries that still need evidence.
