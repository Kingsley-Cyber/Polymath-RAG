# unit: orchestrator/orchestrator/_small-modules
anchor: orchestrator/orchestrator/__init__.py:1

## purpose
Four leaf modules of the orchestrator package. `contracts.py` = Pydantic request/response models, "Validation only" (orchestrator/orchestrator/contracts.py:1). `json_logging.py` installs one JSON handler on root + uvicorn loggers with secret redaction and size bounds (orchestrator/orchestrator/json_logging.py:1-18). `registry.py` answers "where does service X live" from `sidecars/*.toml`, validated at boot (orchestrator/orchestrator/registry.py:1-7). Unit imported by: `main.py`, `mcp_server.py`, `api/web_auth.py`, `api/web_settings.py`, `web_accounts.py`, `web_boundary.py`, `web_scope.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| IngestRequest | class | corpus_id: str(min1), source: str(min1), profile: str = "default" | orchestrator/orchestrator/contracts.py:7-10 | — |
| IngestResponse | class | run_id: str, accepted: bool | orchestrator/orchestrator/contracts.py:13-15 | — |
| ChatRequest | class | message: str(min1), corpus_id: str \| None = None | orchestrator/orchestrator/contracts.py:18-20 | — |
| REQUIRED_FIELDS | tuple | ("timestamp", "level", "service", "event", \*CONTEXT_FIELDS) | orchestrator/orchestrator/json_logging.py:32 | — |
| secret_values | def | (environ: dict[str, str] \| None = None) -> tuple[str, ...] | orchestrator/orchestrator/json_logging.py:53-59 | — |
| redact | def | (text: str, secrets: Iterable[str] = (), limit: int \| None = MAX_MESSAGE_CHARS) -> str | orchestrator/orchestrator/json_logging.py:62-72 | — |
| RedactingJsonFormatter | class | (service: str = SERVICE, secrets: Iterable[str] \| None = None) | orchestrator/orchestrator/json_logging.py:75-91 | — |
| configure_orchestrator_logging | def | (stream: IO[str] \| None = None, \*, level: int = logging.INFO, force: bool = False, secrets: Iterable[str] \| None = None) -> logging.Handler \| None | orchestrator/orchestrator/json_logging.py:109-125 | unit importers: main.py + 6 web/MCP modules (FACTS.importers) |
| Sidecar | class | (name, config: dict, manifest: dict \| None, base_url: str); .unpinned -> bool; .is_ready() -> bool | orchestrator/orchestrator/registry.py:17-35 | — |
| load_sidecar_registry | def | (root: Path \| None = None) -> Mapping[str, Sidecar] | orchestrator/orchestrator/registry.py:38-57 | — |

Per-symbol callers beyond the unit are not in FACTS. Importing `json_logging` runs `configure_orchestrator_logging()` at module scope (orchestrator/orchestrator/json_logging.py:128).

## contracts

**secret_values** — orchestrator/orchestrator/json_logging.py:53-59
- in: `environ`, or `os.environ` when None (line 55)
- out: values of vars whose name matches `(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN)` case-insensitive (line 39), kept iff `len(v) >= 8` and not starting with `"/"`, `"~"`, `"env:"` (line 57), sorted longest-first (line 58)
- post: tuple built from a set — no duplicates

**redact** — orchestrator/orchestrator/json_logging.py:62-72
- in: `text`, literal `secrets`, `limit` (None = unbounded, lines 69-70)
- out: each secret replaced by `"<redacted>"` (line 66), then the 8 `_PATTERNS` regexes in order (lines 40-49, applied at 67-69), then if over limit: `out[:limit] + f"… [{len(out) - limit} more characters cut: a log line never carries source text]"` (lines 70-71)
- post: output ≤ limit + suffix length when limit is not None [INFERRED — from `out[:limit] + suffix`]

**RedactingJsonFormatter.format** — orchestrator/orchestrator/json_logging.py:82-88
- post: `record.msg` redacted at MAX_MESSAGE_CHARS and `record.args = None` (line 83); each string CONTEXT_FIELD redacted at `500` chars (line 87); tracebacks at MAX_EXCEPTION_CHARS (line 91)

**configure_orchestrator_logging** — orchestrator/orchestrator/json_logging.py:109-125
- pre: returns None, no changes, when `POLYMATH_LOG_FORMAT` is `"plain"` (line 113) or root has a foreign handler and `force=False` (line 116)
- post: root.handlers = non-ours + exactly one handler tagged `_MARK` (lines 120-121); `root.setLevel(level)` (line 122); `"uvicorn"` and `"uvicorn.access"` get `handlers = [handler]` (lines 123-124)
- idempotent: a previous own handler is dropped (line 121)

**Sidecar.unpinned / is_ready** — orchestrator/orchestrator/registry.py:26-28, 30-35
- unpinned ⇔ `pinned_release` startswith `"__PIN_"` (line 28)
- is_ready: GET `{base_url}/ready`, timeout `2.0` (line 32); True iff status 200 and `json().get("ready")` truthy (line 33)

**load_sidecar_registry** — orchestrator/orchestrator/registry.py:38-57
- root default: `Path(__file__).resolve().parents[2] / "sidecars"` (line 41)
- per `sorted(root.glob("*.toml"))` (line 44): `base = cfg["manifest_url"].rsplit("/manifest", 1)[0]` (line 48); GET `{base}/manifest`, timeout `5.0` (line 51)

## effect surface
- Postgres: none (FACTS.tables_read / tables_written empty)
- Qdrant: none; `polymath_session` / `polymath_csrf` (FACTS.collections) appear in SOURCE only as regex literals at orchestrator/orchestrator/json_logging.py:47
- Files read: `sidecars/*.toml` via glob (orchestrator/orchestrator/registry.py:44)
- Network: `httpx.get` `{base_url}/ready` timeout `2.0` (orchestrator/orchestrator/registry.py:32); `httpx.get` `{base}/manifest` timeout `5.0` (orchestrator/orchestrator/registry.py:51)
- Env read: `POLYMATH_LOG_FORMAT` default `"json"`, `"plain"` disables (orchestrator/orchestrator/json_logging.py:113); secret-named vars for scrubbing (orchestrator/orchestrator/json_logging.py:55-57)
- Global state: root + uvicorn loggers mutated, at import time (orchestrator/orchestrator/json_logging.py:121-124, 128)

## invariants
INVARIANT: context-field limit 500 ≤ MAX_MESSAGE_CHARS 2000 ≤ MAX_EXCEPTION_CHARS 4000 — orchestrator/orchestrator/json_logging.py:87, 33, 34 [DERIVED]
  fails-if: a context field could carry more text than a message, or a message more than a traceback.
INVARIANT: literal scrub set = env values with len >= 8 not starting with "/", "~", "env:" — orchestrator/orchestrator/json_logging.py:57 [DERIVED]
  fails-if: a short (<8) or path-shaped secret value survives literal scrubbing; only `_PATTERNS` shapes remain.
INVARIANT: after configure, root holds exactly one handler tagged `_MARK = "_polymath_orchestrator_json"` — orchestrator/orchestrator/json_logging.py:37, 120-121 [DERIVED]
  fails-if: repeated imports stack duplicate JSON handlers → duplicated log lines.
INVARIANT: unpinned ⇔ pinned_release startswith "__PIN_" — orchestrator/orchestrator/registry.py:26-28 [DERIVED]
  fails-if: a `__PIN_*` placeholder is trusted as a real release pin.
INVARIANT: base_url = manifest_url minus trailing "/manifest" — orchestrator/orchestrator/registry.py:48 [DERIVED]
  fails-if: a manifest_url without that suffix yields base_url = the whole URL and probes the wrong /ready path [INFERRED — rsplit on an absent separator returns the string unchanged].

## determinism & idempotency
determinism: NONDETERMINISTIC (network: orchestrator/orchestrator/registry.py:32, orchestrator/orchestrator/registry.py:51; env: orchestrator/orchestrator/json_logging.py:55-57, orchestrator/orchestrator/json_logging.py:113)
idempotency: SAFE — `redact`/`secret_values` pure given inputs; `configure_orchestrator_logging` replaces its own prior handler (orchestrator/orchestrator/json_logging.py:120-121); `load_sidecar_registry` writes nothing, refetches per call.

## failure behaviour
- `Sidecar.is_ready`: `except Exception: return False` — any network/JSON error swallowed; caller sees not-ready (orchestrator/orchestrator/registry.py:33-35) [DERIVED]
- manifest fetch: `r.raise_for_status()` (orchestrator/orchestrator/registry.py:52) raised then `except Exception: manifest = None` (orchestrator/orchestrator/registry.py:53-55) — swallowed; `Sidecar.manifest` becomes `{}` via `manifest or {}` (orchestrator/orchestrator/registry.py:22); a fetched JSON `null` is indistinguishable from a failed fetch [INFERRED — both map to `{}`]
- `configure_orchestrator_logging` returns None with logging untouched on `POLYMATH_LOG_FORMAT=plain` (orchestrator/orchestrator/json_logging.py:113-114) or a foreign root handler without `force` (orchestrator/orchestrator/json_logging.py:116-117)
- No error codes escape this unit [DERIVED — the only `raise` is registry.py:52, swallowed at :53-54]

## dumb-code flags
- Inline magic timeouts `2.0` / `5.0`, asymmetric, unexplained (orchestrator/orchestrator/registry.py:32, 51).
- Two overlapping secret vocabularies: env-name regex `(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN)` (orchestrator/orchestrator/json_logging.py:39) vs key/value pattern `password|passwd|secret|token|api[_-]?key|access[_-]?key|invite[_-]?code|polymath_session|polymath_csrf` (orchestrator/orchestrator/json_logging.py:47).
- Import-time side effect: module-level `configure_orchestrator_logging()` (orchestrator/orchestrator/json_logging.py:128).
- `_StdoutHandler.stream` setter is a deliberate no-op `pass` with `type: ignore[override]` (orchestrator/orchestrator/json_logging.py:100-106).
- `secret_values` strips values (`str(v).strip()`, orchestrator/orchestrator/json_logging.py:56) but `redact` replaces the stripped form — an occurrence containing the stripped-out whitespace is not replaced [INFERRED].
- Docstring-only claim "a token that uploads for 6 hours" (orchestrator/orchestrator/json_logging.py:12) — no code constant backs it.
- Magic default `profile: str = "default"` (orchestrator/orchestrator/contracts.py:10).

## refactor notes
- `_MARK` string owns handler identity; renaming it orphans previously installed handlers (orchestrator/orchestrator/json_logging.py:37, 116, 120-121).
- Removing the module-level `configure_orchestrator_logging()` (orchestrator/orchestrator/json_logging.py:128) silently unconfigures logging for all 7 importers in FACTS.importers.
- Field names come from `polymath_shared.logging.CONTEXT_FIELDS` / `JsonFormatter` (orchestrator/orchestrator/json_logging.py:28) — REQUIRED_FIELDS couples to the shared package.
- `UVICORN_LOGGERS = ("uvicorn", "uvicorn.access")` (orchestrator/orchestrator/json_logging.py:35); `uvicorn.error` relies on propagation — any new non-propagating uvicorn logger keeps plain-text lines.
- TOML schema keys `"release"` (orchestrator/orchestrator/registry.py:23) and `"manifest_url"` (orchestrator/orchestrator/registry.py:48) are the implicit `sidecars/*.toml` contract; missing sidecars degrade /ready but never block startup (orchestrator/orchestrator/registry.py:5-6).
- `contracts.py` is declared "Validation only" (orchestrator/orchestrator/contracts.py:1) — adding behavior there breaks the stated contract.

## VERIFY
```verify
grep -Fq 'MAX_MESSAGE_CHARS = 2000' orchestrator/orchestrator/json_logging.py
grep -Fq 'MAX_EXCEPTION_CHARS = 4000' orchestrator/orchestrator/json_logging.py
grep -Fq 'startswith("__PIN_")' orchestrator/orchestrator/registry.py
grep -Fq 'timeout=5.0' orchestrator/orchestrator/registry.py
grep -Fq 'profile: str = "default"' orchestrator/orchestrator/contracts.py
! grep -Fq 'httpx' orchestrator/orchestrator/contracts.py
test "$(grep -c -F 'REDACTED' orchestrator/orchestrator/json_logging.py)" -ge 9
```
