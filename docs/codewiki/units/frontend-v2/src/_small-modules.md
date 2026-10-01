# unit: frontend-v2/src/_small-modules
anchor: frontend-v2/src/main.tsx:1-12

## purpose
React DOM entry point for `frontend-v2`. Runs `initAppearance()` at module load, then mounts `<App />` wrapped in `<StrictMode>` into the DOM element with id `"root"` via `createRoot`. Invoked by the bundler/HTML shell, not by other modules. [DERIVED]

## public surface
No exported symbols — this module is an entry point consumed only for its top-level side effects; FACTS list no importers. — frontend-v2/src/main.tsx:6-12 [DERIVED]

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| — (no exports) | module | side effects only | frontend-v2/src/main.tsx:6-12 | — |

## contracts
Mount (implicit entry side effect)
- in: nothing (no arguments; module evaluation) — frontend-v2/src/main.tsx:6-11 [DERIVED]
- out: React tree `<StrictMode>` → `<App />` rendered into the `"root"` DOM node — frontend-v2/src/main.tsx:8-11 [DERIVED]
- pre: a DOM element with id `"root"` exists at evaluation time; enforced only by the `!` non-null assertion (compile-time), no runtime check — frontend-v2/src/main.tsx (line out of range) → actual line 8 [DERIVED]
- post: `initAppearance()` has run exactly once before the first render call — frontend-v2/src/main.tsx:6 before frontend-v2/src/main.tsx:8 [DERIVED]

Note: `initAppearance` and `App` are black boxes here; only their import paths are known — frontend-v2/src/main.tsx:3-4 [DERIVED]

## effect surface
- DOM read: `document.getElementById("root")` — frontend-v2/src/main.tsx:8 [DERIVED]
- DOM write: React render into that node — frontend-v2/src/main.tsx:8-11 [DERIVED]
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty) — frontend-v2/src/main.tsx:1-12 [DERIVED]
- Qdrant / files / network / subprocess / env flags: none visible in SOURCE — frontend-v2/src/main.tsx:1-12 [DERIVED]

## invariants
INVARIANT: `initAppearance();` (line 6) executes before `createRoot(...).render(...)` (line 8) — frontend-v2/src/main.tsx:6 < frontend-v2/src/main.tsx:8 [DERIVED]
  fails-if: appearance setup runs after first paint (visual flash) or never runs.
INVARIANT: `createRoot` call count == 1 — frontend-v2/src/main.tsx:8 [DERIVED]
  fails-if: a second root on the same container → React duplicate-mount error.
INVARIANT: DOM lookup id === `"root"` — frontend-v2/src/main.tsx:8 [DERIVED]
  fails-if: id mismatch with the HTML shell → `createRoot(null)` TypeError.

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env reads in this file; only dependency is DOM state — frontend-v2/src/main.tsx:1-12) — `initAppearance` internals are outside this unit and unverified here. [DERIVED]
idempotency: UNSAFE (module-scope side effects `initAppearance()` and `createRoot(...).render(...)` are unguarded; re-execution would re-run appearance init and create a second root on the same node) — frontend-v2/src/main.tsx:6,8 [INFERRED]

## failure behaviour
No try/catch anywhere; nothing is swallowed — frontend-v2/src/main.tsx:1-12 [DERIVED]
- `initAppearance()` throwing aborts module evaluation; `<App />` never mounts — frontend-v2/src/main.tsx:6 [INFERRED: call is unguarded and precedes render]
- Missing `#root` element: `!` hides it from the type checker only; runtime gets `createRoot(null)` → TypeError — frontend-v2/src/main.tsx:8 [INFERRED: assertion semantics]

## dumb-code flags
- Non-null assertion `!` on `document.getElementById("root")` converts a missing-root HTML bug into an opaque runtime TypeError instead of an explicit check — frontend-v2/src/main.tsx:8 [DERIVED]
- No magic numbers, duplicated literals, or dead branches visible — frontend-v2/src/main.tsx:1-12 [DERIVED]

## refactor notes
- Import specifiers `"./App"` and `"./lib/appearance"`: renaming/moving those files breaks this entry point — frontend-v2/src/main.tsx:3-4 [DERIVED]
- Moving `initAppearance()` after the render call changes startup ordering (appearance applied post-mount) — frontend-v2/src/main.tsx:6,8 [DERIVED]
- DOM id `"root"` is a cross-file contract with the HTML shell (not in this material) — frontend-v2/src/main.tsx:8 [INFERRED]

## VERIFY
```verify
grep -Fq 'initAppearance();' frontend-v2/src/main.tsx
grep -Fq 'createRoot(document.getElementById("root")!).render(' frontend-v2/src/main.tsx
grep -Fq '<StrictMode>' frontend-v2/src/main.tsx
grep -Fq 'import { App } from "./App";' frontend-v2/src/main.tsx
grep -Eq 'import \{ initAppearance \} from "\./lib/appearance";' frontend-v2/src/main.tsx
test "$(grep -c -F 'StrictMode' frontend-v2/src/main.tsx)" -ge 3
```
