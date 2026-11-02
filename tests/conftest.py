"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def shared_on_path(repo_root: Path) -> None:
    p = repo_root / "shared"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# PROVIDER-ATTEMPT-LEDGER-V1 test isolation.
#
# The ledger records at `LLMExtractionClient.complete_one`, which unit tests exercise
# with fake lanes. With POLYMATH_PG_DSN set (it is, because tests run against the dev
# database) those fakes wrote real rows into `llm_provider_attempts` — two rows for
# lanes named `cp_success` / `cp_refused` were found in the production ledger during the
# 2026-09-12 bootstrap. An accounting ledger polluted by test fixtures cannot be
# reconciled against, so the whole test session opts out at import time.
import os as _os

_os.environ.setdefault("POLYMATH_ATTEMPT_LEDGER", "0")
_os.environ["POLYMATH_ATTEMPT_LEDGER"] = "0"

# CORPUS-ACCESS-PARITY F6 test isolation: creating a friend creates its private library row in Postgres
# (orchestrator/web_accounts.py). Tests create friends in throwaway registries all the time; with the dev database behind
# POLYMATH_PG_DSN each would leave an `fr-<name>` corpus in the live fleet. The session opts out; a test that proves the
# creation turns it back on for itself and deletes what it made.
_os.environ["POLYMATH_PRIVATE_LIBRARY_AUTOCREATE"] = "0"

# R1 N1 (DNS rebinding) test infrastructure: the web boundary (orchestrator/web_boundary.py) now refuses a DIRECT request — one
# with no proxy header — whose Host is not loopback (403 NON_LOOPBACK_HOST). Starlette's TestClient defaults to base_url
# "http://testserver", i.e. Host "testserver", which the boundary rightly reads as some other machine's name. Production code keeps
# no test exemption; instead, for this whole test session, a TestClient built WITHOUT its own base_url (keyword or positional) and
# WITHOUT a Host header of its own gets base_url "http://127.0.0.1" — the address every in-repo caller uses
# (http://127.0.0.1:7200). How: TestClient.__init__ (Starlette's class; fastapi.testclient re-exports the same class) is wrapped
# once, here, at import, before any test module builds a client; the wrapper only fills in that one default and calls the original.
# Paths, cookies, request headers and every assertion stay the same (no test reads "testserver" back from a default client); a test
# that passes its own base_url or Host — a rebinding test, a proxied "https://testserver" client — keeps it exactly. Not covered:
# TestClient.websocket_connect always dials ws://testserver, so a websocket test through the boundary gives the client a Host
# header of its own (TestClient(app, headers={"host": "127.0.0.1"})); the orchestrator has no websocket route today.
import inspect as _inspect

from starlette import testclient as _starlette_testclient

_LOOPBACK_BASE_URL = "http://127.0.0.1"
_TEST_CLIENT = _starlette_testclient.TestClient
_TEST_CLIENT_INIT = _TEST_CLIENT.__init__
_TEST_CLIENT_SIGNATURE = _inspect.signature(_TEST_CLIENT_INIT)


def _names_its_host(headers) -> bool:
    if not headers:
        return False
    keys = headers.keys() if hasattr(headers, "keys") else (pair[0] for pair in headers)
    return any(str(k).lower() == "host" for k in keys)


def _test_client_init_on_loopback(self, *args, **kwargs):
    try:
        given = _TEST_CLIENT_SIGNATURE.bind_partial(self, *args, **kwargs).arguments
    except TypeError:                                   # arguments the original refuses: let it say so, unchanged
        given = {"base_url": None}
    if "base_url" not in given and not _names_its_host(given.get("headers")):
        kwargs["base_url"] = _LOOPBACK_BASE_URL
    _TEST_CLIENT_INIT(self, *args, **kwargs)


if not getattr(_TEST_CLIENT_INIT, "_polymath_loopback_default", False):
    _test_client_init_on_loopback._polymath_loopback_default = True
    _TEST_CLIENT.__init__ = _test_client_init_on_loopback
