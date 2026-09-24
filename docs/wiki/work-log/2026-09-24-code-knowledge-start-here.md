---
change_id: CODE-KNOWLEDGE-V1-START-HERE
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents + one operations script. The implementation bootstrap for CODE-KNOWLEDGE-V1 (a single start-here file), notes 6–7 folded into the representation spec (§11 LLM requests, §12 large files), and scripts/bounce_fleet.sh (the owner's one-click fleet restart, moved from a session scratchpad into the repository). No runtime code change; the script is used only when the owner or the agent restarts the fleet."
last_reviewed: 2026-09-24
---

# CODE-KNOWLEDGE-V1: START HERE, notes 6–7, and the fleet restart script

## Contract
- The owner, 2026-09-24: "i hope you are bootstrapping idea in a md for a new session implemnetations", pasted with two
  notes:
  - note 6: what to send the LLM for the code profile / pMAP;
  - note 7: breaking down a very large file (e.g. a 400 KB Power Apps YAML).
- The polymath-bootstrap rule: a new session must continue from repository truth. The plan had grown to about 12 files;
  a new session needs ONE entry point.

## Changes
- `docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTES_6_7.md`: notes 6 and 7, verbatim.
- `docs/wiki/plans/CODE-LANGUAGE-REPRESENTATIONS-V1.md`:
  - §11 enrichment requests: the existing `doc-profile-v3.2` labels and `map-prompt-v2` MAP line are kept; the message
    arrangement, the code rules and the language addenda are defined;
  - §12 large files and oversized units: storage stays whole; parse first; section-plus-context requests; token budgets;
    syntax-boundary splits marked PARTIAL; profiles built upward, never from hooks; connected units retrieved together;
    reuse / invalidation; acceptance.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1-START-HERE.md` (new), sections §0–§7:
  - what is being built;
  - the bootstrap + read order;
  - the decided table;
  - the open items;
  - the slice order C0 → C14 with proofs;
  - the code anchors, verified against production `eb93d24`;
  - the run rules;
  - the traps.
- `scripts/bounce_fleet.sh` (new): the one-supervisor restart the owner ran this session (a lock against double clicks,
  a stale-lock cleanup, TERM → wait → `boot_polymath.sh` → wait for /ready + the expected fleet on one bundle).
  - It always boots from the fleet checkout (`POLYMATH_FLEET_ROOT`).
  - Declared in `scripts/README.md` + the TREE.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1.md` and `CONTINUITY-REPORT.md` point a new session at START HERE.
- The register (11.456).

## Proof
- **Contracts re-read:**
  - `shared/polymath_shared/document_profile/prompt.py` (`PROMPT_VERSION = "doc-profile-v3.2"`, the labels ONE / SUMMARY
    / TOPIC / TERM / Q / SEARCH / THEORY / CONCEPT / SEEALSO + END);
  - `map_prompt.py` (`MAP_PROMPT_VERSION = "map-prompt-v2"`, `MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>`).

  §11 keeps both formats unchanged.
- **Code anchors** in START HERE §5 were checked with graft (refreshed to `eb93d24`) and direct reads:
  - `intake_worker.process_event` L151;
  - `materializer.materialize` L143 / `TEXT_MEDIA_TYPES` L38;
  - `chunker.materialize_chunks` L510;
  - `ParentSkeleton` L271 / `build_parent_skeletons` L401;
  - `DocumentGroundingContextV1` L160;
  - `retrieve_candidates` L674;
  - `chat_retrieve_mode` L767;
  - MCP `upload_document` L179.
- **`bash -n scripts/bounce_fleet.sh`:** the syntax check passes. The script body is the one the owner ran successfully
  twice this session (READY after about 55 s, 24 / 13 / one bundle), with the lock added after a double click.
- **Guards:** `agent_preflight`, `repo_guard`, `wiki_worm --check`, `bundle_integrity`, each exit code on its own line.

## Rejected claims
- "Build the file profile from pMAP hooks": three hooks cannot carry enough behaviour (note 7). Profiles are built upward
  from unit descriptions.
- "Cut large files by characters": boundaries come from the parser only; no silent truncation.

## Open contract gaps
- The owner's real-code inputs (START HERE §3.1), above all the Roblox project format.
- C0's tool evaluations and the capacity measurement (decision 6).
- The token counting method for each enrichment lane (§12 item 4) is measured in C0 / C6.
