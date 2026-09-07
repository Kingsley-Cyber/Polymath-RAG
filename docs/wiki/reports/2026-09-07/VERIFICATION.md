---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# VERIFICATION — what was executed to validate this state (2026-09-07 closeout)

All commands run from `/Users/king/Documents/polymath-rebuild/polymath-v4` with `.venv/bin/python` unless stated. "Result" is the observed output; "Interpretation" is what it establishes and nothing more.

```text
Command: git branch --show-current; git status --short; git worktree list; git branch -a; git log --oneline --decorate -n 14; git stash list
Purpose: capture the starting Git state
Result: branch architecture/evidence-first-v5; status empty; worktrees polymath-v4 (branch) + polymath-v4-main (main) both 22f93c3; branches main, architecture/evidence-first-v5, origin/main, origin/architecture/evidence-first-v5 all 22f93c3; no stash
Interpretation: nothing uncommitted; branch and main identical locally and remotely
```

```text
Command: git status --short --ignored | grep '^!!' (filtered of caches)
Purpose: account for ignored paths before any cleanup
Result: .env, .ruff_cache/, graphify-out/, research/registry/compiled/, research/state/, resources/vendor/{nltk,propbank-frames.zip,semlink.zip,verbnet-3.3.zip}, shared/polymath_shared.egg-info/, sidecars/{gliner_runtime,spacy_runtime}/
Interpretation: runtime data, vendored resources, build artefacts — intentionally ignored; none removed
```

```text
Command: .venv/bin/python scripts/repo_guard.py
Purpose: repository rules (declarations, script registry, work-log for code changes, forbidden files)
Result: "repo guard: ok", exit 0 (before the handoff files; re-run after declaring them — see final section)
Interpretation: tree conforms to the scaffold
```

```text
Command: .venv/bin/python scripts/wiki_worm.py --check
Purpose: wiki front-matter and open-work audit
Result: lists open work-logs (expected: append-only records with open gaps) and prints "wiki: ok"
Interpretation: every wiki file has valid front-matter
```

```text
Command: .venv/bin/python scripts/agent_preflight.py
Purpose: agent preflight (CI job "agent-preflight" equivalent)
Result: "preflight: ok"
Interpretation: bootstrap invariants hold
```

```text
Command: .venv/bin/python -m pytest -q tests/determinism/test_document_profile_stage.py test_document_profile_compiler.py test_document_profile_context.py test_document_profile_projection.py test_fleet_autopilot_demand.py test_control_plane_v2.py test_fleet_v3_limits.py test_no_legacy_sidecars.py test_supervisor_env_overlay.py test_chat_model_catalog.py test_chat_retrieval_v2.py -p no:cacheprovider   (shell WITHOUT .env sourced)
Purpose: every suite touching today's subsystems, plus the chat-retrieval suite that fails under a .env-sourced shell
Result: 75 passed, exit 0
Interpretation: today's code is pinned green; the earlier local failure of test_chat_retrieval_v2 was the shell's POLYMATH_CHAT_RERANK_DEADLINE_S=12, not code
```

```text
Command: (earlier today, .env sourced) .venv/bin/python -m pytest -q tests/determinism
Purpose: full determinism suite
Result: 4 failures — test_chat_retrieval_v2 rerank_deadline_s pin (env), test_incremental_census parity (project_qdrant backlog moved between passes: 14048 vs 14028), test_fact_endpoint_eligibility (one live pronoun endpoint "you" in dev facts data), test_supervisor_env_overlay (passed alone; flaked during the fleet boot)
Interpretation: none attributable to today's changes; CI (clean env, fresh DB) is green on the same tree — see next entry. Recorded as UNFINISHED_WORK U11
```

```text
Command: gh run list --commit 0c78579 / --commit 22f93c3 (via scratchpad ci_wait_ff.sh); git -C ../polymath-v4-main merge --ff-only; git push origin main
Purpose: CI gate and fast-forward for the two implementation commits
Result: 0c78579: agent-preflight, contracts, determinism, repo-governance all success → main → 0c78579 (09:18 local); 22f93c3: all four success → main → 22f93c3 (09:23 local)
Interpretation: main carries only CI-green commits
```

```text
Command: curl 127.0.0.1:7200/ready; :8742/ready; :8743/ready; SQL counts on stage_tickets
Purpose: live fleet state at closeout
Result: 200 / 200 / 200; project_qdrant open 19; doc_profile open 0; doc_profile tickets done 67; artifacts with doc_profile 67; profile points 67
Interpretation: fleet healthy; backfill terminal; routing re-projection still draining (the reason the rerank deadline stays at 12 s)
```

```text
Command: .venv/bin/python scripts/document_profile_gate.py --corpus cinema --per-doc 3 --tag gate1
Purpose: self-retrieval gate over the 67 profiles
Result: documents 67, probes 400, self_top1_rate 0.858, self_top3_rate 0.995, median_rank 1, 0 misses, 2 probes beyond rank 3; punch question top-15 includes The Laban Workbook (6) and Your Move (15)
Interpretation: the profile collection retrieves its own documents; the plan's Laban gate is met through the profile lane alone. Output: docs/wiki/experiments/document-profile-gate-gate1.json
```

Not tested in this closeout: `tests/integration` (needs the full live stack in a known state; not run today), frontend build (unchanged today), migrations against a fresh container (CI's determinism job does this on every push and was green), the retrieval lane (does not exist yet).

## Final state after the closeout commit
(appended below by the closeout pass)
