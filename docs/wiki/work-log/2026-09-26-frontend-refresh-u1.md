---
change_id: FRONTEND-REFRESH-U1
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Design tokens, Light / Dark / System + accent, the pre-paint appearance script, Settings → Appearance; the ten palettes, the sidebar swatches and the Google Fonts import are gone."
architecture_impact: "frontend-v2 only: src/styles/tokens.css (new), src/styles/themes.css (removed), src/styles/app.css (restyled on tokens), src/lib/appearance.ts (new), index.html, src/main.tsx, src/App.tsx, src/screens/Settings.tsx, three test files (new)."
last_reviewed: 2026-09-26
---

# FRONTEND-REFRESH U1: tokens and themes

## Contract
- FRONTEND-REFRESH-V1 §3 / slice U1 (plan of record 11.504). Owner decisions: Light / Dark / System + accent, Indigo by default,
  the system font stack.

## Changes
- **`src/styles/tokens.css`.**
  - Colors per mode (light / dark) with four accents.
  - The type scale, the space scale, radii, the focus ring and motion.
  - The legacy variable names (`--fg`, `--line`, `--bg-raised`, …) alias the new tokens, so screens' inline styles keep working until U6.
- **`src/lib/appearance.ts`.**
  - Stores `{mode, accent}` in `polymath.appearance`. System follows `prefers-color-scheme`, live.
  - A small store shares the value between Settings and, later, the top bar.
  - The ten old theme ids migrate once, at start-up, and the old key is removed:
    - the never-chosen default → System;
    - slate, paper, champagne → Light (the plan's table had slate as dark; corrected in the plan);
    - the dark palettes → Dark with the nearest accent.
- **`index.html`.** A few lines of inline script apply the stored choice before the first paint. Light mode no longer flashes dark, and the sign-in screen follows the theme.
- **Settings → Appearance.** A segmented control for the mode, and accent swatches with names.
- **Removed:** `themes.css` (10 palettes), the sidebar swatch grid, and the Google Fonts `@import` (Rubik, Roboto Mono). The system font stack loads nothing.
- **`app.css` restyled on the tokens**, with the class names kept:
  - sentence-case labels, pills and table headers (no uppercase monospace);
  - a visible `:focus-visible` ring, reduced-motion support, and chat-delete buttons that show on keyboard focus;
  - tables that scroll inside their card, and one primary color for the New chat button and primary buttons.

## Proof
- New vitest files (25 tests):
  - `tokens-contrast.test.ts` parses `tokens.css`. For both modes × 4 accents, every text pair is ≥ 4.5:1 and control edges are ≥ 3:1. A parser check makes sure a renamed token cannot skip the gate, and the formula is checked against known WCAG values.
  - `appearance.test.ts`: all ten old ids, the migration at start-up, round-trip storage, malformed values, System resolution.
- Full suite: 54 passed, 7 skipped (the live checks). `tsc --noEmit` clean; `npm run build` green.
- Seen in the in-app browser on a dev server from this worktree (proxying to :7200; the live `dist` untouched): Overview dark, Settings dark → Light, Chat light.

## Rejected claims
- "`.css?raw` gives the test the stylesheet": vitest stubs CSS imports, even with `?raw`. The test reads the file through
  `node:fs`, typed by a one-function declaration (`src/__tests__/node-fs.d.ts`; the project installs no `@types/node`).

## Open contract gaps
- U2 (the shell: top bar, phone drawer, moving the library picker / delete / control status); U3–U6.
