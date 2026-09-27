---
change_id: FIX-IT-ALL-ADMISSION
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The owner agreed to every recommendation: FRONTEND-REFRESH-V1, TRAIL-INTERFACE-V1 and DEEP-RESEARCH-MODE-V1 become plans of record with their decisions recorded; the Trail-extension bug hunt is started with the owner's OpenCode models."
architecture_impact: "Docs only: the three plans' status and decision sections, docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md (new), the register, CONTINUITY, scaffold TREE."
last_reviewed: 2026-09-26
---

# FIX-IT-ALL: the three plans admitted, the bug hunt started

## Contract
- The owner (2026-09-26): "i agree please fix it all, and i think you need to use my opencode env and use a smart workflow
  to identify bugs for trail os extensions parts, i think its exetremely buggy and has hidden bugs."

## Changes
- **Plan statuses.** FRONTEND-REFRESH-V1, TRAIL-INTERFACE-V1 and DEEP-RESEARCH-MODE-V1 move from PROPOSED to ACTIVE (plan of
  record). Each decisions section now starts with a DECIDED 2026-09-26 line naming the recommended options the owner accepted.
- **`docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md`.** The scope (six slices, about 16,500 lines), the models
  that answered and those that refused, and the method: OpenCode hunt → independent Claude pass → adversarial verification →
  synthesis.
- **The owner's OpenCode config.** A read-only agent was added outside the repository at
  `~/.config/opencode/agent/bug-hunter-readonly.md` (tools: read, grep, glob, list; everything else off).

## Proof
- Model smoke tests, each on one 81-line file:
  - `zai-coding-plan/glm-5.3`: answered in 116 s and followed callers read-only.
  - `ollama-cloud/gpt-oss:120b`: answered in 8 s.
  - Refused: `opencode-go/*` (no active Go subscription), Ollama's kimi / deepseek / glm (not in free usage),
    `opencode/big-pickle` (free tier only inside OpenCode), OpenRouter's free Qwen (rate-limited), `glm-5.3-highspeed`
    (not in the plan).
- Guards: preflight, repo_guard, wiki_worm = 0 (recorded at commit).

## Rejected claims
- "OpenCode's CLI still reaches the free Zen models" (memory, 2026-09-21): it no longer does. `opencode run -m
  opencode/big-pickle` answers "OpenCode's free tier can only be used from within OpenCode".

## Open contract gaps
- The hunt's verified results and their fix slices; the three plans' slices (U0–U6, T0–T6, DR0–DR5).
