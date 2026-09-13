---
title: "WORK LOG — U-2 bounded Groq Parent-MAP forensic probe: RPD not exhausted, conservation chain reconciles; cinema resumption at OWNER-REVIEW gate"
change_id: GROQ-MAP-FORENSIC-PROBE-V1
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (bounded probe executed; acceptance gate substantially met; owner-review gate reached)
register: 11.192
package: "scripts/groq_map_forensic_probe.py + docs/wiki/experiments/u2-groq-map-forensic-probe-2026-09-10/"
architecture_impact: "None (read-only forensic observation). A cinema-free bounded Groq probe on SYNTHETIC parents through the production client + 11.185 conservation chain. No corpus/DB write, no cinema, no JSON mode, max_attempts=1. Answers the forensic hold's core question: provider RPD is NOT exhausted and local↔provider accounting reconciles; the historical +0/0-errors pass was a local LIMITER_REFUSED cascade. Cinema backfill resumption remains OWNER-GATED."
---

> **Ledger:** owner authorization 2026-09-10 (U-2 bounded probe). Authority
> `docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md` (acceptance gate). Register **11.192**. Forensic hold
> (11.184/11.185) — probe respects it (cinema untouched); resumption not authorized here.

## Contract

Requested outcome: execute the owner-authorized bounded Groq Parent-MAP forensic probe under the existing
forensic limits — observe the 11.185 conservation chain against real Groq, benchmark MAP batch sizes, reconcile
local vs provider RPD — WITHOUT touching cinema or resuming the backfill.

- **Smallest acceptance:** provider RPD observable + reconciled; LIMITER_REFUSED = 0 HTTP; batch sizes
  15/20/30/40/60 benchmarked; no retry loop; plaintext DSL + compiler only. All cinema-free.
- **Owner/public contract:** none changed. Public surface = the probe script + evidence.
- **Inputs/outputs/persistence:** SYNTHETIC parents (no corpus); Groq compound-mini calls (bounded); output =
  evidence JSON; NO map persisted, NO cinema, NO DB write.
- **Verifier/rollback:** the probe writes nothing but evidence — nothing to roll back; `--dry` re-validates offline.

## Changes

- `scripts/groq_map_forensic_probe.py` — GROQ-MAP-FORENSIC-PROBE-V1 (dry + live; synthetic parents; real
  `complete_one` path with `max_attempts=1`; limiter `state()` deltas; `compile_maps` yield; conservation
  reconciliation). Default-safe (never spends without `--live`).
- `docs/wiki/experiments/u2-groq-map-forensic-probe-2026-09-10/` — README (findings + gate + estimate) + 3 result
  JSONs (preflight, batch-benchmark, per-account-rpd).
- `docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md` — probe-result note appended.
- register 11.192; scaffold `TREE` declarations.

## Proof

17 bounded `groq/compound-mini` requests (preflight 1 + benchmark 10 + per-account 6), ~3 RPD/account:

- **Provider RPD OBSERVABLE + NOT exhausted:** all 6 accounts ~246–248 remaining of ~250 (limit measured).
  Contradicts the disputed "RPD exhausted" inference (11.178).
- **Conservation reconciles:** `day_count` +1 per dispatch; dispatched==requests; RPD-remaining tracks dispatch;
  0 `LIMITER_REFUSED` in-probe; `max_attempts=1` (no waste).
- **Batch reliability 15/20/30/40/60 = yield 1.0** on SYNTHETIC parents (60/60 twice) — best-case; real-parent
  reliability at 20–60 (the 11.178 concern) still pending a real-parent benchmark, so the proven cap 15 stands.
- With 11.185's offline census (926 `LIMITER_REFUSED` = 0 HTTP), the historical +0/0-errors pass was a LOCAL
  refusal cascade, not provider exhaustion.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.

Cinema-finish estimate (owner review): ~10,739 unresolved parents → ~716 requests at cap-15 (or ~179 at batch 60
if real-parent reliability confirms); capacity ~1,500 req/day across 6 accounts ⇒ finishes in well under a day.

## Rejected claims

- **"The six Groq accounts exhausted daily RPD."** REJECTED — measured ~247/250 remaining per account.
- **"MAP_RELIABILITY_CAP can be raised to 60 now."** REJECTED (this slice) — 1.0 yield at 60 is SYNTHETIC-only;
  raising the cap needs a real-parent (non-cinema) benchmark first.
- **"The probe authorizes resuming cinema backfill."** REJECTED — resumption is owner-gated (probe → owner
  review → bounded canary → owner review → backfill); not done here.

## Open contract gaps

- **OWNER-REVIEW GATE:** resuming cinema pMAP (bounded canary → full backfill) awaits owner review of these
  findings + estimate. Do NOT resume on a quota reset.
- **Real-parent batch benchmark** (non-cinema, e.g. a throwaway book) to confirm 20–60 reliability before raising
  `MAP_RELIABILITY_CAP` above 15.
- The probe is synthetic-parent only by design (cinema-free); it proves capacity + accounting, not real-corpus
  map QUALITY.
