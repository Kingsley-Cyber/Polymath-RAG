---
change_id: SUMMARIES-SCALE-OUT-V1
owner: governance
date: 2026-09-02
status: complete (activates on the next ingest with ≥2 open summary tickets)
architecture_impact: fleet slot summaries2; autopilot summary-lane scale-out rule; budget profiles
last_reviewed: 2026-09-02
---

# WORK LOG — one summaries worker was the pipeline's tail

## Contract
Owner: "fix it" — the two items left open after the MCP test: (1) one
summaries worker serialized a run's enrichment and every summary stage;
(2) the launchd auto-boot cannot read the checkout under ~/Documents.

## Changes
1. `fleet_autopilot.desired_slots`: when the summary lane has ≥ 2 open
   tickets (a run's enrichment plus its parent_summary, or two runs), the
   autopilot also wakes `summaries2`; one open ticket keeps one worker;
   never a third. Same shape as EXTRACT-SCALE-OUT-V1.
2. `process_supervisor.FLEET`: slot `summaries2` (workers.summary_worker).
3. `config/runtime_budget.yaml`: `summaries2` in the three profiles that
   list `summaries` (per_worker_gb 0.15 — fits the ceiling).
4. Safety: tickets are lease-exclusive, and enrichment persistence is
   idempotent on the content identity (ENRICH-IDENTITY-V2) with a unique
   READY-per-parent index, so two workers sweeping the same corpus never
   double-pay and cannot double-write.

## Proof
- test_fleet_autopilot_demand::test_summaries_scale_out_on_two_open_summary_tickets
  green (one ticket → one worker; two → two; many → still two); the
  autopilot/supervisor/watchdog/client suites green after the change.
- Supervisor relaunched with the new slot (fleet idle, 0 open tickets);
  the slot is parked until demand. First live receipt = the next ingest:
  the supervisor log will show "autopilot: waking summaries2".

## The launchd item — what is and is not fixable from here
The v5 launcher (`~/PolymathRuntime/bin/polymath-v5-boot.sh`, outside
~/Documents) fails at `/bin/bash: …/scripts/boot_polymath.sh: Operation not
permitted` — macOS TCC denies launchd-spawned processes access to
~/Documents. No code change in the repo can lift that. Two real fixes,
both owner actions:
- Grant Full Disk Access to `/bin/bash` (System Settings → Privacy &
  Security → Full Disk Access → + → /bin/bash), then
  `launchctl kickstart -k gui/501/com.polymath.v5`. Broad grant; works.
- Move the checkout out of ~/Documents (e.g. ~/polymath-v4) and update the
  launcher's REPO path, the MCP/Hermes notes and this wiki's paths. Narrow;
  a one-time relocation.
Until one of those happens the fleet runs from the manual supervisor
launch recorded in the continuity report (it survives everything but a
reboot/logout; the launcher then logs the same denial once a minute).

## Rejected claims
- Granting the TCC permission from this session — modifying security
  settings is the owner's action, not the executor's.
- A symlink from outside ~/Documents — TCC checks the resolved path.

## Open contract gaps
- First live receipt for `summaries2` is owed: the next ingest with ≥ 2
  open summary-lane tickets ("autopilot: waking summaries2" in the
  supervisor log, two summaries registrations heartbeating).
- launchd auto-boot: owner action pending (Full Disk Access for /bin/bash,
  or relocate the checkout); the manual supervisor launch is the standing
  state until then.
