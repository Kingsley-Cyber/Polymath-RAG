#!/usr/bin/env python3
"""LANE-REGISTRY-V1 operator entrypoint (RAG-PIPELINE-FINISH Phase 2/3 gate).

Prints the sanitized account/model lane inventory — every functional pool's lanes,
their account (api_key_env NAME only), declared capacity seed, reachability, and the
cross-function credential-sharing audit — WITHOUT making any provider call and
WITHOUT rendering any secret value.

    Owner   : governance (read-only diagnostic)
    Inputs  : config/cloud_providers.json, config/extraction_models/limiter.yaml,
              env / .env credential PRESENCE (boolean only)
    Writes  : nothing (stdout only)
    Safe    : yes — no network, no provider call, no secret rendered
    Verifier: tests/determinism/test_lane_registry.py

Usage:
    .venv/bin/python scripts/lane_inventory.py            # human table
    .venv/bin/python scripts/lane_inventory.py --json     # machine JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

from polymath_shared.llm_extraction import lane_registry as LR  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Sanitized provider lane inventory (no provider call).")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of the table")
    args = ap.parse_args()
    reg = LR.build_registry()
    if args.json:
        print(json.dumps(reg.to_dict(), indent=2, sort_keys=True))
    else:
        print(LR.sanitized_inventory(reg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
