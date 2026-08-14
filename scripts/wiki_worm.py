"""Read-only wiki audit. See AGENTS.md and scripts/README.md."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


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


def audit(root: Path) -> tuple[list[str], list[str], list[str]]:
    wiki = root / "docs" / "wiki"
    errors: list[str] = []
    open_refactors: list[str] = []
    open_work: list[str] = []
    if not wiki.is_dir():
        return ["docs/wiki is missing"], open_refactors, open_work

    for path in sorted(wiki.rglob("*.md")):
        relative = path.relative_to(root).as_posix()
        metadata = parse_front_matter(path.read_text())
        if metadata is None:
            errors.append(f"{relative}: missing front matter")
            continue
        if not metadata.get("last_reviewed"):
            errors.append(f"{relative}: missing last_reviewed")
        status = metadata.get("status")
        if "refactors" in path.parts and path.name != "README.md":
            if status != "done":
                open_refactors.append(relative)
        if "work-log" in path.parts and path.name != "README.md":
            if status != "complete":
                open_work.append(relative)

    return errors, open_refactors, open_work


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--check", action="store_true", help="Audit only; this script never writes.")
    args = parser.parse_args(argv)

    errors, open_refactors, open_work = audit(args.root.resolve())
    print("open refactors:")
    for item in open_refactors:
        print(f"  {item}")
    print("open work logs:")
    for item in open_work:
        print(f"  {item}")
    if errors:
        print("WIKI CHECK FAILED", file=sys.stderr)
        for item in errors:
            print(f"  {item}", file=sys.stderr)
        return 1
    print("wiki: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
