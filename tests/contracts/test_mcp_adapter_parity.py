"""GOVERNED-CONVERGENCE-V1 TG1 — MCP Server A / Server B adapter-tool parity.

The governed adapter run must be drivable from BOTH MCP surfaces: Server A (orchestrator/orchestrator/mcp_server.py,
streamable-http :8930, bearer key — Hermes) and Server B (mcp_server/polymath_mcp.py, stdio, no credential — Claude
Code / Codex). Both register the SAME seven adapter_* tools with the SAME parameters and the same described semantics,
and neither loses the REASONING-BOUNDARY-V1 canonical trio (search / explore / answer).

Both modules are loaded BY FILE PATH from this checkout (neither has an intra-package import), so the executed path is
the code under test even inside a worktree — the editable `.pth` would otherwise resolve `orchestrator` to MAIN.
"""
import ast
import asyncio
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER_A = "orchestrator/orchestrator/mcp_server.py"
SERVER_B = "mcp_server/polymath_mcp.py"
ADAPTER_TOOLS = ("adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status",
                 "adapter_result", "adapter_cancel")
CANONICAL_TRIO = ("polymath_search", "polymath_explore", "polymath_answer")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__   # executed path == this checkout
    return mod


def _tools(server) -> dict:
    return {t.name: t for t in asyncio.run(server.list_tools())}


def _both() -> tuple[dict, dict]:
    return _tools(_load("parity_mcp_server_a", SERVER_A).mcp), _tools(_load("parity_mcp_server_b", SERVER_B).server)


def test_both_servers_register_the_seven_adapter_tools():
    a, b = _both()
    for name in ADAPTER_TOOLS:
        assert name in a, f"Server A lost {name}"
        assert name in b, f"Server B lacks {name}"
    assert sorted(n for n in a if n.startswith("adapter_")) == sorted(ADAPTER_TOOLS)
    assert sorted(n for n in b if n.startswith("adapter_")) == sorted(ADAPTER_TOOLS)


def test_adapter_tools_take_the_same_parameters_on_both_servers():
    a, b = _both()
    for name in ADAPTER_TOOLS:
        sa, sb = a[name].input_schema, b[name].input_schema
        assert sa.get("properties", {}) == sb.get("properties", {}), name      # names, types AND defaults
        assert sorted(sa.get("required") or []) == sorted(sb.get("required") or []), name


def test_adapter_tools_describe_the_same_semantics_on_both_servers():
    a, b = _both()
    for name in ADAPTER_TOOLS:
        assert " ".join((a[name].description or "").split()) == " ".join((b[name].description or "").split()), name


def test_both_servers_keep_the_canonical_trio():
    a, b = _both()
    for name in CANONICAL_TRIO:
        assert name in a, f"Server A lost {name}"
        assert name in b, f"Server B lost {name}"


def test_capabilities_advertises_exactly_the_seven_adapter_tools():
    tree = ast.parse((ROOT / "orchestrator/orchestrator/api/capabilities.py").read_text())
    value = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "ADAPTER_MCP_TOOLS" for t in n.targets))
    assert sorted(ast.literal_eval(value)) == sorted(ADAPTER_TOOLS)


def test_server_b_adapter_tools_only_proxy_the_adapter_routes():
    """The proxies decide nothing: every adapter_* body on Server B is one `_adapter(...)` call onto /adapter/*."""
    tree = ast.parse((ROOT / SERVER_B).read_text())
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ADAPTER_TOOLS}
    assert sorted(fns) == sorted(ADAPTER_TOOLS)
    for name, fn in fns.items():
        body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]   # drop the docstring
        assert len(body) == 1 and isinstance(body[0], ast.Return), name
        call = body[0].value
        assert isinstance(call, ast.Call) and getattr(call.func, "id", None) == "_adapter", name
        path = call.args[1]
        literal = path.value if isinstance(path, ast.Constant) else "".join(
            v.value for v in path.values if isinstance(v, ast.Constant))
        assert literal.startswith("/adapter/"), (name, literal)
