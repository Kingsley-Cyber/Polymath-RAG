"""C0: how far does resolution WITHOUT type inference reach on this repository's Python calls? (CODE-KNOWLEDGE-V1 C0)

The Python card's open question (spec §8 item 2): LibCST-only resolution vs a SCIP / pyright-class resolver. LibCST's
QualifiedNameProvider resolves a name through the import table and the enclosing scopes; it does not infer the type of
`obj` in `obj.method()`. This script measures the call-site mix with stdlib `ast` and the same import-table + enclosing
class rule, so the share of repo-internal calls that ONLY type inference could link is a number, not a guess.

Categories per call site:
- resolved_same_module / resolved_import: a repo function or class, found through the module scope or the import table;
- resolved_self: `self.m()` / `cls.m()` where the enclosing class defines `m`;
- self_inherited_or_attr: `self.m()` where the enclosing class does not define `m` (a base class or an attribute);
- import_ambiguous: the import names a repo module but the name is not a top-level definition there (re-export, etc.);
- external: the callee comes from a module outside the repository (stdlib or a third-party package);
- builtin: a Python builtin;
- local_or_param: a name bound inside the function (local variable, parameter, nested def);
- attr_unknown_repo_name: `obj.m()` on an object of unknown type where some repo class defines a method `m`
  (the upper bound of what type inference could add as repo-internal CALLS edges);
- attr_unknown_other: `obj.m()` where no repo class defines `m` (library objects: cursors, loggers...);
- attr_builtin_type_method: `obj.m()` where `m` is a method of a built-in type (`get`, `append`, `join`...);
- other_dynamic: calls on subscripts, call results, lambdas.

Deterministic, no network, no database. Run from the repository root:
    .venv/bin/python docs/wiki/experiments/code-knowledge-c0-2026-09-24/python_calls.py . > python_calls.json
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_ROOTS = ("shared/", "orchestrator/", "workers/", "control/", "")   # the fleet's PYTHONPATH + the repo root
PRODUCT_AREAS = ("shared", "orchestrator", "workers", "control", "mcp_server", "sidecars")
BUILTINS = set(dir(builtins))
# method names of the built-in container / text types: `x.get()`, `x.append()`, `x.join()` are overwhelmingly calls on
# those types, so they never count as a possible repo-internal method even when some repo class defines the same name
BUILTIN_TYPE_METHODS = {n for t in (str, bytes, dict, list, set, frozenset, tuple, int, float) for n in dir(t)}


def load_census():
    spec = importlib.util.spec_from_file_location("census", HERE / "census.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def module_name(path: str) -> str:
    for root in SOURCE_ROOTS:
        if root and path.startswith(root) and path.count("/") >= 2:
            rel = path[len(root):]
            break
    else:
        rel = path
    rel = rel[:-3] if rel.endswith(".py") else rel[:-4]
    parts = rel.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


class ModuleIndex:
    def __init__(self, trees: dict[str, ast.Module]):
        self.defs: dict[str, set[str]] = {}          # module -> top-level function / class names
        self.methods: dict[str, set[str]] = defaultdict(set)   # method name -> classes that define it
        for mod, tree in trees.items():
            names = set()
            for n in tree.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(n.name)
                if isinstance(n, ast.ClassDef):
                    for m in n.body:
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            self.methods[m.name].add(f"{mod}.{n.name}")
            self.defs[mod] = names

    def is_repo_module(self, name: str) -> bool:
        return name in self.defs


def resolve_relative(mod: str, is_pkg: bool, level: int, target: str | None) -> str:
    base = mod.split(".") if is_pkg else mod.split(".")[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join([*base, target] if target else base)


def classify_file(mod: str, is_pkg: bool, tree: ast.Module, idx: ModuleIndex) -> Counter:
    imported_names: dict[str, tuple[str, str]] = {}   # local name -> (module, name)
    imported_modules: dict[str, str] = {}              # local alias -> module
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    imported_modules[a.asname] = a.name
                else:
                    imported_modules[a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom):
            src = resolve_relative(mod, is_pkg, n.level, n.module) if n.level else (n.module or "")
            for a in n.names:
                local = a.asname or a.name
                if idx.is_repo_module(f"{src}.{a.name}"):
                    imported_modules[local] = f"{src}.{a.name}"      # `from pkg import submodule`
                else:
                    imported_names[local] = (src, a.name)
    top = idx.defs.get(mod, set())
    out = Counter()

    def visit(node: ast.AST, cls: ast.ClassDef | None, local_names: set[str]):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, child, local_names)
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                args = child.args
                bound = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
                bound |= {x.arg for x in (args.vararg, args.kwarg) if x}
                if not isinstance(child, ast.Lambda):
                    for sub in ast.walk(child):
                        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                            bound.add(sub.id)
                        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub is not child:
                            bound.add(sub.name)
                visit(child, cls, local_names | bound)
                continue
            if isinstance(child, ast.Call):
                out[classify_call(child.func, cls, local_names)] += 1
            visit(child, cls, local_names)

    def classify_call(f: ast.AST, cls: ast.ClassDef | None, local_names: set[str]) -> str:
        if isinstance(f, ast.Name):
            if f.id in local_names:
                return "local_or_param"
            if f.id in top:
                return "resolved_same_module"
            if f.id in imported_names:
                src, name = imported_names[f.id]
                if idx.is_repo_module(src):
                    return "resolved_import" if name in idx.defs[src] else "import_ambiguous"
                return "external"
            if f.id in imported_modules:
                return "external" if not idx.is_repo_module(imported_modules[f.id]) else "import_ambiguous"
            if f.id in BUILTINS:
                return "builtin"
            return "local_or_param"          # module-level assignment, star import or a name bound elsewhere
        if isinstance(f, ast.Attribute):
            v = f.value
            if isinstance(v, ast.Name) and v.id in ("self", "cls") and cls is not None:
                own = {m.name for m in cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
                return "resolved_self" if f.attr in own else "self_inherited_or_attr"
            if isinstance(v, ast.Name) and v.id in imported_modules and v.id not in local_names:
                target = imported_modules[v.id]
                if idx.is_repo_module(target):
                    return "resolved_import" if f.attr in idx.defs[target] else "import_ambiguous"
                return "external"
            if isinstance(v, ast.Name) and v.id in imported_names and v.id not in local_names:
                src, name = imported_names[v.id]
                if not idx.is_repo_module(src):
                    return "external"                 # e.g. `from datetime import datetime; datetime.now()`
            if f.attr in BUILTIN_TYPE_METHODS:
                return "attr_builtin_type_method"
            return "attr_unknown_repo_name" if f.attr in idx.methods else "attr_unknown_other"
        return "other_dynamic"

    visit(tree, None, set())
    return out


# names of library APIs the repository calls on library objects (DB-API cursors, HTTP responses, the Qdrant client,
# subprocess, json); test fakes re-define them, so a name match alone would count them as repo-internal
LIBRARY_API_NAMES = {"execute", "executemany", "fetchone", "fetchall", "fetchmany", "commit", "rollback", "close",
                     "cursor", "json", "raise_for_status", "read", "write", "search", "post", "get", "put", "delete",
                     "run", "query_points", "collection_exists", "upsert", "scroll", "retrieve", "send", "recv",
                     "connect", "load", "dump", "dumps", "loads"}


def tight_type_only_estimate(files, idx: ModuleIndex, census, resolved: int) -> dict:
    """The TIGHT estimate for product code: `obj.m()` calls where `m` is a method of a PRODUCT class (not only of a
    test / eval fake) and not a library API name or a built-in type method."""
    prod_mods = {module_name(p) for p, _ in files if census.area_of(p) in PRODUCT_AREAS}
    prod_methods = {m for m, owners in idx.methods.items() if any(o.rsplit(".", 1)[0] in prod_mods for o in owners)}
    tight = Counter()
    for p, tree in files:
        if census.area_of(p) not in PRODUCT_AREAS:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                v, a = n.func.value, n.func.attr
                if isinstance(v, ast.Name) and v.id in ("self", "cls"):
                    continue
                if a in BUILTIN_TYPE_METHODS or a in LIBRARY_API_NAMES or a not in prod_methods:
                    continue
                tight[a] += 1
    n = sum(tight.values())
    return {"product_code_type_only_candidates": n, "distinct_method_names": len(tight),
            "top": tight.most_common(20),
            "share_of_repo_internal_calls_resolved_without_types": round(resolved / max(resolved + n, 1), 3)}


def main(root: Path) -> dict:
    census = load_census()
    files = []
    for p in census.tracked_files(root):
        if not p.endswith(".py"):
            continue
        text = (root / p).read_text(encoding="utf-8", errors="replace")
        if census.skip_reason(p, text):
            continue
        files.append((p, ast.parse(text, filename=p)))
    trees = {module_name(p): t for p, t in files}
    idx = ModuleIndex(trees)
    total, product, tests = Counter(), Counter(), Counter()
    for p, tree in files:
        c = classify_file(module_name(p), p.endswith("__init__.py"), tree, idx)
        total.update(c)
        if census.area_of(p) in PRODUCT_AREAS:
            product.update(c)
        if "/tests/" in f"/{p}" or Path(p).name.startswith("test_"):
            tests.update(c)

    def shares(c: Counter) -> dict:
        n = sum(c.values())
        internal_resolved = c["resolved_same_module"] + c["resolved_import"] + c["resolved_self"]
        need_types = c["attr_unknown_repo_name"] + c["self_inherited_or_attr"] + c["import_ambiguous"]
        return {"call_sites": n, "by_category": dict(c.most_common()),
                "repo_internal_resolved_without_types": internal_resolved,
                "candidates_only_type_inference_or_mro_could_link": need_types,
                "share_of_repo_internal_candidates_resolved_without_types":
                    round(internal_resolved / max(internal_resolved + need_types, 1), 3)}

    prod = shares(product)
    return {"measure": "CODE-KNOWLEDGE-V1 C0 Python call-site resolution without type inference",
            "files": len(files), "repo_modules": len(idx.defs),
            "whole_repository": shares(total), "product_code": prod, "tests": shares(tests),
            "product_code_tight": tight_type_only_estimate(files, idx, census,
                                                           prod["repo_internal_resolved_without_types"]),
            "caveats": [("module names map shared/ orchestrator/ workers/ control/ and the repo root, as the fleet's "
                         "PYTHONPATH does; a package imported under another name counts as external"),
                        "attr_unknown_repo_name is an UPPER bound: a method name shared with a library type counts",
                        "inheritance (MRO) and decorators are not followed; LibCST would follow the same scopes"]}


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()), indent=1))
