# Tests

Three buckets, by what they protect.

- `contracts/`: every JSON schema validates. Examples and
  hand-written negative cases.
- `determinism/`: given the same input, the same output. Canonical
  hashing, idempotent retries, receipt-stable writes.
- `integration/`: end-to-end flows. Slower. Gated to nightly.

## Where a test may connect (SEALED-TEST-ISOLATION-V1)

- The database comes from `POLYMATH_TEST_DSN` only (`sealed_env.sealed_dsn()`), never port 5432. Unset: database tests skip.
- A connection to a live fleet port is refused inside every test (`tests/sealed_env.py`, installed by `tests/conftest.py`).
- A deliberate live probe calls `sealed_env.live_fleet("what it probes")` first; it runs only with `POLYMATH_LIVE_PROBES=1`.
- `integration/` keeps its own opt-in, `POLYMATH_INTEGRATION=1`.
- `contracts/test_sealed_test_isolation.py` fails on a live DSN literal or a live URL handed to a network call.
- How to run the suites against a throwaway database: `docs/RUNBOOK.md`, "Run the test suites".
