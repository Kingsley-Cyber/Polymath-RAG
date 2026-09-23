---
change_id: CODE-KNOWLEDGE-V1-ADMISSION
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents only: the owner's CODE-KNOWLEDGE-V1 execution packet is admitted byte-identical, with a plan-of-record pointer and a feasibility review mapped to the repository. No code, schema, flag or runtime change."
last_reviewed: 2026-09-23
---

# CODE-KNOWLEDGE-V1 — packet admitted, feasibility reviewed against the repository

## Contract
Owner, 2026-09-23: "I have a plan to implement a code RAG in Polymath where it retrieves and extracts code. The plan is already
created. Review it, map it to the actual code and layout in the repo, and give me a feasibility report. It won't be implemented
in this session; we will compact first and execute. I don't want to change much about backend ingestion and extraction; I
want to build upon current infrastructure."

A plan that lives only in a zip is invisible to the next session, so this slice admits it (the polymath-bootstrap rule) and
records the review in the repository.

## Changes
- `docs/code-knowledge-v1/`: the owner's packet (`~/Documents/polymath-rebuild/polymath-code-knowledge-v1-execution-packet.zip`),
  8 files byte-identical. `PACKET_MANIFEST.json` sha256 verified after the copy (0 mismatches). It lives outside
  `docs/wiki/`, so the owner's files keep their bytes; `docs/wiki/` requires front matter.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1.md`: plan-of-record pointer with read order and status.
- `docs/wiki/reports/2026-09-23/CODE-KNOWLEDGE-V1-FEASIBILITY.md`: the review. It covers:
  - the verdict;
  - what to keep;
  - the drift table;
  - today's behavior with code files;
  - a per-slice map with anchors;
  - the uncovered gaps;
  - the phased execution;
  - 8 owner decisions;
  - 2 independent bugs.
- Addendum (same day, register 11.414): the owner's second design note, saved verbatim at
  `docs/code-knowledge-v1/ADDENDUM_2026-09-23_OWNER_NOTE.md` and reconciled in report §10 (agreements, 3 conflicts with
  recommendations, additions by phase, 5 more owner decisions). The Canvas Authoring MCP claim was checked against
  Microsoft Learn and the NuGet package listing.

## Proof
- I read the whole packet. Three read-only mappings (ingestion / semantic layers / query) walked slices C0–C13 against
  production `9aa265e`, and every anchor cited in the report was re-checked in the real repository (Graft graph a0182c7;
  the ingestion and semantic modules are unchanged since).
- Facts observed live and read-only:
  - `/upload` returns 422 for code extensions;
  - `/intake` materializes a `text/plain` `.py`, and tier_v3 chunks it damagingly (confirmed with an in-memory run);
  - LibCST / tree-sitter / luau / dotnet are not installed;
  - PyYAML is installed;
  - `POLYMATH_DOC_PROFILE_VNEXT=0`.

## Rejected claims
- "The packet can be executed as written": no. The drift table (report §3) overrides it in 9 places, notably the
  fleet-wide contract keys, which would mark every live corpus stale, and the public-mode list.
- "Code can be uploaded today": no. It is rejected at `/upload`, and via `/intake` it is corrupted by tier_v3.

## Open contract gaps
- None changed by this slice (documents only): NOT_AFFECTED.
- Execution is BLOCKED on the owner decisions in report §8.
