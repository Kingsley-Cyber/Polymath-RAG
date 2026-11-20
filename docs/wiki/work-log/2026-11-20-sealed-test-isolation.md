---
change_id: SEALED-TEST-ISOLATION-V1
owner: governance
date: 2026-11-20
status: merged
status_note: "Merged into local production 2026-11-20 (fast-forward from branch fix/sealed-test-isolation, rebased on 7390441b). Sealed run 4,944 passed / 31 skipped / 0 failed; 0 live rows written. Not pushed to GitHub: the push would also publish 16 earlier unpushed production commits to the public repo; waits for the owner."
architecture_impact: "tests only (tests/sealed_env.py new, tests/conftest.py, 47 test files under tests/contracts + tests/determinism, two frontend-v2 live tests), pyproject.toml (pytest pythonpath), the two GitHub workflows that run a Postgres service (moved off port 5432). No runtime code, schema, contract or store changes."
last_reviewed: 2026-11-20
---

# SEALED-TEST-ISOLATION-V1: no test reaches a live store or the live fleet unless the operator opts in

## Contract
- The owner, 2026-11-20: "no test reaches a live store or the live fleet unless the operator explicitly opts in." Suggested shape:
  one shared helper that resolves the database DSN only from `POLYMATH_TEST_DSN` and refuses port 5432, and one explicit opt-in
  (`POLYMATH_LIVE_PROBES=1`) for the tests that deliberately probe the live fleet, which otherwise skip with a clear reason.
  "Never weaken what a test asserts; only change where it connects and when it runs." A failing check first.
- Owner: `governance` (repository test infrastructure). No process owner changes; no runtime code is touched.
- Smallest acceptance:
  1. No test file under `tests/` (except the helper) names the live Postgres in a DSN literal, or calls a live fleet URL.
  2. Test code takes its database only from `POLYMATH_TEST_DSN`; a value that names port 5432 (or no port) stops the session.
  3. A connection to a live fleet port from inside a test is refused (the Python socket layer and psycopg), unless the test
     is a declared live probe and the operator set `POLYMATH_LIVE_PROBES=1` (tests under `tests/integration/` keep their own
     opt-in, `POLYMATH_INTEGRATION=1`).
  4. The sealed reproduction (throwaway Postgres on a non-5432 port, `env -i`, `pytest tests/contracts tests/determinism`)
     leaves no new row in the live database and no new live query receipt.
- Inputs: the environment (`POLYMATH_TEST_DSN`, `POLYMATH_LIVE_PROBES`, `POLYMATH_INTEGRATION`). Outputs: test outcomes and a
  terminal summary of refused connections. Persistence effect: none. Failure modes: a test that silently depended on the live
  data now skips or fails (listed under Proof); a CI job that still runs Postgres on 5432 stops at session start.
- Verifier: `tests/contracts/test_sealed_test_isolation.py` (static scan + guard behaviour) and the sealed reproduction.
  Rollback boundary: revert the branch; nothing outside the repository changes.

## Measured (2026-11-20, before the change)
- The sealed reproduction still touched the live fleet: `tests/determinism/test_incremental_census.py:31` hardcodes
  `postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath`; it seeded a `census-probe` corpus into the live database, ran
  `compute_census(conn, mode="full")` on live data and hung; the probe rows were purged afterwards.
- Live probes called `http://127.0.0.1:7200` and wrote live `query_receipts` (clients `ui-stream`, `Python-urllib`).
- `rg -l` for the live addresses over `tests/contracts tests/determinism`: 48 files (10 contracts, 38 determinism).

## Changes
- **`tests/sealed_env.py` (new)**: the one place under `tests/` that names a live address. `sealed_dsn()` reads
  `POLYMATH_TEST_DSN` only; unset skips the calling test with the reason; `dsn_refusal()` refuses a DSN with no port or a live
  fleet port (`LiveStoreRefused`, a `psycopg.OperationalError`). `session_environment()` sets `POLYMATH_PG_DSN` to the same
  value, so code under test (settings, pools, child processes) reaches the sealed database. `install_guard()` wraps
  `socket.socket.connect` / `connect_ex` and `psycopg.Connection.connect` / `AsyncConnection.connect` / `psycopg.connect`:
  a connection to a port in `LIVE_PORTS` (Postgres, Qdrant, Redis, Neo4j, orchestrator, embedder, reranker, local extractor,
  Trail MCP, friends-access door, MCP server; from `compose.yaml`, the supervisor, `settings.py` and `lsof`) raises a
  closed-port error and is counted. `live_fleet(what)` skips unless `POLYMATH_LIVE_PROBES=1`; with it, the guard opens for
  that test only. `sealed_dsn_with_password()` gives the sealed address with another password (a login that must fail).
- **`tests/conftest.py`**: `pytest_configure` applies `session_environment` (a live `POLYMATH_TEST_DSN` is a usage error,
  exit 4, before any test) and installs the guard; `pytest_runtest_protocol` and `pytest_make_collect_report` wrappers name
  the running test (or module being collected) for the refusal log and open the guard for `tests/integration/` only when
  `POLYMATH_INTEGRATION=1`; `pytest_terminal_summary` prints a `live-fleet guard` section (database, probes, refusals).
- **`pyproject.toml`**: pytest `pythonpath = ["tests"]`, so `import sealed_env` works with `--noconftest` too.
- **`tests/conftest.py`: `LITELLM_MODE=PRODUCTION`** for the session. litellm runs `dotenv.load_dotenv()` on first import
  (`litellm/__init__.py:26`, litellm 1.98.0, skipped unless `LITELLM_MODE` is `DEV`; nothing else in litellm reads it). Under
  pytest the search climbs from litellm's own folder; with the live checkout's `.venv` it reaches `polymath-v4/.env`, so a
  sealed run (`env -i`, a worktree with no `.env`) got the fleet's `POLYMATH_CHAT_*` flags, sidecar URLs and real provider
  keys (`DEEPSEEK_API_KEY`, `GROQ_API_KEY_1..6`; names traced, values never printed) as soon as
  `tests/contracts/test_deep_research_route.py` imported litellm. The fleet sources `.env` itself.
- **28 determinism files** (`DSN = "...@127.0.0.1:5432/..."` or `os.environ.get(..., <live default>)`): the constant is gone;
  every use is `sealed_dsn()` (scripted with `tokenize`, code tokens only). In the 10 files whose `_pg()` /
  `_pg_reachable()` runs at import (a skip marker), the probe first returns None / False when `POLYMATH_TEST_DSN` is unset
  (a skip may not be raised at import). `test_extraction_eligibility.py` defaulted `POLYMATH_PG_DSN` to the live database
  for code under test; it now defaults to the sealed one when set. `test_runtime_config_contract.py`: the wrong-password and
  password-never-echoed tests log in to the sealed database (`sealed_dsn_with_password`), not to port 5432.
- **6 live-probe files** (`test_chat_funnel`, `test_chat_retrieval_v2`, `test_chat_synthesis`, `test_chat_hygiene`,
  `test_chat_runtime`, `test_chat_carry`): each `test_live_*` calls `sealed_env.live_fleet(...)` first and uses
  `LIVE_ORCHESTRATOR` / `LIVE_RERANKER`; the funnel probe reads its receipt from `LIVE_PG_DSN`, where the live orchestrator
  writes it (it read `POLYMATH_TEST_DSN` with a live default before, so in a sealed run it looked in the wrong database).
- **`tests/contracts/test_corpus_access_parity.py`**: `# not-a-connection` on one fake error text (no code change).
- **`tests/contracts/test_sealed_test_isolation.py` (new)**: the failing check (17 tests): an AST scan for live DSN literals
  and live URLs handed to a network call, a self-test of the scan, and the runtime guard checks (each uses port 8755, where
  nothing listens, or a Unix socket path that does not exist, so a broken guard fails without live contact).
- **`frontend-v2`**: `live-contract.test.ts` fetches the live OpenAPI document only with `POLYMATH_LIVE_PROBES=1` (its free
  and paid tiers skip otherwise); `proxy-covers-backend.test.ts` reads the process environment as `live-contract` does
  (vitest does not copy `POLYMATH_*` into `import.meta.env`, so it always called `:7200` and ignored `POLYMATH_BASE_URL`) and
  skips unless `POLYMATH_LIVE_PROBES=1`.
- **`.github/workflows/determinism.yml`**: the Postgres service on `55432:5432`; both DSNs and the `psql` steps on 55432.
- **Docs**: `docs/RUNBOOK.md` "Run the test suites" (the sealed commands and the three variables), `tests/README.md`,
  register 11.580, scaffold `TREE` (two test files, this work-log), CONTINUITY "Do Not Do".
- Of the 48 files the owner's `rg` listed, 37 changed; the other 11 name a live address only as data (in-process
  `TestClient(base_url=...)`, Host header strings, Caddy config text, a fixture upload URL, a faked supervisor health URL).

## Proof
All runs: a throwaway `postgres:16-alpine` on `127.0.0.1:55432` with all 68 migrations (83 tables), `env -i` with only
`HOME`, `PATH`, `PYTHONPATH` (the worktree's four packages; `importlib` confirmed each resolves to the worktree) and the two
DSNs pointing at it; the live checkout's `.venv` interpreter.
- **Fail first**: before `tests/sealed_env.py` existed, the new contract test failed at import. With the helper and before the
  migration, its two scans failed listing 35 live DSN literals and 13 live URL calls (the owner's 48 files minus the data-only
  ones; two hits were the scan's own example text, then marked).
- **Collect-only, no database**: both suites collect with no error; the guard refused 1 connection, `test_graph_lifecycle_v2`'s
  import-time `_neo4j()` to the live Neo4j (7688), which it opened on every collection before. `tests/integration` collect-only:
  11 import-time live Postgres connections refused (`test_retrieve_evidence_rows` 10, `test_generation_swap_lineage` 1).
- **Sealed run 1** (02:09:24–02:22:57Z): 4,926 passed, 31 skipped, 13 failed. Guard: 166 refused, none of them inside a failing
  test: embedder 8742 156 times (`test_query_scope.py` procedures / concepts: `_vector_object_ranks` → `_embed_query`; each
  call then waits `_await_embedder`'s 150 s wake budget, `orchestrator/orchestrator/api/fast.py:317`), Postgres 5432 3 times
  (`test_supervisor_readiness.py::test_worker_slots_without_health_url_are_untouched`, a supervisor with `dsn=""`), Qdrant 6334
  twice (`test_document_status_endpoint.py`), the Neo4j collection probe once, and this change's own guard tests (4). Each of those
  reached the live fleet before this change.
- **The 13 failures are pre-existing**: all 13 pass alone on this branch and on the untouched base `14e8deb8` (a temporary
  detached worktree, removed after), and pass with every module collected but only they selected. A file-level bisection found
  the polluter, `tests/contracts/test_deep_research_route.py`; that file followed by the 13 fails all 13 on BOTH trees,
  identically. Cause: litellm's import-time `load_dotenv()` (see Changes); a hook on `os.environ` writes traced the provider key
  to `litellm/__init__.py:27` → `dotenv/main.py:108`. Safe to run on the base: the guard log shows neither the polluter nor the 13
  made any live connection, and none starts a subprocess.
- **With `LITELLM_MODE=PRODUCTION`**: the polluter + the contract test + the 13: 72 passed; the `os.environ` hook saw no key
  written. **Sealed run 2** (02:38:41–02:51:55Z): **4,940 passed, 31 skipped, 0 failed** in 785 s; the guard summary is the same
  166 refusals.
- **After the rebase onto `production` 7390441b** (TRUE-CORPUS-DELETE-V1, register 11.579, landed during this work; register
  row renumbered to 11.580, two append conflicts kept both sides): contract test + the new `test_true_corpus_delete.py` 21
  passed; **sealed run 3** (02:54:41–03:08:08Z): **4,944 passed, 31 skipped, 0 failed**, the same 166 refusals, and 0 live rows
  newer than its start in any of the 60 tables.
- **The live database was not written** (read-only probe, `default_transaction_read_only=on`, over the 60 live tables with a
  creation / receipt timestamp, plus `query_receipts` and the `census-probe` corpus): after run 2, **0 rows newer than T1 in any
  table, 0 query receipts, 0 `census-probe` rows**. After run 1: 0 receipts, 0 probe rows; the only new rows were 24
  `worker_registrations` (02:10:14–17Z) and 1 `control_owners` (02:10:23Z) whose pids are the running fleet workers started at
  02:10:14Z: a fleet restart by another session, not the tests. Another session's unguarded suite run (02:02–02:09Z) wrote nothing
  either. The 10 live receipts of 01:45–01:48Z ("chroma keyer", "Zorblax-9", clients `ui-stream` / `Python-urllib`) predate this
  session's first test run (the measured incident).
- **Live probes skip with the reason** (`live fleet probe (...): ... set POLYMATH_LIVE_PROBES=1`): 10 tests, which is the whole
  difference in skips against the 2026-11-19 sealed run (20–21 skipped).
- **`frontend-v2`**, against a local stub server on an ephemeral port: without the opt-in the stub received 0 requests; with
  `POLYMATH_LIVE_PROBES=1` each live test file sent its request (before the fix `proxy-covers-backend` never saw
  `POLYMATH_BASE_URL`). Full vitest: 239 passed, 13 skipped (the 12 live-contract tests + the proxy test); `tsc --noEmit` clean.
- `make guards` (preflight, repo guard, wiki worm): ok. Code wiki `verify.py`: 2,415 / 2,415 assertions on 378 pages (no page
  covers a changed file, so no refresh).

## Rejected claims
- "pytest-socket does this" (miketheman/pytest-socket, MIT, 348 stars, pushed 2026-11-16, release 0.8.1 of 2026-08-19): it
  allows or blocks by HOST only; the sealed database and in-test servers sit on 127.0.0.1 beside the live fleet, so the rule
  has to be per PORT. And libpq opens its own sockets, which no Python socket hook sees.
- "A static scan is enough": code under test defaults to live ports (`settings.py`: 5432, 6334, 7688, 8742, 8743; the live
  checkout's `.env` through the editable install) and no test file names them; the collect-only run below shows one more
  path no scan could see (`test_graph_lifecycle_v2._neo4j()` opening the live Neo4j at import).
- "Make DB tests fail when `POLYMATH_TEST_DSN` is unset": the repo's DB tests already skip when Postgres is unreachable;
  a skip with the reason keeps that, and CI sets the variable.

## Open contract gaps
- **Child processes are outside the in-process guard.** They inherit `POLYMATH_PG_DSN` = the sealed DSN, so a child that uses
  the configured database is safe; a child that dials a live HTTP port directly is not refused. Today only
  `scripts/chat_carry_probe.py` does that, and its test is a gated live probe. A new subprocess test that reaches the fleet
  would need the same gate.
- **Clients that do not use Python sockets or psycopg** (gRPC, a C driver) are not hooked. None is in use (`rg prefer_grpc`
  finds nothing; Qdrant is reached over HTTP).
- **Graph, vector and sidecar tests skip in a sealed run**: there is no sealed Neo4j / Qdrant / embedder, and the guard refuses
  the live ones. A sealed store on a non-fleet port (through the settings' env variables) would let them run.
- **`tests/integration/`**: `POLYMATH_INTEGRATION=1` opens the guard for the whole bucket (its documented purpose); 25 of its
  47 files have no gate of their own and, without the opt-in, now see refused connections. The bucket was only collected
  here (11 import-time live Postgres reads refused), not run. Eight of its files fail to import under a `PYTHONPATH` that
  names the four package folders (`orchestrator.orchestrator`): that is how this harness sets the path, not this change.
- **`test_settings_resolve_the_deployed_credential`** compares the resolved DSN with `ROOT/.env` when that file exists, i.e. in
  the live checkout only; with `POLYMATH_TEST_DSN` set the session points `POLYMATH_PG_DSN` at the sealed database, so that
  comparison fails there. DB tests must not run in the live checkout anyway; in a worktree or CI there is no `.env`.
- **Three tests leaned on the live fleet without saying so** and now see refusals (they pass): `test_query_scope.py`
  procedures / concepts call the embedder through `_vector_object_ranks` and each waits `_await_embedder`'s full 150 s wake
  budget (about 5 of the 13 minutes of a sealed run); `test_supervisor_readiness.py::test_worker_slots_without_health_url_are_untouched`
  opens Postgres with an empty DSN (libpq's 5432); `test_document_status_endpoint.py` reaches Qdrant. Injecting a fake
  embedder / Qdrant there is a test change of its own, not made here.
- **`tests/contracts/test_deep_research_route.py` and the 13 tests it broke**: the cause (litellm loading the live `.env`) is
  fixed for test sessions; whether any production process relies on litellm's own `.env` loading is not examined (the fleet
  sources `.env` before it starts).
- **GitHub CI is not run**: the workflow change (Postgres on 55432) is proven only by reading it; nothing is pushed.
- **No base-commit baseline**: running the untouched suites in the sealed harness would leak into the live fleet again (that
  is the defect), so each failure below is read on its own.

## Contract impact
- `scripts/contract_impact.py --staged`: "CONTRACT IMPACT: none (no changed file maps to an architecture contract)." No
  runtime contract is touched; every disposition: NOT_AFFECTED.
