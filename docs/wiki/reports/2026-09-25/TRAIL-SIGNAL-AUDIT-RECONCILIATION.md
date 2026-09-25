---
title: "Reconciliation: the external Trail Signal holistic audit against the code (2026-09-25)"
date: 2026-09-25
last_reviewed: 2026-09-25
status: "RECONCILED — register 11.484; confirmed items are gap rows A-01..A-08 (+ T-01, K-01, K-02 already open)"
owner: "@king"
---

# Reconciliation: the Trail Signal holistic audit (external, 2026-09-25)

**Verdict.** The audit's FAIL is about the owner's full vision: a knowledge system that wakes itself, explores the
corpus and carries justified discoveries forward. It does not say the document RAG or the governed product-research
workflow is broken. Of its 17 findings:
- 11 were re-checked here by reading the code and are confirmed. Ten become new gap rows A-01..A-08 (three of them share
  A-08); the source-role finding was already open (K-01, K-02);
- 1 is already owned: T-01 holds the Trail judgement defects. The audit also credits one fix to 11.478 (the MCP truncation
  marker);
- 1 was not re-checked;
- 2 are unknown until the owner authorizes live runs, and 2 are questions only the owner can answer.

The audit is stored verbatim beside this file (`TRAIL-SIGNAL-HOLISTIC-AUDIT.md`). Evidence class of every re-check below:
READ at production `0e2451e4` (no tests or live calls were needed).

## Per finding

| Audit | Claim (short) | Re-check (READ) | Where it lives now |
|---|---|---|---|
| REQ-01 | Nothing starts a discovery run from a state change | CONFIRMED. The only production caller of `service.start` is the API (`orchestrator/orchestrator/api/adapter.py:55`). `control/control/main.py` has no adapter, Trail or discovery reference. The standalone `maintenance_triggers` is called only by its own module and `adapters/ecommerce/tests/run_all.py`. | **A-01** |
| REQ-02 | A started run waits for a connected client at agent / harness steps | CONFIRMED by design. The worker docstring says "HARNESS_ACTION steps are never executed here — the host harness answers them through adapter_submit" (`workers/workers/adapter_step_worker.py:14-15`), and AGENT_REASON steps wait for an agent the same way. No dispatcher was found. | **A-02** |
| REQ-03, REQ-12, REQ-13 | No corpus-wide exploration frontier, no governed maintenance feed, no reactivation of stale or blocked work | CONFIRMED only as absence: the maintenance creator has no production caller (above), and nothing consumes invalidation or capability-return events. These build on A-01. | **A-08** |
| REQ-04 | "No useful signal" does not end the run cleanly | CONFIRMED. `C_primitives` may output `generative_signal: false`, but `C_lineage_route` branches only on `steps.C_lineage.output.valid` (false → repair, or `Z_refuse_lineage`); every valid lineage goes to `C_population` (`config/adapters/ecommerce.product_research.json`). The standalone `signal_gate` (`adapters/ecommerce/python/executors.py:69-78`, NO_GENERATIVE_SIGNAL "is a SUCCESS outcome") is registered only for the standalone engine (`executors.py:797`). | **A-03** |
| REQ-05 | The user's research limits do not reach research | CONFIRMED. The input schema accepts `geography`, `freshness_days`, `constraints`, `exclusions`, `category`. The worker's Trail payload (`_payload_for`, `adapter_step_worker.py`) sends stage, hypotheses, admitted evidence, priors and gaps, and none of those fields. Trail compiles every directive with `geography=None, language=None` (`governance/trail/src/trail_signal/contexts/workflow/application/research_operations.py:253, 258, 282`). | **A-04** |
| REQ-06 | Trail judgement defects M1-01..03 remain | ALREADY OPEN: **T-01**. A repair changes the defect-preserving tests, so it needs the owner's explicit authorization. | T-01 |
| REQ-07 | A closed research question can come back; the loop exits on Trail's gaps only | CONFIRMED. Ledger gaps are filtered by `status == "open"`, but agent `open_gaps` from every non-Trail output and bridge gaps are offered again. Each gets its own origin-based id, and nothing checks the ledger's closed status across origins (`shared/polymath_shared/adapter/research_gaps.py:84-98`). `M_loop` branches only on `steps.L_judge.output.open_gaps` (manifest). | **A-05** |
| REQ-08 | The final citation check misses reference fields | CONFIRMED. `_cited_ids` collects only keys ending in `_ids` (`shared/polymath_shared/adapter/transitions.py:192-206`); `*_refs` keys and `evidence_chain` items are not checked against the run's records. | **A-06** |
| REQ-09 | The CSV is registry input, not a joined runtime record | Accurate reading of the design; whether a CSV deliverable is wanted is an owner question (below). | owner question |
| REQ-10 | Reference-only scope is missing (code could reach general ideation) | ALREADY OPEN: **K-01, K-02** (no `knowledge_role` / source-use anywhere in runtime code, re-checked by grep). The audit agrees with the roadmap: K1 before C1. | K-01, K-02 → K1 |
| REQ-11 | Legacy clipping without completeness metadata; graph-fact rows excluded from intake | NOT RE-CHECKED here. The audit credits 11.478's MCP truncation marker as fixed. | carried in this file |
| REQ-14 | Today's hosted MCP completion | UNKNOWN: needs the existing hosted acceptance run (the owner's word). | Live Qualification Queue |
| REQ-15 | Browser "WebMCP" | Hosted HTTP MCP exists; no browser `modelContext` binding. Needed only if the owner meant the browser standard. | owner question |
| REQ-16 | Arbitrary-source cross-domain quality | UNKNOWN: the frozen non-presupposing benchmark (G8) is unrun and needs the owner's words. | Live Qualification Queue |
| REQ-17 | The older `trail.product_discovery` workflow lacks the restored meaning | CONFIRMED for the semantic view: `config/adapters/trail.product_discovery.json` never opts into `context.semantics.trail`, while `ecommerce.product_research` (0.6.0) does. Both are listed to clients. | **A-07** |

## Proposed order (the owner decides)

1. **K1 stays next** (roadmap row 6b; K-01, K-02). The audit also puts it before any code ingestion.
2. **Then an A-track of small correctness slices on the governed workflow**, which the audit puts before any automation:
   - A-03: route `generative_signal: false` to a clean "retained as knowledge" end before population / hypotheses;
   - A-04: carry geography / freshness / constraints into the Trail payload and directives;
   - A-06: check `*_refs` and `evidence_chain` against the run's records;
   - A-05: close a gap across origins and keep a required unresolved gap visible at exit;
   - A-07: say which adapter is the preferred entry (no silent retirement).
3. **Automation (A-01, A-02, A-08) only after an owner mandate:**
   - what may start by itself (e.g. a source revision becoming queryable);
   - what research may run without a human;
   - who approves registry publication.
   Build it inside the existing control tick and adapter runtime, never as a second scheduler.
4. **T-01** when the owner authorizes changing the defect-preserving M1 tests.

## Owner questions

1. "WebMCP": the hosted MCP (nothing to build), or the browser standard?
2. Is a CSV deliverable required? If yes, it is a projection of the run's records, never a new write authority.
3. The autonomy mandate (item 3 above).
4. T-01: may the M1 defect-preserving tests be reconciled in the repair?
5. Order: the A-track after K1 (proposed), or before it?
