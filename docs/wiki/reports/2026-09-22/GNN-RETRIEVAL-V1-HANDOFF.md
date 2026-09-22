---
title: "GNN-RETRIEVAL-V1 — HANDOFF (stage: implemented + qualified on the branch; NOT merged, NOT live)"
date: 2026-09-22
last_reviewed: 2026-09-22
status: handoff
owner: "@king"
---

# GNN-RETRIEVAL-V1 — handoff, 2026-09-22

## Where everything is
| Thing | Location |
|---|---|
| Branch / worktree | `experiment/gnn-retrieval` in `~/Documents/polymath-rebuild/pmv4-gnn` (worktree of polymath-v4), commits `5f65984` (the experiment) + `f461b83` (work-log dispositions); base = checkpoint tag `restoration-integrated-2026-09-22` = `production` `4176eb2` |
| `production` (main checkout, live fleet :7200) | still `4176eb2` — **GNN is NOT merged, NOT deployed**; the live UI has no GNN |
| Plan of record | `docs/wiki/plans/GNN-RETRIEVAL-V1.md` |
| Verdict | `docs/wiki/reports/2026-09-22/GNN-RETRIEVAL-V1-QUALIFICATION.md` — **D + C** (projection helps, topology not causal; duplicates existing routing) → keep experimental |
| Work-log / register | `docs/wiki/work-log/2026-09-22-gnn-retrieval-v1.md`, register row 11.401 |
| Raw results | `docs/wiki/experiments/gnn-route/cinema/{build,build-m2,qualify-m1,qualify-m2}-2026-09-22.json` |
| Owner design (controlling) | `~/Documents/polymath-rebuild/polymath_gnn_retrieval_experiment.zip` |
| Snapshot arrays (outside git) | `~/PolymathRuntime/gnn_route/cinema/gs_3673c34e9b06f569c46a9782/` |
| Qdrant (isolated, experimental) | `polymath_gnn_parent_embed_e794ec4cab197a3f_{m0-identity-real, m1-smooth-{real,nograph,shuffled}, m2-hsage-{real,nograph,shuffled}}` — production collections untouched |

## What is DONE
Backend mode (`retrieval_modes.MODE_GNN`, `gnn_route.py`, engine lane I `GNN_ROUTE`, `chat_retrieve_mode` GNN = the GNN route alone, `ui.py` accepts GNN + `retrieval.gnn` receipt) · frontend-v2 `PUBLIC_MODES += GNN` + LaneTable alias + vitest · offline half `eval/gnn_route/` + `scripts/gnn_route_build.py` / `gnn_route_qualify.py` · cinema built (M0, M1, M2 × real/nograph/shuffled) · qualification over L + B for M1 and M2 · tests: `test_gnn_route.py` 13, `test_gnn_offline.py` 6, engine pin extended · guards 0/0/0/READY on the worktree · HTTP E2E of all five modes on an experiment server (:7201, started FROM the worktree) · frontend E2E in the built-in browser on :7201 (GNN selectable, `mode:"GNN"` sent, requested = executed = GNN, union = `gnn_route` only, 12 cited; HYBRID normal afterwards).

## What is NOT done (in order)
1. ~~Attribution of the full suite~~ **DONE (2026-09-22, both trees, `-rf`, DB-free):** worktree `6 failed, 2996 passed, 16 skipped` — production `7 failed, 2976 passed, 16 skipped`. The worktree's six (`test_chat_runtime::…compiler_on…`, `test_chat_synthesis::…brainrot_transform`, `test_document_profile_stage::…receipt_chain`, `test_fact_endpoint_eligibility::…pronoun_endpoint`, `test_killchain_pass2::…identifiers…`, `test_query_receipts::…wired`) are a strict subset of production's seven (its extra one, `test_adapter_service_store::…leases…`, is a timing test). **No worktree-only failure → G18 holds; the +20 passed are the new GNN tests.** Raw lists: `/tmp/gnn_suite_worktree.txt`, `/tmp/gnn_suite_production.txt` (tmp — regenerate if needed).
2. **Merge into `production`** (owner's call; the experiment is default-off and removable): `cd ~/Documents/polymath-rebuild/polymath-v4 && git status --short` (must be empty) `&& git merge --no-ff experiment/gnn-retrieval`.
3. **Rebuild the served UI** (`frontend-v2/dist` is git-ignored; the fleet's orchestrator serves it from the MAIN checkout): `cd polymath-v4/frontend-v2 && npm run build`.
4. **ONE bounce** (per CONTINUATION.md's block: `pgrep -f control.process_supervisor | xargs kill -TERM` → wait for 0 supervisors / 0 children / nothing on :7200 → `mkdir -p /private/tmp/polymath_fleet && nohup bash scripts/boot_polymath.sh > /private/tmp/polymath_fleet/boot.log 2>&1 &` → `/ready` true, embedder + reranker, 24 healthy on ONE bundle). Fleet was idle (0 open adapter runs) all day.
5. **Live proof on :7200**: open `http://127.0.0.1:7200/v2/` → Chat → "+ New chat" → Retrieval = GNN → ask a corpus-directed question (e.g. "What do the cinema documents say about how a camera crew keeps equipment working through a shooting day?") → Query trace shows requested = executed = GNN, `gnn_route` lane only. (One paid synthesizer call.)
6. **Cleanup**: stop the experiment server `kill $(lsof -nP -iTCP:7201 -sTCP:LISTEN | tail -1 | awk '{print $2}')`; remove the untracked symlink `pmv4-gnn/frontend-v2/node_modules` (→ main's node_modules; never commit it); `git worktree remove ../pmv4-gnn` after the merge.
7. **Record**: CONTINUATION.md / CONTINUITY-REPORT.md top note ("GNN-RETRIEVAL-V1 merged at <sha>, live after bounce <time>; verdict D + C; experimental"); memory `project_polymath_gnn_retrieval_v1.md` already written.

## Rules that still bind
Never `git add -A` in polymath (stage by path) · no push of any ref · the checkpoint tag is the rollback (`git reset --hard restoration-integrated-2026-09-22` + the same bounce) · a GNN candidate is never evidence · don't claim GNN value from union growth (the controls decided: real ≤ shuffled / = no-graph) · production Qdrant collections are never written by the experiment (`project.assert_isolated`) · removal = drop the `polymath_gnn_parent_*` collections + revert; no reingest.

## Known pre-existing UI facts (not caused here)
FAST is not in the v2 public selector (backend accepts it); a first message on a scratch chat strands its stream (scratch-key remount trap, memory 2026-09-17) — "+ New chat" works.
