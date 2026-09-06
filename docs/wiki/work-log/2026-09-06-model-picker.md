---
title: "WORK LOG — MODEL-PICKER-V1: the chat model dropdown as collapsible provider sections"
change_id: MODEL-PICKER-V1
date: 2026-09-06
owner: governance (owner request 2026-09-06: "the model drop down … collapsible by associative provider so it's not just a long list at once as the keys grow")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.107
package: frontend/src/components/ModelPicker.tsx (new), frontend/src/components/TopBar.tsx (uses it), frontend/src/types.ts (grouping fields), frontend/src/app.css (picker rules), orchestrator/orchestrator/api/ui.py (catalog rows carry provider / provider_label / model), tests/determinism/test_chat_model_catalog.py, frontend/dist (rebuilt), scripts/scaffold_polymath_v4.py
architecture_impact: "Presentation of the existing catalog. The `/synthesizers` rows gain three data fields — `provider` (the provider row id: opencode-free, alibaba-model-studio, ollama-free), `provider_label` (display name) and `model` (bare model name) — so the UI groups by DATA, never by parsing ids; ids, labels, ordering and the default rule are unchanged. The native `<select>` is replaced by a button + popover: one section per provider with a caret, count and 'current' marker; the section holding the selected model opens by default; open/closed state per provider is remembered in localStorage; a filter box appears when the catalog exceeds twelve models (OpenCode's 31 free models will trigger it); Escape / outside click closes; selection semantics identical (`onSynthesizer(id)`). Under 640 px the popover docks to the bottom of the viewport."
---

# WORK LOG — MODEL-PICKER-V1

## Contract

The model control shows the current provider and model on one line and opens into provider sections that collapse independently, so a catalog of dozens of models reads as a handful of headings. Grouping fields are part of the catalog contract; the boundary rule (11.101: the chat catalog never feeds extraction / enrichment / compiler config) is untouched.

## Changes

- `ui.py`: `_litellm_models` rows add `provider` / `provider_label` / `model`; `_ollama_models` rows add `provider: ollama-free`, `provider_label: Ollama cloud (free)`, `model`.
- `ModelPicker.tsx`: groups by `provider` (label `provider_label`), default-open section = the one holding the selection, per-provider open state in `pm-model-picker-open`, filter over model and provider names above twelve entries, `role=listbox` / `option`, `aria-expanded` on section heads, `default` and `not pulled` tags from the row flags.
- `TopBar.tsx`: the Model control renders `ModelPicker`; `types.ts`: optional `provider`, `provider_label`, `model`, `kind`, `available` on `Synthesizer`; `app.css`: `.model-picker*` / `.model-group*` / `.model-item*` rules on the existing tokens.
- Test: `test_catalog_rows_carry_the_provider_grouping_fields` (OpenCode and Ollama rows carry the three fields; every row carries provider / provider_label / model / kind / available).

## Proof

- Offline: `test_chat_model_catalog.py` 9 tests green (the boundary test included); `npm run build` clean (tsc + vite).
- Live after the orchestrator respawn: `/synthesizers` returns 15 models in 2 provider groups (Alibaba Model Studio 9, Ollama cloud (free) 6); OpenCode's 31 appear as a third group once `OPENCODE_API_KEY` is in `.env` and the orchestrator is respawned.
- In-app browser on the final bundle: button reads "ALIBABA MODEL STUDIO · deepseek-v4-flash-0731"; opening shows the filter box (15 > 12) and two sections — Alibaba Model Studio 9 (open, holds the selection) and Ollama cloud (free) 6 (collapsed); collapsing Alibaba marks it "9 · current", expanding Ollama lists its six models, the open state persists as `{"alibaba-model-studio": false, "ollama-free": true}` in localStorage; picking gemma4:31b-cloud closes the popover and the button reads "OLLAMA CLOUD (FREE) · gemma4:31b-cloud"; typing "qwen" in the filter narrows to one section with five qwen models; Escape closes; selection restored to deepseek-v4-flash-0731; no console errors; at a 375 px viewport the popover docks to the bottom (fixed, 8 px margins, 359 px wide) with no horizontal overflow

## Rejected claims

- "Use `<optgroup>` in the native select" — rejected: optgroups group but do not collapse, and the owner asked for collapsible sections as the list grows.
- "Group by the LiteLLM route prefix (openai/, anthropic/)" — rejected: the route is not the provider (Alibaba serves DeepSeek through an Anthropic-format app; OpenCode serves many vendors through an OpenAI-format one); the provider row id is the associative key.

## Open contract gaps

- Keyboard navigation inside the popover is tab order only (no arrow-key roving); Escape and outside-click close it.
- The picker shows what the catalog offers; it does not show hidden providers (key unset) — the Models tab does.
