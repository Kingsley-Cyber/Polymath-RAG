---
change_id: RESEARCH-PACKAGE-V1
owner: governance
date: 2026-09-03
status: DONE (package in tree; harness green from the new location)
architecture_impact: TRAIL OS (the opportunity-research control plane) lives in this repo as `research/`, its own package with its own harness, docs, worklog and registry; Polymath is its native corpus backend next door. No Polymath module imports it and it imports no Polymath module — the contracts (`contracts/retrieve/v1/*`, `/capabilities`, `/chat evidence=true`) stay the seam.
last_reviewed: 2026-09-03
---

# WORK LOG — RESEARCH-PACKAGE-V1: one repo, two packages, one seam

Owner (2026-09-03): "this is why i say it just needs to be together in one
repo like in its own file … why can't a copy of the repo be made in the
polymath rag with codes that routes in that folder dir".

## Why now
The first Hermes test bypassed the research controller and improvised a
brief from Polymath's raw tools (query receipts: client `python-httpx`, 8
abstained chat questions, 12 EXPLORE retrievals, then a summary of the
marketer's own five case studies). To an agent, "Polymath" was a set of raw
tools and TRAIL was a separate thing it had to know to go find. Co-locating
the package is the precondition for mounting the controlled run as a
Polymath capability (MCP `research_*` tools — next slice).

## Contract
- `research/` = the TRAIL OS repository content (159 tracked files) verbatim:
  `python/`, `graph/`, `prompts/`, `schemas/`, `registry/` (seed packs +
  small tables), `docs/`, `tests/run_all.py` (396 checks), `SKILL.md`,
  `WORKLOG.md`. Paths inside are relative to the package root; it runs from
  any location.
- Ownership stays split: extraction, retrieval, memory = Polymath; evidence
  laws, allocation, portfolio, sourcing, maintenance = research/. The package
  must keep working against any docs/18 corpus backend (`--generic` proves it).
- Review artifacts and local ledgers are ignored in git
  (`research/registry/{compiled,patches}/`, `research_evidence.csv`, sqlite).
- The Hermes skill directory becomes a symlink to this package; the GitHub
  repo TRAIL_AGENT_AUTORESEARCH becomes a mirror or is archived (owner's call).

## Changes
- `research/` (160 files, copied from TRAIL_AGENT_AUTORESEARCH main 7c94e8e + the maintenance layer v1.6.0).
- `scripts/scaffold_polymath_v4.py`: 160 TREE rows under RESEARCH-PACKAGE-V1.
- `.gitignore`: research review artifacts / local ledgers ignored.
- Register 11.71, continuity checkpoint, this work-log.

## Proof
- `python3 research/tests/run_all.py` from this repo → ALL 396 CHECKS PASSED (receipt below).
- `research/python/controller.py doctor` PASS from the new path.
- `scripts/repo_guard.py` ok with every research file declared.

## Rejected claims
- "Merging the code fixes agent bypass by itself" — rejected: an agent can still call `retrieve` directly; the fix is
  mounting the controlled run as a Polymath tool (next slice) and pointing the raw tools at it (done in the MCP
  instructions). Co-location makes that natural; it is not the fix on its own.
- "Import research/ from Polymath modules for convenience" — rejected: the two packages stay import-free; the
  contracts are the seam, so `research/` keeps working against any docs/18 backend.

## Open contract gaps
- MCP `research_init / research_step / research_submit / research_status / research_report` not yet mounted.
- The GitHub repo TRAIL_AGENT_AUTORESEARCH still holds the previous canonical copy; mirror-or-archive is the owner's call.
- `research/tests/run_all.py` is not yet invoked by Polymath's own pytest run (it is run by hand from this repo).
