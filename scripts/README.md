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

No script may commit, push, delete, migrate, or repair services unless its
contract names that mutation and requires an explicit operator flag.
