"""PRODUCTION-APP-BOOTSTRAP-V1: the query application must import and
register every required production route.

Regression for the P0 class found by the 2026-08-26 SMART verification:
`orchestrator.main` referenced `ask_router` without importing it — the
worker fence passed 13/13 while the product API could not even import.
A NameError at module scope, or a route referenced without
registration, must fail HERE, in seconds, without stores.

This test needs NO database, NO sidecars, NO network: FastAPI route
registration is pure Python.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "shared", ROOT / "orchestrator"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# Every production route the query product requires. A route removed
# from this set is an OWNER decision, not a refactor side effect.
REQUIRED_ROUTES = {
    ("/health", "GET"),
    ("/ready", "GET"),
    ("/sidecars", "GET"),
    ("/intake", "POST"),
    ("/ask", "POST"),
    ("/retrieve", "POST"),
    ("/evidence", "POST"),
    ("/chat", "POST"),
}


def _load_app():
    """Import the production FastAPI app exactly as uvicorn would
    (PYTHONPATH=orchestrator → `orchestrator.main:app`). Falls back to
    the repo-root form when another test already bound the outer
    package. An import-time NameError/ImportError surfaces here as the
    test failure it should always have been."""
    try:
        from orchestrator.main import app
    except ImportError:
        from orchestrator.orchestrator.main import app

    return app


def test_production_app_imports_cleanly():
    app = _load_app()
    assert app.title == "Polymath Orchestrator"


def _flatten_routes(routes):
    """FastAPI >=0.141 wraps include_router() output in _IncludedRouter
    (no .path); older versions inline APIRoute objects. Duck-typed walk
    covers both."""
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _flatten_routes(inner.routes)
        else:
            yield route


def test_every_required_route_is_registered():
    app = _load_app()
    registered = {
        (route.path, method)
        for route in _flatten_routes(app.routes)
        for method in (getattr(route, "methods", None) or [])
    }
    missing = REQUIRED_ROUTES - registered
    assert not missing, f"unregistered production routes: {sorted(missing)}"


def test_no_router_referenced_without_import():
    """Source-level guard: every `app.include_router(NAME)` in main.py
    must bind NAME at module scope. This is the exact defect class that
    escaped: registration referencing an unimported name."""
    import ast

    src_path = ROOT / "orchestrator" / "orchestrator" / "main.py"
    tree = ast.parse(src_path.read_text())

    bound: set[str] = set()
    referenced: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            bound.add(node.name)
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == "include_router"):
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    referenced.append(arg.id)

    unbound = [name for name in referenced if name not in bound]
    assert not unbound, f"include_router references unbound names: {unbound}"
    assert referenced, "main.py registers no routers — bootstrap is broken"
