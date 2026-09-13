---
title: "WORK LOG — Frontend V2 parity with the legacy /ui on the five things the owner named: themes, grouped model selection, sidebar collapse, bottom-docked chat composer, ChatGPT-style thread"
change_id: FRONTEND-V2-PARITY-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.227
architecture_impact: "frontend-only, additive. Two new files (styles/themes.css, components/ModelPicker.tsx), three edited (App.tsx, screens/Chat.tsx, styles/app.css) plus the Synthesizer type widened to declare fields the backend ALREADY returns. No backend contract, endpoint, payload or retrieval behaviour touched; no new API call added. The V2 default look is unchanged for anyone who never picks a theme."
---

> Direct owner request, mid-session 2026-09-12: "the ui is good however it missing some
> things https://rag.kingsleylab.xyz/ui/ that this url has. like themes, style of model
> selections, side panel collapse. chat on the bottom. and chatgpt style."
>
> Useful side effect: the legacy `/ui` is behind the same Caddy basic-auth wall that has
> blocked the authenticated public-URL spot-check all session — but BOTH frontends are
> served by the same orchestrator on :7200, so comparing them locally needed no
> credential at all.

## Contract

Requested outcome: V2 gains the five things the owner named, without regressing the V2
contracts that already hold (truthful mode/engine badges, readiness triad, evidence
inspector).

- **Smallest acceptance:** each of the five works in a real browser against the live
  orchestrator; `npm run build` (tsc + vite) clean; no console errors; a real grounded
  chat turn still renders with its citations and badges.
- **Owner / public contract:** none changed — this is presentation only.
- **Verifier / rollback:** `npm run build` + `npm test`; every change is confined to
  `frontend-v2/src`, so rollback is a revert of this commit and a rebuild.

## Changes

- `frontend-v2/src/styles/themes.css` — NEW. The nine legacy palettes (obsidian, nord,
  solar, rose, espresso, graphite, slate, paper, champagne) ported onto **V2's own**
  token names (`--bg`/`--bg-raised`/`--bg-sunken`/`--line`/`--line-soft`/`--fg`/
  `--fg-dim`/`--fg-faint`/`--accent`/`--accent-dim` + the status hues), not legacy's
  (`--bg-2`/`--text`/`--border`/…). Selected by `data-theme` on `<html>`. The untagged
  default remains V2's original dark instrument palette, so a session that never picks a
  theme looks exactly as before.
  The four status *background* tints are derived ONCE at the bottom with
  `color-mix(in srgb, var(--ok) 15%, var(--bg))` rather than hand-picked per theme —
  which is what makes the light themes work: a light theme automatically gets a light
  tint against its own `--bg` instead of the dark-theme tint leaking through. (Verified
  live: under `champagne`, `--ok-bg` resolves to `color-mix(in srgb, #5f8f56 15%,
  #f6f0e6)`.)
- `frontend-v2/src/components/ModelPicker.tsx` — NEW. The legacy grouped picker, ported.
  Groups by PROVIDER from the catalog's own `provider`/`provider_label`/`model` fields —
  never by parsing ids — collapses each section, auto-opens the one holding the current
  selection, shows a filter box past 12 entries, persists open/closed per provider in
  localStorage, closes on outside-click/Escape. Replaces a flat `<select>` that listed 24
  raw ids like `litellm:anthropic/deepseek-v4-flash-0731`.
- `frontend-v2/src/lib/contracts.ts` — `Synthesizer` widened from
  `{id?, name?, label?, offered?}` to also declare `description`/`kind`/`available`/
  `default`/`provider`/`provider_label`/`model`. These are fields the backend **already
  returns** — confirmed against the live endpoint before adding them, not assumed — V2's
  type simply never declared them.
- `frontend-v2/src/App.tsx` — theme state (localStorage `polymath-v2.theme`, applied as
  `document.documentElement.dataset.theme`, cleared for the default), collapse state
  (`polymath-v2.nav-collapsed`), a `«`/`»` toggle in a new `.nav__top`, a swatch row, and
  a `glyph` per NAV entry for the collapsed rail. Both `localStorage` calls are
  try/caught (private-mode browsers throw on write).
- `frontend-v2/src/screens/Chat.tsx` — the ChatGPT-style restructure: composer **docked
  at the bottom** (`.chat__composer`, `margin-top:auto`), thread scrolls above it in
  **chronological** order (the old code rendered `turns.slice().reverse()`, newest-first,
  which is the opposite of a chat), the question renders as a right-aligned user bubble
  instead of a card heading, a centered welcome state replaces "No turns yet.", the input
  is a `<textarea>` (Enter sends, Shift+Enter newlines) instead of a single-line
  `<input>`, and a `useEffect` follows the thread to the bottom as it streams.
- `frontend-v2/src/styles/app.css` — styles for the above: collapse rail, swatches,
  picker menu, composer/thread/bubble, and a `.screen--chat` modifier that makes the chat
  screen a full-height flex column (`flex:1; min-height:0; overflow:hidden`) so the
  composer can dock rather than scroll away with the content.
- `orchestrator/orchestrator/main.py` — corrected a stale docstring on
  `_SPAStaticFilesV2` that claimed "React Router (BrowserRouter) serves /v2/chat,
  /v2/files…". It does not: `App.tsx` holds the screen in plain `useState<ScreenId>`,
  with no router. The class's real contract is "a deep path never 404s and the app boots
  at its default screen", NOT "the URL selects the screen" — now stated, with the live
  verification noted.

## Proof

All against the live orchestrator at `127.0.0.1:7200/v2/`, in a real browser:

- **Build**: `npm run build` (tsc --noEmit && vite build) clean; `npm test` 1/1 pass;
  `tests/determinism/test_v2_spa_fallback.py` 5/5 still pass after the docstring fix.
- **Themes**: clicking Champagne switched `body` background `rgb(13,16,20)` →
  `rgb(246,240,230)`, set `data-theme="champagne"`, persisted to localStorage, and the
  derived `--ok-bg` recomputed against the new light `--bg`. Screenshot confirms every
  surface (cards, borders, text, pills) adapted — no dark-theme remnants.
- **Collapse**: nav width 208px → 52px, `.nav__item span` computed `display:none`,
  `shell--collapsed` applied, state persisted (`"1"`).
- **Model picker**: opens to 3 collapsed provider groups — "Alibaba Model Studio (9)",
  "OpenCode (free) (8)", "Ollama cloud (free) (6)" — with a filter box; expanding Ollama
  lists bare model names (`gemma4:31b-cloud`, `gpt-oss:120b-cloud`, …) instead of raw
  ids; Escape closes it.
- **Bottom composer + ChatGPT thread**: composer's bottom edge == viewport height
  (620 == 620) on an empty thread AND after an answer rendered; welcome state shows
  "Grounded answers, exact evidence."; input is a `TEXTAREA`.
- **A real turn still works end-to-end**: asked "what is ZQX-58003" through the new UI —
  user bubble rendered, grounded answer returned ("**ZQX-58003** is the core calibration
  procedure … [S1][S5]", 682 chars), badges `HYBRID · ⌖ EXACT · chat-retrieval-v2`
  preserved, thread auto-scrolled to the bottom.
- **Console**: zero errors across the whole session (theme switch, collapse, picker,
  streamed turn).
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Fence: frontend-only; nothing under `shared/polymath_shared`, `workers/workers` or
  `control/control` touched, so no fleet bounce. The orchestrator serves
  `frontend-v2/dist` directly (`main.py:161`), so `npm run build` alone publishes it.

## Rejected claims

- **"Port the legacy CSS wholesale so V2 looks like /ui."** REJECTED — the owner asked
  for five specific capabilities, not a visual rewrite. V2's own design system stays; the
  themes are mapped onto V2's tokens so its layout, density and component styling are
  untouched.
- **"Hand-pick the status background tints for each of the nine themes."** REJECTED —
  36 hand-maintained values that silently drift. `color-mix` against each theme's own
  `--bg` is one rule that is correct for dark and light themes by construction.
- **"Derive the model groups by parsing the `litellm:anthropic/...` id prefix."**
  REJECTED — the catalog already carries `provider`/`provider_label`, and the legacy
  picker's own docstring warns against parsing ids. Confirmed the live endpoint returns
  them before relying on it.
- **"A deep link like /v2/files should open the Files screen."** REJECTED as out of
  scope and currently untrue by design: the app has no router (see the `main.py`
  docstring correction). Adding routing is a real change with its own contract; it was
  not one of the five things asked for. Named here so the gap is recorded rather than
  silently implied to work.

## Open contract gaps

- **No chat history / "New chat" list.** The legacy `/ui` has a persisted chat list in
  its sidebar; V2 keeps turns in component state only, so switching screens loses the
  thread. Not requested explicitly, and it needs a storage decision (localStorage vs a
  backend contract), so it is recorded rather than guessed at.
- **No URL routing**, per the rejected claim above — screen selection is state, so a
  refresh returns to Overview and screens are not linkable.
- The theme set is the legacy nine plus V2's own default; no light/dark *auto* mode that
  follows the OS `prefers-color-scheme`.
