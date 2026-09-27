---
change_id: HEADER-CONTROLS
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Owner instruction 2026-09-27: in the UI only Deep research and Reasoning stay in the chat box; Retrieval, Model and Corpus Explore move to the top bar next to the library. A per-browser store carries them to the request builders, which send the same fields as before. Unit and worktree proven on feat/header-controls (pmv4-hdr, from feat/fix-it-all at 84a67f49); measured in a real browser on a stubbed build; not merged, not deployed."
architecture_impact: "frontend-v2/src/lib/composerSettings.ts (new: the store, key polymath-v2.chat-settings); frontend-v2/src/components/ChatControls.tsx (new: the top bar's Retrieval / Model / Corpus Explore, the phone button + panel); frontend-v2/src/App.tsx (reads /synthesizers and /capabilities once, renders ChatControls on the Chat screen, passes models + corpusExploreAvailable to Chat); frontend-v2/src/screens/Chat.tsx (reads the store; the composer keeps Deep research, Depth, Reasoning; the fold and optionsSummary removed; corpus_explorer sent only while the capability is advertised); frontend-v2/src/styles/app.css (the header controls, the ≤ 1099 px panel, the ≤ 560 px composer grid; the fold CSS removed); frontend-v2/src/ui/icons.tsx (sliders); tests: header-controls.test.tsx (new), composer-settings.test.ts (new), chat-composer.test.tsx (rewritten); scripts/scaffold_polymath_v4.py (5 TREE entries). No backend change: the chat and deep requests carry the same fields."
last_reviewed: 2026-09-27
---

# HEADER-CONTROLS: Retrieval, Model and Corpus Explore move to the top bar

## Contract
- The owner, 2026-09-27: "in the ui only deepresearch should be in the chatbox and reasoning. everything else should be in
  the header top next to corpus selector".
- What moves: the Retrieval mode select, the Model picker and the Corpus Explore switch. They sit in the top bar right
  after the library selector, on the Chat screen only, with the same words as labels.
- What stays in the composer: Deep research (with Depth while on) and Reasoning.
- One value per browser: the three choices live in a small store (`polymath-v2.chat-settings`), so the top bar and the
  composer read the same thing and a reload keeps it. Defaults as before: HYBRID, the backend's default model, explore off.
- The chat request (`/chat/stream`) and the deep request (`/research/deep`) keep the same fields: `mode`, `synthesizer`
  (when a model is picked), `corpus_explorer` (when on AND the server advertises `corpus-explorer`). Nothing changes for the
  backend; `live-contract.test.ts` still reads the fields from `body` / `deepRequest` in Chat.tsx.
- Phones: the top bar cannot fit three controls beside the selector; they go behind ONE icon button, "Chat options".
- Boundaries: worktree `pmv4-hdr`, branch `feat/header-controls` from `feat/fix-it-all` at `84a67f49`. No live system, no
  register / CONTINUITY / plan edits, no push.

## Changes
- **`lib/composerSettings.ts`** (new, in the pattern of `appearance.ts`): `{ mode, model, corpusExplore }` under one key,
  `useComposerSettings()` → `[settings, patch]`, `get / set / updateComposerSettings`. Every read and write of storage is in
  try/catch; each field is validated on its own (an unknown mode → HYBRID, a non-string model → "", anything but `true` →
  off), and the stored string is the truth: the snapshot is re-parsed only when that string changes (a stable reference
  otherwise), so a value cleared or written elsewhere shows on the next render, and another window's write is picked up by
  the `storage` event. With no storage (private mode) the choice lives in memory for the session.
- **`components/ChatControls.tsx`** (new): the three controls, rendered ONCE: a `.topbar__chat` wrapper with an
  `IconButton` "Chat options" (`aria-expanded`, `aria-controls`) and the `.topbar__controls` group (`role="group"`,
  `aria-label="Chat options"`) holding the Retrieval `<label>` + select, the Model group (`aria-labelledby` its label) with
  the existing `ModelPicker`, and the Corpus Explore `<label>` + checkbox, the last only when the capability is advertised.
  Escape, a click outside or the button closes the panel. A stored model the catalog no longer offers is reset to the
  default (it would otherwise send a synthesizer the backend cannot run).
- **`App.tsx`**: Workspace reads `/synthesizers` and `/capabilities` once (before: Chat read both on every mount) and
  derives `corpusExploreAvailable`; the top bar renders `<ChatControls>` right after the library `<label>` while
  `screen === "chat"`; `<Chat>` gets `models` and `corpusExploreAvailable`.
- **`screens/Chat.tsx`**: reads `mode / model / corpusExplore` from the store; `reasoning`, `deep`, `preset` stay local.
  The `body` and `deepRequest` builders are unchanged apart from `corpus_explorer`, now gated on the capability as well as
  the switch. The composer's `.composer__chips` holds Deep research, Depth (while on) and Reasoning; the fold button, its
  state, `optionsSummary()` and the `useId` went. Props `models` and `corpusExploreAvailable` replace the two fetches.
- **`styles/app.css`**: `.topbar` is `position: relative`; `.topbar__library` has a 120 px floor and its select `width:
  100%`, so a long library name gives way before anything overflows. `.topbar__controls` is an inline flex row; only the
  model chip shrinks (120 px floor, the model text ellipsized on one line). `@media (max-width: 1099px)`: the button shows,
  the group becomes a panel under the bar (`left/right: 8px`, `max-width: 360px`, one control per 36 px row, the model
  menu right-aligned) shown while `--open`. The fold block (`.composer__options`, `.composer__fold*`, the ≤ 560 px rules)
  and the composer's picker-menu override were removed. `@media (max-width: 560px)`: the composer becomes a two-row grid
  (the box and Send on the first row, the chips across the second: see Proof for why).
- **`ui/icons.tsx`**: `sliders` (Lucide sliders-horizontal) for the phone button.
- **Tests** (vitest, jsdom): `header-controls.test.tsx` (new, 7): the controls show on the Chat screen only, after the
  library; Retrieval in the bar sets the mode of the next chat request and of a deep run; the Model picker sets
  `synthesizer` (and the default sends none); Corpus Explore shows only when advertised and sets `corpus_explorer`; the
  choices survive a remount under one key; a stale stored model falls back; the phone button opens the panel and Escape /
  outside click / the button close it. `composer-settings.test.ts` (new, 4): defaults, round-trip + patch, per-field
  validation, storage as the truth. `chat-composer.test.tsx` (rewritten, 3): only Deep research and Reasoning (Depth while
  on) and no fold; the stored mode / model / explore ride on the request, explore only when the server offers it;
  Reasoning stays the composer's. The two DR7f fold cases were removed with the fold. `chat-surface`, `chat-session`,
  `chat-deep`, `deep-research-ui`, `shell` and `friends-access` pass unchanged (they find the Retrieval select wherever it
  is, and the first `.topbar select` is still the library).
- `scripts/scaffold_polymath_v4.py`: TREE entries for the two new modules, the two new tests and this work-log.

## Proof
- **Tests first.** At `84a67f49` the three new test files fail to load (no `lib/composerSettings`). With only the store
  module copied onto the base, 9 of 14 cases fail on their assertions (the composer still lists Retrieval and Model, no
  `.topbar__controls`, no "Chat options" button, the stored model is not reset); the 5 that pass are the store's own 4 and
  the composer's Reasoning case, which holds before and after. Run in a throwaway detached worktree, removed afterwards.
- **The request fields, read the way `live-contract.test.ts` reads them** (the same TypeScript walk over Chat.tsx, run
  offline, no server): `chatStream` sends `message, corpus_id, mode, require_retrieval, synthesizer, reasoning,
  corpus_explorer`; `deepResearchStream` sends `question, corpus_id, preset, mode, synthesizer, plan`. Identical to the base.
- **Measured in a real browser** (the production build served from the scratchpad with `fetch` replaced by a fake backend:
  a 16-model catalog, a 39-character library name, `corpus-explorer` advertised; nothing reached :7200):
  - 1280 px, icon rail: bar 1224 / 1224 (client / scroll); the chips Retrieval 166, Model 256, Corpus Explore 129 px, one
    30 px row; the composer's two chips on one row.
  - 1100 px (the narrowest desktop), sidebar open, the long library: 868 / 868; the library select 260 → 209 px, the model
    button 90 px on one line (26 px tall), Retrieval and Corpus Explore untouched, nothing under the status pill. (Before
    the shrink rules the model button wrapped to 44 px and Corpus Explore slid under the pill; both fixed.)
  - 1024 px, sidebar open: the button at x 516 right after the library; the panel 360 × 150 under the bar, three 36 px
    rows; the model menu 320 px inside the viewport (264–584); 792 / 792.
  - 375 px: bar 375 / 375; menu button 34 px after the 126 px library; the panel 359 px (8–367), the model menu 31–351;
    `document.documentElement.scrollWidth` 375 with the panel and the menu open.
  - 375 px, the composer: the two chips need 288 px; beside the Send button 267 px remain, so they stacked (row 66 px,
    composer 143 px). With Send beside the box (the ≤ 560 px grid) they share one 30 px row and the composer is 109 px —
    the height of yesterday's closed fold (the old open fold was 204 px without the box). A three-line question: 132 px.
    Deep research on: Depth joins the row and Reasoning wraps (row 66 px, composer 145 px), no sideways scroll.
  - 560 px: the grid (Send beside the box, one row); 561 px: the flex row, Send at the right, one row; the header button
    shows at both (≤ 1099 px), inline from 1100 px.
  - Dark mode at 375 px (panel open) and 1280 px (inline): tokens only, nothing hard-coded.
  - Tab order at 1280 px: library → Retrieval → Model → Corpus Explore → status → theme → account; the hidden phone button
    is not focusable; a keyboard change on Retrieval stores `{"mode":"GRAPH","model":"","corpusExplore":false}`.
- **Guards** on the final tree: `tsc --noEmit` 0; vitest (live-contract and proxy-covers-backend excluded): 20 files, 147
  tests (18 / 135 at `84a67f49`: +14 new, −2 fold cases); `repo_guard`, `agent_preflight`, `wiki_worm --check` ok.

## Rejected claims
- "Fold the header only on phones (≤ 560 or ≤ 759 px)": no. Between 760 and 1099 px the sidebar may be open (232 px); a
  760 px window then leaves ~530 px of bar, and the inline row needs ~780 px. The fold follows the shell's own tablet
  breakpoint (1099 px, where the rail collapses), so no width overflows.
- "Keep a smaller composer fold on phones": no. The rule was to remove the fold if the two chips fit one row at 375 px.
  Beside the Send button they do not (288 vs 267 px); with Send beside the box they do (309 px), at the closed fold's
  height and with the Deep research switch in reach without a tap. A fold would have hidden the owner's headline switch.
- "The composer still needs `/synthesizers`": no. The answers name their model from the catalog App reads once; one fetch
  per app load instead of one per chat mount.
- "Corpus Explore should keep hiding while Deep research is on" (the old `!deep` coupling): not kept. The top bar does not
  know the composer's Deep switch; the deep request never carried the flag and still does not. Listed as a gap.

## Open contract gaps
- Live proof after the owner's deploy: the bar on the owner's desktop and phone (the three controls, the panel, a real
  library name), the Corpus Explore toggle following `/capabilities`, and the width of the real reasoning labels at 375 px
  (a label wider than ~80 px wraps the composer row to 66 px; nothing overflows).
- The Corpus Explore switch stays visible while Deep research is on (it is ignored by the deep request, as before).
- Reasoning and Deep research are not remembered across reloads, by design (the owner named only the three).
- The plan note and the register row are the lead's: this slice made no plan or register edits.
