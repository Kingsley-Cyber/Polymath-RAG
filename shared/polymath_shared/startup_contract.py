"""RUNTIME-CONFIG-CONTRACT-V1 (P21, 2026-08-28) — validate before serving.

The sequence a host process must follow:

    load declared configuration
        -> validate required values
        -> test critical dependencies
        -> start

What it used to do:

    try the environment
        -> not there
        -> silently use a built-in password
        -> start anyway
        -> explode on the first user query

MEASURED: a normally launched orchestrator authenticated against
Postgres with the wrong credential and returned HTTP 500 on every
/retrieve — each request burning a 30s connection-pool timeout, with the
real cause ("password authentication failed for user") visible only in
the server log. The process reported itself healthy throughout.

A missing or wrong production credential must look like STARTUP BLOCKED
with a named cause, never like a later unexplained 500.
"""
from __future__ import annotations


def _env_file_state() -> str:
    """Say whether the declared config source was even found — the
    difference between "wrong value" and "never loaded" is the whole
    diagnosis, and guessing it wrong sends the operator the wrong way."""
    import os
    from pathlib import Path

    env_file = Path(__file__).resolve().parents[2] / ".env"
    src = ("POLYMATH_PG_DSN set in the environment"
           if os.environ.get("POLYMATH_PG_DSN")
           else "POLYMATH_PG_DSN not set in the environment")
    found = "present" if env_file.exists() else "MISSING"
    return f"{src}; {env_file.name} {found}"


class StartupContractError(RuntimeError):
    """Configuration is unusable. Refuse to serve rather than fail per
    request. Carries a machine-readable `code`."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def validate_postgres(dsn: str, *, timeout: float = 5.0) -> None:
    """Prove the workflow authority is reachable with THESE credentials.

    Postgres is the authority for the whole pipeline, so a process that
    cannot reach it is not degraded — it is unable to do its job.
    """
    if not dsn:
        raise StartupContractError(
            "POSTGRES_CONFIG_MISSING",
            "no Postgres DSN is configured; set POLYMATH_PG_DSN or "
            "provide a .env at the repo root")
    try:
        import psycopg
    except Exception as exc:                                # pragma: no cover
        raise StartupContractError(
            "POSTGRES_DRIVER_MISSING", f"psycopg unavailable: {exc}") from exc

    try:
        conn = psycopg.connect(dsn, connect_timeout=timeout)
    except Exception as exc:
        message = str(exc).strip().splitlines()[0] if str(exc) else type(exc).__name__
        # Never echo the DSN — it carries the password.
        if "authentication failed" in message.lower():
            raise StartupContractError(
                "POSTGRES_AUTH_FAILED",
                "Postgres rejected the configured credentials. Check "
                f"POLYMATH_PG_DSN and the repo .env ({_env_file_state()}). "
                "Refusing to serve rather than failing per request.",
            ) from exc
        raise StartupContractError(
            "POSTGRES_UNREACHABLE",
            f"cannot reach the workflow authority: {message}") from exc
    else:
        conn.close()


def validate_startup(settings=None) -> dict:
    """Run every startup precondition. Raises StartupContractError on the
    first failure; returns a small report when the process may serve."""
    if settings is None:
        from polymath_shared.settings import get_settings

        settings = get_settings()

    validate_postgres(str(settings.postgres.dsn))
    return {"postgres": "ok", "contract": "runtime-config-contract-v1"}
