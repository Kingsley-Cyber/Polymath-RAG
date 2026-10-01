# unit: frontend-v2/src/screens/Models.tsx
anchor: frontend-v2/src/screens/Models.tsx:1-232

## purpose
F1 — Models screen, "parity with the legacy `/ui` Models screen" (frontend-v2/src/screens/Models.tsx:9). Operator UI to manage the LiteLLM providers the chat synthesizer can use: list, add/update (provider + endpoint + key + model list), test a model, delete (frontend-v2/src/screens/Models.tsx:11-12). Keys are entered here, stored server-side, and never shown back (frontend-v2/src/screens/Models.tsx:14-16).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Models` | function (React component) | `() -> JSX` | frontend-v2/src/screens/Models.tsx:24 | frontend-v2/src/App.tsx |

Module-local helper: `keyLabel(p: LlmProvider): string` (frontend-v2/src/screens/Models.tsx:18), not exported.

## contracts
`Models()` (frontend-v2/src/screens/Models.tsx:24)
- in: none (props-free component).
- state: `nonce`, `busy: string | null`, `err`, `notice`, `tests: Record<string, LlmTestResult>` keyed by `provider_id` (frontend-v2/src/screens/Models.tsx:26-30); form state `provider/apiBase/apiKey/models/enabled` (frontend-v2/src/screens/Models.tsx:33-37).
- data: `providers = useAsync((s) => api.llmProviders(s), [nonce])`, `rows = providers.data ?? []` (frontend-v2/src/screens/Models.tsx:39-40).

`onSave()` (frontend-v2/src/screens/Models.tsx:68-87)
- pre: `provider.trim()` non-empty, else `setErr("Provider is required.")` and return (frontend-v2/src/screens/Models.tsx:69).
- out: `api.saveProvider({ provider: provider.trim(), api_key: apiKey, api_base: apiBase.trim(), models: models.split(",").map((m) => m.trim()).filter(Boolean), enabled })` (frontend-v2/src/screens/Models.tsx:72-78).
- post: success → `setNotice(`Saved provider "${out.saved}".`)` + `resetForm()`; `finally` → `setBusy(null); refresh()` (frontend-v2/src/screens/Models.tsx:79-86).
- `api_key: ""` keeps the stored key on an existing provider (frontend-v2/src/screens/Models.tsx:74).

`onDelete(p: LlmProvider)` (frontend-v2/src/screens/Models.tsx:89-102)
- pre: user confirms dialog with title `Delete the provider ${p.provider}?`, action `"Delete provider"`, `danger: true` (frontend-v2/src/screens/Models.tsx:90-91).
- out: `api.deleteProvider(p.provider_id)` (frontend-v2/src/screens/Models.tsx:94).
- post: `setNotice(`Deleted "${p.provider}".`)`; `finally` → `setBusy(null); refresh()` (frontend-v2/src/screens/Models.tsx:95-100).

`onTest(p: LlmProvider)` (frontend-v2/src/screens/Models.tsx:104-116)
- pre: `p.models[0]` exists, else `setErr(`"${p.provider}" has no model to test.`)` (frontend-v2/src/screens/Models.tsx:105-106).
- out: `api.testModel(model)` with `model = p.models[0]` only (frontend-v2/src/screens/Models.tsx:105,109).
- post: `tests[p.provider_id] = res`, or `{ ok: false, model, error: describeError(e) }` on throw (frontend-v2/src/screens/Models.tsx:110,138).

`editRow(p: LlmProvider)` (frontend-v2/src/screens/Models.tsx:54-62)
- prefills `provider`, `api_base`, `models.join(", ")`, `enabled`; sets `apiKey` to `""` — "never prefill a secret; blank keeps the stored key" (frontend-v2/src/screens/Models.tsx:55-59).

`keyLabel(p)` (frontend-v2/src/screens/Models.tsx:18-22)
- `p.api_key.startsWith("env:")` → `` `${p.api_key} (${p.api_key_set ? "set" : "UNSET"})` ``; else `p.api_key_set` → `` `…${p.api_key}` ``; else `"no key"`.

## effect surface
- Network via `api` (frontend-v2/src/lib/api.ts): `api.llmProviders(s)` (frontend-v2/src/screens/Models.tsx:39), `api.saveProvider({...})` (:72), `api.deleteProvider(p.provider_id)` (:94), `api.testModel(model)` (:109).
- Postgres tables: none — FACTS lists `tables_read: []`, `tables_written: []`; all persistence is server-side behind the four `api` calls above.
- Qdrant / files / subprocesses / env flags: none in SOURCE.
- Browser state only: `useState` locals; refresh via `nonce` increment (frontend-v2/src/screens/Models.tsx:26,41).

## invariants
INVARIANT: `apiKey` after `editRow` === `""` — frontend-v2/src/screens/Models.tsx:57 [DERIVED]
  fails-if: stored secret round-trips to the browser, breaking "the UI never displays or transmits them back" (:16).
INVARIANT: key sent on save === current `apiKey` state; `""` preserves stored key — frontend-v2/src/screens/Models.tsx:74 [DERIVED]
  fails-if: editing a provider silently wipes its server-side key.
INVARIANT: `tests` map keyed by `provider_id` on write (:110,:138) and read (:145) — frontend-v2/src/screens/Models.tsx:110-145 [DERIVED]
  fails-if: test result rendered on the wrong provider row.
INVARIANT: test target === `p.models[0]`, first model only — frontend-v2/src/screens/Models.tsx:105 [DERIVED]
  fails-if: remaining models in `p.models` are never connectivity-tested.
INVARIANT: `refresh()` runs in `finally` after both save and delete — frontend-v2/src/screens/Models.tsx:84-85,99-100 [DERIVED]
  fails-if: table shows stale provider list after a mutation.
INVARIANT: header counts `rows.length` configured vs `rows.filter((r) => r.ready).length` ready — frontend-v2/src/screens/Models.tsx:124-125 [DERIVED]
  fails-if: operator sees wrong readiness summary.
INVARIANT: `keyLabel` shows at most `…${p.api_key}` (last chars) or `env:NAME`, never a full literal key — frontend-v2/src/screens/Models.tsx:18-21 [DERIVED]
  fails-if: key disclosure in the table if the backend ever returns the raw key (UI trusts the "NEVER returns a raw key" contract, :12-14) [INFERRED: trust boundary is documented, not enforced client-side].

## determinism & idempotency
determinism: NONDETERMINISTIC (network: `llmProviders`/`saveProvider`/`deleteProvider`/`testModel` — frontend-v2/src/screens/Models.tsx:39,72,94,109)
idempotency: SAFE (save is add-or-update per the "Add / update a provider" form, :191; delete gated by confirm, :90-91; double-fire prevented by `disabled={!!busy}` on all action buttons, :172-177,:219-221)

## failure behaviour
- `describeError(e)`: for `ApiError`, parses `e.message.slice(e.message.indexOf("{"))` as JSON; if `body?.message` → `` `${body.error_code ?? "error"}: ${body.message}` ``; parse failure swallowed by `catch { /* not JSON */ }` and raw `e.message` returned (frontend-v2/src/screens/Models.tsx:43-50).
- Non-`ApiError`: `e instanceof Error ? e.message : String(e)` (frontend-v2/src/screens/Models.tsx:51).
- Handler errors → `setErr` → `banner banner--bad` (frontend-v2/src/screens/Models.tsx:82,97,132); list errors via `providers.error` → `banner--bad` (:133).
- `onTest` throw is not an error banner: stored as `{ ok: false, model, error }` and rendered as `` `✕ ${test.error || "failed"}` `` (frontend-v2/src/screens/Models.tsx:138,158-159).
- Empty state shown only when `!rows.length && !providers.loading`: `"No providers configured — add one below."` (frontend-v2/src/screens/Models.tsx:185-187).

## dumb-code flags
- Stringly-typed error contract: `JSON.parse(e.message.slice(e.message.indexOf("{")))` — fragile text scraping of an error message (frontend-v2/src/screens/Models.tsx:46).
- Inline style `{ marginBottom: 12 }` duplicated 4× across banners (frontend-v2/src/screens/Models.tsx:130-133).
- `disabled={!!busy}` repeated on 5 buttons (frontend-v2/src/screens/Models.tsx:172,174,176,219,221).
- Duplicated no-models guard: button `disabled={!!busy || !p.models.length}` (:172) plus runtime check at :106.
- Hard-coded provider examples `"openai · anthropic · groq · …"` in placeholder (frontend-v2/src/screens/Models.tsx:195).
- Magic prefix `"…"` in key label (frontend-v2/src/screens/Models.tsx:20).

## refactor notes
- `Models` is imported by `frontend-v2/src/App.tsx` (FACTS.importers) — rename/move requires updating App.
- Consumes `api.llmProviders`, `api.saveProvider`, `api.deleteProvider`, `api.testModel` from `../lib/api` — changing those signatures breaks this screen (frontend-v2/src/screens/Models.tsx:39,72,94,109).
- Depends on `LlmProvider` fields `provider`, `provider_id`, `api_base`, `api_key`, `api_key_set`, `models`, `enabled`, `ready` and `LlmTestResult` fields `ok`, `model`, `error`, `reply` from `../lib/contracts` — field renames break rows/tests rendering (frontend-v2/src/screens/Models.tsx:18-21,54-59,124-125,145-169).
- `useConfirm` returns the pair `[confirm, confirmDialog]` from `../ui/Dialog`; `confirmDialog` must stay in JSX (frontend-v2/src/screens/Models.tsx:25,120).
- Refresh protocol is the `nonce` state increment feeding `useAsync` deps — changing `useAsync`'s re-run contract breaks list refresh (frontend-v2/src/screens/Models.tsx:39,41).

## VERIFY
```verify
grep -Fq 'export function Models()' frontend-v2/src/screens/Models.tsx
grep -Fq 'api.llmProviders(s), [nonce]' frontend-v2/src/screens/Models.tsx
grep -Fq 'await api.saveProvider({' frontend-v2/src/screens/Models.tsx
grep -Fq 'await api.deleteProvider(p.provider_id)' frontend-v2/src/screens/Models.tsx
grep -Fq 'await api.testModel(model)' frontend-v2/src/screens/Models.tsx
test "$(grep -c -F 'marginBottom: 12' frontend-v2/src/screens/Models.tsx)" -ge 4
! grep -Fq 'setApiKey(p.api_key)' frontend-v2/src/screens/Models.tsx
```
