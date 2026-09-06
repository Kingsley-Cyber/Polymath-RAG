---
title: "WORK LOG — LEGIBILITY-V1: every theme's text clears WCAG AA on every surface; bold is the occasional highlight"
change_id: LEGIBILITY-V1
date: 2026-09-06
owner: governance (owner request 2026-09-06: "a ui/ux color fix to make text legible, and occasional highlights of text is good. its gotten to the point where its hard to read text and differentiate with ui/ux")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.104
package: frontend/src/themes.css (per-theme --text-dim / --accent), frontend/src/app.css (LEGIBILITY-V1 block), frontend/dist (rebuilt), scripts/scaffold_polymath_v4.py (asset names)
architecture_impact: "CSS only, on top of READING-HIERARCHY-V1 (11.103). Root cause of 'hard to read': secondary text (`--text-dim`) sat below the WCAG AA threshold (4.5:1) in the light themes (paper / champagne / slate measured 3.8–4.0:1 on the page ground, lower on the raised `--bg-3` surfaces the process rail, badges and evidence use), and the reading column inherited that dim tone in several places. Fix: (1) `--text-dim` raised per theme so it measures ≥ 5.2:1 on `--bg` and ≥ 4.6:1 on `--bg-3` in all nine themes; light-theme accents darkened to ≥ 4.5:1 so links and the active state read as text; (2) the answer column is forced to full `--text`, secondary tone is reserved for machine information, the evidence quote reads at 90 % of full text; (3) the occasional highlight: `strong` inside an answer renders as a soft accent wash (13 % accent over the ground, clone-boxed across line wraps), `::selection` is a 32 % accent wash, inline code and blockquotes carry a faint accent tint — colour communicates anchor / selection / quote, never decorates prose. No component logic changed; the streaming contract and backend are untouched."
---

# WORK LOG — LEGIBILITY-V1

Owner's complaint (2026-09-06): text is hard to read and hard to separate from the UI. The typography contract (11.103) fixed size, rhythm and hierarchy but kept the theme colours, and the dim token those themes used for secondary text is below the accessibility floor in every light theme.

## Contract

Every text tone clears WCAG AA (≥ 4.5:1) on every surface it is used on, in every theme; the reading column is full-contrast; colour marks state, anchors and selection, never prose. Measured contrast (live UI, computed styles, WCAG 2.x ratio):

Before: obsidian (default) dim 6.6:1 — fine; paper / champagne / slate dim 3.8–4.0:1 on `--bg` and lower on `--bg-3` (below AA 4.5:1); light-theme accents 3.9–4.3:1.

After (final bundle `index-MEa6z85q.js` / `index-BX3b8jmX.css`):

| theme | text on bg | dim on bg | dim on bg-3 | accent on bg |
|---|---|---|---|---|
| obsidian | 16.66 | 6.63 | 5.79 | 7.92 |
| paper | 11.30 | 5.22 | 4.73 | 4.50 |
| champagne | 11.62 | 5.26 | 4.82 | 4.51 |
| slate | 13.81 | 5.22 | 4.85 | 4.55 (accent #3465d2; #396bd6 measured 4.49) |
| nord | 10.84 | 5.71 | 4.60 | 6.24 |
| solar | 12.25 | 6.28 | 4.60 | 4.68 |
| graphite | 10.55 | 6.32 | 4.64 | 5.67 |
| rose | 15.21 | 6.22 | 5.30 | 8.76 |
| espresso | 15.01 | 6.53 | 5.56 | 7.66 |

Every cell ≥ 4.5 (AA for body text); obsidian / rose / espresso unchanged.

## Changes

themes.css: `--text-dim` raised in nord (#a6b0c1), solar (#9faaa8), slate (#5b667f), paper (#6e6450), graphite (#b6bdc8), champagne (#726149); `--accent` darkened in slate (#3465d2), paper (#9c621c), champagne (#8a6832). app.css, LEGIBILITY-V1 block:

- Answer prose, list items and user text at full `--text`.
- `strong` / `b` inside `.answer .md`: full text colour on a `color-mix(accent 13 %)` wash, 0.18 em side padding, 3 px radius, `box-decoration-break: clone` (the highlight follows a wrapped anchor).
- `::selection`: 32 % accent wash. Blockquotes: 86 % text on a 6 % accent tint. Inline code: text colour on a 10 % accent tint over `--bg-3`. Links: accent with a 45 % accent underline.
- Evidence: quote at 90 % text, primary locator at 84 %, secondary locators dim. Process rail: rows at 74 %, the active row full, details and the collapsed summary dim (summary full on hover / focus). Metadata, chips and copy buttons dim (now AA on every surface), full on hover.

## Proof

- `npm run build` clean; dist rebuilt; scaffold re-declared; `repo_guard.py` ok.
- In-app browser on the final bundle: the nine-theme contrast table above; paper theme rendered with the warm anchor wash and the page ground (a first read taken inside the 250 ms theme transition showed the previous ground behind the composer — a transition artefact, re-measured after 1.5 s: body ground `rgb(247 242 231)`, text `rgb(58 50 38)`); obsidian anchor wash `color(srgb 0.49 0.64 0.96 / 0.13)` under full text.
- Observed on the live answers: the model bolds whole sentences (a 2.5-line bold thesis), which turns the highlight into a marker stripe — that is a synthesis-prompt matter, handled by PRESENTATION-V1 (11.105), not by CSS.

## Rejected claims

- "The dark composer band in the paper theme is a bug" — rejected: a computed-style read inside the 250 ms body transition; after 1.5 s the ground is the theme's.
- "Contrast is fine because obsidian is fine" — rejected: the default theme passed, the light themes did not, and the owner uses more than one.

## Open contract gaps

- No theme was redesigned; hue and identity are unchanged, only the two failing tokens per theme moved.
- Semantic state colours (ok / warn / err) were not re-audited as text; they are used on badges with their own fills.
