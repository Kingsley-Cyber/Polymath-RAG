# 23 — Registry maintenance: how the CSVs grow

Owner (2026-09-03): "and the csv, is it complete?" — the seed registry is;
the skill's own tables were not growing because the maintenance graph had no
executor layer. This document is that layer's contract.

## The law (unchanged, docs/08)

Runtime discovers → maintenance evaluates → a human approves (L5) → a PATCH
is emitted → the human applies it and commits → `registry.py` compiles →
future runs consume. No run and no executor edits a live registry file.

## The walk (`graph/maintenance_graph.yaml`, all executors in `python/maintenance.py`)

| node | what happens | deterministic? |
|---|---|---|
| collect | dedupe candidates by (kind, name); stamp `runs` from the work graph's cross-run recurrence | yes |
| normalize | `slug`, `target_table`, `promotion_risk` (graph laws) | yes |
| resolve_type | draft the row each candidate would become: activities/frictions/mechanisms → a seed in the AtomicActivitySeed schema (`trailsignal/discovered_activity_niche_seed.csv`, `fact_status: hypothesis`); query patterns → `search_query_templates`; sources → `source_registry` (disabled by default); motifs → no table (held) | yes |
| deduplicate | NEW / ALIAS (token Jaccard ≥ 0.6) / MERGE (within batch) / EXISTING against the compiled snapshot | yes |
| novelty_check | NEW_SEED / NEW_ROW / EXTENDS_EXISTING / KNOWN | yes |
| evidence_review | `sufficient` when runs ≥ the kind's threshold (policies `maintenance_triggers`) and it cites observations; discovery candidates below the bar get ONE research visit, then are held | yes |
| research | agent lane (web stack); a capability_failure is an honest answer | agent |
| promotion_gate | ELIGIBLE / HELD (with reason) / EXISTING; verdict NEEDS_APPROVAL or NO_CHANGES | yes |
| human_approval | the owner submits `approvals: [{candidate_id, decision: approve\|reject\|hold, note}]` | human |
| patch | patched COPIES + a unified diff under `registry/patches/<run>/`; live files untouched | yes |
| compile_registry | compiles the overlay (live + patch) in a temp copy: valid?, seeds/templates before → after | yes |
| regression | doctor + overlay compile → `MAINTENANCE_COMPLETE` or `BLOCKED` | yes |

Vertical growth is never invented: a friction candidate whose family is not
in `friction_library` is HELD with the reason. Horizontal growth (new seeds
from existing families and predicates) is the cheap, encouraged path.

## Commands

```
python3 python/maintenance_triggers.py evaluate --create-run candidates/maint_N.json
python3 python/controller.py step --state candidates/maint_N.json        # repeat to human_approval
python3 python/controller.py submit --state … --node human_approval --file approvals.json
python3 python/controller.py step --state …                              # patch → compile → regression → publish
# then: copy registry/patches/<run>/trailsignal/* over registry/trailsignal/ and commit — that is the promotion
```

`registry/patches/` is gitignored: the patch is the review artifact, the
commit is the decision.
