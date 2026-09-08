---
title: "WORK LOG — P6 intent-conditioned graph assist (HYBRID auto-attach)"
change_id: GRAPH-ASSIST-V1
date: 2026-09-08
owner: worker (live-reader graph assist, reversible + default-off)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.164
package: orchestrator/orchestrator/api/chat_retrieval.py, orchestrator/orchestrator/api/ui.py, tests/determinism/test_chat_modes.py
architecture_impact: "P6 (§37/§38): graph assist auto-activates on a HYBRID turn when the query intent is relational (RELATIONSHIP → policy.graph=auto), WITHOUT adding a 4th public mode (§2) — `chat_retrieve_mode` gains a `graph_assist` kwarg and, in the HYBRID branch, replicates the GRAPH branch's qvec-capture + bounded `_attach_graph` hop while KEEPING `meta.mode=HYBRID`. Fed from `policy_for(_plan.intent).graph` at the ui.py call site, gated behind the intent policy (default off ⇒ byte-identical). Neo4j degrades cleanly (fail-open), so auto-enable is safe. Facts ride the existing `out['graph_relationships']` side channel (never evidence — that is P7); the ui surface gate is relaxed to show them when present. `_with_graph_assist` factors the shared capture+attach."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P6** — this work-log is the EVIDENCE for that ledger row (the MD phase table is the control point; this does not duplicate it).

# WORK LOG — P6 intent-conditioned graph assist

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §37/§38/§64: graph traversal auto-enables when the
intent is relational, as an ASSIST to HYBRID — not a separate public mode (§2). Neo4j =
source-attested relationships; graph facts are never routing-inferred evidence.

Owner: `worker`. Verifier: `test_chat_modes.py` + `chat_regression --check` + a live probe.
Rollback: intent policy off / `graph_assist="off"` (default) — no attach.

## Changes

- **`chat_retrieval.py`:** `_with_graph_assist(...)` factors the qvec-capture + `_attach_graph`
  shared by GRAPH mode and the HYBRID assist; `chat_retrieve_mode` gains `graph_assist` and,
  for a HYBRID turn with `graph_assist in {auto, strong}`, attaches the bounded hop and keeps
  `meta.mode=HYBRID`.
- **`ui.py`:** compute `_graph_assist = policy_for(_plan.intent).graph` when the intent policy
  is on; pass it to `chat_retrieve_mode`; relax the streamed-facts gate to
  `ui_mode == "GRAPH" or fast.get("graph_relationships")` so assist facts surface.

## Proof

- **Flag OFF byte-identical:** `chat_regression --check` → `131 rows, 0 failing`.
- **Unit:** `test_chat_modes.py` — `graph_assist="auto"` on HYBRID attaches the bounded facts
  and keeps `meta.mode="HYBRID"`; `off`/`conditional` attach nothing. 24/24.
- **LIVE (Neo4j up, cinema):** a relational query with `graph_assist="auto"` attached **20
  facts** (seeds: 12 surfaces + 8 cards) with `mode=HYBRID`, `graph_degraded=None`;
  `graph_assist="off"` attached nothing (mode HYBRID, 0 rels).

## Rejected claims

- **Not** a 4th public mode (§2): `meta.mode` stays HYBRID; `MODE_LANES` unchanged.
- **Not** a hard change: default off ⇒ byte-identical; Neo4j down ⇒ `graph_degraded`, the
  HYBRID answer stands (fail-open).
- **Not** evidence: facts ride the side channel; they are not yet localized to source
  children (P7) and never count as routing-inferred evidence.

## Open contract gaps

- **Next (P7):** route graph DESTINATIONS through the parent-MAP localization (§39/§42):
  entity → doc_ids (entity-card `doc_ids`, currently discarded; or fact object/subject →
  `entities JOIN facts JOIN evidence`) → `search_parent_maps` → lane-E child deepening, so the
  destinations become SOURCE children the cross-encoder judges — not just a fact list.
- Graph fact VALUE depends on the corpus's Neo4j graph density; on sparse graphs the assist
  is safe (fail-open) but adds few facts.
