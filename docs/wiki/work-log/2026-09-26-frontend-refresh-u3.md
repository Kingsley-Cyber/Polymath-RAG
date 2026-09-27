---
change_id: FRONTEND-REFRESH-U3
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Outline icons without a package, IconButton with a required label, loading / empty / error states; the icon rail stays labelled."
architecture_impact: "frontend-v2 only: src/ui/icons.tsx (new), src/ui/states.tsx (new), src/App.tsx, src/screens/Login.tsx, src/styles/app.css, src/components/PhaseStub.tsx (removed, unused), tests."
last_reviewed: 2026-09-26
---

# FRONTEND-REFRESH U3: shared pieces and icons

## Contract
- FRONTEND-REFRESH-V1 §5 / slice U3 (plan of record 11.504); problems P13 (inconsistent blocks) and P14 (unnamed rail buttons).

## Changes
- **`ui/icons.tsx`.** 30 outline icons copied from Lucide, with its ISC notice in the file; no icon package. `Icon` is
  `aria-hidden`. `IconButton` requires `label`, which becomes its accessible name and its tooltip.
- **Icons used in:** the sidebar items (the icon rail now shows real icons, each button named by its label), New chat,
  collapse / expand / close, the top bar's menu and light/dark buttons, and the chat-delete buttons. The sign-in card gets a mark.
- **`ui/states.tsx`.**
  - `Skeleton`: `role="status"`, with a spoken label.
  - `EmptyState`.
  - `ErrorState`: `role="alert"`, with Retry.
  U5 uses them in Files.
- **Buttons, fields and tables stay plain CSS classes** (`btn`, `btn--primary`, `btn--danger`, `field`, `table.t`). A wrapper
  component would add weight without removing any inconsistency.
- **Removed:** `components/PhaseStub.tsx` (unused).

## Proof
- `ui-pieces.test.tsx`, 5 tests:
  - an icon button's name and tooltip, and its hidden icon;
  - the svg attributes;
  - every item of the collapsed rail keeps its name;
  - loading, empty and error states differ, and are announced;
  - a closed dialog is absent, Esc asks to close it, and the title labels it.
- `chat-session.test.tsx` now finds the New chat button by its new text ("New chat"; the glyph became an icon). The test is otherwise unchanged.
- Totals: vitest 67 passed; `tsc --noEmit` clean. Seen on the dev server: sidebar and top-bar icons, light mode.

## Rejected claims
- None.

## Open contract gaps
- U4 (Chat), U5 (Files states and columns, Graph, Compare, Overview wording), U6 (owner screens, polish, remove the legacy aliases).
