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
| `scripts/check_install.sh` | control | loopback health endpoints | nothing | `bash scripts/check_install.sh` |
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
