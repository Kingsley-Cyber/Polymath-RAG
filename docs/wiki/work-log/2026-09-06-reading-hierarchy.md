---
title: "WORK LOG — READING-HIERARCHY-V1: the answer as a knowledge document — three densities, one font contract, typography tokens"
change_id: READING-HIERARCHY-V1
date: 2026-09-06
owner: governance (owner design contract 2026-09-06: "turn retrieved information into a readable knowledge document while preserving the machinery underneath it")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.103
package: frontend/src/app.css (tokens + rules), frontend/dist (rebuilt), scripts/scaffold_polymath_v4.py (asset names)
architecture_impact: "CSS only, on top of CHAT-UI-SURGICAL-V1 (11.102). The reading layer is a token contract in app.css (`--pm-*`): answer prose Rubik 15.5 px / 1.62 / 78ch measure; headings 21 / 18 / 16 px at weight 600, line 1.25, 1.55 rem above and 0.4 rem below with a tight 0.3 em to the first unit; paragraphs 0.78 em apart; lists 1.35 rem indent with 0.28 rem items; bold = 600 (a semantic anchor, never shouting); tables 13.5 px; blockquotes dim. Machine information is Roboto Mono and smaller: the process rail 12.5 px (details 11 px), metadata (mode, verdict, model, latency, ids) 11 px with 10.5 px badges at weight 500, code 12.5 px. Sources read as footnotes: a transparent panel with a 2 px left rule, [n] title in 13 px prose with the human locator at 600, the quote 13 px / 1.5, provenance 11 px mono behind the existing expander. Prose stays monochrome (colour lives in the system layer). Model markdown renders with `white-space: normal` inside the document so soft line breaks never force breaks. No component logic changed; the streaming contract, retrieval and backend are untouched."
---

# WORK LOG — READING-HIERARCHY-V1

Owner's thesis: presentation is the last reasoning interface between the RAG system and the reader; the knowledge must dominate, machine activity and metadata must be visibly subordinate, evidence must read like footnotes. v3.3 already used Rubik at ~0.95 rem / 1.6 with an 82ch measure and Roboto Mono for technical text; v4 carried a 14 px / 1.55 system font and a card around every answer.

## Contract

| layer | font | size / line | rules |
|---|---|---|---|
| answer prose | Rubik | 15.5 px / 1.62, 78ch | paragraphs 0.78 em apart; bold 600; links accent-underlined; monochrome |
| headings | Rubik 600 | h1 21 / h2 18 / h3 16 / h4 15.5, line 1.25 | 1.55 rem above, 0.4 rem below, 0.3 em to the first paragraph/list; first child flush |
| lists / tables / quotes | Rubik | lists 1.35 rem indent, 0.28 rem items, nested tighter; tables 13.5 px; quotes 14.5 px dim | continuation lines align to the text |
| process rail | Roboto Mono 500 | 12.5 px / 1.4, details 11 px | header, rows and details all machine-typed; the reasoning pane stays prose at 12.5 px |
| metadata | Roboto Mono 500 | 11 px; badges 10.5 px, tracking 0.06 em | mode, verdict, model, latency, chips |
| evidence | Rubik | title 13 px (locator 600), quote 13 px / 1.5 | transparent panel, 2 px left rule; provenance 11 px mono behind the expander |
| code | Roboto Mono | 12.5 px / 1.5 | unchanged block chrome |

Tokens: `--pm-prose`, `--pm-mono`, `--pm-answer-size/line/width`, `--pm-h1/h2/h3-size`, `--pm-heading-line`, `--pm-source-size/line`, `--pm-process-size/line`, `--pm-process-meta-size`, `--pm-meta-size`, `--pm-space-paragraph/section/list-item`. Fonts load from Google Fonts (`@import`, display=swap) with system fallbacks; a machine without network renders the same hierarchy in the fallback faces.

## Changes

- `frontend/src/app.css`: the `@import`, the `:root` tokens, `body` on the prose stack, the READING-HIERARCHY-V1 rule block (answer/markdown, rail, metadata, evidence footnotes, code); the earlier badge weight lowered to 500.
- `frontend/dist` rebuilt (`npm run build`, tsc clean; css 20.8 kB) and re-declared in the scaffold.

## Proof

Computed styles read from the running UI (in-app browser, `/ui`, 2026-09-06 17:3xZ, after reload on the new bundle; Rubik reported loaded by `document.fonts.check`):

- answer: `Rubik`, 15.5 px, line 25.11 px (1.62), max-width 767.9 px (78ch), transparent background
- paragraph: 0 / 12.09 px margins (0.78 em; first-child flush), `.md` white-space normal
- heading h2: 18 px, weight 600, line 22.5 px, margin 24.8 px above / 6.4 px below
- list: padding-left 21.6 px (1.35 rem), item margin 4.48 px (0.28 rem)
- process rail: `Roboto Mono` stack, 12.5 px (rows 12.5 px)
- metadata row: `Roboto Mono` stack, 11 px; badges 10.5 px
- evidence (32 rows): title `Rubik` 13 px with the locator at 600, quote 13 px / 19.5 px, panel transparent with a 2 px left rule
- `npm run build` clean; `repo_guard` / `agent_preflight` ok; no console errors on reload.

## Rejected claims

- "Bigger headings make structure clearer." Rejected: 28–36 px headings belong to marketing pages; 21 / 18 / 16 keep reading momentum and still separate sections by spacing.
- "Colour the key concepts in the prose." Rejected: colour fragments reading; it stays in the system layer (accent = clickable/active, green/amber/red = state).
- "Keep the evidence panel as a boxed card." Rejected: sources are footnotes, not a second answer.

## Open contract gaps

1. **The synthesis prompt does not yet cooperate with the renderer.** An information-presentation contract for the LLM (short information-dense paragraphs, headings only when they clarify, lists only for parallel concepts, bold only for anchors, conclusion → mechanism → detail) is a prompt change in the synthesis layer with a citation-precision re-run behind it — proposed, not done here.
2. **Font loading needs network once.** Rubik and Roboto Mono come from Google Fonts; a fully offline deployment would vendor the two families next to the bundle.
3. **Chat chrome (sidebar, top bar) keeps 14 px system sizing** by design; only the reading column moved to the contract.
