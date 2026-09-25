---
change_id: AUTORESEARCH-PLAN-ADMITTED
owner: "@king"
date: 2026-09-25
status: complete
status_note: "Plan of record admitted (documents only); execution continues in slices R1–R7."
architecture_impact: "none (documents only: a plan of record, gap register sections S and H, roadmap row 6d, CONTINUITY)"
last_reviewed: 2026-09-25
---

# Admit AUTORESEARCH-SOURCES-AND-HARNESS-V1 (R0)

## Contract
- The owner, 2026-09-25:
  - "for the auto research can you include tik tok, video comments into the equations. and include cj drop shipping
    alongside alibaba product search";
  - "this repo should work with ai agent harness like openclaw or hermes, claude code, codex, etcs. execute this e2e.
    first plan gap analysis and then execute".
- The bootstrap rule: a plan that lives only in chat is admitted into the repo before execution.

## Changes
- `docs/wiki/plans/AUTORESEARCH-SOURCES-AND-HARNESS-V1.md` (new): the gap analysis, the governance path for a source
  change, the declared decisions D1–D8, slices R0–R7 with acceptance, and the owner questions.
- `docs/wiki/plans/GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md`: section S (S-01..S-04, S-06, S-07) and section H
  (H-01..H-07). S-05 is a decision, S-08 is evidence and H-08 is confirmed good, so none of them is a gap row.
- `docs/wiki/plans/LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md`: row 6d, before C1.
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md`: row 11.489. `docs/wiki/plans/CONTINUITY-REPORT.md`: the CURRENT block
  names the new plan. The scaffold TREE declares the new files.

## Proof
- The gap analysis is EXECUTED and read-only:
  - three investigations covered the sources, harness neutrality and Trail governance;
  - `binding.handle` and Trail's registry compiler, router, admission and directive compiler were run in memory on the
    live data, writing nothing;
  - both MCP servers were imported in-process.
- The key claims were re-checked by hand:
  - the Trail rows for TikTok, YouTube, CJ, Alibaba and 1688;
  - the channel lists in `policies.yaml`;
  - the first-tool template in `binding.py:416-419,488-491`;
  - the TikTok channel's host tool in `executors.py:215-222`;
  - the HARNESS_ACTION `output_schema` default in `transitions.py:154`;
  - the manifest's unknown classes at lines 2397 and 2514;
  - the absence of MCP prompts and resources.
- Baseline first: TikTok, CJ Dropshipping and comments were searched in polymath-v4, TRAIL_AGENT_AUTORESEARCH,
  trail-signal-os and the Hermes skill. The ecommerce domain is a mirror of TRAIL_AGENT_AUTORESEARCH, and no other tooling
  exists.

## Rejected claims
- "Add TikTok comments to the adapter's registry mirror": the mirror admits nothing. Admission reads only the embedded
  Trail snapshot.
- "Edit governance/trail/data in place": those files are SHA-pinned. The change goes through Trail's gate and a re-pin.
- "Count every comment as an independent voice": comments under one video are not independent. A per-thread group is an
  admission-code change that needs an owner-accepted ADR (D4).

## Open contract gaps
- None changed: this slice only adds documents. ADAPTER_RUNTIME, EVIDENCE_BOUNDARY_API and the Trail pin change in R1–R3,
  and are recorded there.
