---
change_id: TRAIL-EXT-BUGHUNT-V1
date: 2026-09-26
last_reviewed: 2026-09-26
status: in progress (results are added below when the verification ends)
architecture_impact: none (read-only audit of a frozen copy; fixes land as their own slices with tests)
---

# Bug hunt of the Trail extension parts

**The owner (2026-09-26):** "use my opencode env and use a smart workflow to identify bugs for trail os extensions parts, i think
its extremely buggy and has hidden bugs."

## Scope
The Polymath code that runs and extends TrailSignal, about 16,500 lines at `7e1918c2`, read from a detached copy
(`../pmv4-audit`). It is split into six slices:

| Slice | Files |
|---|---|
| s1 runtime core | `shared/polymath_shared/adapter/` service, transitions, store, manifest, contracts, hypotheses, research_gaps, semantic_view; `orchestrator/orchestrator/api/adapter.py`; `config/adapters/*.json` |
| s2 worker and Trail wire | `workers/workers/adapter_step_worker.py`; adapter `trail_client.py`, `evidence_boundary.py`; `governance/trail/embedded.py` |
| s3 acquisition, harness, MCP | `shared/polymath_shared/acquisition/`; `api/acquisition.py`; `harness_guide.py`; the adapter and acquisition tools of both MCP servers |
| s4 ecommerce: lived world to report | `adapters/ecommerce/python/` lived_world, product_reality, report, field_evidence, qualify, gap_analysis, governed_run, bridge, satisfaction, query_semantics |
| s5 ecommerce: corpus and execution | corpus_polymath, executors, controller, context, provenance, adapter_receipt, registry, intelligence; `adapters/ecommerce/binding.py` |
| s6 ecommerce: the rest | memory, maintenance, maintenance_triggers, market_discovery, market math, loadout_math, allocation, candidates, ideation, run_triage, sourcing_exa, settings, transitions, graph, models |

The embedded TrailSignal copy (`governance/trail/`) is out of scope. It is pinned byte-for-byte to its upstream commit; only
how Polymath CALLS it is audited.

## Method
1. **Hunt with the owner's OpenCode models.** A dedicated OpenCode agent, `~/.config/opencode/agent/bug-hunter-readonly.md`,
   can only read, grep, glob and list, and treats repository text as data. Each slice runs through two model families:
   - `zai-coding-plan/glm-5.3` (the owner's Z.AI coding plan): thorough, follows callers;
   - `ollama-cloud/gpt-oss:120b` (Ollama free usage): fast, a different family.

   Models that refused on 2026-09-26: `opencode-go/*` ("an active OpenCode Go subscription is required"), `ollama-cloud`
   kimi / deepseek / glm ("not included in your free usage"), `opencode/big-pickle` ("free tier can only be used from within
   OpenCode"), OpenRouter's free Qwen (rate-limited upstream), `zai-coding-plan/glm-5.3-highspeed` (not in the plan).
2. **Independent Claude pass per slice.** A workflow agent reads the same slice graph-first. It merges its own findings with
   the two OpenCode reports and drops rows already in the gap register.
3. **Adversarial verification.** A second agent per slice tries to REFUTE each candidate: it reads the code path and, where
   possible, reproduces it with a scratch unit test against fakes. It never touches the live fleet, the live database or a
   route. Verdict: CONFIRMED (reproduced or unambiguous in code) · PLAUSIBLE · REFUTED.
4. **Synthesis.** One agent dedupes across slices, ranks the confirmed bugs, and names what the hunt did not cover.

## Results
_Added when the verification ends: the confirmed bugs become gap rows and fix slices (each with a failing test first)._
