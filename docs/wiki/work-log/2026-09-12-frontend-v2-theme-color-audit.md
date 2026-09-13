---
title: "WORK LOG — FRONTEND-V2-THEME-COLOR-AUDIT: hardcoded colors that broke every non-default theme"
change_id: FRONTEND-V2-THEME-COLOR-AUDIT
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.248
architecture_impact: "frontend-v2 CSS only. Replaces every hardcoded color that bypassed the theme tokens with a theme-derived value (color-mix / var). No component, contract, or backend change."
---

> Owner: "the color scheme is inconsistent … font color for each theme is piss poor, I
> can[t] read, and the hover color is black for some themes." Correct — the themes
> redefined the tokens, but a handful of rules used BAKED-IN colors that only worked on
> the dark default.

## Contract

Every theme must be legible. A themeable design system means NO rule hardcodes a color
that a palette can't override.

## Changes

The 9 themes each redefine the full token set (`--fg`, `--bg*`, `--accent`, status hues).
But `app.css` had 11 rules with LITERAL colors, tuned for the dark default, that ignored
the active theme:

| rule | was | why it broke |
|---|---|---|
| `table.t tr:hover td` | `#11151a` (near-black) | **the "black hover"** — a black wash over a light theme, text unreadable |
| `.banner` / `--bad` / `--ok` text | `#f0d9a0` / `#f3b3b0` / `#9be0ac` (light) | light text on the light themes' light banner tint → ~1.5:1, unreadable |
| `.banner--info` bg | `#0f1b2b` (dark navy) | a dark box in a light UI |
| `button.btn--primary` border/hover | `#2f5c96` / `#234a78` (fixed blue) | clashed on every non-blue theme (espresso, rose, solar, paper…) |
| `.pill--*` borders | `#1c4526` / `#5c2326` / `#513d10` | fixed darks on light tints |
| `.files__del:hover` border | `#5c2326` | fixed dark red |

Every one is now theme-derived:
- **text on any status surface → `var(--fg)`** (the status is carried by the coloured
  left border + a per-theme `color-mix` tint, never by baked-in light text);
- **row hover → `color-mix(in srgb, var(--accent) 10%, var(--bg))`** — a gentle tint in
  the theme's own accent hue instead of black;
- **primary button / pill / delete borders → `color-mix(... var(--accent|--ok|--bad) …)`**
  so they track the palette.

## Proof

`tsc && vite build` clean. WCAG contrast of `--fg` on the fixed surfaces, computed across
the themes that were worst (light) and the darkest:

```
theme      fg/bad-banner  fg/ok-banner  fg/table-hover
slate            10.76         11.39          12.14
paper             8.83          9.37          10.02
champagne         9.74          9.92          10.27
obsidian         13.87         13.18          14.82
```

Every combination is **≥ 8.8:1** — past WCAG AAA (7:1); the replaced light-on-light
banner text was ~1.5:1 and the table hover was near-black. A full grep confirms the only
literal hex left in `app.css` are the `:root` default-palette token definitions and
drop-shadows.

## Rejected claims

- **"Just darken the light themes' text."** Rejected: the text tokens were already dark
  and fine; the unreadability came from RULES that ignored the tokens, not the tokens.
- **"Hand-pick a color per theme per element."** Rejected as 11×9 values that drift out
  of sync — `color-mix` against each theme's own `--bg`/`--accent` derives them once.

## Open contract gaps

- `--fg-faint` (small uppercase labels) sits ~2.5–3:1 on the two warmest light themes
  (paper/champagne) by design for "faint" text; raise it if any real label reads too
  weak. Not a blocker — body and secondary text are `--fg`/`--fg-dim` (≥ 4.5:1).
