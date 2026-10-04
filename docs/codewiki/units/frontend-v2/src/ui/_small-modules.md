# unit: frontend-v2/src/ui/_small-modules
anchor: frontend-v2/src/ui/CopyButton.tsx:1-29

## purpose
Seven presentational modules for the frontend-v2 React app: copy affordances (`CopyButton`, `CopyField`, `Secret`), native-`<dialog>` modals and confirm flows (`Dialog`, `ConfirmByName`, `useConfirm`), a password field with reveal (`PasswordInput`), inline outline icons copied from Lucide (`Icon`, `IconButton`), and `Skeleton`/`EmptyState`/`ErrorState` for data views. frontend-v2/src/ui/CopyButton.tsx:1-3, frontend-v2/src/ui/Dialog.tsx:3-4, frontend-v2/src/ui/states.tsx:3-5 [DERIVED]
Sole external importer: `frontend-v2/src/App.tsx`. material-6110425088-1194001861777541.md:89-101 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `CopyButton` | function | `({ text: string; label: string; className?: string })` -> button | frontend-v2/src/ui/CopyButton.tsx:9 | App.tsx |
| `CopyField` | function | `({ value: string; what: string; block?: boolean; primary?: boolean })` -> JSX | frontend-v2/src/ui/CopyField.tsx:8 | App.tsx |
| `Dialog` | function | `({ open: boolean; title: string; onClose: () => void; children: ReactNode; actions: ReactNode })` -> JSX \| null | frontend-v2/src/ui/Dialog.tsx:5 | App.tsx, ConfirmByName, useConfirm |
| `ConfirmByName` | function | `({ open, title, name, what, action, onConfirm, onClose })` -> JSX | frontend-v2/src/ui/Dialog.tsx:27 | App.tsx |
| `ConfirmOptions` | interface | `{ title: string; body: ReactNode; action: string; danger?: boolean }` | frontend-v2/src/ui/Dialog.tsx:61 | useConfirm |
| `useConfirm` | function | `()` -> `[(o: ConfirmOptions) => Promise<boolean>, ReactNode]` | frontend-v2/src/ui/Dialog.tsx:65 | App.tsx |
| `PasswordInput` | function | `({ id?, value, onChange, autoComplete, placeholder?, autoFocus? })` -> JSX | frontend-v2/src/ui/PasswordInput.tsx:5 | App.tsx |
| `Secret` | function | `({ value: string; what: string; block?: boolean; rows?: number })` -> JSX | frontend-v2/src/ui/Secret.tsx:8 | App.tsx |
| `IconName` | type | `keyof typeof PATHS` (closed union) | frontend-v2/src/ui/icons.tsx:55 | siblings |
| `Icon` | function | `({ name: IconName; size?: number } & SVGProps<SVGSVGElement>)` -> svg | frontend-v2/src/ui/icons.tsx:58 | App.tsx; CopyButton/CopyField/PasswordInput/Secret/states (intra-unit) |
| `IconButton` | function | `({ icon: IconName; label: string } & Omit<ButtonHTMLAttributes, "aria-label"\|"title"\|"children">)` -> button | frontend-v2/src/ui/icons.tsx:68 | App.tsx |
| `Skeleton` | function | `({ rows?: number; label?: string })` -> JSX | frontend-v2/src/ui/states.tsx:7 | App.tsx |
| `EmptyState` | function | `({ title: string; children?: ReactNode; action?: ReactNode })` -> JSX | frontend-v2/src/ui/states.tsx:16 | App.tsx |
| `ErrorState` | function | `({ message: string; onRetry?: () => void })` -> JSX | frontend-v2/src/ui/states.tsx:26 | App.tsx |

## contracts
- `CopyButton` — in: `text` copied via `copyText(text)`; post on ok: `copied=true` for `2000` ms, icon swaps `"copy"` -> `"check"`, class gains `copy-btn--done`; pre/post: pending timer cleared on unmount via ref. frontend-v2/src/ui/CopyButton.tsx:12,18-22,25 [DERIVED]
- `CopyField` — pre: button `disabled={!value}`; post ok: "Copied" for `2000` ms; post fail: `failed=true` renders `role="alert"` hint; `block` renders `<pre tabIndex={0}>`, else `<code>`. frontend-v2/src/ui/CopyField.tsx:21,28,33,38,45 [DERIVED]
- `Dialog` — pre: none; post: `open===false` renders `null`; `open` flip calls `showModal()` (fallback `setAttribute("open", "")`); Esc fires `onCancel` -> `preventDefault()` + `onClose()`. frontend-v2/src/ui/Dialog.tsx:13,16,18 [DERIVED]
- `ConfirmByName` — pre: danger button `disabled={!match || busy}` where `match = typed === name`; state (`typed`,`error`,`busy`) reset when `open` turns true; Enter key triggers confirm. post: `onConfirm` success -> `onClose()`; throw -> error into `banner banner--bad`, `busy` reset in `finally`. frontend-v2/src/ui/Dialog.tsx:35-36,40,45,54,56 [DERIVED]
- `useConfirm` — out: `[confirm, element]`; promise resolves `true` only from the action button, `false` from Cancel/Esc (`onClose` -> `answer(false)`). frontend-v2/src/ui/Dialog.tsx:68,70-72 [DERIVED]
- `PasswordInput` — toggles `type={show ? "text" : "password"}`; `autoComplete` restricted to `"current-password" | "new-password"`; eye button has `aria-pressed={show}`. frontend-v2/src/ui/PasswordInput.tsx:9,16,19-21 [DERIVED]
- `Secret` — `block` renders `<textarea readOnly rows={rows}>` (default `rows = 10`), else `<code>`; copy ok -> "Copied" check for `2000` ms; no failure surface. frontend-v2/src/ui/Secret.tsx:8,10,14-15 [DERIVED]
- `Icon` — default `size = 16`; svg `viewBox="0 0 24 24"`, `strokeWidth={2}`, `aria-hidden="true"`, `focusable="false"`. frontend-v2/src/ui/icons.tsx:58,60-61 [DERIVED]
- `IconButton` — `label` required; it is both `aria-label` and `title` (both omitted from the prop type). frontend-v2/src/ui/icons.tsx:67-69,71 [DERIVED]
- `Skeleton` — default `rows = 4`; `role="status"` + `aria-live="polite"`; row widths `92 - (i % 3) * 14` %. frontend-v2/src/ui/states.tsx:7,9-11 [DERIVED]
- `ErrorState` — `role="alert"`; Retry button only when `onRetry` given. frontend-v2/src/ui/states.tsx:28,31 [DERIVED]

## effect surface
- Clipboard write via `copyText` from `frontend-v2/src/lib/auth` — frontend-v2/src/ui/CopyButton.tsx:2, frontend-v2/src/ui/CopyField.tsx:2, frontend-v2/src/ui/Secret.tsx:2 [DERIVED]
- DOM modal: `d.showModal()` / `setAttribute("open", "")` — frontend-v2/src/ui/Dialog.tsx:13 [DERIVED]
- Timers: `window.setTimeout(..., 2000)` (CopyButton), bare `setTimeout(..., 2000)` (CopyField, Secret) — frontend-v2/src/ui/CopyButton.tsx:22, frontend-v2/src/ui/CopyField.tsx:21, frontend-v2/src/ui/Secret.tsx:10 [DERIVED]
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty; module imports are only react, `../lib/auth`, `./icons`) — frontend-v2/src/ui/CopyButton.tsx:1-3, frontend-v2/src/ui/Dialog.tsx:1, frontend-v2/src/ui/states.tsx:1-2 [DERIVED]
- Qdrant / files / network / subprocess / env flags: none read anywhere in the seven files. frontend-v2/src/ui/icons.tsx:1, frontend-v2/src/ui/PasswordInput.tsx:1-2 [DERIVED]

## invariants
INVARIANT: copied-feedback dwell = `2000` ms in CopyButton, CopyField and Secret — frontend-v2/src/ui/CopyButton.tsx:22, frontend-v2/src/ui/CopyField.tsx:21, frontend-v2/src/ui/Secret.tsx:10 [DERIVED]
  fails-if: check-icon/label dwell diverges between copy surfaces.
INVARIANT: ConfirmByName confirm enabled iff `typed === name` && `!busy` (exact string match) — frontend-v2/src/ui/Dialog.tsx:36,45 [DERIVED]
  fails-if: destructive action runs on partial/trimmed match, desyncing with the backend token check.
INVARIANT: Dialog output = `null` when `open === false` — frontend-v2/src/ui/Dialog.tsx:16 [DERIVED]
  fails-if: stale modal text/state leaks into the page behind a closed dialog.
INVARIANT: `PATHS` key count = 38 (lines 15-52, one key each) — frontend-v2/src/ui/icons.tsx:15-52 [DERIVED]
  fails-if: `IconName` union changes and a `name="…"` literal at a call site stops compiling.
INVARIANT: CopyField button `disabled` iff `value === ""` — frontend-v2/src/ui/CopyField.tsx:28 [DERIVED]
  fails-if: empty-string copy attempts hit the clipboard API.
INVARIANT: every icon-only control gets its accessible name from the wrapper (`IconButton` label, or `aria-label`/`title` on raw buttons), never from `Icon` — frontend-v2/src/ui/icons.tsx:61,71, frontend-v2/src/ui/CopyButton.tsx:16 [DERIVED]
  fails-if: screen readers encounter unnamed buttons.

## determinism & idempotency
determinism: DETERMINISTIC markup from props/state; NONDETERMINISTIC inputs are the clipboard result of `copyText` (frontend-v2/src/ui/CopyButton.tsx:18, frontend-v2/src/ui/CopyField.tsx:17, frontend-v2/src/ui/Secret.tsx:10) and `showModal` availability (frontend-v2/src/ui/Dialog.tsx:13). [DERIVED]
idempotency: SAFE — no persistence; repeat clicks re-enter the same states; ConfirmByName resets per open (frontend-v2/src/ui/Dialog.tsx:35); CopyButton clears the prior timer before arming a new one (frontend-v2/src/ui/CopyButton.tsx:21-22). [DERIVED]

## failure behaviour
- `copyText` resolves false: CopyButton returns early with no feedback (frontend-v2/src/ui/Dialog.tsx n/a — frontend-v2/src/ui/CopyButton.tsx:19); CopyField shows `role="alert"` "The browser blocked copying: select the text and press ⌘C." (frontend-v2/src/ui/CopyField.tsx:33); Secret silently skips (frontend-v2/src/ui/Secret.tsx:10). [DERIVED]
- `onConfirm` rejection: message string into `banner banner--bad`; `busy` reset in `finally`; dialog stays open. frontend-v2/src/ui/Dialog.tsx:40,56 [DERIVED]
- No `showModal` support: fallback `setAttribute("open", "")`. frontend-v2/src/ui/Dialog.tsx:13 [DERIVED]
- Esc in any Dialog: `onCancel` -> `preventDefault()` + `onClose`; for `useConfirm` that resolves the promise `false`. frontend-v2/src/ui/Dialog.tsx:18,70 [DERIVED]
- `ErrorState`: `role="alert"`, Retry offered only when `onRetry` provided. frontend-v2/src/ui/states.tsx:28,31 [DERIVED]

## dumb-code flags
- CopyField and Secret arm bare `setTimeout` with no unmount cleanup, while CopyButton stores the timer in a ref and clears it — `setState` after unmount possible. frontend-v2/src/ui/CopyField.tsx:21, frontend-v2/src/ui/Secret.tsx:10, frontend-v2/src/ui/CopyButton.tsx:11-12 [INFERRED: same 2000 ms pattern, cleanup present in only one of three]
- `size={15}` repeated at three copy call sites vs Icon default `size = 16` (PasswordInput eye uses 16). frontend-v2/src/ui/CopyButton.tsx:25, frontend-v2/src/ui/CopyField.tsx:29, frontend-v2/src/ui/Secret.tsx:17, frontend-v2/src/ui/icons.tsx:58, frontend-v2/src/ui/PasswordInput.tsx:21 [DERIVED]
- `2000` ms literal duplicated three times. frontend-v2/src/ui/CopyButton.tsx:22, frontend-v2/src/ui/CopyField.tsx:21, frontend-v2/src/ui/Secret.tsx:10 [DERIVED]
- `useConfirm` doc says "Cancel, Esc and the backdrop answer false" but no backdrop/click handler exists — only `onCancel` (Esc) is wired. frontend-v2/src/ui/Dialog.tsx:63,18 [INFERRED: no click handler in SOURCE]
- CopyField visible text: inline shows `"Copy"`, block shows `` `Copy ${what}` ``, while `aria-label` is always `` `Copy ${what}` ``. frontend-v2/src/ui/CopyField.tsx:25,30 [DERIVED]
- Skeleton width magic numbers `92` and `14`. frontend-v2/src/ui/states.tsx:11 [DERIVED]

## refactor notes
- Renaming/deleting any export here requires updating `frontend-v2/src/App.tsx`, the sole importer. material-6110425088-1194001861777541.md:89-101 [DERIVED]
- `IconName` is a closed union over `PATHS`; call-site literals in this unit: `"check"`, `"copy"` (frontend-v2/src/ui/CopyButton.tsx:25, frontend-v2/src/ui/CopyField.tsx:29, frontend-v2/src/ui/Secret.tsx:17), `"eye"`/`"eyeOff"` (frontend-v2/src/ui/PasswordInput.tsx:21), `"alert"` (frontend-v2/src/ui/states.tsx:29). [DERIVED]
- ConfirmByName comment: "the backend requires the same token" — the exact-match rule `typed === name` must track that backend check. frontend-v2/src/ui/Dialog.tsx:26,36 [DERIVED]
- Stylesheet coupling: `.copy-btn--hover` is hidden until pointer hover per CSS (comment), plus `copyfield__*`, `secret__copy`, `dialog*`, `state*`, `skeleton*`, `icon-btn` class names — renaming any breaks styling. frontend-v2/src/ui/CopyButton.tsx:6-7,15, frontend-v2/src/ui/CopyField.tsx:27,36 [DERIVED]
- Lucide ISC license header must be preserved when copying/modifying icons.tsx. frontend-v2/src/ui/icons.tsx:3-12 [DERIVED]
- Unmount-on-close (`if (!open) return null`) is Dialog's state-reset mechanism; replacing it needs explicit reset, since ConfirmByName relies on the `open` effect. frontend-v2/src/ui/Dialog.tsx:16,35 [DERIVED]

## VERIFY
```verify
grep -Fq 'window.setTimeout(() => setCopied(false), 2000)' frontend-v2/src/ui/CopyButton.tsx
grep -Fq 'The browser blocked copying: select the text and press ⌘C.' frontend-v2/src/ui/CopyField.tsx
grep -Fq 'const match = typed === name;' frontend-v2/src/ui/Dialog.tsx
grep -Fq 'if (!open) return null;' frontend-v2/src/ui/Dialog.tsx
grep -Fq 'satisfies Record<string, ReactNode>' frontend-v2/src/ui/icons.tsx
grep -Fq 'rows = 10' frontend-v2/src/ui/Secret.tsx
! grep -Fq 'useState' frontend-v2/src/ui/states.tsx
test "$(grep -c -F 'size={15}' frontend-v2/src/ui/CopyButton.tsx)" -ge 1
```
