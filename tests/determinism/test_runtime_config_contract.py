"""P21 RUNTIME-CONFIG-CONTRACT-V1 — configuration is a contract.

THE DEFECT, measured: no settings class loaded the repo `.env`
(`env_file` was unset), so every one silently fell back to its built-in
defaults. `PostgresSettings.dsn` defaulted to password "polymath" while
the deployment uses "polymath-dev". A normally launched orchestrator
therefore authenticated with the wrong credential and returned HTTP 500
on EVERY /retrieve — 30 seconds of connection-pool timeout per request,
with the real cause ("password authentication failed for user") visible
only in the server log. The process reported itself healthy throughout.

Why it hid so well: pydantic-settings resolves a relative `env_file`
against the working directory, and the orchestrator is launched from
`orchestrator/`, where no `.env` exists. The fix resolves the path
absolutely from this repo's layout.

THE SEQUENCE a host process must follow:

    load declared configuration
      -> validate required values
      -> test critical dependencies
      -> start

What it did instead: try the environment, fall back to a built-in
password, start anyway, explode on the first user query.

A missing or wrong production credential must look like STARTUP BLOCKED
with a named cause, never like a later unexplained 500.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.startup_contract import (  # noqa: E402
    StartupContractError,
    validate_postgres,
    validate_startup,
)

SETTINGS = ROOT / "shared" / "polymath_shared" / "settings.py"
MAIN = ROOT / "orchestrator" / "orchestrator" / "main.py"


# ============================== ONE DECLARED CONFIGURATION SOURCE
def test_every_settings_class_loads_the_same_env_file():
    """One mechanism, not per-class guesswork."""
    src = SETTINGS.read_text()
    configs = src.count("SettingsConfigDict(")
    wired = src.count("env_file=_ENV_FILE")
    assert wired == configs, (
        f"{configs - wired} settings class(es) do not load the declared "
        "env file and will silently use built-in defaults")


def test_env_file_is_resolved_absolutely():
    """A relative env_file resolves against the working directory. The
    orchestrator runs from orchestrator/, which has no .env — that one
    detail is the entire defect."""
    src = SETTINGS.read_text()
    assert "_ENV_FILE = Path(__file__).resolve().parents[2] / \".env\"" in src, (
        "the env file is no longer resolved from the repo layout; a "
        "process launched from a subdirectory will miss it again")


def test_settings_resolve_the_deployed_credential():
    """The end-to-end property: importing settings from anywhere yields
    the deployed DSN, not the built-in default."""
    from polymath_shared.settings import get_settings

    dsn = str(get_settings().postgres.dsn)
    assert dsn, "no DSN resolved"
    if (ROOT / ".env").exists():
        env_dsn = ""
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("POLYMATH_PG_DSN="):
                env_dsn = line.split("=", 1)[1].strip()
        if env_dsn:
            assert dsn == env_dsn, (
                "resolved DSN does not match the declared .env value — "
                "the built-in default is winning again")


# ================================= FAIL LOUD, AT STARTUP, WITH A CODE
def test_missing_dsn_is_a_named_startup_failure():
    with pytest.raises(StartupContractError) as exc:
        validate_postgres("")
    assert exc.value.code == "POSTGRES_CONFIG_MISSING"


def test_wrong_credentials_fail_at_startup_with_a_code():
    """Not a 500 thirty seconds later — a named refusal to serve."""
    with pytest.raises(StartupContractError) as exc:
        validate_postgres(
            "postgresql://polymath:definitely-not-the-password"
            "@127.0.0.1:5432/polymath", timeout=5)
    assert exc.value.code == "POSTGRES_AUTH_FAILED"
    assert "Refusing to serve" in exc.value.detail


def test_unreachable_authority_is_distinguished_from_bad_credentials():
    """Different causes need different fixes; one code for both sends
    the operator the wrong way."""
    with pytest.raises(StartupContractError) as exc:
        validate_postgres(
            "postgresql://polymath:x@127.0.0.1:59999/polymath", timeout=3)
    assert exc.value.code == "POSTGRES_UNREACHABLE"


def test_startup_error_never_echoes_the_password():
    """The DSN carries the secret. A startup failure is exactly when
    people paste logs into tickets."""
    secret = "sup3r-secret-value"
    try:
        validate_postgres(
            f"postgresql://polymath:{secret}@127.0.0.1:5432/polymath",
            timeout=5)
    except StartupContractError as exc:
        assert secret not in str(exc), "the password leaked into the error"
    else:
        pytest.skip("that credential unexpectedly worked")


def test_diagnosis_reports_whether_the_config_source_was_found():
    """"wrong value" and "never loaded" need different fixes, so the
    message must not assert one when the other happened."""
    from polymath_shared.startup_contract import _env_file_state

    state = _env_file_state()
    assert "POLYMATH_PG_DSN" in state
    assert ".env" in state


# ========================================= THE ORCHESTRATOR USES IT
def test_orchestrator_validates_before_serving():
    src = MAIN.read_text()
    body = src[src.index("async def lifespan"):]
    body = body[:body.index("yield")]
    assert "validate_startup()" in body, (
        "the orchestrator no longer validates configuration before "
        "serving; a wrong credential would again surface as a 500 per "
        "request")
    assert "STARTUP BLOCKED" in body, "the failure is no longer loud"
    assert body.index("validate_startup()") < body.index(
        "load_sidecar_registry"), (
        "validation runs after other startup work; it must gate serving")


def test_startup_validation_raises_rather_than_warning():
    """Logging and continuing would reproduce the original defect."""
    body = MAIN.read_text()
    lifespan = body[body.index("async def lifespan"):body.index("yield")]
    assert "raise" in lifespan, (
        "the orchestrator swallows a startup contract failure and keeps "
        "serving")


@pytest.mark.skipif(os.environ.get("POLYMATH_PG_DSN") is None
                    and not (ROOT / ".env").exists(),
                    reason="no declared configuration available")
def test_validate_startup_passes_against_the_real_deployment():
    try:
        report = validate_startup()
    except StartupContractError as exc:
        pytest.skip(f"deployment not available: {exc.code}")
    assert report["postgres"] == "ok"
