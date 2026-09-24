"""C0b: LibCST 1.9.0 on this repository (CODE-KNOWLEDGE-V1 C0b, register 11.461).

The four checks for the Python card's parser of record: it exists (pinned version), runs on a fixture, runs on the real
repository, and gives useful output. Measured against the C0a stdlib baseline (`../code-knowledge-c0-2026-09-24/`):
- parse: every tracked Python file through `MetadataWrapper` (PositionProvider + QualifiedNameProvider), with timing;
- spans: LibCST's positions of top-level functions / classes vs stdlib `ast` (def line, decorator line, end line);
- names: for every call site in product code, what QualifiedNameProvider resolves the callee to (a repository
  definition, a builtin, an external module, or nothing) vs C0a's import-table estimate.

Runs in a throwaway venv with libcst installed (never the fleet .venv). No network, no database, no model.
    <venv>/bin/python docs/wiki/experiments/code-knowledge-c0b-2026-09-24/libcst_eval.py . > libcst_eval.json
"""
from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path

import libcst as cst
from libcst.metadata import (
    MetadataWrapper,
    PositionProvider,
    QualifiedNameProvider,
    QualifiedNameSource,
)

HERE = Path(__file__).resolve().parent
C0A = HERE.parent / "code-knowledge-c0-2026-09-24"
PRODUCT_AREAS = ("shared", "orchestrator", "workers", "control", "mcp_server", "sidecars")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Calls(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    def __init__(self) -> None:
        self.names: list[set] = []

    def visit_Call(self, node: cst.Call) -> None:
        try:
            self.names.append(self.get_metadata(QualifiedNameProvider, node.func, set()))
        except KeyError:
            self.names.append(set())


class TopDefs(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self.depth = 0
        self.defs: list[tuple[str, int, int]] = []

    def _enter(self, node) -> None:
        if self.depth == 0:
            pos = self.get_metadata(PositionProvider, node)
            self.defs.append((node.name.value, pos.start.line, pos.end.line))
        self.depth += 1

    def _leave(self, node) -> None:
        self.depth -= 1

    visit_FunctionDef = _enter
    leave_FunctionDef = _leave
    visit_ClassDef = _enter
    leave_ClassDef = _leave


def main(root: Path) -> dict:
    census = load("census", C0A / "census.py")
    calls_mod = load("python_calls", C0A / "python_calls.py")
    files = []
    for p in census.tracked_files(root):
        if p.endswith(".py"):
            text = (root / p).read_text(encoding="utf-8", errors="replace")
            if not census.skip_reason(p, text):
                files.append((p, text))
    trees = {calls_mod.module_name(p): ast.parse(t) for p, t in files}
    idx = calls_mod.ModuleIndex(trees)
    repo_names = {f"{m}.{n}" for m, names in idx.defs.items() for n in names}
    repo_names |= {owner.split(":")[0] + "." + meth for meth, owners in idx.methods.items() for owner in owners}

    parse_errors, t_parse = [], 0.0
    span = Counter()
    resolution = Counter()
    for path, text in files:
        t0 = time.perf_counter()
        try:
            wrapper = MetadataWrapper(cst.parse_module(text))
            tops = TopDefs()
            wrapper.visit(tops)
            calls = Calls()
            if census.area_of(path) in PRODUCT_AREAS:
                wrapper.visit(calls)
        except Exception as exc:  # noqa: BLE001 — a parse failure is a finding, not a crash
            parse_errors.append({"path": path, "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
            t_parse += time.perf_counter() - t0
            continue
        t_parse += time.perf_counter() - t0
        # spans vs stdlib ast (top-level functions and classes, matched by name + order)
        tree = trees[calls_mod.module_name(path)]
        ref = [(n.name, n.lineno, min([n.lineno] + [d.lineno for d in n.decorator_list]), n.end_lineno)
               for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        for (name, s, e), (rname, def_line, deco_line, end_line) in zip(tops.defs, ref):
            if name != rname:
                span["name_mismatch"] += 1
                continue
            span["compared"] += 1
            span["start_equals_def_line"] += int(s == def_line)
            span["start_equals_first_decorator"] += int(s == deco_line)
            span["end_equals"] += int(e == end_line)
        span["count_mismatch_files"] += int(len(tops.defs) != len(ref))
        # callee names in product code
        module = calls_mod.module_name(path)
        for names in calls.names:
            if not names:
                resolution["unresolved"] += 1
                continue
            kinds = set()
            for q in names:
                full = q.name if q.source != QualifiedNameSource.LOCAL else f"{module}.{q.name}"
                if full.startswith("."):                 # a relative import: resolve it against this module
                    rest = full.lstrip(".")
                    base = calls_mod.resolve_relative(module, path.endswith("__init__.py"),
                                                      len(full) - len(rest), None)
                    full = f"{base}.{rest}" if base else rest
                if q.source == QualifiedNameSource.BUILTIN:
                    kinds.add("builtin")
                elif full in repo_names:
                    kinds.add("repo_definition")
                elif q.source == QualifiedNameSource.IMPORT and full.split(".")[0] not in {m.split(".")[0] for m in idx.defs}:
                    kinds.add("external")
                else:
                    kinds.add("named_not_a_repo_definition")
            if len(kinds) > 1:
                resolution["ambiguous_multiple_kinds"] += 1
            else:
                resolution[kinds.pop()] += 1
    c0a = json.loads((C0A / "python_calls.json").read_text())["product_code"]
    return {
        "measure": "CODE-KNOWLEDGE-V1 C0b LibCST on this repository",
        "tool": {"libcst": importlib.metadata.version("libcst"), "python": sys.version.split()[0]},
        "files": len(files), "parse_errors": parse_errors, "parse_and_metadata_seconds": round(t_parse, 1),
        "top_level_spans_vs_stdlib_ast": dict(span),
        "product_code_call_sites": sum(resolution.values()),
        "product_code_callee_resolution": dict(resolution.most_common()),
        "c0a_stdlib_baseline_product_code": {
            "call_sites": c0a["call_sites"],
            "repo_internal_resolved_without_types": c0a["repo_internal_resolved_without_types"]},
        "reading": [
            ("QualifiedNameProvider resolves names through imports and scopes, not through types: `obj.m()` on an "
             "unknown object stays unresolved, as the spec requires"),
            "repo_definition = the qualified name equals a repository function / class / method the stdlib index knows",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()), indent=1))
