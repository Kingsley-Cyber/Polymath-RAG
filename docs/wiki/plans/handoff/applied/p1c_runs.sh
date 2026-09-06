#!/bin/zsh
cd /Users/king/Documents/polymath-rebuild/polymath-v4 || exit 1
set -a; . ./.env; set +a
P=.venv/bin/python
echo "== B after composer (deterministic) $(date +%T)"; $P scripts/chat_baseline.py --run --tag p1c-B-after --compiler on --retrieval v2 2>&1 | grep -E "\"gold_in_union\"|\"hit@10_selected\"|\"mrr_selected\"|\"survival_selected_given_union\"|\"dominance_violations\"|\"dominance_eligible_turns\"|\"wall_p50_s\"|Error" | tail -8
echo "== M after composer $(date +%T)"; $P scripts/chat_baseline.py --run --tag p1c-M-after --compiler on --retrieval v2 --fixture eval/fixtures/chat_multi_M.json 2>&1 | grep -E "\"dims_ok_rate\"|\"dims_covered_rate\"|\"dims_silent\"|\"dominance_violations\"|\"wall_p50_s\"|Error" | tail -6
echo "== B after composer (LLM: citation precision) $(date +%T)"; $P scripts/chat_baseline.py --run --tag p1c-B-llm-after --llm --compiler on --retrieval v2 2>&1 | grep -E "\"citation_precision_mean\"|\"tags_total\"|\"tags_valid\"|\"gold_cited\"|\"abstain_markers\"|\"wall_p50_s\"|Error" | tail -7
echo "== DONE $(date +%T)"
