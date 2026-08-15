"""I1 manifest-driven bulk ingestion CLI (scripts/ingest.py).

Subcommands:
  plan    read-only per-source action plan (no writes, ever)
  run     submit only contractually required intake work
  status  reconciliation report from authoritative run state

The manifest declares WHAT should be ingested; the control plane
decides what remains to be done; workers perform the existing
pipeline. This CLI never invokes workers directly and never bypasses
outbox, leases, receipts, census, or verification.

Completion is NEVER inferred from subprocess exit codes — the status
report reads authoritative Postgres run state.

Safe invocation:
  .venv/bin/python scripts/ingest.py plan --manifest path/to/manifest.yaml
  .venv/bin/python scripts/ingest.py run  --manifest path/to/manifest.yaml [--batch-size N] [--dry-run]
  .venv/bin/python scripts/ingest.py status --manifest path/to/manifest.yaml

Paths resolve relative to the MANIFEST file, not the process cwd.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.manifest import ManifestError, load_manifest  # noqa: E402
from control.manifest_ingest import execute_manifest, plan_manifest, status_manifest  # noqa: E402


def _load(args) -> dict:
    try:
        return load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"MANIFEST ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)


def cmd_plan(args) -> int:
    doc = _load(args)
    with tx() as conn:
        plan = plan_manifest(conn, doc, args.manifest)
    print(json.dumps(plan, indent=2))
    return 0


def cmd_run(args) -> int:
    doc = _load(args)
    with tx() as conn:
        result = execute_manifest(
            conn, doc, args.manifest,
            batch_size=args.batch_size, dry_run=args.dry_run,
        )
    print(json.dumps(result, indent=2))
    return 0


def cmd_status(args) -> int:
    doc = _load(args)
    with tx() as conn:
        report = status_manifest(conn, doc, args.manifest)
    print(json.dumps(report, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--manifest", required=True, help="path to the manifest YAML")

    p_plan = sub.add_parser("plan", parents=[common], help="read-only action plan")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sub.add_parser("run", parents=[common], help="submit required intake work")
    p_run.add_argument("--batch-size", type=int, default=32,
                       help="max intake submissions per invocation (default 32)")
    p_run.add_argument("--dry-run", action="store_true",
                       help="compute submissions without writing anything")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", parents=[common], help="reconciliation report")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
