"""SEALED-TEST-ISOLATION-V1: no test reaches a live store or the live fleet unless the operator opts in.

Two kinds of check:
- STATIC: no test file under tests/ (the helper `tests/sealed_env.py` and the opt-in `tests/integration/` bucket aside) names
  the live Postgres in a DSN literal, or hands a live fleet URL to a network call. A literal that is only data (a fake error
  message, a refusal example) carries the comment `# not-a-connection` on one of its lines.
- RUNTIME: the guard that `tests/conftest.py` installs refuses a connection to a live fleet port (Python sockets and psycopg),
  `sealed_dsn()` takes the database only from POLYMATH_TEST_DSN and refuses a live port, `live_fleet()` skips unless the
  operator set POLYMATH_LIVE_PROBES=1, and a session whose POLYMATH_TEST_DSN names port 5432 stops before any test runs.
Every runtime check uses a port nothing on this host listens on (8755, the retired local extractor) or a Unix socket path that
does not exist, so a broken guard fails the check without reaching the live fleet.
"""
from __future__ import annotations

import ast
import os
import re
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import sealed_env

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
HELPER = TESTS / "sealed_env.py"
MARKER = "# not-a-connection"
LOOPBACK = r"(?:127\.0\.0\.1|localhost|\[::1\])"
PG_DSN = re.compile(r"postgres(?:ql)?://(?:[^@\s\"'/]*@)?" + LOOPBACK + r"(?::(\d+))?(?=[/\s\"'?]|$)")
FLEET_URL = re.compile(r"(?:https?|bolt|neo4j|redis)://" + LOOPBACK + r":(\d+)")
#: the terminal name of a call that opens a connection to the URL it is given
NETWORK_CALLS = {"urlopen", "Request", "get", "post", "put", "patch", "delete", "head", "options", "request", "stream",
                 "Client", "AsyncClient", "create_connection", "connect", "driver", "from_url", "QdrantClient", "Redis"}
UNUSED_LIVE_PORT = 8755           # in LIVE_PORTS; the local extractor lane is retired, so nothing listens here


def _scanned_files() -> list[Path]:
    return sorted(p for p in TESTS.rglob("*.py")
                  if p != HELPER and "integration" not in p.relative_to(TESTS).parts[:1])


def _text_of(node: ast.AST) -> str | None:
    """A string literal's text; an f-string's literal parts joined around `{}`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}" for v in node.values)
    return None


def _label(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name


def _marked(lines: list[str], node: ast.AST) -> bool:
    return any(MARKER in lines[i - 1] for i in range(node.lineno, (node.end_lineno or node.lineno) + 1))


def _call_name(call: ast.Call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def _live_dsn_literals(path: Path) -> list[str]:
    src = path.read_text()
    lines = src.splitlines()
    found = []
    for node in ast.walk(ast.parse(src)):
        text = _text_of(node)
        if text is None or _marked(lines, node):
            continue
        for m in PG_DSN.finditer(text):
            if m.group(1) is None or int(m.group(1)) in sealed_env.LIVE_PORTS:
                found.append(f"{_label(path)}:{node.lineno}")
    return found


def _live_url_calls(path: Path) -> list[str]:
    src = path.read_text()
    lines = src.splitlines()
    found = []
    for call in ast.walk(ast.parse(src)):
        if not isinstance(call, ast.Call) or _call_name(call) not in NETWORK_CALLS:
            continue
        for arg in [*call.args, *(k.value for k in call.keywords)]:
            text = _text_of(arg)
            if text is None or _marked(lines, arg):
                continue
            if any(int(m.group(1)) in sealed_env.LIVE_PORTS for m in FLEET_URL.finditer(text)):
                found.append(f"{_label(path)}:{arg.lineno}")
    return found


# ── STATIC ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_no_test_names_the_live_database_in_a_dsn():
    """The census incident (2026-11-20): a hardcoded `...@127.0.0.1:5432/polymath` seeded probe rows into the live database."""
    offenders = [hit for p in _scanned_files() for hit in _live_dsn_literals(p)]
    assert offenders == [], ("a DSN literal names the live Postgres (port 5432 or no port); take the database from "
                             f"sealed_env.sealed_dsn() instead: {offenders}")


def test_no_test_hands_a_live_fleet_url_to_a_network_call():
    """The receipts incident (2026-11-20): probes called http://127.0.0.1:7200 on every run and wrote live query receipts."""
    offenders = [hit for p in _scanned_files() for hit in _live_url_calls(p)]
    assert offenders == [], ("a network call is given a live fleet URL; a deliberate live probe calls "
                             f"sealed_env.live_fleet(...) and uses sealed_env.LIVE_ORCHESTRATOR / LIVE_RERANKER: {offenders}")


def test_the_scan_sees_what_it_is_meant_to_see(tmp_path):
    """The scan itself: it flags a live DSN, a port-less DSN and a live URL handed to a call; it passes a sealed DSN, an
    in-process TestClient base_url, a Host header and a marked literal."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import psycopg, urllib.request\n"
        f"DSN = {sealed_env.LIVE_PG_DSN!r}\n"
        "NOPORT = 'postgresql://u:p@localhost/db'\n"              # not-a-connection: the scan's own example text
        "psycopg.connect(DSN)\n"
        f"urllib.request.urlopen({sealed_env.LIVE_ORCHESTRATOR + '/ready'!r})\n"
        f"urllib.request.Request(f'{sealed_env.LIVE_RERANKER}{{path}}')\n")
    good = tmp_path / "good.py"
    good.write_text(
        "SEALED = 'postgresql://u:p@127.0.0.1:55432/db'\n"
        "c = TestClient(app, base_url='http://127.0.0.1:7200')\n"
        "c.get('/ready', headers={'host': '127.0.0.1:7200'})\n"
        "MSG = 'connection to postgresql://u:secret@127.0.0.1:5432/x failed'  # not-a-connection: a fake error text\n")
    assert len(_live_dsn_literals(bad)) == 2 and len(_live_url_calls(bad)) == 2
    assert _live_dsn_literals(good) == [] and _live_url_calls(good) == []


# ── RUNTIME ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dsn,refused", [
    (sealed_env.LIVE_PG_DSN, True),
    ("postgresql://u:p@127.0.0.1/db", True),                       # not-a-connection: no port means libpq's 5432
    ("host=127.0.0.1 port=5432 dbname=polymath", True),
    ("host=localhost dbname=polymath", True),
    ("postgresql://u:p@127.0.0.1:55432/polymath", False),
    ("host=127.0.0.1 port=55432 dbname=polymath", False),
])
def test_a_test_dsn_must_name_a_port_outside_the_live_fleet(dsn, refused):
    assert (sealed_env.dsn_refusal(dsn) is not None) is refused


def test_sealed_dsn_reads_only_the_test_variable(monkeypatch):
    monkeypatch.setenv("POLYMATH_PG_DSN", "postgresql://u:p@127.0.0.1:55432/other")
    monkeypatch.delenv(sealed_env.TEST_DSN_ENV, raising=False)
    with pytest.raises(pytest.skip.Exception, match=sealed_env.TEST_DSN_ENV):
        sealed_env.sealed_dsn()                                    # POLYMATH_PG_DSN alone is never taken
    monkeypatch.setenv(sealed_env.TEST_DSN_ENV, sealed_env.LIVE_PG_DSN)
    with pytest.raises(sealed_env.LiveStoreRefused):
        sealed_env.sealed_dsn()
    monkeypatch.setenv(sealed_env.TEST_DSN_ENV, "postgresql://u:p@127.0.0.1:55432/polymath")
    assert sealed_env.sealed_dsn() == "postgresql://u:p@127.0.0.1:55432/polymath"


def test_the_session_points_code_under_test_at_the_sealed_database():
    sealed = "postgresql://u:p@127.0.0.1:55432/polymath"
    assert sealed_env.session_environment({sealed_env.TEST_DSN_ENV: sealed, "POLYMATH_PG_DSN": sealed_env.LIVE_PG_DSN}) \
        == {"POLYMATH_PG_DSN": sealed}
    assert sealed_env.session_environment({"POLYMATH_PG_DSN": sealed_env.LIVE_PG_DSN}) == {}
    with pytest.raises(sealed_env.LiveStoreRefused):
        sealed_env.session_environment({sealed_env.TEST_DSN_ENV: sealed_env.LIVE_PG_DSN})


def test_a_socket_to_a_live_fleet_port_is_refused():
    sealed_env.install_guard()
    with pytest.raises(sealed_env.LiveFleetRefused):
        socket.create_connection(("127.0.0.1", UNUSED_LIVE_PORT), timeout=2)
    s = socket.socket()
    try:
        assert s.connect_ex(("127.0.0.1", UNUSED_LIVE_PORT)) != 0
    finally:
        s.close()


def test_a_socket_to_any_other_port_still_connects():
    sealed_env.install_guard()
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    accepted = threading.Thread(target=lambda: server.accept()[0].close(), daemon=True)
    accepted.start()
    try:
        socket.create_connection(server.getsockname(), timeout=2).close()
    finally:
        accepted.join(timeout=2)
        server.close()


def test_a_psycopg_connection_to_the_live_port_is_refused():
    psycopg = pytest.importorskip("psycopg")
    sealed_env.install_guard()
    with pytest.raises(sealed_env.LiveStoreRefused):
        psycopg.connect("host=/nonexistent-polymath-socket-dir port=5432 dbname=polymath connect_timeout=1")
    with pytest.raises(sealed_env.LiveStoreRefused):
        psycopg.Connection.connect("host=/nonexistent-polymath-socket-dir dbname=polymath connect_timeout=1")


def test_a_live_probe_skips_unless_the_operator_opts_in(monkeypatch):
    sealed_env.install_guard()
    monkeypatch.delenv(sealed_env.LIVE_PROBES_ENV, raising=False)
    with pytest.raises(pytest.skip.Exception, match=sealed_env.LIVE_PROBES_ENV):
        sealed_env.live_fleet("a probe")
    monkeypatch.setenv(sealed_env.LIVE_PROBES_ENV, "1")
    sealed_env.live_fleet("a probe")                               # opted in: the guard opens for this test only
    try:
        with pytest.raises(ConnectionRefusedError) as refused:
            socket.create_connection(("127.0.0.1", UNUSED_LIVE_PORT), timeout=2)
        assert not isinstance(refused.value, sealed_env.LiveFleetRefused)
    finally:
        sealed_env.close_live_fleet()                              # conftest also closes it after every test


def test_litellm_never_loads_a_dotenv_into_the_test_session():
    """litellm's import-time load_dotenv found the live checkout's .env from its .venv and loaded the fleet's configuration
    and provider keys into a sealed run; the session turns it off (litellm skips it unless LITELLM_MODE is "DEV")."""
    if not sealed_env._state["installed"]:
        pytest.skip("tests/conftest.py is not loaded (--noconftest)")
    assert os.environ.get("LITELLM_MODE") == "PRODUCTION"


def test_a_session_whose_test_dsn_names_port_5432_stops_before_any_test():
    env = {**os.environ, sealed_env.TEST_DSN_ENV: sealed_env.LIVE_PG_DSN}
    done = subprocess.run([sys.executable, "-m", "pytest", str(Path(__file__)), "--collect-only", "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == pytest.ExitCode.USAGE_ERROR, done.stdout[-600:] + done.stderr[-600:]
    assert sealed_env.TEST_DSN_ENV in done.stderr and "polymath-dev" not in done.stdout + done.stderr   # the password stays out
