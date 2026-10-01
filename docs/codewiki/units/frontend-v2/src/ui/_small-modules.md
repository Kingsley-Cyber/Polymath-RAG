# unit: frontend-v2/src/ui/_small-modules
anchor: frontend-v2/src/ui/CopyField.tsx:1-51

## purpose
Presentational widget kit for the single-profile frontend-v2 app: copy-to-clipboard fields (CopyField, Secret), native-`<dialog>` modals and confirm flows (Dialog, ConfirmByName, useConfirm), a password field with show/hide (PasswordInput), an inline Lucide-derived SVG icon set (icons.tsx), and the loading/empty/error states every data view needs (states.tsx) — CopyField.tsx:4-7, Dialog.tsx:3-4, states.tsx:4-5 [DERIVED]. The unit exists so "still loading", "nothing here" and "failed" never look alike (states.tsx:4-5) and so `window.prompt/confirm/alert` are replaced (Dialog.tsx:3-4) [DERIVED]. Sole importer: `frontend-v2/src/App.tsx` — FACTS.importers [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CopyField | function | ({ value: string, what: string, block?: boolean = false, primary?: boolean = false }) -> JSX | frontend-v2/src/ui/CopyField.tsx:8 | App.tsx (unit-level) |
| Dialog | function | ({ open: boolean, title: string, onClose: () => void, children: ReactNode, actions: ReactNode }) -> JSX | frontend-v2/src/ui/Dialog.tsx:5 | App.tsx (unit-level) |
| ConfirmByName | function | ({ open, title, name: string, what: ReactNode, action: string, onConfirm: () => Promise<void> \| void, onClose }) -> JSX | frontend-v2/src/ui/Dialog.tsx:27 | App.tsx (unit-level) |
| ConfirmOptions | interface | { title: string; body: ReactNode; action: string; danger?: boolean } | frontend-v2/src/ui/Dialog.tsx:61 | App.tsx (unit-level) |
| useConfirm | hook | () -> [(o: ConfirmOptions) => Promise<boolean>, ReactNode] | frontend-v2/src/ui/Dialog.tsx:65 | App.tsx (unit-level) |
| PasswordInput | function | ({ id?, value, onChange, autoComplete: "current-password" \| "new-password", placeholder?, autoFocus? }) -> JSX | frontend-v2/src/ui/PasswordInput.tsx:5 | App.tsx (unit-level) |
| Secret | function | ({ value: string, what: string, block?: boolean = false, rows?: number = 10 }) -> JSX | frontend-v2/src/ui/Secret.tsx:8 | App.tsx (unit-level) |
| IconName | type | keyof typeof PATHS (38 keys) | frontend-v2/src/ui/icons.tsx:55 | App.tsx (unit-level) |
| Icon | function | ({ name: IconName, size?: number = 16 } & SVGProps\<SVGSVGElement\>) -> JSX | frontend-v2/src/ui/icons.tsx:58 | App.tsx; CopyField.tsx:3, PasswordInput.tsx:2, Secret.tsx:3, states.tsx:2 |
| IconButton | function | ({ icon: IconName, label: string } & Omit\<ButtonHTMLAttributes, "aria-label"\|"title"\|"children"\>) -> JSX | frontend-v2/src/ui/icons.tsx:68 | App.tsx (unit-level) |
| Skeleton | function | ({ rows?: number = 4, label?: string = "Loading…" }) -> JSX | frontend-v2/src/ui/states.tsx:7 | App.tsx (unit-level) |
| EmptyState | function | ({ title: string, children?: ReactNode, action?: ReactNode }) -> JSX | frontend-v2/src/ui/states.tsx:16 | App.tsx (unit-level) |
| ErrorState | function | ({ message: string, onRetry?: () => void }) -> JSX | frontend-v2/src/ui/states.tsx:26 | App.tsx (unit-level) |

FACTS.importers is unit-level; per-symbol attribution is not proven. Dialog.tsx imports only React (Dialog.tsx:1) — no intra-unit dependency [DERIVED].

## contracts

**Dialog** — Dialog.tsx:5-23
- in: `open`, `title`, `onClose`, `children`, `actions` — Dialog.tsx:5-6 [DERIVED]
- post: when `open && !d.open`, calls `showModal()`; if `showModal` is not a function, falls back to `setAttribute("open", "")` — Dialog.tsx:12-13 [DERIVED]
- post: `!open` renders `null` — closed dialog is not in the page — Dialog.tsx:16 [DERIVED]
- Esc: `onCancel` is `preventDefault()`ed then routed to `onClose()` — Dialog.tsx:18 [DERIVED]

**ConfirmByName** — Dialog.tsx:27-58
- pre: confirm button `disabled={!match || busy}` where `match = typed === name` — Dialog.tsx:36,45 [DERIVED]
- pre: `name` is a token the backend also requires — Dialog.tsx:26 [DERIVED]
- post: `open` turning true resets `typed`/`error`/`busy` — Dialog.tsx:35 [DERIVED]
- post: `onConfirm()` throw → `e.message` in `banner banner--bad`, dialog stays open, `busy` cleared in `finally`; success → `onClose()` — Dialog.tsx:40-41 [DERIVED]
- Enter key submits — Dialog.tsx:54 [DERIVED]

**useConfirm** — Dialog.tsx:65-80
- out: `[confirm, element]`; caller renders `element`, awaits `confirm(options)` — Dialog.tsx:63,79 [DERIVED]
- post: promise resolves `true` only from the action button; Cancel/Esc/backdrop answer `false` (per doc) — Dialog.tsx:63-64,70-72 [DERIVED]

**CopyField** — CopyField.tsx:8-50
- in: `value: string`, `what: string`, `block = false`, `primary = false` — CopyField.tsx:8-12 [DERIVED]
- pre: button `disabled={!value}` — CopyField.tsx:27 [DERIVED]
- post: success → `copied` for 2000 ms, label "Copied", icon `check` — CopyField.tsx:19-21,24,28-29 [DERIVED]
- post: failure → `role="alert"` text "The browser blocked copying: select the text and press ⌘C." — CopyField.tsx:32 [DERIVED]

**Secret** — Secret.tsx:8-21
- in: `value`, `what`, `block = false`, `rows = 10` — Secret.tsx:8 [DERIVED]
- post: success → `copied` for 2000 ms — Secret.tsx:10 [DERIVED]
- failure: `ok === false` produces no state change and no message — Secret.tsx:10 [DERIVED]

**PasswordInput** — PasswordInput.tsx:5-25
- in: `autoComplete` limited to `"current-password" | "new-password"` — PasswordInput.tsx:9 [DERIVED]
- post: eye button toggles input `type` text/password; `aria-pressed` mirrors `show` — PasswordInput.tsx:15-19 [DERIVED]

**Icon / IconButton** — icons.tsx:55-75
- in: `Icon` takes `name: IconName` (one of the 38 `PATHS` keys, lines 15-52), `size = 16` — icons.tsx:14-53,58 [DERIVED]
- post: svg is `aria-hidden="true" focusable="false"`, `viewBox="0 0 24 24"`, `strokeWidth={2}` — icons.tsx:60-61 [DERIVED]
- pre: `IconButton` requires `label`; it becomes both `aria-label` and `title` — icons.tsx:68-71 [DERIVED]

**Skeleton / EmptyState / ErrorState** — states.tsx:7-34
- Skeleton: `role="status" aria-live="polite"`, sr-only `label` default "Loading…", `rows = 4` — states.tsx:9-11 [DERIVED]
- ErrorState: `role="alert"`, fixed title "Couldn't load this", Retry button only when `onRetry` provided — states.tsx:28-31 [DERIVED]

## effect surface
- Clipboard write via `copyText(value)` imported from `frontend-v2/src/lib/auth.ts` — CopyField.tsx:2,16; Secret.tsx:2,10 [DERIVED]
- Browser timers: `setTimeout(..., 2000)` — CopyField.tsx:20; Secret.tsx:10 [DERIVED]
- Postgres tables read/written: none — FACTS `tables_read: []`, `tables_written: []` [DERIVED]
- Network, files, subprocesses, env flags: none in this unit [DERIVED]

## invariants
INVARIANT: copied-reset delay in CopyField (2000) = copied-reset delay in Secret (2000) — CopyField.tsx:20 / Secret.tsx:10 [DERIVED]
  fails-if: the two copy widgets give inconsistent "Copied" feedback durations
INVARIANT: ConfirmByName confirm enabled iff `typed === name` AND `!busy` — Dialog.tsx:36,45 [DERIVED]
  fails-if: destructive action fires on a partial or mistyped token
INVARIANT: Dialog renders null when `!open` — Dialog.tsx:16 [DERIVED]
  fails-if: stray text or stale state leaks into the page behind a closed modal
INVARIANT: useConfirm resolves `true` only from the action button; every dismissal path resolves `false` — Dialog.tsx:70-72 [DERIVED]
  fails-if: callers would read a Cancel/Esc as consent
INVARIANT: Skeleton row width % = `92 - (i % 3) * 14` (cycle 92/78/64) — states.tsx:11 [DERIVED]
  fails-if: skeleton silhouette stops approximating loaded-content widths
INVARIANT: every icon renders `viewBox="0 0 24 24"` with `strokeWidth={2}` regardless of `name` — icons.tsx:60 [DERIVED]
  fails-if: any PATHS geometry drawn outside the 24×24 grid clips or scales oddly
INVARIANT: IconButton always sets `aria-label` and `title` to `label` — icons.tsx:71 [DERIVED]
  fails-if: icon-only control loses its accessible name

## determinism & idempotency
determinism: NONDETERMINISTIC (clipboard outcome via `copyText` — CopyField.tsx:16-18, Secret.tsx:10; 2000 ms timer resets — CopyField.tsx:20, Secret.tsx:10; `ConfirmByName` awaits caller-supplied `onConfirm` — Dialog.tsx:40). All markup is otherwise a pure function of props. [DERIVED]
idempotency: SAFE (no writes; repeated copy clicks re-run `copyText` and re-arm the same 2000 ms timeout — CopyField.tsx:15-23; re-render with `open=false` unmounts cleanly — Dialog.tsx:16) [DERIVED]

## failure behaviour
- `copyText` false → CopyField sets `failed`, renders `role="alert"` hand-copy instruction — CopyField.tsx:17-18,32 [DERIVED]
- `copyText` false in Secret is swallowed: no state set, no message — Secret.tsx:10 [DERIVED]
- `ConfirmByName`: `onConfirm` throw → `e.message` (or `String(e)`) in `banner banner--bad`; `busy` reset in `finally`; dialog stays open — Dialog.tsx:40-41,56 [DERIVED]
- `showModal` unavailable → `setAttribute("open", "")`: dialog displays but without native focus trap / background inert — Dialog.tsx:13 [INFERRED: attribute-only open is non-modal]
- No error codes are raised; FACTS has no fallbacks list for this unit [DERIVED]

## dumb-code flags
- Literal `2000` duplicated with no shared constant — CopyField.tsx:20, Secret.tsx:10 [DERIVED]
- Copy/"Copied"/`check`-icon logic duplicated in CopyField and Secret under different CSS contracts (`btn copyfield__btn` vs `icon-btn icon-btn--sm secret__copy`) — CopyField.tsx:26-30 / Secret.tsx:16-18 [DERIVED]
- Inconsistent failure defaults: CopyField reports clipboard failure, Secret silently drops it — CopyField.tsx:14,32 vs Secret.tsx:10 [DERIVED]
- Busy label `"Deleting…"` is hardcoded although `action` is a parameter — Dialog.tsx:46 [DERIVED]
- useConfirm doc claims "the backdrop answer false" but Dialog wires no backdrop-click handler, only `onCancel` (Esc) — Dialog.tsx:63-64 vs 18-23 [INFERRED: no onClick on the dialog element in SOURCE]
- Magic numbers `92` and `14` in the Skeleton width formula — states.tsx:11 [DERIVED]

## refactor notes
- `IconName = keyof typeof PATHS`: removing/renaming any of the 38 keys (icons.tsx:15-52) is a compile-time break for every `Icon`/`IconButton` user — App.tsx plus CopyField.tsx:3, PasswordInput.tsx:2, Secret.tsx:3, states.tsx:2 [DERIVED]
- `ConfirmByName.name` mirrors a backend token ("the backend requires the same token"); loosening `typed === name` desyncs the client check from the server's — Dialog.tsx:26,36 [DERIVED]
- `copyText` lives in `frontend-v2/src/lib/auth.ts`; moving it breaks CopyField.tsx:2 and Secret.tsx:2 [DERIVED]
- `useConfirm` returns a positional `[confirm, element]` pair and the doc mandates rendering `element` before awaiting — Dialog.tsx:63,79 [DERIVED]
- CSS class strings (`copyfield*`, `dialog*`, `field`, `banner--bad`, `btn--danger-solid`, `btn--primary`, `pw*`, `secret*`, `icon-btn`, `skeleton*`, `state*`) are the stylesheet contract; renaming them needs CSS edits outside this material — CopyField.tsx:26-45, Dialog.tsx:18-56, PasswordInput.tsx:15-20, Secret.tsx:13-18, states.tsx:8-31 [DERIVED]
- Blast radius cap: only `frontend-v2/src/App.tsx` imports this unit — FACTS.importers [DERIVED]

## VERIFY
```verify
grep -Fq 'const match = typed === name' frontend-v2/src/ui/Dialog.tsx
grep -Fq 'setTimeout(() => setCopied(false), 2000)' frontend-v2/src/ui/CopyField.tsx
grep -Fq 'setTimeout(() => setCopied(false), 2000)' frontend-v2/src/ui/Secret.tsx
grep -Fq 'autoComplete: "current-password" | "new-password"' frontend-v2/src/ui/PasswordInput.tsx
grep -Fq 'rows = 10' frontend-v2/src/ui/Secret.tsx
grep -Fq 'width: `${92 - (i % 3) * 14}%`' frontend-v2/src/ui/states.tsx
grep -Fq 'size = 16' frontend-v2/src/ui/icons.tsx
! grep -Fq 'useState' frontend-v2/src/ui/icons.tsx
```
