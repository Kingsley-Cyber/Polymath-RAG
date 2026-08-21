# RECONSTRUCTION RUNBOOK — Polymath V5

Postgres is the sole authority. Neo4j and Qdrant are projections and can be
destroyed at any time without semantic loss.

## Neo4j wipe / rebuild

```bash
.venv/bin/python eval/v5/reconstruct.py --corpora <corpus1> <corpus2> ...
```
Wipes the graph, rebuilds every listed corpus's runs through the production
projector, and verifies `after == expected-from-Postgres` exactly (nodes and
edges; zero missing, zero extra). Pre-wipe residue from WIPED runs is
reported separately — facts of deleted runs persist in global tables and are
not reconstructable by run.

## Qdrant loss / rebuild

```bash
.venv/bin/python eval/v5/reconstruct.py --corpora <...> --qdrant-corpus <id>
```
Deletes the corpus collection, re-embeds under the pinned contract, rebuilds,
verifies exact point-count identity.

## Semantic replay (no stores involved)

```bash
.venv/bin/python eval/v5/shadow_settlement.py --corpus <id>   # ledger -> decisions
.venv/bin/python eval/v5/replay_full.py --corpus <id>         # ledger -> fact ids
```
Invariants: UNRULED_SEMANTIC_DELTA=0, SET_DIFFERENCE=0; fact-id set
IDENTICAL. Bundle integrity is verified fail-closed before any shadow.

## Expected invariants after any rebuild

- graph: projected == eligible (report.py invariant, per corpus)
- seal replay: DETERMINISTIC against stamped hashes
- zero duplicate mentions / entities / facts (content-addressed ids)

## Mid-recovery queries

FAST/HYBRID require a query_ready corpus and the reranker; GRAPH returns
documents even at zero graph facts. During a projection rebuild, queries
against the affected corpus may see partial vector/graph results — degraded
state is explicit (typed refusals for not-ready corpora), never silently
wrong (Postgres truth is untouched).
