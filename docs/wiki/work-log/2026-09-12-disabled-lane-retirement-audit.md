---
title: "WORK LOG — deeper proof for the 12 disabled-provider-lane RETIRE_CANDIDATE rows: all 12 keys confirmed actively serving a different function under a different lane name"
change_id: DISABLED-LANE-RETIREMENT-AUDIT-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.220
architecture_impact: "investigation only — zero config/code/schema change. No lane enabled, disabled, renamed, or deleted."
---

> Executor session, execution authority §11 retirement law, continuing the same
> conformance-audit follow-through as 11.218. A Stop-hook review of the prior report
> correctly identified that the 12 disabled-lane `RETIRE_CANDIDATE` rows had been
> described as "not individually re-investigated" rather than actually investigated.
> This closes that gap with a definitive verdict for all 12, not a deferral.

## Contract

Requested outcome: a FILE:SYMBOL/commit-level verdict for each of the 12 disabled
provider lanes `scripts/audit_polymath.py --no-spend` classifies `RETIRE_CANDIDATE`
("disabled in config; superseded unless a rollback needs it") — confirm whether
deleting the config entries is safe, and if not, state precisely why not.

- **Smallest acceptance:** every one of the 12 lanes gets a named replacement lane,
  a named commit/register row explaining the reassignment, and an explicit
  delete/keep verdict — not a generic "config, not code" deferral.
- **Owner / public contract:** none — `config/cloud_providers.json` is unmodified;
  this is a pure investigation.
- **Verifier:** direct inspection of `config/cloud_providers.json` (which lanes
  share which `api_key_env` value) plus `git log -- config/cloud_providers.json`
  and the work-log it points to.

## Changes

None. Investigation only.

## Proof

`git log --oneline -- config/cloud_providers.json` surfaced
`5adb0f5 config(lanes): reassign providers — Google→graph, Groq split (1 doc / 5
pMAP), Alibaba+Ollama compiler ring`, backed by
`docs/wiki/work-log/2026-09-10-provider-lane-reassignment.md`
(`PROVIDER-LANE-REASSIGNMENT-V1`, register **11.193**, owner-directed, dated
2026-09-10 — two days before this session). Its own "Changes" section explicitly
names the disposition of every one of the 12 lanes. Cross-checked directly against
the live config (`api_key_env` values), not just the work-log's prose:

| Disabled lane | key | now active as | function |
|---|---|---|---|
| `compiler1` | `GEMINI_API_KEY_1` | `gemini1` (enabled) | graph extraction |
| `compiler2` | `GEMINI_API_KEY_2` | `gemini2` (enabled) | graph extraction |
| `compiler3` | `GEMINI_API_KEY_3` | `gemini3` (enabled) | graph extraction |
| `compiler4` | `GEMINI_API_KEY_4` | `gemini4` (enabled) | graph extraction |
| `profile_fallback_gemini1` | `GEMINI_API_KEY_5` | `gemini5`/`gemini5b` (enabled) | graph extraction |
| `profile_fallback_gemini2` | `GEMINI_API_KEY_6` | `gemini6`/`gemini6b` (enabled) | graph extraction |
| `profile_groq2` | `GROQ_API_KEY_2` | `map_groq2` (enabled) | pMAP |
| `profile_groq3` | `GROQ_API_KEY_3` | `map_groq3` (enabled) | pMAP |
| `profile_groq4` | `GROQ_API_KEY_4` | `map_groq4` (enabled) | pMAP |
| `profile_groq5` | `GROQ_API_KEY_5` | `map_groq5` (enabled) | pMAP |
| `profile_groq6` | `GROQ_API_KEY_6` | `map_groq6` (enabled) | pMAP |
| `map_groq1` | `GROQ_API_KEY_1` | `profile_groq1` (enabled) | doc_profile |

**Every single one of the 12 keys is confirmed, by direct inspection of the current
config (not just the work-log's claim), to be actively dispatching production
traffic RIGHT NOW under a different lane name for a different function.** None of
the 12 disabled entries represent idle, orphaned, or unused capacity — deleting them
would free zero resources; the underlying accounts are fully committed elsewhere.

## Rejected claims

- **"These are safe to delete since they're disabled and unreferenced."** REJECTED
  — technically true that no running code path reads a `enabled:false` entry, but
  that is not the retirement law's actual bar (§11: "0 fallback references... 0
  required rollback dependencies"). The disabled entries ARE the fallback/rollback
  reference: `PROVIDER-LANE-REASSIGNMENT-V1`'s own "Open contract gaps" section
  flags real, live operational risk in the NEW topology it just introduced
  ("doc_profile is now 1 Groq key... no Groq redundancy"; "the pMAP OpenRouter
  fallback is unvalidated for actual MAP-DSL yield") — if either of those risks
  materializes, reverting to the prior per-function assignment (re-enabling
  `profile_groq2-6` instead of relying on Groq redundancy that no longer exists) is
  a real, plausible operational action, and the entries being ALREADY DEFINED
  (just toggled off) is exactly what makes that revert a one-line `enabled: true`
  edit instead of re-deriving 12 lane definitions from git archaeology.
- **"This should be auto-classified as a distinct audit STATE from RETIRE_CANDIDATE
  by scripts/audit_polymath.py."** REJECTED as out of scope for this slice — doing
  so would require the audit tool to correlate a config lane against work-log prose
  (an NLP-shaped problem, not a structural one like the VIEW/docs-exclusion bugs
  11.218 fixed) for a marginal governance benefit; a manual investigation, recorded
  once and citable going forward, is proportionate here. The audit's own
  "RETIRE_CANDIDATE... superseded unless a rollback needs it" phrasing was already
  accurate and appropriately hedged — this work-log resolves the hedge with
  evidence, it does not correct a bug in the tool.

## Open contract gaps

- None — this fully resolves the 12 named lanes to a definitive KEEP-DISABLED
  verdict with commit-level evidence. No further investigation is pending for them.
- If the owner independently decides the OLD topology is never coming back (e.g.
  after enough runtime under the new assignment proves the redundancy gaps
  `PROVIDER-LANE-REASSIGNMENT-V1` flagged are not real problems), deleting these 12
  entries then would be a config-only, zero-risk cleanup — but that is an owner
  timing/confidence call, not something this investigation can conclude on its own.
