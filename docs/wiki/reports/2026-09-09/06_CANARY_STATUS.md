---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 06 — Canary Status

## Full-pipeline canary (directive §17: `/upload`→semantic-ready <4min ×3)
**DOES NOT EXIST → consecutive passes = 0/3.** No `scripts/*pipeline*` / upload-to-ready timed canary in
the repo. This is unfinished work (`05` P1). The "3 consecutive passes" clock has never started.

## Stage canaries present (scripts/)
| canary | scope | last-known |
|---|---|---|
| `parent_map_canary.py` | pMAP contract live (MAP DSL + compiler + projection) | PASS 22/22 & 11/11, injection-resisted (11.136) |
| `parent_map_projection_canary.py` | pMAP → Qdrant projection | PASS (11.x) |
| `profile_vnext_canary.py` | doc_profile vNext prompt/compile | PASS |
| `profile_vnext_selfretrieval_canary.py` | profile self-retrieval | PASS |
| `profile_atom_canary.py` | profile atoms (10 kinds) | PASS (cinema 609 atoms) |
| `chat_compiler_canary.py` | chat plan compile | PASS |
| `siliconflow_extraction_canary.py` | siliconflow extraction lanes | PASS 3/3 (11.182) |
| `shadow_route_canary.py` | profile→map→child shadow route | PASS 36 probes (11.154) |
| `vnext_readiness_report.py` | read-only readiness view | VERIFIED live |

## Ad-hoc model probes THIS session (scratchpad, no durable canary)
- **mistral-nemo** via OpenRouter/deepinfra-fp8 on the Benesh doc: doc_profile PASS, pMAP PASS 9/9, 6-way concurrency 6/6 clean. (bounded, ~0.01 spend)
- **llama-3.1-8b** same: doc_profile PASS (sparse), **pMAP FAIL 0/9** (dropped `MAP\|` prefix + ~⅓ mis-assigned descriptors).
- **Gemini extract** (3.1/3.5-flash-lite, 3.7-flash, flash-lite-latest): all PASS graph-extraction schema+quote gate on a clean chunk; relation density favored the cheap 3.1-flash-lite.
These are throwaway probes (`/private/tmp/.../scratchpad/`), not committed canaries.

## d7-h1-test corpus (reference)
`d7-h1-test` reached **VNEXT_COMPLETE** end-to-end (78/78 parents mapped, 3/3 profiles, 30 atoms) — the
first corpus to flip the readiness verdict autonomously (11.176). Cinema is PARTIAL (11.4%) under hold.

## Verdict
Stage-level pipeline is qualified; the **service-level (upload→ready) canary is unbuilt**. Report canary
stability as **0/3** until that exists and runs.
