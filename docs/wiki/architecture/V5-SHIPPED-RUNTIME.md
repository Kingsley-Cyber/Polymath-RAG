---
change_id: V5-SHIPPED-RUNTIME
owner: governance
date: 2026-08-21
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# V5 SHIPPED RUNTIME — actual system diagram

```
                         com.polymath.v5 (LaunchAgent, boot)
                                     │
                          scripts/boot_polymath.sh
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
        docker stores        control.process_supervisor   (awaits pg)
   Postgres · Redis                  │  (14 slots, bounded restart,
   Qdrant · Neo4j                    │   quarantine, health checks)
                                     │
     ┌───────────┬───────────┬───────┼────────┬─────────────┐
     ▼           ▼           ▼       ▼        ▼             ▼
 gliner:8740 spacy:8744 embedder:8742 reranker:8743  orchestrator:7200
 (batch-probed) (own venv)                            FAST/HYBRID/GRAPH
     ▼
 control.main (ticket DAG, census, lease release, stale sweep, barriers)
     │
     ├─ intake ─ profile ─ EXTRACT ─ canonicalize ─ project_canonical
     │                        │        ─ project_neo4j ─ project_qdrant
     │                        │        ─ verify_projections
     │                        ▼
     │   batched pass-1 (one call-set/doc) → raw L1 (COPY-style bulk)
     │   lexical pass-2 → syntax (512-batched) → slice manifest
     │   rescue → L2 hypotheses (never deletes L1)
     │   evidence bundle sealed → SETTLEMENT (single authority, doc order)
     │   → mentions/entities (executemany) → candidates → compiler
     │   → L4 dispositions → facts (incl. PARKED)
     │
     └─ in-flight lease keeper (60s renew + heartbeat during long stages)

 Postgres = only authority.  L1/L2 append-only.  Projections rebuildable
 (eval/v5/reconstruct.py).  Replay: shadow_settlement + replay_full.
 Seals: eval/sealed (refuse on drift; content-hash contamination checks).
```
