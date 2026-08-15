"""Repository governance checks. See AGENTS.md and scripts/README.md."""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


IGNORED_NAMES = {
    ".DS_Store",
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "weights.digest",
}
IGNORED_PREFIXES = (
    "stores/postgres/data/",
    "stores/qdrant/data/",
    "stores/neo4j/data/",
    "var/log/",
    "stores/redis/dump.rdb",
    "resources/vendor/nltk/",
    "resources/vendor/verbnet-3.3.zip",
    "resources/vendor/propbank-frames.zip",
    "resources/vendor/semlink.zip",
)
IGNORED_SUFFIXES = (".egg-info", ".pid")
MODULE_OWNERS = {
    "control": "control",
    "orchestrator": "orchestrator",
    "polymath_shared": "shared",
    "sidecars": "sidecar",
    "workers": "worker",
}
WORK_LOG_FIELDS = {
    "change_id",
    "owner",
    "date",
    "status",
    "architecture_impact",
}
WORK_LOG_SECTIONS = (
    "## Contract",
    "## Changes",
    "## Proof",
    "## Rejected claims",
    "## Open contract gaps",
)


def load_scaffold(root: Path) -> ModuleType:
    path = root / "scripts" / "scaffold_polymath_v4.py"
    spec = importlib.util.spec_from_file_location("polymath_scaffold", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load scaffold from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declared_paths(root: Path) -> set[str]:
    module = load_scaffold(root)
    return {item[0] for item in module.TREE}


def is_ignored(relative: str) -> bool:
    path = Path(relative)
    if any(part in IGNORED_NAMES for part in path.parts):
        return True
    if any(part.endswith(IGNORED_SUFFIXES) for part in path.parts):
        return True
    return relative.startswith(IGNORED_PREFIXES)


def actual_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not is_ignored(path.relative_to(root).as_posix())
    }


def parse_front_matter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def check_declared_files(root: Path) -> list[str]:
    declared = declared_paths(root)
    actual = actual_files(root)
    errors = [f"missing declared path: {path}" for path in sorted(declared - actual)]
    errors.extend(f"undeclared repository file: {path}" for path in sorted(actual - declared))
    return errors


def check_script_registry(root: Path) -> list[str]:
    registry = (root / "scripts" / "README.md").read_text()
    errors: list[str] = []
    for path in sorted(declared_paths(root)):
        if path.startswith("scripts/") and path != "scripts/README.md":
            if f"`{path}`" not in registry:
                errors.append(f"script missing from registry: {path}")
    return errors


def check_work_logs(root: Path) -> list[str]:
    errors: list[str] = []
    folder = root / "docs" / "wiki" / "work-log"
    entries = sorted(path for path in folder.glob("*.md") if path.name != "README.md")
    if not entries:
        return ["work log has no entries"]
    for path in entries:
        relative = path.relative_to(root).as_posix()
        text = path.read_text()
        metadata = parse_front_matter(text)
        if metadata is None:
            errors.append(f"{relative}: invalid front matter")
            continue
        missing = WORK_LOG_FIELDS - set(metadata)
        if missing:
            errors.append(f"{relative}: missing fields {sorted(missing)}")
        positions = [text.find(section) for section in WORK_LOG_SECTIONS]
        if any(position < 0 for position in positions):
            errors.append(f"{relative}: missing required work-log section")
        elif positions != sorted(positions):
            errors.append(f"{relative}: work-log sections out of order")
    return errors


def check_dependencies(root: Path) -> list[str]:
    path = root / "architecture" / "dependencies.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid dependency map: {exc}"]
    owners = data.get("owners", {})
    errors: list[str] = []
    if not isinstance(owners, dict) or not owners:
        return ["dependency map has no owners"]
    for owner, config in owners.items():
        for dependency in config.get("may_depend_on", []):
            if dependency not in owners:
                errors.append(f"{owner}: unknown dependency {dependency}")
    for pair in data.get("forbidden_imports", []):
        if pair.get("from") not in owners or pair.get("to") not in owners:
            errors.append(f"invalid forbidden import pair: {pair}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(owner: str) -> None:
        if owner in visiting:
            errors.append(f"dependency cycle includes {owner}")
            return
        if owner in visited:
            return
        visiting.add(owner)
        for dependency in owners[owner].get("may_depend_on", []):
            visit(dependency)
        visiting.remove(owner)
        visited.add(owner)

    for owner in owners:
        visit(owner)
    return errors


def path_owner(relative: str, owners: dict) -> str | None:
    for owner, config in owners.items():
        if any(relative.startswith(prefix) for prefix in config.get("paths", [])):
            return owner
    return None


def check_forbidden_imports(root: Path) -> list[str]:
    data = json.loads((root / "architecture" / "dependencies.json").read_text())
    owners = data["owners"]
    forbidden = {(item["from"], item["to"]) for item in data["forbidden_imports"]}
    errors: list[str] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if is_ignored(relative) or relative.startswith("scripts/") or relative.startswith("tests/"):
            continue
        owner = path_owner(relative, owners)
        if owner is None:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=relative)
        except SyntaxError as exc:
            errors.append(f"{relative}: syntax error prevents import check: {exc.msg}")
            continue
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        for module in imported:
            target = MODULE_OWNERS.get(module)
            if target and (owner, target) in forbidden:
                errors.append(f"{relative}: forbidden {owner} import of {target}")
    return errors


def changed_paths(root: Path, base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"cannot diff against {base}")
    return {line for line in result.stdout.splitlines() if line}


def check_change_companions(root: Path, base: str) -> list[str]:
    changed = changed_paths(root, base)
    errors: list[str] = []
    has_work_log = any(
        path.startswith("docs/wiki/work-log/") and not path.endswith("README.md")
        for path in changed
    )
    architecture_changed = bool(
        {"ARCHITECTURE.md", "architecture/dependencies.json"} & changed
    )
    if architecture_changed:
        requirements = {
            "ARCHITECTURE_CHANGELOG.md": "architecture changelog",
        }
        for path, label in requirements.items():
            if path not in changed:
                errors.append(f"architecture change missing {label}: {path}")
        if not any(path.startswith("docs/wiki/decisions/") and not path.endswith(("README.md", "0000-template.md")) for path in changed):
            errors.append("architecture change missing ADR")
        if not any(path.startswith("docs/wiki/refactors/") and not path.endswith("README.md") for path in changed):
            errors.append("architecture change missing refactor entry")
        if not has_work_log:
            errors.append("architecture change missing work log")
    if any(path.startswith("scripts/") for path in changed):
        if "scripts/README.md" not in changed:
            errors.append("script change missing scripts/README.md update")
        if not has_work_log:
            errors.append("script change missing work log")
    if any(path.startswith(("contracts/", "stores/postgres/migrations/")) for path in changed):
        if not has_work_log:
            errors.append("contract or migration change missing work log")
    return errors


PRODUCTION_MODEL_SURFACES = [
    "sidecars/", "deployment/", "orchestrator/", "workers/", "control/",
    "shared/", "Makefile", ".env.example", "compose.yaml", "pyproject.toml",
]
FORBIDDEN_ALTERNATE_MODEL_IDS = [
    "gliner_large", "gliner-community", "NuNER_Zero", "nuner",
]


def check_production_model_surface(root: Path) -> list[str]:
    """Model-surface guard (2026-08-14 cleanup): the ONLY supported
    production GLiNER entity model is urchade/gliner_medium-v2.1 @
    40ec4193. Alternate models evaluated in EM1 (HISTORICAL / FROZEN /
    NOT PRODUCTION) may only appear in eval/ and history docs — never
    on an active production surface."""
    errors: list[str] = []
    for surface in PRODUCTION_MODEL_SURFACES:
        surface_path = root / surface
        candidates = ([surface_path] if surface_path.is_file()
                      else sorted(surface_path.rglob("*")) if surface_path.is_dir()
                      else [])
        for path in candidates:
            if not path.is_file():
                continue
            if surface_path.is_file():
                pass
            elif path.suffix not in (".py", ".toml", ".yaml", ".yml", ".json",
                                     ".md", ".sql", ".plist", ".example", ".cypher"):
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            relative = path.relative_to(root).as_posix()
            for model_id in FORBIDDEN_ALTERNATE_MODEL_IDS:
                if model_id in text:
                    errors.append(
                        f"{relative}: alternate GLiNER model id {model_id!r} on a "
                        "production surface (historical references belong in eval/ only)"
                    )
    return errors


def run_checks(root: Path, base: str | None = None) -> list[str]:
    checks = [
        check_declared_files,
        check_script_registry,
        check_work_logs,
        check_dependencies,
        check_forbidden_imports,
        check_production_model_surface,
    ]
    errors: list[str] = []
    for check in checks:
        errors.extend(check(root))
    if base:
        try:
            errors.extend(check_change_companions(root, base))
        except RuntimeError as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--base", help="Git base revision for companion-change checks")
    args = parser.parse_args()
    errors = run_checks(args.root.resolve(), args.base)
    if errors:
        print("REPO GUARD FAILED", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print("repo guard: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
