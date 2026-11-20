"""SEALED-TEST-ISOLATION-V1: where a test may connect.

Rules (work-log docs/wiki/work-log/2026-11-20-sealed-test-isolation.md):

1. Test code takes its database from POLYMATH_TEST_DSN only: `sealed_dsn()`. The DSN must name a port, and not a live fleet
   port (5432 is the live Postgres). Unset: the calling test skips, saying so. A live port: LiveStoreRefused; tests/conftest.py
   turns that into a usage error before any test runs. The session also sets POLYMATH_PG_DSN to the same value, so code under
   test (settings, pools, child processes) reaches the sealed database too.
2. A connection to a live fleet port from inside a test is refused: Python sockets (HTTP, Bolt, Redis) and psycopg (libpq opens
   its own sockets, so the socket hook never sees it). The refusal looks like a closed port (ConnectionRefusedError /
   psycopg.OperationalError), which is what GitHub CI sees. tests/conftest.py prints every refusal at the end of the run.
3. One opt-in: a test that deliberately probes the running fleet calls `live_fleet(what)` first. It skips unless the operator
   set POLYMATH_LIVE_PROBES=1; with it, the guard opens for that test only. Tests under tests/integration/ keep their own opt-in,
   POLYMATH_INTEGRATION=1, which opens the guard for that bucket.

This module is the only file under tests/ that names a live address (tests/contracts/test_sealed_test_isolation.py checks it).
It never prints a DSN: a DSN carries the password.
"""
from __future__ import annotations

import errno
import os
import socket
from collections import Counter

import psycopg
from psycopg.conninfo import conninfo_to_dict

TEST_DSN_ENV = "POLYMATH_TEST_DSN"
LIVE_PROBES_ENV = "POLYMATH_LIVE_PROBES"
INTEGRATION_ENV = "POLYMATH_INTEGRATION"

#: The live fleet's ports (compose.yaml, control/control/process_supervisor.py, shared/polymath_shared/settings.py,
#: orchestrator/orchestrator/mcp_server.py, scripts/friends_access_caddy.py; the listeners checked with lsof on 2026-11-20).
#: Refused on every host: no test has a reason to reach them anywhere, and the friends-access door listens on every address.
LIVE_PORTS: dict[int, str] = {
    5432: "Postgres",
    6333: "Qdrant (container port)",
    6334: "Qdrant",
    6379: "Redis",
    7200: "orchestrator",
    7474: "Neo4j HTTP (container port)",
    7475: "Neo4j HTTP",
    7687: "Neo4j Bolt (container port)",
    7688: "Neo4j Bolt",
    8742: "embedder sidecar",
    8743: "reranker sidecar",
    8755: "local extractor sidecar",
    8767: "Trail MCP",
    8794: "friends-access door",
    8930: "MCP server",
}

#: The live fleet's addresses, for live probes only (each one calls `live_fleet()` first).
LIVE_PG_DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
LIVE_ORCHESTRATOR = "http://127.0.0.1:7200"
LIVE_RERANKER = "http://127.0.0.1:8743"

NO_SEALED_DB = (f"no sealed test database: set {TEST_DSN_ENV} to a throwaway Postgres on a port other than 5432 "
                "(docs/RUNBOOK.md, 'Run the test suites')")


class LiveFleetRefused(ConnectionRefusedError):
    """A socket to a live fleet port, refused by the test guard (no connection was made)."""


class LiveStoreRefused(psycopg.OperationalError):
    """A Postgres connection to a live port, refused by the test guard, or a POLYMATH_TEST_DSN that names one."""


#: (port, where) -> attempts refused this session; `where` is the test's node id.
refused: Counter[tuple[int, str]] = Counter()
_state: dict[str, object] = {"installed": False, "open": False, "where": "collection"}


def dsn_refusal(dsn: str) -> str | None:
    """Why `dsn` may not be the sealed test database, or None. It must name a port, and not a live one."""
    try:
        params = conninfo_to_dict(dsn)
    except Exception as exc:  # noqa: BLE001 — the message names the error type only: the DSN carries the password
        return f"it cannot be read as a Postgres DSN ({type(exc).__name__})"
    ports = [p.strip() for p in str(params.get("port") or "").split(",") if p.strip()]
    if not ports:
        return "it names no port, and libpq would use 5432, the live Postgres"
    live = [int(p) for p in ports if p.isdigit() and int(p) in LIVE_PORTS]
    if live:
        return f"it names port {live[0]} ({LIVE_PORTS[live[0]]}), a live fleet port"
    return None


def sealed_dsn() -> str:
    """The sealed test database's DSN, from POLYMATH_TEST_DSN only. Skips the calling test when it is unset."""
    raw = os.environ.get(TEST_DSN_ENV, "").strip()
    if not raw:
        import pytest
        pytest.skip(NO_SEALED_DB)
    why = dsn_refusal(raw)
    if why:
        raise LiveStoreRefused(f"{TEST_DSN_ENV} cannot be the test database: {why}")
    return raw


def sealed_dsn_with_password(password: str) -> str:
    """The sealed database's address with another password: a login there that must fail (skips like `sealed_dsn()`)."""
    from psycopg.conninfo import make_conninfo
    return make_conninfo(sealed_dsn(), password=password)


def sealed_dsn_configured() -> bool:
    """True when POLYMATH_TEST_DSN is set (for a skip decided at import time, where `sealed_dsn()` may not skip)."""
    return bool(os.environ.get(TEST_DSN_ENV, "").strip())


def session_environment(env) -> dict[str, str]:
    """The environment a test session sets: POLYMATH_PG_DSN follows POLYMATH_TEST_DSN when that is set."""
    raw = str(env.get(TEST_DSN_ENV, "") or "").strip()
    if not raw:
        return {}
    why = dsn_refusal(raw)
    if why:
        raise LiveStoreRefused(f"{TEST_DSN_ENV} cannot be the test database: {why}. Point it at a throwaway Postgres "
                               "on another port (docs/RUNBOOK.md, 'Run the test suites').")
    return {"POLYMATH_PG_DSN": raw}


def live_fleet(what: str) -> None:
    """A deliberate live probe: skip unless the operator set POLYMATH_LIVE_PROBES=1; then open the guard for this test."""
    if os.environ.get(LIVE_PROBES_ENV) != "1":
        import pytest
        pytest.skip(f"live fleet probe ({what}): it writes live query receipts and may spend model calls; "
                    f"set {LIVE_PROBES_ENV}=1 to run it against the running fleet")
    _state["open"] = True


def close_live_fleet() -> None:
    _state["open"] = False


def begin(where: str, *, open_: bool = False) -> None:
    """Called by tests/conftest.py around each test (and each integration module's collection)."""
    _state["where"] = where
    _state["open"] = open_


def end() -> None:
    _state["where"] = "between tests"
    _state["open"] = False


def _refuse(port: int) -> str | None:
    if _state["open"]:
        return None
    refused[(port, str(_state["where"]))] += 1
    return (f"live-fleet guard: port {port} ({LIVE_PORTS[port]}) belongs to the live fleet; a test may reach it only as a "
            f"declared live probe with {LIVE_PROBES_ENV}=1 (tests/sealed_env.py)")


def _socket_port(address) -> int | None:
    if isinstance(address, tuple) and len(address) >= 2 and isinstance(address[1], int) and address[1] in LIVE_PORTS:
        return address[1]
    return None


def _pg_port(conninfo: str, kwargs: dict) -> int | None:
    try:
        params = conninfo_to_dict(conninfo) if conninfo else {}
    except Exception:  # noqa: BLE001 — psycopg reports its own parse error on the real call
        return None
    raw = kwargs.get("port") or params.get("port") or os.environ.get("PGPORT") or "5432"
    for p in str(raw).split(","):
        if p.strip().isdigit() and int(p) in LIVE_PORTS:
            return int(p)
    return None


def install_guard() -> None:
    """Refuse live fleet ports for the rest of this process. Idempotent."""
    if _state["installed"]:
        return
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def connect(self, address):
        port = _socket_port(address)
        why = port is not None and _refuse(port)
        if why:
            raise LiveFleetRefused(errno.ECONNREFUSED, why)
        return real_connect(self, address)

    def connect_ex(self, address):
        port = _socket_port(address)
        if port is not None and _refuse(port):
            return errno.ECONNREFUSED
        return real_connect_ex(self, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex

    real_pg = psycopg.Connection.connect.__func__
    real_apg = psycopg.AsyncConnection.connect.__func__

    def pg_connect(cls, conninfo: str = "", **kwargs):
        port = _pg_port(conninfo, kwargs)
        why = port is not None and _refuse(port)
        if why:
            raise LiveStoreRefused(why)
        return real_pg(cls, conninfo, **kwargs)

    async def apg_connect(cls, conninfo: str = "", **kwargs):
        port = _pg_port(conninfo, kwargs)
        why = port is not None and _refuse(port)
        if why:
            raise LiveStoreRefused(why)
        return await real_apg(cls, conninfo, **kwargs)

    psycopg.Connection.connect = classmethod(pg_connect)
    psycopg.AsyncConnection.connect = classmethod(apg_connect)
    psycopg.connect = psycopg.Connection.connect          # the module alias was bound at import
    _state["installed"] = True
