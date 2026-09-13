---
title: "WORK LOG — auditing the other skips that could hide a break, after one of them did"
change_id: SKIP-MASKING-AUDIT-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.240
architecture_impact: "tests and one verifier gate only. Three skip branches narrowed so they can no longer classify our own faults as environment conditions; one live integration test resolves its corpus from /corpora instead of a hardcoded id (it had been permanently skipping); the suite gate now reports the SKIP COUNT."
---

> 11.239 fixed the skip that hid a production break. It did not answer the obvious next
> question: how many others are shaped like that?

## Contract

§18's vocabulary rule in spirit: a status must mean what it says. `NOT_TESTED` is never
green — and a SKIP is a `NOT_TESTED` that a suite renders as success.

## Changes

**The audit.** 49 `pytest.skip` calls across `tests/`. Most are honest environment gates
("dev postgres not reachable", "orchestrator not reachable") whose condition is a
connection failure — those are correct. The dangerous shape is a skip whose condition is
*an error we might have caused*. Three survived the filter:

1. **`test_runtime_config_contract.py` — the test could not fail.**
   ```python
   try:    report = validate_startup()
   except StartupContractError as exc:
           pytest.skip(f"deployment not available: {exc.code}")
   assert report["postgres"] == "ok"
   ```
   Raise → skip; return → assert. The only failure mode of "validate_startup passes
   against the real deployment" was unreachable — and `POSTGRES_AUTH_FAILED`, the code
   this test most exists to catch, was being skipped on. Now only genuinely absent
   infrastructure (`POSTGRES_CONFIG_MISSING` / `POSTGRES_UNREACHABLE` /
   `POSTGRES_DRIVER_MISSING`) may skip; anything else fails.

2. **`test_retrieve_plan_capabilities.py` — a skip reason that was a guess.** It skipped
   whenever the response carried `errors`, calling it "corpus not query_ready". The real
   condition was `QUERY_SCOPE_UNKNOWN: corpus 'mark-builds-brands-v1' not found` — a
   hardcoded corpus id absent from this deployment. Two fixes: `_ready_corpus()` now asks
   `/corpora` and skips with the true reason (absent, or present-but-not-ready, or no
   ready corpus at all), and the in-test guard matches ERROR CODES rather than a
   substring of the payload. **The substring version matched `corpus_id`, which appears
   in every error as a FIELD NAME — so the guard admitted everything**, the same
   match-the-mention bug the conformance censuses had. Both tests in that file now
   **PASS instead of skipping**: they had been silently not running.

3. **`test_medic.py` — a label, not a question.** `SELECT 1 FROM medic_actions` inside a
   broad `except` reported any connection drop, permission problem or query bug as
   "migration 0053 not applied". Now it asks `to_regclass('medic_actions')` and lets real
   errors propagate.

**And the durable part.** `verify_final_state.py`'s suite gate now reports the **skip
count** alongside failures, on PASS as well as FAIL. A rising skip count is the visible
shape of coverage quietly leaving, and it was invisible.

## Proof

- `test_runtime_config_contract.py` + `test_medic.py`: 16 passed.
- `test_retrieve_plan_capabilities.py`: **2 passed, 0 skipped** (was 1 passed, 1 skipped
  — permanently, against a corpus that does not exist here).
- The suite gate's detail line now ends `SKIPPED: N (a skip is not a pass — see 11.239)`.

## Rejected claims

- **"The other 46 skips are the same problem."** Rejected on inspection: a skip whose
  condition is a refused connection is an honest environment gate. The filter was "could
  this condition be caused by our own code?", and it selected three.
- **"Ban `pytest.skip` in an `except` block with a lint rule."** Rejected for now: the
  legitimate uses have exactly that shape (`except psycopg.OperationalError` → skip), so
  the rule would be noise. Reporting the COUNT catches the same drift without forbidding
  a correct pattern.

## Open contract gaps

- The audit covered `tests/`. `scripts/` carries its own skip-like early returns that
  were not reviewed.
