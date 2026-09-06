---
title: "WORK LOG — SIDEBAR-COLLAPSE-V1: the side panel collapses to a rail"
change_id: SIDEBAR-COLLAPSE-V1
date: 2026-09-06
owner: governance (owner request 2026-09-06: "a button that collapses the side panel for a better ui/ux")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.110
package: frontend/src/components/Sidebar.tsx (rail + toggle), frontend/src/App.tsx (state, persistence, ⌘/Ctrl+B), frontend/src/app.css (rail rules), frontend/dist (rebuilt), scripts/scaffold_polymath_v4.py (asset names)
architecture_impact: "Frontend only. The sidebar gains a collapse toggle in its brand row; collapsed, it renders a 52 px rail — brand dot (click expands), new chat, the five views as inline-SVG icons with labels as tooltips and `role=tab` / `aria-selected`, and the expand toggle at the bottom. State lives in App, persists per viewer (`pm-sidebar-open`), and ⌘B / Ctrl+B toggles it. Under 640 px the collapsed panel becomes one short row (brand, new chat, view icons, toggle) instead of a 30 vh stack. No streaming, retrieval or backend change; the chat list is simply not rendered while collapsed."
---

# WORK LOG — SIDEBAR-COLLAPSE-V1

## Contract

One control collapses and restores the side panel; the collapsed state keeps every action reachable (new chat, the five views) in a rail that costs 52 px; the choice is remembered; the keyboard has a way in.

## Changes

- `Sidebar.tsx`: props `collapsed` / `onToggle`; the expanded layout keeps its markup and gains the toggle in the brand row; the collapsed layout is the rail; icons are inline strokes on `currentColor` (no icon font, no emoji).
- `App.tsx`: `sidebarOpen` state initialised from localStorage, written back on change; a window keydown handler for ⌘/Ctrl+B (no shift / alt), `preventDefault` so the browser's bookmark shortcut does not fire.
- `app.css`: `.sidebar.collapsed` (52 px, centred column), `.sb-toggle` / `.rail-btn` (32 px targets, focus ring, accent-tinted active and new-chat states), width transition with a reduced-motion override, the ≤ 640 px row layout.

## Proof

- `npm run build` clean; dist rebuilt and re-declared; guard ok.
- In-app browser on the final bundle: toggle collapses the panel to the rail (brand dot, new chat, five view icons with the right labels, toggle at the bottom) and the reading column takes the width; the state persists across a reload (`pm-sidebar-open = 0`, panel opens collapsed); ⌘B expands it again; no console errors. At a 375 px viewport the collapsed panel is a single 45 px row (brand dot, new chat, the five view icons, toggle at the right) with no horizontal overflow; expanding restores the stacked panel.

## Rejected claims

- "Hide the panel entirely when collapsed" — rejected: new chat and the view switcher would vanish; the rail keeps them one click away and is the pattern the owner's reference apps use.
- "Put the toggle in the top bar" — rejected: the control belongs to the thing it controls; in the rail it is the bottom item, in the panel it sits beside the brand.

## Open contract gaps

- No swipe gesture on touch; the row layout under 640 px plus the toggle covers it.
- The keyboard shortcut is global; if a text field ever needs ⌘B for bold, scope it then.
