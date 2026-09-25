"""Finish-line Item 2 / D — every `search_atoms` CALLER passes the corpus scope, and passes the RIGHT one.

`orchestrator` resolves to the MAIN checkout under the editable install, so this pin reads the SOURCE of this checkout
(AST) instead of importing it: the executed path is the code under test, in a worktree too.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCAN = ("orchestrator", "workers", "control", "shared", "mcp_server", "scripts", "eval")
UI = ROOT / "orchestrator/orchestrator/api/ui.py"
CHAT = ROOT / "orchestrator/orchestrator/api/chat_retrieval.py"


def _calls(tree, name="search_atoms"):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Attribute) and f.attr == name) or (isinstance(f, ast.Name) and f.id == name):
                yield node


def _scope_src(call) -> str | None:
    kw = next((k for k in call.keywords if k.arg == "corpus_ids"), None)
    return ast.unparse(kw.value) if kw else None


def test_every_search_atoms_call_in_the_repo_passes_corpus_ids():
    seen, missing = 0, []
    for top in SCAN:
        for path in sorted((ROOT / top).rglob("*.py")):
            if ".venv" in path.parts or "site-packages" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:
                continue
            for call in _calls(tree):
                seen += 1
                if _scope_src(call) is None:
                    missing.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert seen >= 6, seen                                   # 5 live callers + the substrate probe (a rename would silently empty this pin)
    assert missing == [], f"unscoped search_atoms call(s): {missing}"


def test_the_live_callers_pass_the_request_corpus_not_a_constant():
    ui, chat = ast.parse(UI.read_text()), ast.parse(CHAT.read_text())
    ui_scopes = sorted(_scope_src(c) for c in _calls(ui))
    assert ui_scopes == ["[cid]", "[corpus_id]"], ui_scopes                        # Corpus Explore's _fetch(cid) and the scout's per-corpus loop
    chat_calls = list(_calls(chat))
    assert sorted(_scope_src(c) for c in chat_calls) == ["[corpus_id]"] * 5       # dual-read atom lane, SEEALSO fan-out, SEEALSO blend lines (11.475), DOC-STEER lines (11.482), WILDCARD atom frontier
    doc_scoped = [ast.unparse(k.value) for c in chat_calls for k in c.keywords if k.arg == "doc_ids"]
    assert doc_scoped == ["q_docs", "q_docs"], doc_scoped                           # the blend and the steer read only the question's own documents' lines


def test_corpus_explore_fetch_uses_its_own_argument():
    fetch = next(n for n in ast.walk(ast.parse(UI.read_text())) if isinstance(n, ast.FunctionDef) and n.name == "_fetch"
                 and any(True for _ in _calls(n)))
    assert [a.arg for a in fetch.args.args] == ["cid"]
    (call,) = list(_calls(fetch))
    assert _scope_src(call) == "[cid]"                       # the bug was exactly this: `_fetch(cid)` ignored `cid`


def test_the_atom_universe_diagnostic_is_scoped_to_the_request_corpora():
    (call,) = list(_calls(ast.parse(UI.read_text()), "count_atoms"))
    assert _scope_src(call) == "corpora"
    src = UI.read_text()
    assert 'key="atom_kind", match=_qm.MatchAny(any=list(CONCEPT_ATOM_KINDS))' not in src       # the unscoped count is gone
