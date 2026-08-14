"""Agent preflight. See AGENTS.md and scripts/README.md.

This command is read-only. Use --strict before deployment to reject unpinned
model manifests in addition to repository-structure failures.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path

from repo_guard import run_checks


def check_python_syntax(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.py"):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            ast.parse(path.read_text(), filename=relative)
        except SyntaxError as exc:
            errors.append(f"{relative}: {exc.msg} at line {exc.lineno}")
    return errors


def check_json_and_toml(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.json"):
        try:
            json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid JSON: {exc}")
    for path in root.rglob("*.toml"):
        try:
            with path.open("rb") as handle:
                tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid TOML: {exc}")
    return errors


def check_model_pins(root: Path) -> list[str]:
    errors: list[str] = []
    for server in (root / "sidecars").glob("*/server.py"):
        manifest = server.with_name("manifest.toml")
        if not manifest.exists():
            errors.append(f"{server.parent.relative_to(root)}: missing manifest.toml")
    for path in (root / "sidecars").rglob("*.toml"):
        if "__PIN_" in path.read_text():
            errors.append(f"{path.relative_to(root)}: unresolved deployment pin")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    errors = run_checks(root)
    errors.extend(check_python_syntax(root))
    errors.extend(check_json_and_toml(root))
    if args.strict:
        errors.extend(check_model_pins(root))

    if errors:
        print("PREFLIGHT FAILED", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print("preflight: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
