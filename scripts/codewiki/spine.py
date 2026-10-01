#!/usr/bin/env python3
"""CODE-WIKI-V1 layers 0-1: the static spine of the code wiki (no model, no network, no database).

Reads the tracked product code and writes, under docs/codewiki/:
  spine.json                  every fact below, machine-readable (the unit pages are built from it)
  facts/routes.md             each HTTP route: method, path, web-boundary class, handler anchor, the UI files that call it
  facts/flags.md              each environment flag: every read with its default (conflicting defaults flagged), .env.example
  facts/db.md                 each Postgres table: columns, the migration that made it, the units that read / write it
  facts/qdrant.md             each Qdrant collection name literal and where it appears
  facts/mcp-tools.md          the MCP tools of Server A (orchestrator/orchestrator/mcp_server.py) and Server B (mcp_server/)
  facts/fallbacks.md          every broad exception handler (`except Exception` / bare `except`) and what it does
  facts/imports.md            the most-imported units (god nodes) and each unit's importers
  runtime/truth-tables.md     the supervised fleet, the sidecars, the compose services, the ports, how code ships
  vocab/<NAME>.md             a vocabulary per shared constant set: the authority, its values verbatim, every consumer
  specimens/prompts.md        every model prompt constant, verbatim
Deterministic: the same commit gives byte-identical output. Usage: .venv/bin/python scripts/codewiki/spine.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "codewiki"
PRODUCT_ROOTS = ("orchestrator/orchestrator/", "shared/polymath_shared/", "workers/workers/", "control/control/", "mcp_server/",
                 "sidecars/", "adapters/", "frontend-v2/src/")
SMALL_LINES = 150           # files under this many lines are grouped per directory
GROUP_MAX_LINES = 1800      # a grouped page holds at most this many source lines
INTERNAL_PKGS = {"polymath_shared": "shared/polymath_shared", "orchestrator": "orchestrator/orchestrator",
                 "workers": "workers/workers", "control": "control/control"}
FLAG_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
SQL_READ = re.compile(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
SQL_WRITE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
SQL_HINT = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b[\s\S]*\b(FROM|INTO|SET|WHERE)\b", re.IGNORECASE)
COLLECTION_RE = re.compile(r"\bpolymath_[a-z0-9_]{3,}\b")
ROUTE_METHODS = {"get", "post", "put", "delete", "patch"}
NONDET_CALLS = {"time.time": "clock", "time.monotonic": "clock", "time.perf_counter": "clock", "datetime.now": "clock",
                "datetime.utcnow": "clock", "date.today": "clock", "uuid.uuid4": "uuid", "uuid.uuid1": "uuid",
                "secrets.token_hex": "random", "secrets.token_urlsafe": "random", "secrets.token_bytes": "random",
                "os.urandom": "random", "subprocess.run": "subprocess", "subprocess.Popen": "subprocess",
                "asyncio.gather": "concurrency", "threading.Thread": "concurrency", "ThreadPoolExecutor": "concurrency"}
NET_PREFIXES = ("httpx.", "requests.", "urllib.request.", "aiohttp.")


def git_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(out.split())


def is_product(path: str) -> bool:
    return (path.startswith(PRODUCT_ROOTS) and path.endswith((".py", ".ts", ".tsx")) and "__tests__" not in path
            and "/tests/" not in path and not path.startswith("adapters/ecommerce/tests"))


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def module_of(path: str) -> str | None:
    """Dotted module for a product .py path (polymath_shared.x.y), None for scripts outside a package root."""
    for mod, base in INTERNAL_PKGS.items():
        if path.startswith(base + "/"):
            rel = path[len(base) + 1:-3].replace("/", ".")
            rel = rel[:-len(".__init__")] if rel.endswith(".__init__") else ("" if rel == "__init__" else rel)
            return mod + ("." + rel if rel else "")
    return None


# ---------------------------------------------------------------- python analysis
def _call_name(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 — a name we cannot print is simply not matched
        return ""


def _docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def analyse_py(path: str, text: str) -> dict:
    facts: dict = {"symbols": [], "routes": [], "mcp_tools": [], "constants": [], "env": [], "imports": [], "sql_reads": [],
                   "sql_writes": [], "collections": [], "nondeterminism": [], "fallbacks": [], "prompts": [], "doc": ""}
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        facts["error"] = f"syntax error: {exc}"
        return facts
    facts["doc"] = (ast.get_docstring(tree) or "").strip().split("\n\n")[0][:500]
    doc_lines = _docstring_lines(tree)
    str_consts: dict[str, str] = {}
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) and node.value else []
        for t in targets:
            if isinstance(t, ast.Name) and isinstance(node.value, ast.AST):
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    str_consts[t.id] = value.value
                if t.id.isupper() or t.id.lstrip("_").isupper():
                    lit = _literal(value)
                    if lit is not None:
                        facts["constants"].append({"name": t.id, "line": node.lineno, "value": lit})
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and len(value.value) >= 300 and (
                            re.search(r"PROMPT|SYSTEM|INSTRUCTION|TEMPLATE", t.id) or value.value.lstrip().startswith("You ")):
                        facts["prompts"].append({"name": t.id, "line": node.lineno, "text": value.value})
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            entry = {"name": node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "def",
                     "line": node.lineno, "end": node.end_lineno, "doc": (ast.get_docstring(node) or "").strip().split("\n")[0][:200]}
            if not isinstance(node, ast.ClassDef):
                entry["args"] = [a.arg for a in node.args.args + node.args.kwonlyargs]
            else:
                entry["methods"] = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            facts["symbols"].append(entry)
            for dec in getattr(node, "decorator_list", []):
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr in ROUTE_METHODS and dec.args and isinstance(dec.args[0], ast.Constant):
                        facts["routes"].append({"method": dec.func.attr.upper(), "path": dec.args[0].value, "handler": node.name,
                                                "line": node.lineno})
                    if dec.func.attr == "tool" and _call_name(dec.func.value) in ("mcp", "server", "app"):
                        name = next((k.value.value for k in dec.keywords if k.arg == "name" and isinstance(k.value, ast.Constant)), node.name)
                        facts["mcp_tools"].append({"name": name, "line": node.lineno, "doc": entry["doc"]})
    seen_nd: set[tuple] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            facts["imports"].extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                pkg = (module_of(path) or "").split(".")
                pkg = pkg[: len(pkg) - node.level + (1 if path.endswith("__init__.py") else 0)]
                base = ".".join(pkg + ([base] if base else []))
            facts["imports"].append(base)
            facts["imports"].extend(f"{base}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            env_name = _env_read(node, name, str_consts)
            if env_name:
                default = _call_name(node.args[1]) if len(node.args) > 1 else (
                    next((_call_name(k.value) for k in node.keywords if k.arg == "default"), None))
                facts["env"].append({"name": env_name, "line": node.lineno, "default": default})
            kind = NONDET_CALLS.get(name) or NONDET_CALLS.get(name.split(".", 1)[-1] if "." in name else name)
            if not kind and name.startswith(NET_PREFIXES):
                kind = "network"
            if kind and (kind, node.lineno) not in seen_nd:
                seen_nd.add((kind, node.lineno))
                facts["nondeterminism"].append({"kind": kind, "call": name[:60], "line": node.lineno})
        elif isinstance(node, ast.Subscript) and _call_name(node.value) in ("os.environ", "environ"):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and FLAG_RE.match(sl.value):
                facts["env"].append({"name": sl.value, "line": node.lineno, "default": "(required)"})
        elif isinstance(node, ast.ExceptHandler):
            broad = node.type is None or _call_name(node.type) in ("Exception", "BaseException")
            if broad:
                facts["fallbacks"].append({"line": node.lineno, "type": _call_name(node.type) if node.type else "(bare)",
                                           "does": _handler_summary(node)})
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.lineno not in doc_lines:
            s = node.value
            if SQL_HINT.search(s):
                facts["sql_reads"].extend({"table": t.lower(), "line": node.lineno} for t in SQL_READ.findall(s))
                facts["sql_writes"].extend({"table": t.lower(), "line": node.lineno} for t in SQL_WRITE.findall(s))
            for c in COLLECTION_RE.findall(s):
                facts["collections"].append({"name": c, "line": node.lineno})
    facts["imports"] = sorted({i for i in facts["imports"] if i.split(".")[0] in INTERNAL_PKGS})
    return facts


def _literal(value: ast.AST):
    """A JSON-able rendering of a literal constant (sets sorted), or None."""
    try:
        if isinstance(value, ast.Call) and _call_name(value.func) in ("frozenset", "set", "tuple") and len(value.args) == 1:
            v = ast.literal_eval(value.args[0])
        else:
            v = ast.literal_eval(value)
    except Exception:  # noqa: BLE001 — not a literal
        return None
    if isinstance(v, (set, frozenset)):
        v = sorted(v, key=str)
    if isinstance(v, tuple):
        v = list(v)
    try:
        json.dumps(v)
    except TypeError:
        return None
    return v


def _env_read(node: ast.Call, name: str, consts: dict[str, str]) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    key = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else (
        consts.get(first.id) if isinstance(first, ast.Name) else None)
    if not key or not FLAG_RE.match(key):
        return None
    if name in ("os.getenv", "getenv") or name.endswith(("environ.get", "environ.setdefault")):
        return key
    if name.endswith(".get") and re.search(r"env", name.split(".")[-2] if "." in name else "", re.IGNORECASE):
        return key
    return None


def _handler_summary(node: ast.ExceptHandler) -> str:
    kinds = []
    for stmt in node.body:
        if isinstance(stmt, ast.Pass):
            kinds.append("pass")
        elif isinstance(stmt, ast.Continue):
            kinds.append("continue")
        elif isinstance(stmt, ast.Return):
            kinds.append("return " + (_call_name(stmt.value)[:40] if stmt.value else "None"))
        elif isinstance(stmt, ast.Raise):
            kinds.append("raise")
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and re.search(r"log|warn|print", _call_name(stmt.value.func)):
            kinds.append("log")
        else:
            kinds.append(type(stmt).__name__.lower())
    silent = all(k in ("pass", "continue", "log") or k.startswith("return") for k in kinds) and "raise" not in kinds
    return ("SWALLOWED: " if silent else "handled: ") + ", ".join(kinds)[:120]


# ---------------------------------------------------------------- typescript analysis
TS_EXPORT = re.compile(r"^export\s+(?:default\s+)?(?:async\s+)?(function|const|interface|type|class)\s+(\w+)", re.MULTILINE)
TS_IMPORT = re.compile(r"""from\s+["'](\.{1,2}/[^"']+)["']""")
TS_API = re.compile(r"""\bhttp\.(get|post|put|del|patch)(?:<[^>()]*>)?\(\s*[`"']([^`"'$]+)""")
TS_FETCH = re.compile(r"""\bfetch\(\s*[`"'](/[^`"'$]+)""")


def analyse_ts(path: str, text: str) -> dict:
    lines = text.splitlines()
    def line_of(pos: int) -> int:
        return text.count("\n", 0, pos) + 1
    facts = {"symbols": [{"name": m.group(2), "kind": m.group(1), "line": line_of(m.start())} for m in TS_EXPORT.finditer(text)],
             "imports": [], "api_calls": []}
    base = Path(path).parent
    for m in TS_IMPORT.finditer(text):
        target = (base / m.group(1)).as_posix()
        target = str(Path(target))
        for cand in (target + ".ts", target + ".tsx", target + "/index.ts", target):
            if (ROOT / cand).is_file():
                facts["imports"].append(cand)
                break
    for m in TS_API.finditer(text):
        method = {"del": "DELETE"}.get(m.group(1), m.group(1).upper())
        facts["api_calls"].append({"method": method, "path": m.group(2).split("?")[0], "line": line_of(m.start())})
    for m in TS_FETCH.finditer(text):
        facts["api_calls"].append({"method": "ANY", "path": m.group(1).split("?")[0], "line": line_of(m.start())})
    facts["lines"] = len(lines)
    return facts


# ---------------------------------------------------------------- units
def build_units(files: list[str]) -> list[dict]:
    sizes = {f: read(f).count("\n") + 1 for f in files}
    units, small = [], defaultdict(list)
    for f in files:
        (units.append({"id": f, "files": [f]}) if sizes[f] >= SMALL_LINES else small[str(Path(f).parent)].append(f))
    for d, group in sorted(small.items()):
        chunk, total = [], 0
        chunks = []
        for f in sorted(group):
            if chunk and total + sizes[f] > GROUP_MAX_LINES:
                chunks.append(chunk)
                chunk, total = [], 0
            chunk.append(f)
            total += sizes[f]
        chunks.append(chunk)
        for i, c in enumerate(chunks, 1):
            suffix = "_small-modules" if len(chunks) == 1 else f"_small-modules-{i}"
            units.append({"id": f"{d}/{suffix}", "files": c})
    for u in units:
        u["lines"] = sum(sizes[f] for f in u["files"])
        u["page"] = f"units/{u['id']}.md"
    return sorted(units, key=lambda u: u["id"])


# ---------------------------------------------------------------- repo-level facts
def migrations() -> dict:
    tables: dict[str, dict] = {}
    for sql in sorted((ROOT / "stores/postgres/migrations").glob("*.sql")):
        text = sql.read_text(errors="replace")
        rel = sql.relative_to(ROOT).as_posix()
        for m in re.finditer(r"CREATE TABLE(?: IF NOT EXISTS)?\s+([a-z_][a-z0-9_]*)\s*\((.*?)\n\);", text, re.DOTALL | re.IGNORECASE):
            cols = [c.strip().split()[0] for c in m.group(2).split("\n")
                    if c.strip() and not c.strip().upper().startswith(("PRIMARY", "UNIQUE", "FOREIGN", "CONSTRAINT", "CHECK", "--", ")"))]
            t = tables.setdefault(m.group(1).lower(), {"columns": [], "created": f"{rel}:{text.count(chr(10), 0, m.start()) + 1}", "altered": []})
            t["columns"].extend(c.strip('",') for c in cols if re.match(r'^"?[a-z_][a-z0-9_]*"?,?$', c, re.IGNORECASE))
        for m in re.finditer(r"ALTER TABLE(?: IF EXISTS)?\s+([a-z_][a-z0-9_]*)\s+ADD COLUMN(?: IF NOT EXISTS)?\s+([a-z_][a-z0-9_]*)", text, re.IGNORECASE):
            t = tables.setdefault(m.group(1).lower(), {"columns": [], "created": None, "altered": []})
            t["columns"].append(m.group(2))
            t["altered"].append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}")
    for t in tables.values():
        t["columns"] = sorted(set(t["columns"]))
    return tables


def fleet() -> list[dict]:
    path = "control/control/process_supervisor.py"
    tree = ast.parse(read(path))
    for node in tree.body:
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(target, ast.Name) and target.id == "FLEET":
            out = []
            for elt in node.value.elts:
                v = ast.literal_eval(elt)
                if isinstance(v, dict):
                    port = re.search(r":(\d{4,5})/", v.get("health_url", ""))
                    out.append({"slot": v["name"], "command": " ".join(v.get("argv", [])), "cwd": v.get("cwd", "."),
                                "health": v.get("health_url", ""), "port": port.group(1) if port else "", "line": elt.lineno})
                else:
                    out.append({"slot": v[0], "command": f"python -m {v[1]}", "cwd": ".", "health": "heartbeat", "port": "",
                                "line": elt.lineno})
            return out
    return []


def sidecars() -> list[dict]:
    out = []
    for toml in sorted((ROOT / "sidecars").glob("*.toml")):
        data = tomllib.loads(toml.read_text())
        for name, v in data.items():
            if isinstance(v, dict):
                out.append({"name": name, "display": v.get("display_name", ""), "release": v.get("release", ""),
                            "manifest": v.get("manifest_url", ""), "device": v.get("device", ""),
                            "file": toml.relative_to(ROOT).as_posix()})
    return out


def compose() -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []
    data = yaml.safe_load(read("compose.yaml")) or {}
    out = []
    for name, svc in sorted((data.get("services") or {}).items()):
        out.append({"service": name, "image": svc.get("image", "(build)"), "ports": [str(p) for p in svc.get("ports") or []],
                    "profiles": svc.get("profiles") or []})
    return out


def env_example() -> dict[str, str]:
    out = {}
    p = ROOT / ".env.example"
    if p.exists():
        for line in p.read_text(errors="replace").splitlines():
            m = re.match(r"^\s*([A-Z][A-Z0-9_]+)=(.*)$", line)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


_BOUNDARY: list = []


def boundary_class(method: str, path: str) -> str:
    """The live web boundary's own classifier (orchestrator/orchestrator/web_boundary.py), imported once."""
    try:
        if not _BOUNDARY:
            sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "shared")]
            from orchestrator import (
                web_boundary,
            )
            _BOUNDARY.append(web_boundary)
        probe = re.sub(r"\{[^}]+\}", "x", path)
        return _BOUNDARY[0].classify(method, probe) or "REFUSED (unclassified)"
    except Exception as exc:  # noqa: BLE001 — the page says the class is unknown rather than guessing
        return f"unknown ({type(exc).__name__})"


# ---------------------------------------------------------------- writers
def md_table(headers: list[str], rows: list[list]) -> str:
    esc = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows])


def header(title: str, what: str) -> str:
    return f"# {title}\n\nGenerated by `scripts/codewiki/spine.py` (static analysis, no model) — {what}. Regenerate, never hand-edit.\n\n"


def write(rel: str, text: str) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    files = [f for f in git_files() if is_product(f)]
    texts = {f: read(f) for f in files}
    per_file = {f: (analyse_py(f, t) if f.endswith(".py") else analyse_ts(f, t)) for f, t in texts.items()}
    units = build_units(files)
    unit_of = {f: u["id"] for u in units for f in u["files"]}
    mod_to_file = {module_of(f): f for f in files if f.endswith(".py") and module_of(f)}

    # importers (reverse import graph, per unit)
    importers: dict[str, set[str]] = defaultdict(set)
    for f, facts in per_file.items():
        targets = set()
        for imp in facts.get("imports", []):
            if imp in mod_to_file:
                targets.add(mod_to_file[imp])
            elif imp.endswith((".ts", ".tsx")):
                targets.add(imp)
        for t in targets:
            if t in unit_of and unit_of[t] != unit_of[f]:
                importers[unit_of[t]].add(unit_of[f])

    tables = migrations()
    known_tables = set(tables)
    example = env_example()

    # routes + the UI calls that reach them
    routes = []
    for f, facts in per_file.items():
        for r in facts.get("routes", []):
            routes.append({**r, "file": f})
    ui_calls = [(c, f) for f, facts in per_file.items() if f.startswith("frontend-v2/") for c in facts.get("api_calls", [])]
    for r in routes:
        rx = re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(r["path"])) + "$")
        r["class"] = (boundary_class(r["method"], r["path"]) if r["file"].startswith("orchestrator/")
                      else "not web (sidecar, loopback only)")
        r["ui"] = sorted({f"{f}:{c['line']}" for c, f in ui_calls if rx.match(c["path"].rstrip("/") or "/") and c["method"] in (r["method"], "ANY")})
    routes.sort(key=lambda r: (r["path"], r["method"]))

    # env flags
    flags: dict[str, list] = defaultdict(list)
    for f, facts in per_file.items():
        for e in facts.get("env", []):
            flags[e["name"]].append({"at": f"{f}:{e['line']}", "default": e["default"]})

    # db readers / writers
    db_use: dict[str, dict] = defaultdict(lambda: {"reads": set(), "writes": set()})
    for f, facts in per_file.items():
        for k, key in (("sql_reads", "reads"), ("sql_writes", "writes")):
            for s in facts.get(k, []):
                if s["table"] in known_tables:
                    db_use[s["table"]][key].add(f"{f}:{s['line']}")

    # vocabularies: a constant set of >= 3 identifier-like strings that other units also spell out
    vocab = []
    for f, facts in per_file.items():
        for c in facts.get("constants", []):
            v = c["value"]
            vals = list(v.keys()) if isinstance(v, dict) else v if isinstance(v, list) else None
            if not vals or len(vals) < 3 or not all(isinstance(x, str) and re.match(r"^[A-Za-z_][\w.:-]{1,40}$", x) for x in vals):
                continue
            consumers = []
            need = min(3, len(vals))
            for g, t in texts.items():
                if unit_of[g] == unit_of[f]:
                    continue
                present = [x for x in vals if f'"{x}"' in t or f"'{x}'" in t]
                if len(present) >= need:
                    first = min((t.find(f'"{x}"') if f'"{x}"' in t else t.find(f"'{x}'")) for x in present)
                    consumers.append({"file": g, "line": t.count("\n", 0, first) + 1, "present": len(present),
                                      "missing": [x for x in vals if x not in present][:12]})
            if consumers:
                vocab.append({"name": c["name"], "file": f, "line": c["line"], "values": vals, "consumers": consumers})
    vocab.sort(key=lambda v: (-len(v["consumers"]), v["name"], v["file"]))
    vocab = vocab[:60]
    names = [v["name"] for v in vocab]
    for v in vocab:
        v["slug"] = v["name"] if names.count(v["name"]) == 1 else f"{v['name']}--{Path(v['file']).stem}"

    # ---- spine.json
    unit_facts = {}
    for u in units:
        merged: dict = defaultdict(list)
        for f in u["files"]:
            for k, v in per_file[f].items():
                if isinstance(v, list):
                    merged[k].extend({**x, "file": f} if isinstance(x, dict) else x for x in v)
        unit_facts[u["id"]] = {"files": u["files"], "lines": u["lines"], "page": u["page"],
                               "hash": sha("".join(texts[f] for f in u["files"])),
                               "doc": " ".join(per_file[f].get("doc", "") for f in u["files"])[:600],
                               "importers": sorted(importers.get(u["id"], [])), **merged}
    spine = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip(),
             "units": unit_facts, "routes": routes, "flags": {k: v for k, v in sorted(flags.items())},
             "tables": {t: {**tables[t], "reads": sorted(db_use[t]["reads"]), "writes": sorted(db_use[t]["writes"])} for t in sorted(tables)},
             "fleet": fleet(), "sidecars": sidecars(), "compose": compose(), "vocab": vocab}
    commit = spine["commit"][:10]
    spine.pop("commit")                                   # keep the file byte-stable across commits that change no code
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "spine.json").write_text(json.dumps(spine, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")

    # ---- facts/routes.md
    rows = [[r["method"], f"`{r['path']}`", r["class"], f"`{r['file']}:{r['line']}` {r['handler']}", ", ".join(f"`{u}`" for u in r["ui"][:4]) or "—"]
            for r in routes]
    def verify_block(lines: list[str]) -> str:
        return "\n\n## VERIFY\n\n```verify\n" + "\n".join(sorted(set(lines))) + "\n```\n"

    write("facts/routes.md", header("Routes", f"{len(routes)} HTTP routes; class = the web boundary's verdict for a proxied caller "
                                    "(public / user / write / owner; REFUSED = not reachable through the website)")
          + md_table(["method", "path", "web class", "handler", "UI callers"], rows)
          + verify_block([f"grep -Fq '\"{r['path']}\"' {r['file']}" for r in routes if "'" not in r["path"]]))

    # ---- facts/flags.md
    rows = []
    for name, uses in sorted(flags.items()):
        defaults = sorted({str(u["default"]) for u in uses})
        warn = " ⚠ defaults differ" if len(defaults) > 1 else ""
        rows.append([f"`{name}`", " / ".join(f"`{d}`" for d in defaults) + warn, f"`{example[name]}`" if name in example else "—",
                     ", ".join(f"`{u['at']}`" for u in uses[:5]) + (f" +{len(uses) - 5}" if len(uses) > 5 else "")])
    conflicts = sum(1 for r in rows if "⚠" in r[1])
    write("facts/flags.md", header("Environment flags", f"{len(flags)} flags read by product code; {conflicts} read with different "
                                   "defaults in different places (⚠, a bug class: the flag means different things per reader)")
          + md_table(["flag", "default(s) in code", ".env.example", "read at"], rows)
          + verify_block([f"grep -Fq '{name}' {uses[0]['at'].rsplit(':', 1)[0]}" for name, uses in sorted(flags.items())]))

    # ---- facts/db.md
    rows = [[f"`{t}`", len(v["columns"]), f"`{v['created']}`" if v["created"] else "altered only",
             ", ".join(f"`{x}`" for x in sorted(spine["tables"][t]["writes"])[:4]) or "—",
             ", ".join(f"`{x}`" for x in sorted(spine["tables"][t]["reads"])[:4]) or "—"] for t, v in spine["tables"].items()]
    write("facts/db.md", header("Postgres tables", f"{len(rows)} tables from stores/postgres/migrations; readers / writers from the SQL "
                                "string literals in product code (first four each; spine.json has all)")
          + md_table(["table", "columns", "created", "written at", "read at"], rows)
          + verify_block([f"grep -Fq '{t}' {v['created'].rsplit(':', 1)[0]}" for t, v in spine["tables"].items() if v["created"]]))

    # ---- facts/qdrant.md
    coll: dict[str, set] = defaultdict(set)
    for f, facts in per_file.items():
        for c in facts.get("collections", []):
            coll[c["name"]].add(f"{f}:{c['line']}")
    write("facts/qdrant.md", header("Qdrant collection names", "every `polymath_*` collection literal; names built at run time "
                                    "(contract-suffixed) show their prefix")
          + md_table(["name", "appears at"], [[f"`{k}`", ", ".join(f"`{x}`" for x in sorted(v)[:6])] for k, v in sorted(coll.items())]))

    # ---- facts/mcp-tools.md
    a = {t["name"]: t for t in per_file.get("orchestrator/orchestrator/mcp_server.py", {}).get("mcp_tools", [])}
    b = {t["name"]: t for t in per_file.get("mcp_server/polymath_mcp.py", {}).get("mcp_tools", [])}
    rows = [[f"`{n}`", f"`orchestrator/orchestrator/mcp_server.py:{a[n]['line']}`" if n in a else "— (missing)",
             f"`mcp_server/polymath_mcp.py:{b[n]['line']}`" if n in b else "— (missing)", (a.get(n) or b.get(n))["doc"]]
            for n in sorted(set(a) | set(b))]
    write("facts/mcp-tools.md", header("MCP tools", f"Server A (HTTP :8930, keyed) has {len(a)} tools, Server B (stdio, proxies :7200) "
                                       f"{len(b)}; a tool missing from one server is a parity gap")
          + md_table(["tool", "Server A", "Server B", "first doc line"], rows))

    # ---- facts/fallbacks.md
    rows, swallowed = [], 0
    for f in sorted(per_file):
        for fb in per_file[f].get("fallbacks", []):
            swallowed += fb["does"].startswith("SWALLOWED")
            rows.append([f"`{f}:{fb['line']}`", fb["type"], fb["does"]])
    write("facts/fallbacks.md", header("Broad exception handlers", f"{len(rows)} `except Exception` / bare `except` handlers, "
                                       f"{swallowed} of them SWALLOW the error (pass / continue / return / log only) — each one can hide a failure")
          + md_table(["where", "catches", "what it does"], rows))

    # ---- facts/imports.md
    god = sorted(((len(v), k) for k, v in importers.items()), reverse=True)[:40]
    write("facts/imports.md", header("Import graph", "the 40 most-imported units (god nodes: a change here has the widest blast "
                                     "radius); each unit page lists its own importers")
          + md_table(["unit", "imported by (units)"], [[f"`{k}`", n] for n, k in god]))

    # ---- runtime/truth-tables.md
    fl = spine["fleet"]
    text = header("Runtime truth tables", "what runs, where it listens, how code reaches it")
    text += "## supervised fleet (`control/control/process_supervisor.py` FLEET)\n\n" + md_table(
        ["slot", "command", "cwd", "health", "port", "declared at"],
        [[f"`{x['slot']}`", f"`{x['command']}`", f"`{x['cwd']}`", x["health"], x["port"] or "—",
          f"`control/control/process_supervisor.py:{x['line']}`"] for x in fl])
    text += "\n\n## sidecars (`sidecars/*.toml`)\n\n" + md_table(["name", "model", "release", "manifest", "device", "file"],
        [[f"`{s['name']}`", s["display"], s["release"], s["manifest"], s["device"], f"`{s['file']}`"] for s in spine["sidecars"]])
    text += "\n\n## stores and services (`compose.yaml`)\n\n" + md_table(["service", "image", "ports", "profiles"],
        [[f"`{c['service']}`", c["image"], ", ".join(c["ports"]) or "—", ", ".join(c["profiles"]) or "default"] for c in spine["compose"]])
    text += """

## how code reaches the running system
| change | what makes it live | anchor |
|---|---|---|
| any Python in orchestrator / shared / workers / control | merge into `production`, then `bash scripts/bounce_fleet.sh` (stops the supervisor, boots one fleet, waits for READY). Between the merge and the bounce the fleet is MIXED: stage workers restart on the new bundle within ~2 min, the orchestrator (:7200) keeps the old code until the bounce | `scripts/bounce_fleet.sh` |
| the web UI (frontend-v2/src) | `cd frontend-v2 && npm run build` — :7200 serves `frontend-v2/dist`, which is git-ignored (an unbuilt change is not live, a stash is lost at the next build) | `frontend-v2/vite.config.ts` |
| an `.env` flag | edit `.env`, then bounce FROM A FRESH SHELL (a bounce inherits the caller's exported environment); verify with `ps eww <pid>` | `scripts/boot_polymath.sh` |
| MCP Server B (stdio) | spawned by the client on each session: a new client session picks up the new code | `mcp_server/polymath_mcp.py` |
"""
    write("runtime/truth-tables.md", text)

    # ---- vocab
    index_rows = []
    for v in vocab:
        rel = f"vocab/{v['slug']}.md"
        partial = sum(1 for c in v["consumers"] if c["missing"])
        index_rows.append([f"[`{v['name']}`]({v['slug']}.md)", len(v["values"]), len(v["consumers"]), partial, f"`{v['file']}:{v['line']}`"])
        body = header(f"VOCAB: {v['name']}", f"authority `{v['file']}:{v['line']}` with {len(v['values'])} values; every other unit "
                      "that spells at least three of them")
        body += f"AUTHORITY: `{v['file']}:{v['line']}` :: `{v['name']}` (count: {len(v['values'])}) [DERIVED]\n\n## values (verbatim)\n\n"
        body += ", ".join(f"`{x}`" for x in v["values"]) + "\n\n## consumers (a consumer missing values may be a split vocabulary)\n\n"
        body += md_table(["consumer", "first use", "values present", "values missing (first 12)"],
                         [[f"`{c['file']}`", f"`{c['file']}:{c['line']}`", f"{c['present']}/{len(v['values'])}",
                           ", ".join(f"`{m}`" for m in c["missing"]) or "—"] for c in v["consumers"]])
        body += f"\n\n## VERIFY\n\n```verify\ngrep -Fq '{v['name']}' {v['file']}\n```\n"
        write(rel, body)
    write("vocab/README.md", header("Vocabularies", f"{len(vocab)} shared value sets, most-consumed first; a consumer that spells "
                                    "only part of an authority's values is the 'same concept, several vocabularies' bug class")
          + md_table(["vocabulary", "values", "consumers", "partial consumers", "authority"], index_rows))

    # ---- specimens/prompts.md
    parts = [header("SPECIMENS: model prompts", "every prompt constant in product code, verbatim (the first 3,000 characters); read "
                    "a prompt next to the schema or vocabulary it must agree with")]
    for f in sorted(per_file):
        for p in per_file[f].get("prompts", []):
            t = p["text"] if len(p["text"]) <= 3000 else p["text"][:3000] + f"\n… ({len(p['text']) - 3000} more characters)"
            parts.append(f"## `{p['name']}` — `{f}:{p['line']}`\n\n~~~text\n{t}\n~~~\n")
    write("specimens/prompts.md", "\n".join(parts))

    print(f"spine @ {commit}: {len(units)} units, {len(routes)} routes, {len(flags)} flags ({conflicts} with differing defaults), "
          f"{len(tables)} tables, {len(coll)} collection names, {len(a)}+{len(b)} MCP tools, {len(rows)} broad handlers "
          f"({swallowed} swallowed), {len(vocab)} vocabularies, {sum(len(per_file[f].get('prompts', [])) for f in per_file)} prompts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
