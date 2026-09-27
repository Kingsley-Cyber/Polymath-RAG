---
title: "FRONTEND-REFRESH-V1 — a calmer, consistent, responsive Polymath web UI without adding weight"
date: 2026-09-26
last_reviewed: 2026-09-26
status: "ACTIVE — plan of record (register 11.504); the owner agreed to every §9 recommendation on 2026-09-26"
owner: "@king"
scope: "frontend-v2 only: design tokens and themes, the app shell, a small in-house set of UI pieces, per-screen passes. No backend change, no new route, no UI framework."
---

# FRONTEND-REFRESH-V1

## 0. The owner's request (2026-09-26)
"i think the themes are bad and ugly, i dont want to make it heavy but its needs improvement and planned out."

The UI is small, about 2,600 lines in all: nine screens (112–281 lines each), `App.tsx` (386 lines), `app.css` (465) and
`themes.css` (106). A refresh fits in a handful of frontend-only slices. None of them needs a bounce: the orchestrator serves
`frontend-v2/dist`, so each merge just needs `npm run build`.

## 1. What is wrong today
Seen on 2026-09-26 at 1280×800 and 375×812, owner view, every screen, four of the ten themes.

| # | Problem | Where |
|---|---|---|
| P1 | **Ten themes that are palette swaps of one layout.** Several are near-duplicates: Paper ≈ Champagne; V2 default ≈ Obsidian ≈ Graphite ≈ Slate. The swatch grid costs sidebar space and fixes nothing that looks wrong. | `styles/themes.css` (13 `[data-theme]` blocks), sidebar |
| P2 | **Developer-console language on every screen.** Uppercase monospace micro-labels on each field and card; raw enum names as status (`SEMANTIC_INCOMPLETE`, `VNEXT_COMPLETE`); internal notes on a user screen ("Why the legacy badge is not used … FRONTEND-V2-PLAN §7"). | Overview, Chat toolbar, Files, Control Plane |
| P3 | **The sidebar carries everything.** Nav, recent chats, the library picker, a destructive **Delete corpus** button, the theme swatches and the control pill all sit in the one column. | `App.tsx` shell |
| P4 | **Loading looks like failure.** Until its requests finish, Files shows "0 documents", "/control_plane not reachable" and `UNKNOWN` pills. | `screens/Files.tsx` |
| P5 | **Phones are broken.** On a 375-px screen the sidebar takes about half the width and cards clip their text. Friends will open the site on phones. | shell, cards |
| P6 | **Chat opens on a boxed form over an empty page.** The controls people change (mode, model, reasoning) sit far from where they type. | `screens/Chat.tsx` |
| P7 | **Wide tables show pipeline internals to everyone.** Files has 12 columns (parents, children, pMAP mapped, excluded, unresolved, graph entities/relations…). | `screens/Files.tsx` |
| P8 | **Faint text fails readability in every theme.** `--fg-faint` (labels, table headers, hints, empty states) is under 4.5:1 in all ten themes (3.52 in the default, 2.64 in Slate). Some status pills fail too (Nord bad 2.62, Champagne warn 2.53), and input borders are 1.3–1.9:1. | tokens |
| P9 | **No screen-size rules at all.** There is no `@media` in any file; the 208-px sidebar never folds on its own. | `app.css` |
| P10 | **Fonts come from Google at run time.** `app.css:1` imports Rubik and Roboto Mono from Google Fonts on every visit. Rubik is used for the whole app, 17 different font sizes are in use, and weights 600/700 are faked by the browser (not loaded). | `app.css` |
| P11 | **Light themes flash dark on load, and the sign-in screen ignores the theme.** The theme is applied after React mounts, inside the signed-in workspace only. | `App.tsx:114-125` |
| P12 | **Browser pop-ups instead of dialogs.** Delete, rename and similar actions use `window.prompt` / `confirm` / `alert`. | `App.tsx:219-230`, Files, Models, Settings |
| P13 | **Inconsistent building blocks.** 107 inline `style={{…}}` props; two separate table styles; Models uses nine class names that have no CSS at all and borrows Files' classes; the swatch colors in `App.tsx` drift from their themes' accents. | screens |
| P14 | **Keyboard and screen-reader gaps.** Only inputs get a focus ring. Collapsed nav buttons are named by a glyph. The Chat and library selects have no `<label>`. Graph rows are mouse-only. The model picker has no arrow keys. Looping animations ignore reduced motion. | shell, Chat, Graph |

## 2. Goals and non-goals
**Goals.**
- One coherent look, with light and dark both done well.
- Works from 360 px phones to wide desktops.
- Plain words for friends, detail on demand for the owner.
- Faster to scan: fewer boxes, clear hierarchy.

**Non-goals (what keeps it light).**
- No UI framework (Tailwind, MUI, Chakra, shadcn) and no CSS-in-JS.
- No router change and no new backend route.
- No change to what the owner's pipeline screens report, only to how it looks.
- No webfont by default.

## 3. Design direction: "quiet library"
- **Color.** Neutral surfaces, one accent color, semantic colors only for status.
- **Type.**
  - The system UI stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`). The Google Fonts import (Rubik, Roboto Mono) goes: one fewer outside request on every visit, and no faked bold weights.
  - Sizes 12 / 13 / 14 / 16 / 20 / 24 px. Chat answers at 16 px with 1.65 line height.
  - Monospace only for ids, code and citation markers.
- **Shape.** Radius 6 px on controls, 10 px on cards. Borders only between regions; elevation comes from surface color, not outlines on every box. Spacing on a 4-px grid (4, 8, 12, 16, 24, 32, 48).
- **Labels.** Sentence case, 13 px, medium weight, secondary color. No uppercase monospace.
- **Status.** Plain words with a colored dot: Ready · Working · Needs enrichment · Paused · Problem. The enum name moves into a tooltip and the owner's details.
- **Motion.** 120–180 ms fades only; `prefers-reduced-motion` turns them off.

### 3.1 Tokens (the only colors any CSS may use)
Proposed values. The contrast test in U1 is the gate: body and secondary text ≥ 4.5:1 on every surface in both modes, and icons and borders of controls ≥ 3:1. Computed on 2026-09-26, the worst pair in each role:
- `--text-3` 4.74 (light) / 4.69 (dark); `--accent` 5.56 / 5.31; the status colors ≥ 5.6 on every surface and on their own soft fill;
- text on an accent fill 6.29 / 6.57; `--border-control` ≥ 3.07 / 3.14.
Today's `--fg-faint`, by comparison, is 3.52 in the default theme.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F7F7F5` | `#111113` | page |
| `--surface` | `#FFFFFF` | `#18181B` | cards, panels, composer |
| `--surface-2` | `#F1F1EE` | `#222226` | hover, subtle fills, table header |
| `--border` | `#E3E3DE` | `#2C2C31` | region dividers, inputs |
| `--border-strong` | `#CFCFC8` | `#3A3A40` | hover edges, table rules |
| `--border-control` | `#8A8A82` | `#6E6E77` | input, select and checkbox edges (≥ 3:1 on every surface) |
| `--text` | `#1C1C1A` | `#EDEDEF` | body |
| `--text-2` | `#55554F` | `#B4B4BB` | labels, secondary |
| `--text-3` | `#6B6B64` | `#8B8B93` | hints, timestamps |
| `--accent` | `#4F46E5` | `#818CF8` | links, primary button, selection |
| `--accent-soft` | `#EEF0FF` | `#262A4A` | selected nav item, chips |
| `--on-accent` | `#FFFFFF` | `#0B0B12` | text on an accent fill |
| `--ok` / `--ok-soft` | `#166534` / `#E8F5EC` | `#4ADE80` / `#16301F` | Ready |
| `--warn` / `--warn-soft` | `#92400E` / `#FDF3E4` | `#FBBF24` / `#33280F` | Working, Needs enrichment |
| `--bad` / `--bad-soft` | `#B91C1C` / `#FDECEC` | `#F87171` / `#3A1717` | Problem, danger buttons |
| `--focus` | `0 0 0 2px var(--surface), 0 0 0 4px var(--accent)` | same | `:focus-visible` ring |

Plus `--radius-1: 6px`, `--radius-2: 10px`, `--space-1…7`, `--font-ui`, `--font-mono`, `--shadow-pop` (menus and dialogs only).

### 3.2 Themes
- **Light, Dark, System** (follows the OS), plus one **accent**: Indigo (default), Teal, Amber, Rose. Each accent swaps only `--accent`, `--accent-soft` and `--on-accent`.
- Stored in `localStorage` as `polymath.appearance = {mode, accent}`, set in Settings → Appearance, with a sun/moon toggle in the top bar.
- The choice is applied **before the first paint** by a few lines of inline script in `index.html`, so light mode never flashes dark. It covers the sign-in screen too.
- The ten old theme ids (saved today as `polymath-v2.theme`) map to the nearest pair, so nobody's saved choice breaks, and an unknown id falls back to System:

| Old theme ids | New mode + accent |
|---|---|
| the never-chosen default (`""`) | System + Indigo (no preference was ever expressed) |
| obsidian, graphite | Dark + Indigo |
| nord | Dark + Teal |
| espresso, solar | Dark + Amber |
| rose | Dark + Rose |
| slate | Light + Indigo |
| paper, champagne | Light + Amber |

_(Corrected in U1: slate, paper and champagne were LIGHT palettes, and paper's / champagne's accents are amber.)_

## 4. Layout
- **Desktop (≥ 1100 px).** Sidebar 232 px (collapsible to 56-px icons), a 52-px top bar, content. Reading screens (Chat, a run report) keep a 760-px column; data screens use the full width.
- **Tablet (760–1099 px).** The sidebar starts collapsed to icons.
- **Phone (< 760 px).**
  - The sidebar becomes a drawer behind a menu button, and the composer sticks to the bottom.
  - Tables scroll inside their card, and two-pane screens (Graph, Compare) stack.
- **Sidebar.**
  - Brand, then **New chat**, then Chat · Compare · Files · Graph.
  - Owner only: Overview · Control Plane · Models.
  - Then Settings, then Recent chats.
- **Top bar.** The current library (a switcher), the page title, the theme toggle, and the account menu (name, Settings, Sign out). The owner also gets a small control-plane status dot that links to Control Plane.
- **Delete corpus** moves to Files → Library settings → Danger zone, behind a dialog that asks you to type the library's name.

## 5. Shared UI pieces (in-house, tiny)
- **`src/ui/` pieces:**
  - Button (primary · secondary · ghost · danger; small and medium);
  - IconButton, whose `aria-label` is required by its type;
  - Field (label, hint, error), Select, Switch;
  - Status (dot + word + tooltip), Card, Table (sticky header, scroll container), Tabs;
  - Dialog (the native `<dialog>`), which replaces every `window.prompt` / `confirm` / `alert`; EmptyState, Skeleton, ErrorState, and one Toast region.
- **Kept and restyled.** The existing shared components stay: Pill/StatePill, ReadinessTriad, ModelPicker (gains arrow keys), ProcessRail, AnswerBody with QueryTrace, LaneTable, EvidenceInspector and AnswerReview. Unused PhaseStub goes.
- **Styles.** One `ui.css`, reading only the tokens.
- **Icons.** About 20 outline icons copied as components from Lucide (ISC license; the notice sits at the top of `src/ui/icons.tsx`). No icon package.
- **Budget.** No new runtime dependency. Today: JS 469 KB (142 KB gzip), CSS 21 KB (5.4 KB gzip). JS may grow ≤ 10 KB gzip; CSS stays ≤ 40 KB unminified.

## 6. Screen passes
- **Chat.**
  - The boxed toolbar goes: Mode, Model, Reasoning and Explore become chips in the composer's footer.
  - The empty state shows the library name and three example questions.
  - Answers sit in the reading column. Citation markers [1] [2] open a hover card with the source title, section and snippet, plus "Open source".
  - A **Stop** button while streaming, **Copy** on each answer, and a small mode badge per answer.
- **Files.**
  - Skeleton rows while loading; "Couldn't reach the server. Retry" on error; an invitation when empty.
  - Default columns: Name · Type · Added · Size · Status. A **Details** switch (owner) adds the pipeline columns.
  - An upload drop zone, and Library settings (the danger zone).
- **Graph.** Search on top, entities on the left, relationships on the right; stacks on phones; entity-type chips.
- **Compare.** Modes as toggle chips; results side by side (desktop) or stacked (phone), with the same citation chips.
- **Overview (owner).** Three readiness cards in plain words, with the enum in a tooltip. The "legacy badge" note moves into a closed "Details" section.
- **Control Plane and Models (owner).** Same data; tokens, Card and Table pieces, compact density.
- **Settings.** Sections: Account · Appearance · API keys · Friends (owner).
- **Login.** A centered card with the brand mark and the same tokens.

## 7. Slices
Every slice:
- is frontend only;
- passes `npx tsc --noEmit`, `npx vitest run` and `npm run build`;
- is committed before any build (`dist` is git-ignored, so uncommitted UI dies at the next rebuild);
- is shown before and after in the in-app browser at 1280, 768 and 375 px, light and dark, owner and friend.

| Slice | What | Proof |
|---|---|---|
| **U0** baseline | Screenshots of every screen (3 widths × 2 modes), bundle sizes, the §8 accessibility list. | `docs/wiki/experiments/frontend-refresh-<date>/README.md` with the numbers; images kept outside the repo. |
| **U1** tokens + themes — DONE 11.506 | `styles/tokens.css`; Light / Dark / System + accents; the old-id migration; Settings → Appearance; every hard-coded color replaced by a token. | A vitest contrast test computes WCAG ratios from `tokens.css` and fails any pair under its threshold, in both modes; a migration test for all ten old ids. |
| **U2** shell — DONE 11.507 | Sidebar, top bar, phone drawer. Moves the library picker, the theme control, Delete corpus and the control dot. Every nav button gets an accessible name. | Shell tests (friend vs owner nav, drawer open/close); 375-px screenshots show no clipping and no horizontal scroll. |
| **U3** UI pieces + icons — DONE 11.508 | `src/ui/*`; Settings and Login adopt them first (the newest screens). | Unit tests for Button, Dialog (focus trap, Esc), Status (tooltip text = enum). |
| **U4** Chat — DONE 11.509; U4b citation hover cards DONE 11.517 | Composer chips, the reading column, citation hover cards, Stop, Copy, the empty state. | `chat-session.test.tsx` and the streaming tests stay green; one real owner question on :7200 (on the owner's word — live chat turns are counted). |
| **U5** Files, Graph, Compare, Overview — DONE 11.510 | Loading, empty and error states; column sets; the danger-zone dialog; stacked layouts on phones. | A test that loading never renders "0 documents"; a type-to-confirm delete test. |
| **U6** owner screens + polish — DONE 11.511 | Control Plane and Models on the shared pieces; focus rings; keyboard for dialogs and the drawer; reduced motion. | The live contract check (`npx vitest run src/__tests__/live-contract.test.ts`) on :7200; final screenshots. |

## 8. Measured baseline
Code facts read on 2026-09-26 (production `7e1918c2`). U0 adds the screenshots and re-measures the bundle.

- **Tokens.**
  - 14 color tokens per theme: `--bg`, `--bg-raised`, `--bg-sunken`, `--line`, `--line-soft`, `--fg`, `--fg-dim`, `--fg-faint`, `--accent`, `--accent-dim`, `--ok`, `--warn`, `--bad`, `--unknown`.
  - Status tints are made with `color-mix` (`themes.css:100-106`); the hard-coded tints at `app.css:24-30` are dead.
  - Spacing, shadows, most radii and all font sizes are literals.
- **Stack.** react 19, react-markdown 10, remark-gfm 4; vite 6, vitest 2, jsdom. No UI kit, no icon set (icons are Unicode glyphs), and no graph drawing (Graph is a table and a list).
- **Tests that pin markup.** U-slices must keep these passing, changing them only together with the markup and never more loosely:

| Test file | What it pins |
|---|---|
| `friends-access.test.tsx` | nav labels via `.nav__item span`. Buttons by exact text: "Sign in", "Settings", "Create key", "I've saved it", "Done", "Add friend". The first two inputs are username then password. `input[placeholder="username (lowercase)"]`. Texts "Sign in to continue.", "Choose your own password to continue", "This key is shown only now", "Friends", "Delete corpus", "POLYMATH_MCP_API_KEY" |
| `chat-session.test.tsx` | `.nav__chat-open` by title, `textarea.composer__input`, `button[aria-label="Send"]` and "Stop", the "＋ New chat" button, the select holding the GNN option |
| `chat-surface.test.tsx` | `.label` "Retrieval", a nav button whose text is exactly "Chat", Markdown output as bare `<table>`/`<td>`/`<strong>`/`<li>`, texts "⌖ synthesis", "⛁ 3 chunks", "Query trace", "Working · 2 steps", "Worked for", "2.4s" |
| `live-contract`, `proxy-covers-backend`, `retrieval-modes` | no DOM assertions (API contract only) |

## 9. Owner decisions
**DECIDED 2026-09-26** (the owner: "i agree please fix it all"): Light / Dark / System + accent; Indigo by default; the system font stack; the order U0 → U6.

1. **Themes:** collapse the ten themes to Light / Dark / System plus an accent (recommended), or keep a few named themes.
2. **Default accent:** Indigo (recommended), Teal, Amber or Rose.
3. **Font:** the system stack (recommended, 0 KB), or Inter self-hosted (about 100 KB).
4. **Order:** U0 → U6 as listed (recommended), or Chat (U4) straight after U1 so friends see the change first.

## 10. Risks
- **Markup changes break test selectors.** A test changes in the same commit as the markup it checks, and asserts the new structure at least as strictly; never loosened.
- **A saved theme id the map does not know** falls back to System instead of breaking the page.
- **The live contract check reads the UI's own sources.** A slice that renames an API helper updates it in the same commit.
