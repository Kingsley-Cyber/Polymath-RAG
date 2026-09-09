---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 07 — Next Action (exactly one)

**OBJECTIVE:** Establish Groq provider-quota topology from live headers — the last gate item before any
cinema pMAP resume. Specifically: does `groq/compound` share an RPD budget with `groq/compound-mini` on
one account, and what is the real per-account RPD? (Config's "RPD 250"/local-230 is an unproven assumption.)

**OWNER GATE:** This spends provider quota. The forensic hold forbids spend without an explicit owner go.
Do **not** run it autonomously — present the budget and wait for authorization. (Backfill stays STOPPED.)

**FILES / MECHANISM:**
- Reuse the repaired path: `client.py:complete_one` → `limiter.py:admit`/`_observe_provider_rpd_locked`
  already capture `x-ratelimit-*-requests` on 2xx. A ~5-call probe:
  - Account 1 (`GROQ_API_KEY_1`) `groq/compound-mini`: 2 calls — watch `x-ratelimit-remaining-requests` decrement.
  - Account 1 `groq/compound`: 2 calls — did compound-mini's remaining move? (shared vs independent RPD).
  - Account 2 (`GROQ_API_KEY_2`) `groq/compound-mini`: 1 call — prove account-2 remaining is independent.
- Capture per call (never the key — non-secret fingerprint only): `x-ratelimit-{limit,remaining,reset}-{requests,tokens}`, model, HTTP status, local day_count, provider_rpd_remaining.

**WHY:** proves/refutes the per-account RPD-cap divergence; without it a resume repeats the original error
(scheduling against an assumed quota).

**LOCAL TEST (free, do first):** `PYTHONPATH=shared .venv/bin/python -m pytest tests/determinism/test_limiter_control_plane.py tests/determinism/test_groq_account_isolation.py -q` — the accounting is already covered offline; confirm green before spending.

**LIVE TEST (only if authorized):** the 5-call probe above; abort on unexpected 429 / missing headers / isolation violation.

**DONE WHEN:** quota topology recorded (shared/independent + real per-account RPD) in a work-log; then the
next gate step is the 15/20/30/40/60 MAP-batch benchmark, then a bounded canary, then owner review.

---
### Parallel no-spend option (if owner defers the probe)
Push the 4 local control-plane commits to origin, and/or build the missing full-pipeline canary
(`05` P1) so pipeline stability is measurable once Groq resumes. Both are free and unblock later phases.
