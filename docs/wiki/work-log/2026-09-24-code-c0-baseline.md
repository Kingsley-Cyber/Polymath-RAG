---
change_id: CODE-KNOWLEDGE-V1-C0A-BASELINE
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Experiments + documents only; no runtime change. C0a of CODE-KNOWLEDGE-V1 (the download-free half of C0): a fleet / receipts baseline, a census of this repository as a code corpus, the profile / pMAP capacity for decision 6, the Python call-resolution measurement that decides LibCST-only vs scip-python, the YAML span check that decides PyYAML vs ruamel / tree-sitter-yaml, and READ-class facts on the official Luau release, the tree-sitter language pack and CodeGraphContext. C0b (running LibCST, the Luau zip, tree-sitter-toml, Rojo / luau-lsp) waits for the owner's download word."
last_reviewed: 2026-09-24
---

# CODE-KNOWLEDGE-V1 C0a: baseline, census, capacity and the tool decisions that need no download

## Contract
- The owner, 2026-09-24: "yes write it into the plan. and inspect the bootstrap skills.bootstrap. compact and begin".
  "Begin" = START-HERE §4 row 1, C0: the fleet / receipts baseline; the §3.3 comparisons on this repository (Python /
  YAML / TOML); whether the macOS Luau release ships `luau-ast`; capacity numbers (decision 6). Each candidate is judged
  by four checks: exists · fixture run · real-input run · useful output.
- Downloads need the owner's explicit word (name, source, size). The download question was asked once and the dialog
  was rejected when the app was quit; it stays open. Nothing was downloaded or installed. Every measurement here uses
  what the machine already has: stdlib `ast` / `tomllib`, PyYAML 6.0.3, tiktoken's locally cached `cl100k_base`, the
  GitHub / PyPI / npm metadata APIs.
- Scope: this repository (the walking skeleton's first corpus, START-HERE §4) at production `62e2671`.

## Changes
All under `docs/wiki/experiments/code-knowledge-c0-2026-09-24/`:
- `baseline.py` → `baseline.json`: read-only SELECTs + `GET /ready`.
- `census.py` → `census.json`: files per card, parents per the Python card, token sizes, YAML / TOML structure.
- `capacity.py` → `capacity.json`: decision 6 arithmetic with every input's source named.
- `python_calls.py` → `python_calls.json`: the call-site mix and what resolves without type inference.
- `yaml_spans.py` → `yaml_spans.json`: PyYAML spans on every tracked YAML file + an anchors / aliases / multi-document
  fixture.
- `tool_reads.json`: READ-class facts (Luau release workflow, language pack README, CodeGraphContext source, sizes).

## Proof
**Baseline** (EXECUTED, `baseline.json`): `/ready` true (embedder + reranker); 24 healthy workers / 13 types on ONE
bundle `87e5db83bf30`. Corpora: `cinema` 67 documents / 84,152 chunks, `commerce-v1` 10 / 11,240. Documents are
`text/markdown` 76 + `text/html` 1; chunk contracts `chunk-structure-v3` 77,812 + `v3.1` 17,580. Runs: 69 reconciling,
26 query_ready, 18 superseded, 1 intake. 4,880 receipts (2026-09-03 → 2026-09-24).

**Census** (EXECUTED, `census.json`, tokens = cl100k proxy, ±10 % against the lane models):

| Card | Files | Structure |
|---|---|---|
| Python | 938 (0 parse errors) | 8,745 parents (730 classes, 7,018 top-level functions incl. 2,788 tests, one module block per file); 2.54M tokens |
| — product code (`shared` `orchestrator` `workers` `control` `mcp_server` `sidecars`) | 272 | 2,544 parents |
| — tests | 379 | 4,005 parents (46 % of all parents) |
| YAML | 55 tracked (54 in the census; 1 skipped with a receipt: `eval/gold/relations_v1.yaml`, generated header) | 260 top-level sections over all 55 (`yaml_spans.json`); 5 GitHub Actions, 1 Compose, the rest generic; 0 anchors; 0 files start with `---` |
| TOML | 10 | 47 tables, 77 keys; `tomllib` gives no positions |
| Luau | 0 | the owner's game is still needed |

Sizes that drive spec §12: 39 Python files are above 8K tokens and 100 are 4–8K; 5 parents are above 8K. The largest
single unit is the `TREE` list literal in `scripts/scaffold_polymath_v4.py` (one statement, ~94K tokens): the §12
splitter must cut inside one statement's elements, not only between statements.

**Capacity, decision 6** (EXECUTED arithmetic, `capacity.json`). Groq limits per key per model: 30 RPM / 1K RPD / 8K TPM
/ 200K TPD (work-log 2026-09-23-groq-model-swap L17). Measured on the 2026-09-23 canary: a gpt-oss-120b profile call
returns ~1,059 tokens; pMAP returns ~27 tokens per parent. The profile request budget follows §12.4: 8K TPM − 758
(profile SYSTEM) − 350 (code rules, ESTIMATE) − 600 (structure / relationships, ESTIMATE) − 2,400 (reserved output) =
3,892 source tokens per request.

| Scope | Files | Parents | Profile requests | Profile days, 1 key (today) | Profile days, 6 keys | pMAP days, 10 Groq lanes |
|---|---|---|---|---|---|---|
| product code | 272 | 2,544 | 437 | 11.0 | 1.8 | 0.46 |
| product code + scripts | 345 | 3,000 | 564 | 14.3 | 2.4 | 0.56 |
| whole repository | 938 | 8,745 | 1,356 | 33.3 | 5.5 | 1.57 |

The daily token budget binds, not latency (a call is ~2.5–3 s). The profile stage is the bottleneck: its pin is
`profile_groq1` + the OpenRouter fallback, and `profile_groq2..6` (gpt-oss-120b) exist in `config/cloud_providers.json`
but are disabled (the owner's 09-23 key mapping: key 1 profiles, keys 2–6 pMAP). The owner says Groq limits are
independent per model per key, so enabling them does not touch the pMAP budgets. This is a proposal for the owner, not
applied.

**Python resolver** (EXECUTED, `python_calls.json`): 80,746 call sites repo-wide. In product code, import-table +
enclosing-class resolution (what LibCST's QualifiedNameProvider does, without type inference) links 4,446 calls into
repository code. The calls only type inference could add are at most 1,780 by method-name match, and **293** once the
names that also exist only on test fakes or on library APIs are excluded (DB-API `execute` / `fetchall` / `fetchone` alone
are 1,084 of the 1,891 name matches). So **93.8 %** of product-code calls into repository code resolve without types.

**YAML** (EXECUTED, `yaml_spans.json`, PyYAML 6.0.3): 55 files, 260 sections, **0** content lines outside every section,
**0** overlaps by character offset. Line spans overlap in 2 single-line JSON-style manifests (`eval/i4/versioned/
manifest.yaml`, `eval/i3_5doc/versioned/manifest.yaml`), so children are cut by `mark.index` character offsets (the
`chunks.char_start / char_end` columns). Comments: 237 lines inside sections, 368 between sections; the rule "gap lines
attach to the following section" keeps them all in the exact source. The fixture gives the anchor (`base`, line 2) and
its 3 aliases (lines 6, 9, 11) with positions, merge keys resolve (`sword` → cooldown 1.5, damage 25), and a
multi-document file splits per document.

**READ-class facts** (`tool_reads.json`):
- The official Luau 0.739 tagged-release workflow builds `Luau.Ast.CLI` (`new-release.yml` L47) and zips `luau*` into
  `luau-macos.zip` (5,757,113 bytes, sha256 `f66cabc7…`). So the zip is built to ship `luau-ast` + `luau-analyze`; no
  source build expected. EXECUTED check waits (C0b).
- `tree-sitter-language-pack` downloads each parser at first use (its README L109 / L121).
- CodeGraphContext links calls by bare method name through a heuristic resolver (`resolve_function_call`, tiers 1–9).

**Decisions C0a proposes** (START-HERE §3.3):

| Question | Decision | Evidence |
|---|---|---|
| Python resolver | **LibCST-only for V1**; `obj.m()` on an unknown type stays `unresolved` with its name, never promoted; scip-python optional later, only if a C9 / C10 question fails on a missing edge | python_calls.json (EXECUTED) |
| Grammars | **single grammar wheels**; the language pack is rejected for the fleet (runtime parser downloads break pinned tools) | tool_reads.json (READ) |
| YAML | **PyYAML** for V1: offsets, anchors / aliases, comments via exact slices. ruamel.yaml / tree-sitter-yaml not needed; ruamel / tomlkit only if C13 writes configs | yaml_spans.json (EXECUTED) |
| TOML | tomllib has no spans: **tree-sitter-toml** (0.02 MB) in C5a, pending the download word | census.json (EXECUTED) |
| Luau | the official zip, pending the download word; Rojo + luau-lsp wait for the owner's game | tool_reads.json (READ) |
| CodeGraphContext | **STUDY only** (its tier / diagnostics idea); its name-based linking is the measured failure mode | tool_reads.json (READ) + python_calls.json |
| Qwen3-Embedding on code | DEFERRED to C9 / C10: it needs the code descriptions C6 / C7 produce | — |
| Capacity (decision 6) | the owner chooses: enable `profile_groq2..6`, and / or start with product code (272 files) | capacity.json |

## Rejected claims
- **"250 profiles per day per Groq key"** (feasibility review, 2026-09-23): that figure was compound's RPD. With
  gpt-oss-120b the 200K TPD binds: ~40 code-profile requests per key per day at ~5K tokens each.
- **"scip-python is needed for cross-file calls":** 6 % of product-code internal calls at most.
- **"PyYAML loses comments, so ruamel is required":** the evidence is the exact source slice; no comment line is lost.
- **"Line spans are enough for YAML":** false on flow-style files; character offsets are.

## Open contract gaps
- **C0b (owner's download word):** LibCST 1.9.0 on this repository (spans + qualified names vs the stdlib measurement);
  the Luau zip (checksum, `luau-ast` present, typed-Luau fixture); tree-sitter-toml; Rojo + luau-lsp once the game exists.
- The code-prompt overheads (350 + 600 tokens) are estimates until C6 / C7 build the prompts; a canary (the owner's
  word) measures the real request against the 8K TPM.
- Owner inputs: the Roblox game (Rojo / Argon files or a place file), YAML / TOML sets, a Power Apps `.pa.yaml` export,
  reference documents per project, .NET approval (C5b).
