"""O-07 (2026-11-01): the orchestrator's runtime logs are JSON with the AGENTS.md §8 fields.

Until now the orchestrator configured no logging at all: its own records (STARTUP BLOCKED included) fell to Python's
last-resort plain-text handler and uvicorn wrote its own plain lines. Importing this module (main.py does) puts ONE handler
on the root logger and on uvicorn's loggers, formatted by the shared `polymath_shared.logging.JsonFormatter` with
service="orchestrator", so every line carries `timestamp, level, service, event, trace_id, run_id, stage, attempt_id,
provider, model_release, device, duration_ms, error_code` (null when a field does not apply) plus `message`.

  * no secrets: before a line is written, the literal values of secret-named environment variables (…KEY, …TOKEN, …SECRET,
    …PASSWORD, …DSN) and the shapes of a bearer (`pmk_…`, `Bearer …`), a provider key (`sk-…`), credentials in a URL, a
    key-in-path connector link (`/k/<key>/mcp`), a decision report's upload token in its upload path
    (`/product/report/<id>/upload/<token>`: the access log line of every upload would otherwise carry a token that uploads
    for 6 hours) and `password= / token= / invite_code= / polymath_session=` values are replaced with `<redacted>`;
  * no source text: a message is cut at MAX_MESSAGE_CHARS and a traceback at MAX_EXCEPTION_CHARS — a log line is not a
    channel for document text (Postgres receipts, not log lines, prove committed state);
  * basicConfig manners: nothing is taken over when the root logger already has a handler (pytest, an operator's own
    `--log-config`); `configure_orchestrator_logging(force=True)` overrides that. POLYMATH_LOG_FORMAT=plain switches it off.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Iterable
from typing import IO

from polymath_shared.logging import CONTEXT_FIELDS, JsonFormatter

SERVICE = "orchestrator"
#: AGENTS.md §8: the field names every runtime log line carries.
REQUIRED_FIELDS = ("timestamp", "level", "service", "event", *CONTEXT_FIELDS)
MAX_MESSAGE_CHARS = 2000
MAX_EXCEPTION_CHARS = 4000
UVICORN_LOGGERS = ("uvicorn", "uvicorn.access")     # uvicorn.error propagates to "uvicorn"
REDACTED = "<redacted>"
_MARK = "_polymath_orchestrator_json"

_SECRET_ENV = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN)", re.IGNORECASE)
_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"pmk_[a-f0-9]{8,32}_[A-Za-z0-9_-]{8,}"), "pmk_" + REDACTED),                    # a Polymath MCP bearer
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 " + REDACTED),                   # an Authorization value
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^:/@\s]+):([^@/\s]+)@"), r"\1\2:" + REDACTED + "@"),  # credentials in a URL
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "sk-" + REDACTED),                                    # a provider API key
    (re.compile(r"/k/[^/\s]+/mcp"), "/k/" + REDACTED + "/mcp"),                                    # a key-in-path connector link
    (re.compile(r"(/product/report/[^/\s]+/upload/)[A-Za-z0-9_-]{20,}"), r"\1" + REDACTED),          # a report's upload token
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|invite[_-]?code|polymath_session|polymath_csrf)"
                r"([\"']?\s*[:=]\s*[\"']?)([^\s&\"',;}]+)"), r"\1\2" + REDACTED),
    (re.compile(r"([?&](?:key|code|token)=)[^&\s\"']+"), r"\1" + REDACTED),                         # a secret query parameter
)


def secret_values(environ: dict[str, str] | None = None) -> tuple[str, ...]:
    """The values of secret-named environment variables (8+ characters), longest first: scrubbed literally from every line.
    A file path (…_KEY_FILE=/…) or an `env:` reference names where a secret lives; it is not one, and stays readable."""
    env = os.environ if environ is None else environ
    vals = {str(v).strip() for k, v in env.items() if _SECRET_ENV.search(k) and isinstance(v, str)}
    keep = {v for v in vals if len(v) >= 8 and not v.startswith(("/", "~", "env:"))}
    return tuple(sorted(keep, key=len, reverse=True))


def redact(text: str, secrets: Iterable[str] = (), limit: int | None = MAX_MESSAGE_CHARS) -> str:
    """`text` with secrets replaced and, past `limit` characters, cut (the cut says how much went)."""
    out = str(text)
    for value in secrets:
        if value and value in out:
            out = out.replace(value, REDACTED)
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    if limit is not None and len(out) > limit:
        out = out[:limit] + f"… [{len(out) - limit} more characters cut: a log line never carries source text]"
    return out


class RedactingJsonFormatter(JsonFormatter):
    """The shared JSON formatter, with the message, the string context fields and the traceback scrubbed and bounded."""

    def __init__(self, service: str = SERVICE, secrets: Iterable[str] | None = None) -> None:
        super().__init__(service)
        self.secrets = tuple(secrets) if secrets is not None else secret_values()

    def format(self, record: logging.LogRecord) -> str:
        record.msg, record.args = redact(record.getMessage(), self.secrets), None
        for field in CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, str):
                setattr(record, field, redact(value, self.secrets, 500))
        return super().format(record)

    def formatException(self, ei) -> str:
        return redact(super().formatException(ei), self.secrets, MAX_EXCEPTION_CHARS)


class _StdoutHandler(logging.StreamHandler):
    """Writes to whatever sys.stdout is at emit time (like logging's last-resort handler does for stderr)."""

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    @property
    def stream(self):  # type: ignore[override]
        return sys.stdout

    @stream.setter
    def stream(self, _value) -> None:
        pass


def configure_orchestrator_logging(stream: IO[str] | None = None, *, level: int = logging.INFO, force: bool = False,
                                   secrets: Iterable[str] | None = None) -> logging.Handler | None:
    """Install the JSON handler (idempotent: a previous handler of ours is replaced, anyone else's is kept). Returns the
    handler, or None when logging is left as it is (already configured by someone else, or POLYMATH_LOG_FORMAT=plain)."""
    if os.environ.get("POLYMATH_LOG_FORMAT", "json").strip().lower() == "plain":
        return None
    root = logging.getLogger()
    if not force and any(not getattr(h, _MARK, False) for h in root.handlers):
        return None
    handler: logging.Handler = logging.StreamHandler(stream) if stream is not None else _StdoutHandler()
    handler.setFormatter(RedactingJsonFormatter(SERVICE, secrets))
    setattr(handler, _MARK, True)
    root.handlers = [h for h in root.handlers if not getattr(h, _MARK, False)] + [handler]
    root.setLevel(level)
    for name in UVICORN_LOGGERS:           # uvicorn configured these before importing the app, and they do not propagate
        logging.getLogger(name).handlers = [handler]
    return handler


configure_orchestrator_logging()
