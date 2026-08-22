"""Every sidecar client must be able to call its own methods.

`RerankerClient` carried its own bare `httpx.Client` while its `rerank()`
called `self.request(...)`, a method that lives only on `SidecarClient`.
Every rerank therefore raised AttributeError and the orchestrator
answered 502 `rerank_unavailable` on FAST, HYBRID and GRAPH alike.

Nothing caught it. The sidecar was healthy and reported ready; the
client was the broken half, and no test or acceptance run had exercised
retrieval since the client was refactored. This fence is static so it
holds without a live sidecar.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import clients as C  # noqa: E402

CLIENTS = [obj for name, obj in vars(C).items()
           if isinstance(obj, type) and name.endswith("Client")]


def test_at_least_the_known_clients_are_discovered():
    names = {c.__name__ for c in CLIENTS}
    assert {"SidecarClient", "GlinerClient", "EmbedderClient",
            "RerankerClient"} <= names, f"client discovery broke: {names}"


@pytest.mark.parametrize("cls", CLIENTS, ids=lambda c: c.__name__)
def test_client_can_call_every_self_method_it_references(cls):
    """A client that calls self.X must actually have X."""
    try:
        src = inspect.getsource(cls)
    except OSError:
        pytest.skip(f"no source for {cls.__name__}")
    tree = ast.parse(ast.unparse(ast.parse(src)))

    def _self_attrs(pred):
        return {n.attr for n in ast.walk(tree)
                if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "self"
                and pred(n)}

    # Attributes ASSIGNED on self (in __init__ or elsewhere) exist at
    # runtime but not on the class, so they are defined for our purposes.
    assigned = {t.attr for node in ast.walk(tree)
                if isinstance(node, (ast.Assign, ast.AnnAssign))
                for t in (node.targets if isinstance(node, ast.Assign)
                          else [node.target])
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                and t.value.id == "self"}
    # Inherited __init__ may assign them too; walk the MRO's sources.
    for base in cls.__mro__[1:]:
        try:
            btree = ast.parse(inspect.getsource(base))
        except (OSError, TypeError):
            continue
        assigned |= {t.attr for node in ast.walk(btree)
                     if isinstance(node, (ast.Assign, ast.AnnAssign))
                     for t in (node.targets if isinstance(node, ast.Assign)
                               else [node.target])
                     if isinstance(t, ast.Attribute)
                     and isinstance(t.value, ast.Name) and t.value.id == "self"}

    referenced = _self_attrs(lambda n: True)
    missing = sorted(a for a in referenced
                     if not hasattr(cls, a) and a not in assigned
                     and not a.startswith("_"))
    assert not missing, (
        f"{cls.__name__} references self.{{{', '.join(missing)}}} but does "
        f"not define or inherit them; every call raises AttributeError")


@pytest.mark.parametrize("cls", CLIENTS, ids=lambda c: c.__name__)
def test_every_client_shares_the_bounded_request_path(cls):
    """Retry, pool invalidation and typed failure are not per-client."""
    if cls is C.SidecarClient:
        return
    assert issubclass(cls, C.SidecarClient), (
        f"{cls.__name__} does not inherit SidecarClient, so it misses the "
        f"bounded timeouts, pool invalidation, retry and SidecarUnavailable "
        f"typing that every other sidecar call gets")


def test_rerank_failure_reports_the_message_not_just_the_type():
    from polymath_shared import rerank as R

    src = inspect.getsource(R.apply_rerank)
    assert "{exc}" in src, (
        "the rerank failure carries only the exception TYPE; "
        "'reranker unavailable: AttributeError' names neither the missing "
        "attribute nor the class")
