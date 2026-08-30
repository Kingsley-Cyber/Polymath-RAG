# Managed scripts

Every repository script is declared in the scaffold `TREE`. Additions require
an owner, documented writes, a safe read-only mode when the script mutates
state, and a work-log entry.

| Script | Owner | Reads | Writes | Safe invocation |
|---|---|---|---|---|
| `scripts/scaffold_polymath_v4.py` | governance | its `TREE` and embedded content | missing declared files only | `python3 scripts/scaffold_polymath_v4.py` |
| `scripts/agent_preflight.py` | governance | repository structure and metadata | nothing | `python3 scripts/agent_preflight.py` |
| `scripts/repo_guard.py` | governance | declared paths, dependency map, work logs, optional Git diff | nothing | `python3 scripts/repo_guard.py` |
| `scripts/wiki_worm.py` | governance | `docs/wiki/` metadata | nothing | `python3 scripts/wiki_worm.py --check` |
| `scripts/check_install.sh` | control | loopback health endpoints, typed local-LLM settings, Ollama local model catalog | nothing | `bash scripts/check_install.sh` |
| `scripts/llm_quality_sample.py` | control | Postgres (facts, evidence, raw ledger, relation candidates) — read-only, seeded sample | nothing | `.venv/bin/python scripts/llm_quality_sample.py --corpus <corpus_id>` |
| `scripts/backfill_document_regions.py` | control | Postgres `chunks.text` (immutable) | `chunks` document-region roles, only with `--apply` (dry-run default; idempotent) | `python scripts/backfill_document_regions.py --corpus <corpus_id> [--apply]` |
| `scripts/boot_polymath.sh` | control | docker compose stores, Postgres readiness | starts stores + sidecars + supervised fleet (idempotent boot recovery) | `./scripts/boot_polymath.sh` |
| `scripts/mission_next.py` | governance | mission phase board (durable state) | phase board rows with `--done`/`--partial` (exit 0 work remains · 3 complete · 4 blocked) | `python scripts/mission_next.py [--status]` |
| `scripts/retire_pronoun_facts.py` | control | Postgres facts with pronoun endpoints | `facts.decision` → REJECT, `fact_admission_decisions` rows, neo4j `projection_receipts` deactivated — only with `--apply` (dry-run default; idempotent; raw observations untouched) | `python scripts/retire_pronoun_facts.py [--apply]` |
| `scripts/run_fleet_supervised.sh` | control | running stores | stops nohup-managed fleets, starts the process supervisor (bounded restart, quarantine) | `./scripts/run_fleet_supervised.sh [pipeline] [rescue] [rule_pack] [chunker]` |
| `scripts/semantic_lane_census.py` | control | durable Postgres state via the compilers' own helpers (no model calls) | nothing (`--backfill` writes census rows) | `python scripts/semantic_lane_census.py --corpus <corpus_id> [--backfill]` |
| `scripts/purge_orphan_projections.py` | control | Qdrant routing collections + Postgres derived rows vs `documents` | deletes orphan points/rows (documents deleted or moved) only with `--apply` (dry-run default; idempotent) | `.venv/bin/python scripts/purge_orphan_projections.py [--apply] [--corpus <id>]` |
| `scripts/start_kimi_stack.sh` | control | running orchestrator + sidecars | starts worker fleet in background | `./scripts/start_kimi_stack.sh` |
| `scripts/run_i4_arm.sh` | control | running orchestrator + sidecars | restarts the worker fleet for one measurement arm (pipeline/rescue/rule-pack) | `./scripts/run_i4_arm.sh kimi_v1 on 1.3.0` |
| `scripts/ingest.py` | control | manifest YAML + Postgres (plan/status read-only) | intake outbox submissions only (`run`; `plan`/`status` write nothing) | `python3 scripts/ingest.py plan --manifest <manifest.yaml>` |

No script may commit, push, delete, migrate, or repair services unless its
contract names that mutation and requires an explicit operator flag.
| `scripts/fetch_resources.py` | governance | `resources/manifests/` | `resources/vendor/` archives | `python3 scripts/fetch_resources.py --force` |
| `scripts/verify_resources.py` | governance | vendor archives + manifests | nothing | `python3 scripts/verify_resources.py` |
| `scripts/flatten_resources.py` | governance | verified vendor archives | `resources/compiled/<contract>/` | `python3 scripts/flatten_resources.py` |
| `scripts/compile_predicate_rules.py` | governance | rules YAML + compiled tables | `compiled_lexical.json` | `python3 scripts/compile_predicate_rules.py` |
| `scripts/trace_report.py` | worker | extraction_trace_events (analysis only) | nothing (stdout) | `.venv/bin/python scripts/trace_report.py surface <run_id> "<surface>"` |
