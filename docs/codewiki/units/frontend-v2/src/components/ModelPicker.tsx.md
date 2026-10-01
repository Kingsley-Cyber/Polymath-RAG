# unit: frontend-v2/src/components/ModelPicker.tsx
anchor: frontend-v2/src/components/ModelPicker.tsx:1-193

## purpose
Grouped synthesizer picker for the V2 frontend: instead of a flat `<select>`, it groups the catalog by PROVIDER into collapsible sections, opens the group holding the current selection, and shows a filter box once the catalog is long. Port of the legacy `/ui` grouped picker (owner request 2026-09-12). [DERIVED] frontend-v2/src/components/ModelPicker.tsx:5-14, 44

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ModelPicker` | function component | `({ synthesizers: Synthesizer[], value: string, onChange: (id: string) => void }) -> JSX` | frontend-v2/src/components/ModelPicker.tsx:44-52 | frontend-v2/src/components/_small-modules |

Module-private helpers (not exported): `loadOpen` (21-27), `groupBy` (29-38), `idOf` (40-42). [DERIVED] frontend-v2/src/components/ModelPicker.tsx:21-42

## contracts
`ModelPicker` — frontend-v2/src/components/ModelPicker.tsx:44-52
- in: `synthesizers: Synthesizer[]`, `value: string`, `onChange: (id: string) => void`. [DERIVED] 44-52
- pre: none enforced. A `value` that is neither `""` nor an id in the catalog renders the fallback label `backend default`. [DERIVED] 59, 63, 131-132
- out: `onChange` fires only from `pick(id)` with the clicked id (`""` = backend default); menu closes and filter resets to `""`. [DERIVED] 110-114
- post/side: on every `expanded` change, writes the map to localStorage key `polymath-v2.model-picker.open`. [DERIVED] 83-85
- `value === ""` display rule: shows the row with `s.default === true` — comment says this is "the same rule as `_default_synthesizer`". [DERIVED] 60-63

`groupBy(synths)` — group id = `s.provider || s.kind || "other"`; label = `s.provider_label || (s.kind === "ollama" ? "Ollama" : id)`. Never parses ids. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:29-38

`idOf(s)` — `s.id ?? s.name ?? ""`. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:40-42

`loadOpen()` — `JSON.parse(localStorage.getItem(OPEN_KEY) || "{}")`, catch → `{}`. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:21-27

## effect surface
- localStorage: read `polymath-v2.model-picker.open` (init state) — 21-27, 55; write same key — 83-85. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:21-27, 83-85
- DOM: `document` listeners `mousedown` + `keydown` (Escape) attached while open, removed on cleanup. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:88-102
- Postgres/Qdrant/network/subprocess/env: none — `tables_read: []`, `tables_written: []` (FACTS) and no such calls in source. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:1-193

## invariants
INVARIANT: filter input renders iff `synthesizers.length >= FILTER_AT` where `FILTER_AT = 12` — frontend-v2/src/components/ModelPicker.tsx:17, 139 [DERIVED]
  fails-if: catalog crossing 12 toggles the filter box on/off; below 12 there is no way to search.
INVARIANT: `value === ""` displays the first row with `s.default === true` — frontend-v2/src/components/ModelPicker.tsx:62, 155-156 [DERIVED]
  fails-if: multiple rows carry `default: true` — `find` takes the first, which may disagree with the backend's pick. [INFERRED] (Array#find first-match semantics)
INVARIANT: group key precedence is `provider` → `kind` → `"other"` in both `groupBy` and `currentGroup` — frontend-v2/src/components/ModelPicker.tsx:32, 105 [DERIVED]
  fails-if: the two orderings ever diverge — the current selection's group would not auto-open.
INVARIANT: stored `expanded[gid]` overrides the default; unset groups default open only when `gid === currentGroup` — frontend-v2/src/components/ModelPicker.tsx:106-108 [DERIVED]
  fails-if: stale localStorage leaves the current selection's section collapsed with no visual cue.
INVARIANT: while a filter query `q` is active, matched groups render expanded regardless of `expanded` — frontend-v2/src/components/ModelPicker.tsx:169 [DERIVED]
  fails-if: dropping `|| q` hides all items under collapsed groups during search.
INVARIANT: `pick` always sets `open = false` and `filter = ""` — frontend-v2/src/components/ModelPicker.tsx:110-114 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (initial `expanded` from localStorage — 21-27, 55; document event listeners — 88-102; rest is pure from props) [DERIVED] frontend-v2/src/components/ModelPicker.tsx:21-27, 55, 88-102
idempotency: SAFE — re-running `pick(id)` only re-fires `onChange` and rewrites the same localStorage snapshot of state. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:110-114, 83-85

## failure behaviour
- `loadOpen` swallows any `JSON.parse` / `localStorage.getItem` failure and returns `{}` — user sees default collapse state, no error surfaced. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:22-26
- The write path `localStorage.setItem(OPEN_KEY, ...)` (84) has no try/catch — a throwing setItem is unhandled. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:83-85
- No error codes raised; nothing else is caught. [DERIVED] frontend-v2/src/components/ModelPicker.tsx:1-193

## dumb-code flags
- Magic threshold `FILTER_AT = 12` while the header comment says the catalog is "currently 24" — the two numbers are unrelated but easy to conflate. frontend-v2/src/components/ModelPicker.tsx:17, 9
- Literal `"backend default"` duplicated at 132 and 157. frontend-v2/src/components/ModelPicker.tsx:132, 157
- Expand condition `isExpanded(g.id) || q` duplicated on consecutive lines 167 and 169. frontend-v2/src/components/ModelPicker.tsx:167, 169
- Asymmetric localStorage handling: read guarded by try/catch (22-26), write unguarded (84).
- Default button uses `aria-selected={value === ""}` (152) but lacks `role="option"`, which item buttons set (177). frontend-v2/src/components/ModelPicker.tsx:152, 177
- Hardcoded provider special-case `s.kind === "ollama" ? "Ollama" : id`. frontend-v2/src/components/ModelPicker.tsx:33

## refactor notes
- localStorage key `"polymath-v2.model-picker.open"` is a persisted user-state contract; renaming it silently resets everyone's expand state. frontend-v2/src/components/ModelPicker.tsx:16
- Component reads `Synthesizer` fields `provider`, `provider_label`, `kind`, `model`, `id`, `name`, `label`, `description`, `default` (import from `../lib/contracts`) — contract changes in `frontend-v2/src/lib/contracts.ts` ripple through grouping, display, and filtering. frontend-v2/src/components/ModelPicker.tsx:2, 32-33, 41, 62, 128, 179, 183
- The `value === ""`-means-backend-default protocol plus the `default: true` flag must stay in sync with the backend `_default_synthesizer` rule (comment claims same rule). frontend-v2/src/components/ModelPicker.tsx:60-63
- Renaming the `ModelPicker` export breaks importer `frontend-v2/src/components/_small-modules` (FACTS.importers). frontend-v2/src/components/ModelPicker.tsx:44
- Stylesheet must keep classes `mp`, `mp__button`, `mp__provider`, `mp__model`, `mp__menu`, `mp__filter`, `mp__item`, `mp__group`, `faint`. frontend-v2/src/components/ModelPicker.tsx:117-183

## VERIFY
```verify
grep -Fq 'polymath-v2.model-picker.open' frontend-v2/src/components/ModelPicker.tsx
grep -Fq 'const FILTER_AT = 12;' frontend-v2/src/components/ModelPicker.tsx
grep -Eq 'provider \|\| s\.kind \|\| "other"' frontend-v2/src/components/ModelPicker.tsx
grep -Fq 'aria-haspopup="listbox"' frontend-v2/src/components/ModelPicker.tsx
test "$(grep -c -F 'mp__' frontend-v2/src/components/ModelPicker.tsx)" -ge 8
! grep -Fq 'fetch(' frontend-v2/src/components/ModelPicker.tsx
```
