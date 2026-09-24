"""C0b: the official Luau toolchain vs tree-sitter-luau on one real Roblox file (CODE-KNOWLEDGE-V1 C0b, register 11.461).

Fixture: `fixtures/KnitServer.luau` from Sleitnick/Knit (MIT, `fixtures/Knit-LICENSE.txt`), commit
bb1ecf3dea69ca89147b9abe802a8c14399cb5e5, sha256 9265abb1a5e9b22ed90b1877698d444f4a114ee1062e8447a11d1be6a9bdb5d7.
Toolchain: luau-lang/luau 0.739 `luau-macos.zip` (sha256 f66cabc7…, verified at download) → `luau-ast`, `luau-analyze`.

What it measures:
- luau-ast: the JSON AST — functions (global / method / local), exported and local type aliases, `require` calls and the
  shape of their argument (a static instance path vs a computed value), typed parameters, spans (0-based line,col);
- luau-analyze: diagnostics without Roblox type definitions;
- tree-sitter-luau 1.2.0 (the fallback): ERROR / MISSING nodes and function counts on the same file.

Runs in the throwaway venv (tree-sitter + tree-sitter-luau). No network, no database, no model.
    <venv>/bin/python luau_eval.py <path-to-luau-binaries-dir> > luau_eval.json
"""
from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import tree_sitter_luau
from tree_sitter import Language, Parser

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "KnitServer.luau"


def walk(node, out: list) -> None:
    if isinstance(node, dict):
        if "type" in node:
            out.append(node)
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)


def dotted(expr: dict) -> str | None:
    """`KnitServer.Util.Promise` for an index chain over a global / local; None when computed."""
    t = expr.get("type")
    if t in ("AstExprGlobal", "AstExprLocal"):
        return expr.get("global") or (expr.get("local") or {}).get("name")
    if t == "AstExprIndexName":
        base = dotted(expr.get("expr") or {})
        return f"{base}.{expr.get('index')}" if base else None
    return None


def line_of(loc: str) -> int:
    return int(loc.split(",")[0]) + 1


def luau_ast(bin_dir: Path) -> dict:
    raw = subprocess.run([str(bin_dir / "luau-ast"), str(FIXTURE)], capture_output=True, text=True, check=True).stdout
    nodes: list[dict] = []
    walk(json.loads(raw), nodes)
    kinds = Counter(n["type"] for n in nodes)
    functions = []
    for n in nodes:
        if n["type"] == "AstStatFunction":
            functions.append({"kind": "global_or_method", "name": dotted(n.get("name") or {}) or "?",
                              "line": line_of(n["location"])})
        elif n["type"] == "AstStatLocalFunction":
            functions.append({"kind": "local", "name": (n.get("name") or {}).get("name", "?"),
                              "line": line_of(n["location"])})
    requires = []
    for n in nodes:
        if n["type"] == "AstExprCall" and (n.get("func") or {}).get("type") == "AstExprGlobal" \
                and n["func"].get("global") == "require":
            arg = (n.get("args") or [{}])[0]
            path = dotted(arg)
            # an index chain (`script.Parent.X`, `KnitServer.Util.Promise`) names an instance path the Rojo sourcemap
            # can resolve; a bare variable (`require(v)` over GetChildren()) is computed at run time: `unresolved`
            shape = "index_chain" if arg.get("type") == "AstExprIndexName" else "computed"
            requires.append({"line": line_of(n["location"]), "argument": path or arg.get("type"), "shape": shape})
    aliases = [{"name": n.get("name"), "exported": bool(n.get("exported")), "line": line_of(n["location"])}
               for n in nodes if n["type"] == "AstStatTypeAlias"]
    typed_args = sum(1 for n in nodes if n["type"] == "AstExprFunction"
                     for a in (n.get("args") or []) if isinstance(a, dict) and a.get("luauType"))
    return {"exit": 0, "ast_bytes": len(raw), "node_kinds": len(kinds),
            "top_node_kinds": dict(kinds.most_common(12)),
            "functions": functions, "type_aliases": aliases, "requires": requires,
            "typed_parameters": typed_args,
            "type_assertions": kinds.get("AstExprTypeAssertion", 0),
            "interpolated_strings": kinds.get("AstExprInterpString", 0)}


def luau_analyze(bin_dir: Path) -> dict:
    run = subprocess.run([str(bin_dir / "luau-analyze"), str(FIXTURE)], capture_output=True, text=True, check=False)
    lines = [x for x in (run.stdout + run.stderr).splitlines() if x.strip()]
    kinds = Counter(x.split(": ", 1)[1].split(";")[0] if ": " in x else x for x in lines)
    return {"exit": run.returncode, "diagnostics": len(lines), "by_message": dict(kinds.most_common())}


def tree_sitter_fallback() -> dict:
    parser = Parser(Language(tree_sitter_luau.language()))
    tree = parser.parse(FIXTURE.read_bytes())
    counts = Counter()
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        counts[n.type] += 1
        if n.is_missing:
            counts["<MISSING>"] += 1
        stack.extend(n.children)
    return {"version": importlib.metadata.version("tree-sitter-luau"),
            "engine": importlib.metadata.version("tree-sitter"),
            "has_error": tree.root_node.has_error, "ERROR_nodes": counts.get("ERROR", 0),
            "MISSING_nodes": counts.get("<MISSING>", 0),
            "function_declarations": counts.get("function_declaration", 0),
            "local_function_declarations": counts.get("local_function_declaration", 0)
            + counts.get("local_function", 0),
            "type_definitions": counts.get("type_definition", 0)}


def main(bin_dir: Path) -> dict:
    return {"measure": "CODE-KNOWLEDGE-V1 C0b official Luau toolchain vs tree-sitter-luau",
            "fixture": {"file": "fixtures/KnitServer.luau", "source": "https://github.com/Sleitnick/Knit",
                        "commit": "bb1ecf3dea69ca89147b9abe802a8c14399cb5e5", "licence": "MIT",
                        "bytes": FIXTURE.stat().st_size},
            "toolchain": {"release": "luau-lang/luau 0.739 luau-macos.zip",
                          "sha256": "f66cabc7937ce1df0c40d160139aa115a4f0db57b2288e35a83f75d218bc3ff3",
                          "binaries": sorted(p.name for p in bin_dir.iterdir() if p.name.startswith("luau"))},
            "luau_ast": luau_ast(bin_dir), "luau_analyze": luau_analyze(bin_dir),
            "tree_sitter_luau": tree_sitter_fallback()}


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1]).resolve()), indent=1))
