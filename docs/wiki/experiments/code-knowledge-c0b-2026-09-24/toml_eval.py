"""C0b: tree-sitter-toml spans on this repository's TOML files (CODE-KNOWLEDGE-V1 C0b, register 11.461).

`tomllib` (the value parser of record) gives no positions (C0a). This checks the planned span reader: every explicit
`[table]` / `[[array]]` header with its line span, ERROR / MISSING nodes, and consistency with tomllib (each header's
dotted name must exist in tomllib's parsed structure).

Runs in the throwaway venv (tree-sitter + tree-sitter-toml). No network, no database, no model.
    <venv>/bin/python toml_eval.py <repo_root> > toml_eval.json
"""
from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import tree_sitter_toml
from tree_sitter import Language, Parser


def header_name(node) -> str:
    for child in node.children:
        if child.type in ("bare_key", "quoted_key", "dotted_key"):
            return child.text.decode().replace('"', "").replace(" ", "")
    return "?"


def exists(data: dict, dotted: str) -> bool:
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[-1] if cur else {}
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def main(root: Path) -> dict:
    parser = Parser(Language(tree_sitter_toml.language()))
    files = [p for p in subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True,
                                       check=True).stdout.splitlines() if p.endswith(".toml")]
    out, totals = [], {"files": 0, "headers": 0, "headers_found_in_tomllib": 0, "ERROR_nodes": 0, "MISSING_nodes": 0}
    for rel in files:
        raw = (root / rel).read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        tree = parser.parse(raw)
        headers, errors, missing = [], 0, 0
        stack = [tree.root_node]
        while stack:
            n = stack.pop()
            if n.type in ("table", "table_array_element"):
                name = header_name(n)
                headers.append({"name": name, "array": n.type == "table_array_element",
                                "lines": [n.start_point[0] + 1, n.end_point[0] + 1], "in_tomllib": exists(data, name)})
            errors += n.type == "ERROR"
            missing += n.is_missing
            stack.extend(n.children)
        headers.sort(key=lambda h: h["lines"][0])
        totals["files"] += 1
        totals["headers"] += len(headers)
        totals["headers_found_in_tomllib"] += sum(h["in_tomllib"] for h in headers)
        totals["ERROR_nodes"] += errors
        totals["MISSING_nodes"] += missing
        out.append({"file": rel, "headers": headers})
    return {"measure": "CODE-KNOWLEDGE-V1 C0b tree-sitter-toml spans",
            "tool": {"tree-sitter": importlib.metadata.version("tree-sitter"),
                     "tree-sitter-toml": importlib.metadata.version("tree-sitter-toml")},
            "totals": totals, "files": out}


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()), indent=1))
