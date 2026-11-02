# unit: frontend-v2/src/ui/_small-modules
anchor: frontend-v2/src/ui/CopyButton.tsx:1-29

## purpose
Shared UI kit for frontend-v2: clipboard copy controls (CopyButton, CopyField, Secret), a native `<dialog>` modal system with typed-name and promise-based confirm (Dialog, ConfirmByName, useConfirm), a password field with show/hide (PasswordInput), an inline 39-icon set copied from Lucide (icons), and the three data-view states loading/empty/error (states). Only external importer is `frontend-v2/src/App.tsx` (FACTS.importers). Replaces `window.prompt / confirm / alert` (frontend-v2/src/ui/Dialog.tsx:3-4) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CopyButton | function | ({ text: string; label: string; className?: string }) -> ReactElement | frontend-v2/src/ui/CopyButton.tsx:9 | App.tsx * |
| CopyField | function | ({ value: string; what: string; block?: boolean; primary?: boolean }) -> ReactElement | frontend-v2/src/ui/CopyField.tsx:8 | App.tsx * |
| Dialog | function | ({ open: boolean; title: string; onClose; children; actions }) -> ReactElement \| null | frontend-v2/src/ui/Dialog.tsx:5 | ConfirmByName, useConfirm (internal, frontend-v2/src/ui/Dialog.tsx:32,70) |
| ConfirmByName | function | ({ open, title, name, what, action, onConfirm: () => Promise<void> \| void, onClose }) -> ReactElement | frontend-v2/src/ui/Dialog.tsx:27 | App.tsx * |
| ConfirmOptions | interface | { title: string; body: ReactNode; action: string; danger?: boolean } | frontend-v2/src/ui/Dialog.tsx:61 | useConfirm param (frontend-v2/src/ui/Dialog.tsx:65) |
| useConfirm | hook | () -> [(o: ConfirmOptions) => Promise<boolean>, ReactNode] | frontend-v2/src/ui/Dialog.tsx:65 | App.tsx * |
| PasswordInput | function | ({ id?, value, onChange, autoComplete: "current-password" \| "new-password", placeholder?, autoFocus? }) -> ReactElement | frontend-v2/src/ui/PasswordInput.tsx:5 | App.tsx * |
| Secret | function | ({ value: string; what: string; block?: boolean; rows?: number }) -> ReactElement | frontend-v2/src/ui/Secret.tsx:8 | App.tsx * |
| IconName | type | keyof typeof PATHS (39 names, frontend-v2/src/ui/icons.tsx:15-53) | frontend-v2/src/ui/icons.tsx:56 | Icon, IconButton params |
| Icon | function | ({ name: IconName; size?: number } & SVGProps<SVGSVGElement>) -> ReactElement | frontend-v2/src/ui/icons.tsx:59 | CopyButton.tsx:3, CopyField.tsx:3, PasswordInput.tsx:3, Secret.tsx:3, states.tsx:2 |
| IconButton | function | ({ icon: IconName; label: string } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" \| "title" \| "children">) -> ReactElement | frontend-v2/src/ui/icons.tsx:69 | — (no internal user visible) |
| Skeleton | function | ({ rows?: number; label?: string }) -> ReactElement | frontend-v2/src/ui/states.tsx:7 | App.tsx * |
| EmptyState | function | ({ title: string; children?: ReactNode; action?: ReactNode }) -> ReactElement | frontend-v2/src/ui/states.tsx:16 | App.tsx * |
| ErrorState | function | ({ message: string; onRetry?: () => void }) -> ReactElement | frontend-v2/src/ui/states.tsx:26 | App.tsx * |

\* FACTS.importers lists only `frontend-v2/src/App.tsx` for this unit; per-symbol imports inside App.tsx are not in the material.

## contracts

**CopyButton** — frontend-v2/src/ui/CopyButton.tsx:9-28
- in: `text: string; label: string; className = ""` (:9)
- out: `<button type="button">` with classes `icon-btn icon-btn--sm copy-btn copy-btn--hover` plus `copy-btn--done` when copied (:15)
- pre: none; copy failure is tolerated silently (:19 `if (!ok) return;`)
- post: on `copyText(text)` ok, aria-label/title = `"Copied"` and icon `"check"` for `2000` ms (:20-22, :25); prior timer cleared before re-arm (:21) and on unmount (:12)

**CopyField** — frontend-v2/src/ui/CopyField.tsx:8-50
- in: `value: string; what: string; block = false; primary = false` (:8-13)
- out: `block` → `<pre className="copyfield__text" tabIndex={0}>` with button above (:34-41); else `<code>` + button after (:43-48)
- pre: button `disabled={!value}` (:28)
- post: ok → `"Copied"` + check icon for `2000` ms (:20-21); `!ok` → `failed=true` → `role="alert"` message `"The browser blocked copying: select the text and press ⌘C."` (:18, :33)

**Dialog** — frontend-v2/src/ui/Dialog.tsx:5-24
- in: `open: boolean; title: string; onClose: () => void; children; actions` (:5-6)
- out: `null` when `!open` (:16); else native `<dialog>` with `aria-labelledby={titleId}` from `useId()` (:9, :17-22)
- post: open transition calls `d.showModal()`, falling back to `d.setAttribute("open", "")` (:13); Esc → `e.preventDefault()` + `onClose()` (:18)

**ConfirmByName** — frontend-v2/src/ui/Dialog.tsx:27-59
- in: `open, title, name, what, action: string, onConfirm: () => Promise<void> | void, onClose` (:28-30)
- pre: gate is exact equality `typed === name` (:36), no trim/case-fold
- out: danger button `disabled={!match || busy}` (:45), busy label hard-coded `"Deleting…"` (:46)
- post: `open` flip to true resets `typed`/`error`/`busy` (:35); confirm → `await onConfirm(); onClose();` — throw → error in `banner banner--bad`, dialog stays open, `busy` reset in `finally` (:39-41); Enter key submits (:54)

**useConfirm** — frontend-v2/src/ui/Dialog.tsx:65-80
- in: none; out: `[confirm, element]` where `confirm(o)` returns `Promise<boolean>` (:67, :79)
- pre: caller must render `element` — it holds the `resolve` closures (:69-77) [INFERRED: unrendered element = promise never settles]
- post: `resolve(true)` only from the action button (:72); Cancel and Esc → `resolve(false)` (:70-71); doc comment also claims the backdrop answers false (:63-64) but no backdrop handler is visible in Dialog

**PasswordInput** — frontend-v2/src/ui/PasswordInput.tsx:5-23
- in: `autoComplete` restricted to `"current-password" | "new-password"` (:9)
- out: input `type={show ? "text" : "password"}` (:16) + eye button with `aria-pressed={show}` and labels `"Show password"` / `"Hide password"` (:19-21)

**Secret** — frontend-v2/src/ui/Secret.tsx:8-21
- in: `value: string; what: string; block = false; rows = 10` (:8)
- out: `block` → readOnly `<textarea rows={rows}>` (:14); else `<code className="mono settings__secret">` (:15); copy button `icon-btn icon-btn--sm` (:16)
- post: ok → `"Copied"` for `2000` ms; failure silently ignored (`if (ok)`) (:10)

**Icon / IconButton** — frontend-v2/src/ui/icons.tsx:59-76
- Icon: `size = 16`; svg `viewBox="0 0 24 24"`, `strokeWidth={2}`, `aria-hidden="true"`, `focusable="false"`, class `"icon"` (:59-63)
- IconButton: `label` required, becomes both `aria-label` and `title`; consumer props omit `"aria-label" | "title" | "children"` (:69-73)

**states** — frontend-v2/src/ui/states.tsx:7-34
- Skeleton: `rows = 4`, `label = "Loading…"`; `role="status" aria-live="polite"` + `sr-only` label; row widths `` `${92 - (i % 3) * 14}%` `` (:7-11)
- EmptyState: title always; `children`/`action` rendered only when provided (:17-21)
- ErrorState: `role="alert"`, fixed title `"Couldn't load this"` + `alert` icon; Retry button only when `onRetry` given (:27-31)

## effect surface
- Clipboard: `copyText` imported from `../lib/auth` and called with the display value — frontend-v2/src/ui/CopyButton.tsx:2,18; frontend-v2/src/ui/CopyField.tsx:2,17; frontend-v2/src/ui/Secret.tsx:2,10. Mechanism inside `copyText` is not in this material.
- Timers: `window.setTimeout`/`window.clearTimeout` — frontend-v2/src/ui/CopyButton.tsx:12,21-22; bare `setTimeout` — frontend-v2/src/ui/CopyField.tsx:21; frontend-v2/src/ui/Secret.tsx:10.
- DOM API: `HTMLDialogElement.showModal` — frontend-v2/src/ui/Dialog.tsx:13.
- Postgres tables: none read/written (FACTS `tables_read`/`tables_written` empty). Env flags/constants: none (FACTS `constants` empty).

## invariants
INVARIANT: copied-feedback duration = `2000` ms in CopyButton, CopyField and Secret — frontend-v2/src/ui/CopyButton.tsx:22, frontend-v2/src/ui/CopyField.tsx:21, frontend-v2/src/ui/Secret.tsx:10 [DERIVED]
  fails-if: "Copied" persists for different lengths per component; the three drift.
INVARIANT: ConfirmByName fires `onConfirm` only when `typed === name` AND not busy — both the guard (:38) and the button `disabled={!match || busy}` (:45) enforce it — frontend-v2/src/ui/Dialog.tsx:36-45 [DERIVED]
  fails-if: destructive action runs without the exact token the backend also requires (comment :26).
INVARIANT: `useConfirm` resolves each promise exactly once — `answer()` resolves `pending` then `setPending(null)` — frontend-v2/src/ui/Dialog.tsx:67-68 [DERIVED]
  fails-if: double-resolve or a permanently pending `await confirm(...)` in the caller.
INVARIANT: closed Dialog renders `null` — frontend-v2/src/ui/Dialog.tsx:16 [DERIVED]
  fails-if: stray dialog text or stale input state leaks into the page.
INVARIANT: Skeleton row widths cycle over 3 rows: `92 - (i % 3) * 14` → {92, 78, 64}% — frontend-v2/src/ui/states.tsx:11 [DERIVED]
  fails-if: skeleton rows all identical width or exceed container.
INVARIANT: every Icon renders at `viewBox="0 0 24 24"` with `strokeWidth={2}` and `aria-hidden="true"` — all 39 PATHS entries — frontend-v2/src/ui/icons.tsx:15-53,61-62 [DERIVED]
  fails-if: icons mis-scale; icon becomes screen-reader noise because the control, not the glyph, must carry the name (IconButton Omit at :70).

## determinism & idempotency
determinism: DETERMINISTIC for markup given props; state transitions NONDETERMINISTIC (clipboard result of `copyText` — frontend-v2/src/ui/CopyButton.tsx:18, frontend-v2/src/ui/CopyField.tsx:17, frontend-v2/src/ui/Secret.tsx:10; `2000` ms timers — same anchors; user input resolving ConfirmByName/useConfirm — frontend-v2/src/ui/Dialog.tsx:36,70-72).
idempotency: SAFE — repeat copy clicks re-run the same feedback, no server/db writes in this unit; ConfirmByName delegates to the caller's `onConfirm` (frontend-v2/src/ui/Dialog.tsx:29), whose idempotency is caller-defined.

## failure behaviour
- Clipboard failure: CopyButton swallows it (`if (!ok) return;` — frontend-v2/src/ui/CopyButton.tsx:19, button keeps its label); CopyField surfaces `role="alert"` with the ⌘C hint (frontend-v2/src/ui/CopyField.tsx:33); Secret swallows it (`if (ok)` — frontend-v2/src/ui/Secret.tsx:10).
- ConfirmByName: `try/catch/finally` around `onConfirm` — error string shown in `banner banner--bad`, dialog stays open, `busy` cleared (frontend-v2/src/ui/Dialog.tsx:40).
- Dialog: no `showModal` → `d.setAttribute("open", "")` fallback, which is non-modal (no focus trap/inert background from that branch) — frontend-v2/src/ui/Dialog.tsx:13 [INFERRED: the native-modal guarantees named at :3 come only from the `showModal` path].
- ErrorState: renders message + Retry only when `onRetry` provided (frontend-v2/src/ui/states.tsx:31); no swallowing, purely display.

## dumb-code flags
- Magic number `2000` duplicated in three files — frontend-v2/src/ui/CopyButton.tsx:22, frontend-v2/src/ui/CopyField.tsx:21, frontend-v2/src/ui/Secret.tsx:10.
- Timer hygiene diverges: CopyButton clears on unmount and before re-arm (frontend-v2/src/ui/CopyButton.tsx:12,21); CopyField and Secret call bare `setTimeout` with no cleanup (frontend-v2/src/ui/CopyField.tsx:21, frontend-v2/src/ui/Secret.tsx:10) — same feature, unequal safety.
- Hard-coded busy label `"Deleting…"` although `action` is a parameter — frontend-v2/src/ui/Dialog.tsx:46.
- CopyField inline variant: visible span says `"Copy"` but aria-label says `` `Copy ${what}` `` — accessible name and visible text disagree (frontend-v2/src/ui/CopyField.tsx:25,30).
- `useConfirm` doc claims "the backdrop answer[s] false" (frontend-v2/src/ui/Dialog.tsx:63-64) but Dialog only handles `onCancel`; no backdrop-click handler is visible (frontend-v2/src/ui/Dialog.tsx:18) [INFERRED: doc overstates the code].
- Duplicated icon swap `copied ? "check" : "copy"` in three components — frontend-v2/src/ui/CopyButton.tsx:25, frontend-v2/src/ui/CopyField.tsx:29, frontend-v2/src/ui/Secret.tsx:17.
- Skeleton width magic numbers `92` and `14` — frontend-v2/src/ui/states.tsx:11.

## refactor notes
- `IconName = keyof typeof PATHS` (frontend-v2/src/ui/icons.tsx:56): renaming/removing any of the 39 PATHS keys breaks every `Icon`/`IconButton` call site; additions are safe.
- The `2000` ms copied-UX + icon swap exists in three copies; extracting it touches CopyButton, CopyField, Secret and their CSS hooks `copy-btn--done`, `copyfield__btn`, `secret__copy` (frontend-v2/src/ui/CopyButton.tsx:15, frontend-v2/src/ui/CopyField.tsx:27, frontend-v2/src/ui/Secret.tsx:16).
- Class-name strings are the styling contract (`btn--danger-solid`, `btn--primary`, `dialog__*`, `state*`, `skeleton*`, `pw*`, `sr-only`, …) — stylesheet is outside this unit (e.g. frontend-v2/src/ui/Dialog.tsx:45,72; frontend-v2/src/ui/states.tsx:9).
- CopyButton hover behavior lives in CSS via `copy-btn--hover`, not in this code (frontend-v2/src/ui/CopyButton.tsx:7,15).
- `useConfirm` callers must render the returned element or every `await confirm(...)` hangs (frontend-v2/src/ui/Dialog.tsx:69-78) [INFERRED].
- ConfirmByName's typed-token check is paired with a backend expecting the same token (frontend-v2/src/ui/Dialog.tsx:26) — loosening the equality breaks that pairing.
- Only external importer is `frontend-v2/src/App.tsx` (FACTS.importers); any signature change radiates there.

## VERIFY
```verify
grep -Fq 'window.setTimeout(() => setCopied(false), 2000)' frontend-v2/src/ui/CopyButton.tsx
grep -Fq 'The browser blocked copying: select the text and press ⌘C.' frontend-v2/src/ui/CopyField.tsx
grep -Fq 'typed === name' frontend-v2/src/ui/Dialog.tsx
! grep -Fq 'window.confirm' frontend-v2/src/ui/Dialog.tsx
grep -Fq 'd.setAttribute("open", "")' frontend-v2/src/ui/Dialog.tsx
grep -Fq 'viewBox="0 0 24 24"' frontend-v2/src/ui/icons.tsx
grep -Fq '92 - (i % 3) * 14' frontend-v2/src/ui/states.tsx
test "$(grep -c -F 'copyText' frontend-v2/src/ui/Secret.tsx)" -ge 2
```
