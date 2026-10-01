# unit: frontend-v2/src/lib/_small-modules
anchor: frontend-v2/src/lib/appearance.ts:1-105
anchor: frontend-v2/src/lib/auth.ts:1-122
anchor: frontend-v2/src/lib/chatStore.ts:1-84
anchor: frontend-v2/src/lib/chunkid.ts:1-26
anchor: frontend-v2/src/lib/composerSettings.ts:1-79
anchor: frontend-v2/src/lib/readiness.ts:1-94
anchor: frontend-v2/src/lib/useAsync.ts:1-22

## purpose
Seven small frontend-v2 client modules: per-browser appearance theming (mode + accent, localStorage, applied to `<html>` dataset), the auth/Settings HTTP client (sign-in, password, API keys), chat session persistence in localStorage, chunk-id extraction from receipt rows, a shared composer-settings store (top-bar controls ↔ composer), pure painting of backend readiness verdicts, and a minimal fetch-on-mount hook. Screens render what these return; the backend decides policy. [DERIVED]

## public surface
Unit-level importers per FACTS.importers: `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/deep.ts`, and the unit itself (`_small-modules`). Per-symbol consumers are not in FACTS → "—".

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Mode | type | "light" \| "dark" \| "system" | appearance.ts:6 | — |
| Accent | type | "indigo" \| "teal" \| "amber" \| "rose" | appearance.ts:7 | — |
| Appearance | interface | { mode: Mode; accent: Accent } | appearance.ts:8 | — |
| APPEARANCE_KEY | const | "polymath.appearance" | appearance.ts:10 | — |
| LEGACY_THEME_KEY | const | "polymath-v2.theme" | appearance.ts:11 | — |
| MODES | const | ["light","dark","system"] | appearance.ts:12 | — |
| ACCENTS | const | ["indigo","teal","amber","rose"] | appearance.ts:13 | — |
| DEFAULT_APPEARANCE | const | { mode: "system", accent: "indigo" } | appearance.ts:14 | — |
| migrateLegacy | function | (id: string \| null \| undefined) -> Appearance | appearance.ts:30-32 | — |
| loadAppearance | function | () -> Appearance | appearance.ts:44-53 | — |
| resolveMode | function | (mode: Mode, dark = prefersDark()) -> "light" \| "dark" | appearance.ts:59-61 | — |
| applyAppearance | function | (a: Appearance, root = document.documentElement) -> void | appearance.ts:63-66 | — |
| getAppearance | function | () -> Appearance | appearance.ts:72 | — |
| setAppearance | function | (next: Appearance) -> void | appearance.ts:74-80 | — |
| useAppearance | function | () -> [Appearance, (a: Appearance) => void] | appearance.ts:90-92 | — |
| initAppearance | function | () -> Appearance | appearance.ts:96-104 | — |
| Me | interface | owner/auth identity record | auth.ts:9-19 | — |
| ApiKey | interface | { key_id, label, created_at, revoked_at } | auth.ts:21-26 | — |
| CreatedKey | interface | ApiKey & { key, prompt, shown_once } | auth.ts:28-32 | — |
| MyKeys | interface | { is_owner, keys, max_active, mcp_url, note? } | auth.ts:34-40 | — |
| ConnectPrompt | interface | { prompt, placeholder, mcp_url, key_included?, connect_command? } | auth.ts:44-50 | — |
| OwnerKey | interface | { key, mcp_url, connector_url, prompt } | auth.ts:53-59 | — |
| LEGACY_OWNER | const | Me (username "king", principal_id "prn_owner") | auth.ts:65-67 | — |
| normalizeMe | function | (raw: unknown) -> Me | auth.ts:69-73 | — |
| auth | const | object of 10 endpoint functions | auth.ts:75-90 | — |
| privateLibrary | function | (me: Me) -> string \| null | auth.ts:93-95 | — |
| copyText | function | (text: string) -> Promise<boolean> | auth.ts:98-121 | — |
| ChatSession | interface | { id, title, corpusId, createdAt, updatedAt, turns } | chatStore.ts:19-26 | — |
| INTERRUPTED | const | "interrupted: the page was reloaded or closed..." | chatStore.ts:29-30 | — |
| newSessionId | function | () -> string | chatStore.ts:33-35 | — |
| emptySession | function | (corpusId: string) -> ChatSession | chatStore.ts:37-40 | — |
| titleFor | function | (s: ChatSession) -> string | chatStore.ts:43-47 | — |
| loadSessions | function | () -> ChatSession[] | chatStore.ts:49-70 | — |
| saveSessions | function | (sessions: ChatSession[]) -> void | chatStore.ts:72-84 | — |
| chunkIdOf | function | (row: Record<string, unknown> \| null \| undefined) -> string | chunkid.ts:14-26 | — |
| ComposerSettings | interface | { mode: PublicMode; model: string; corpusExplore: boolean } | composerSettings.ts:11 | — |
| COMPOSER_SETTINGS_KEY | const | "polymath-v2.chat-settings" | composerSettings.ts:13 | — |
| DEFAULT_COMPOSER_SETTINGS | const | { mode: "HYBRID", model: "", corpusExplore: false } | composerSettings.ts:15 | — |
| getComposerSettings | function | () -> ComposerSettings | composerSettings.ts:51-56 | — |
| setComposerSettings | function | (next: ComposerSettings) -> void | composerSettings.ts:58-63 | — |
| updateComposerSettings | function | (patch: Partial<ComposerSettings>) -> void | composerSettings.ts:65-67 | — |
| useComposerSettings | function | () -> [ComposerSettings, (patch) => void] | composerSettings.ts:77-79 | — |
| ReadyState | type | "ready" \| "blocked" \| "degraded" \| "unknown" | readiness.ts:14 | — |
| Verdict | interface | { state, label, detail? } | readiness.ts:16-21 | — |
| controlReady | function | (cr: ControlPlane["control_ready"] \| null \| undefined) -> Verdict | readiness.ts:33-36 | — |
| semanticReady | function | (sr: SemanticReadiness \| null) -> Verdict | readiness.ts:39-44 | — |
| vnextReady | function | (sr: SemanticReadiness \| null) -> Verdict | readiness.ts:50-65 | — |
| docSearchable | function | (d: DocSummary \| null \| undefined) -> boolean | readiness.ts:70-72 | — |
| docVnext | function | (d: DocSummary) -> Verdict | readiness.ts:76-85 | — |
| CHECKING | const | { state: "unknown", label: "CHECKING" } | readiness.ts:90 | — |
| settled | function | (a: { data, error }, verdict: (d) -> Verdict) -> Verdict | readiness.ts:92-94 | — |
| Async | interface | { data: T \| null; error: string \| null; loading: boolean } | useAsync.ts:3 | — |
| useAsync | function | (fn: (signal) -> Promise<T>, deps: unknown[]) -> Async<T> | useAsync.ts:6-21 | — |

## contracts

**loadAppearance() -> Appearance** (appearance.ts:44-53)
- in: none. reads localStorage `APPEARANCE_KEY` = "polymath.appearance" (appearance.ts:48).
- pre: none (works with no storage, bad JSON).
- post: valid stored {mode, accent}; else legacy key "polymath-v2.theme" mapped via `migrateLegacy` (appearance.ts:51-52); else DEFAULT_APPEARANCE. Never throws.

**setAppearance(next)** (appearance.ts:74-80)
- post: JSON written to APPEARANCE_KEY, LEGACY_THEME_KEY removed, `applyAppearance` called, all listeners fired. Write failure (private mode) swallowed — value still applied in memory.

**resolveMode(mode, dark)** (appearance.ts:59-61)
- post: "system" -> dark ? "dark" : "light"; explicit mode returned as-is.

**normalizeMe(raw: unknown) -> Me** (auth.ts:69-73)
- pre: raw is any /auth/me payload.
- post: `!m || typeof m.is_owner !== "boolean" || typeof m.username !== "string"` -> LEGACY_OWNER; else `{ ...LEGACY_OWNER, ...m, local: Boolean(m.local) }`.

**chunkIdOf(row) -> string** (chunkid.ts:14-26)
- in: receipt row that carries either `chunk_id` (string) or `locator` "chunk:<id>@<start>:<end>".
- post: the chunk id; "" when neither field is a non-empty string.

**loadSessions() -> ChatSession[]** (chatStore.ts:49-70)
- post: parses "polymath-v2.chats"; non-array or throw -> []. Rows kept only when `typeof s.id === "string" && Array.isArray(s.turns)` (chatStore.ts:56-59). Every turn with `done` falsy is rewritten to `{ ...t, done: true, error: t.error ?? INTERRUPTED }` (chatStore.ts:63-66).

**saveSessions(sessions)** (chatStore.ts:72-84)
- post: drops `turns.length === 0` rows, sorts by `updatedAt` desc, slices to MAX_SESSIONS = 50, writes JSON. Any failure swallowed.

**getComposerSettings() -> ComposerSettings** (composerSettings.ts:51-56)
- post: re-reads the stored string every call; re-parses only when the raw string changed (stable reference, `useSyncExternalStore` requirement); returns session-memory value when storage is unreadable.

**controlReady(cr)** (readiness.ts:33-36)
- post: null/undefined -> `{ state: "unknown", label: "UNKNOWN", detail: "/control_plane not reachable" }`; otherwise passes through backend `state`/`label`/`detail` verbatim.

**vnextReady(sr)** (readiness.ts:50-65)
- post: no `sr.vnext` -> UNKNOWN; verdict "VNEXT_COMPLETE" -> ready; degraded label "SEARCHABLE · BASIC PROFILES" only when `p.unresolved === 0 && docs > 0 && typeof v.profiled === "number" && v.profiled >= docs` (readiness.ts:60); else blocked with backend verdict.

**docSearchable(d)** (readiness.ts:70-72)
- post: `!!d && (d.vnext_ready || (d.map_unresolved === 0 && d.profile_present))`.

**useAsync(fn, deps) -> Async<T>** (useAsync.ts:6-21)
- post: sets loading, resolves to `{ data, error: null, loading: false }` or `{ data: null, error: message, loading: false }`; errors after abort/unmount are discarded (`if (!live || ac.signal.aborted) return`, useAsync.ts:15).

## effect surface
- Network (all via `http` from ./api, auth.ts:7): POST /auth/owner-password (auth.ts:77), GET /auth/me (auth.ts:78), POST /auth/login (auth.ts:79), POST /auth/logout (auth.ts:80), POST /auth/password (auth.ts:82), GET /keys (auth.ts:84), POST /keys (auth.ts:85), DELETE /keys/{keyId} (auth.ts:86), GET /keys/prompt (auth.ts:87), GET /keys/owner (auth.ts:89). Matches FACTS.api_calls (10 calls).
- localStorage keys written/read: "polymath.appearance" (appearance.ts:10), "polymath-v2.theme" read + removed (appearance.ts:51, 77), "polymath-v2.chats" (chatStore.ts:28), "polymath-v2.chat-settings" (composerSettings.ts:13).
- DOM: `document.documentElement.dataset.mode/.accent` (appearance.ts:63-66); `matchMedia("(prefers-color-scheme: dark)")` polled and subscribed (appearance.ts:56, 86); hidden-textarea `document.execCommand("copy")` fallback (auth.ts:108-116); `navigator.clipboard.writeText` (auth.ts:100).
- Postgres tables read/written: none (FACTS.tables_read / tables_written empty). Qdrant collections: none. Subprocesses: none. Env flags: none (FACTS.constants empty).
- Browser events: `window` "storage" listener for cross-window composer sync (composerSettings.ts:71).

## invariants
INVARIANT: MAX_SESSIONS = 50 persisted sessions max — chatStore.ts:31, chatStore.ts:79 [DERIVED]
  fails-if: >50 real conversations exist — oldest by `updatedAt` silently evicted.
INVARIANT: persisted sessions all have turns.length ≥ 1 (empty "New chat" filtered before write) — chatStore.ts:76-78 [DERIVED]
  fails-if: blanks accumulate and evict real conversations at the 50 cap (stated reason, chatStore.ts:74-75).
INVARIANT: every turn returned by loadSessions has done === true — chatStore.ts:63-66 [DERIVED]
  fails-if: a stored unfinished turn would render its chat busy forever after reload.
INVARIANT: titleFor label length ≤ 42 (`q.length > 42` → `q.slice(0, 41) + "…"`) — chatStore.ts:44-47 [DERIVED]
  fails-if: sidebar labels overflow; truncation boundary shifts.
INVARIANT: vnextReady degraded requires p.unresolved === 0 AND docs > 0 AND v.profiled >= docs — readiness.ts:60 [DERIVED]
  fails-if: a library with unresolved parents is painted amber instead of red (owner complaint, readiness.ts:46-49).
INVARIANT: docSearchable === (vnext_ready || (map_unresolved === 0 && profile_present)) — readiness.ts:71 [DERIVED]
  fails-if: a searchable file with only the base profile shows "Blocked" (owner complaint, readiness.ts:67-69).
INVARIANT: LEGACY maps 10 ids ("", obsidian, graphite, nord, espresso, solar, rose, slate, paper, champagne) — appearance.ts:17-28 [DERIVED]
  fails-if: a pre-refresh theme falls to DEFAULT_APPEARANCE instead of its nearest mode/accent.
INVARIANT: auth endpoint count = 10 — auth.ts:77-89 [DERIVED] (= FACTS.api_calls length)
  fails-if: a screen calls a key/auth route that no longer exists in `auth`.
INVARIANT: normalizeMe fallback identity is username "king", principal_id "prn_owner" — auth.ts:65-67 [DERIVED]
  fails-if: old backends (404 on /auth/me) display as a non-owner.

## determinism & idempotency
determinism: NONDETERMINISTIC — `newSessionId` uses Date.now + Math.random (chatStore.ts:33-35); network in all `auth` calls (auth.ts:75-90); `matchMedia` system preference + its change event (appearance.ts:56, 86); localStorage availability (appearance.ts:39-41). All other functions are pure mappings over their inputs. [DERIVED]
idempotency: SAFE — setAppearance overwrites the same key and removes the legacy key (appearance.ts:77); saveSessions is filter/sort/slice of its input (chatStore.ts:76-80); loadSessions is a read + in-memory rewrite. One-way note: initAppearance's migration deletes "polymath-v2.theme" once (appearance.ts:99-101). [DERIVED]

## failure behaviour
- localStorage unavailable/private mode: `storage()` returns null → DEFAULT_APPEARANCE (appearance.ts:39-41, 46); setAppearance write swallowed (appearance.ts:77); composer value kept in memory for the session (composerSettings.ts:60); saveSessions swallow → history dropped (chatStore.ts:81-83).
- Bad JSON: loadAppearance catch → legacy key path (appearance.ts:50-52); parse() → DEFAULT_COMPOSER_SETTINGS (composerSettings.ts:33-36); loadSessions catch → [] (chatStore.ts:67-69).
- Malformed shapes: normalizeMe → LEGACY_OWNER (auth.ts:71-72); loadSessions row filter drops bad rows instead of the whole list (chatStore.ts:55-59).
- copyText: clipboard API failure falls through to execCommand textarea copy; both failing returns `false` (auth.ts:99-121).
- useAsync: errors after abort or unmount discarded (useAsync.ts:15); live errors become `e.message` or `String(e)` (useAsync.ts:16).
- No error codes raised anywhere; all handlers swallow to a default/empty value.

## dumb-code flags
- Storage-key prefix drift: "polymath.appearance" (appearance.ts:10) vs "polymath-v2.theme"/"polymath-v2.chats"/"polymath-v2.chat-settings" (appearance.ts:11, chatStore.ts:28, composerSettings.ts:13). [DERIVED]
- `model: ""` sentinel meaning "backend default model, nothing picked" (composerSettings.ts:14-15). [DERIVED]
- INTERRUPTED is a user-facing sentence doubling as the persisted error marker (chatStore.ts:29-30). [DERIVED]
- FACTS.imports lists "frontend-v2/src/lib/contracts.ts" twice (FACTS.imports) — duplicated import edge. [DERIVED]
- Magic numbers 42/41 in titleFor (chatStore.ts:46); MAX_SESSIONS = 50 unnamed (chatStore.ts:31). [DERIVED]
- `query_ready` appears only in the rejecting comment; no function in readiness.ts accepts it (readiness.ts:8-11). [DERIVED]

## refactor notes
- APPEARANCE_KEY is a cross-page contract: index.html reads the stored choice before first paint (appearance.ts:3-4). Renaming the key orphans every stored appearance and breaks pre-paint application. [DERIVED]
- `useSyncExternalStore` snapshot identity: getAppearance returns the module-level `current` replaced only on set/init (appearance.ts:69-79); getComposerSettings caches the parsed object and re-parses only on raw-string change (composerSettings.ts:47-56). Returning fresh objects per call breaks React rendering. [DERIVED]
- chunkIdOf encodes the receipt-section mismatch (final_detail[]/legend[] bare `chunk_id`; chunks[] `locator` only). Joining sections on `chunk_id` without it produced 0 matches and duplicate Evidence rows (chunkid.ts:4-13). [DERIVED]
- Verdict labels are user-visible verbatim strings: "SEARCHABLE · BASIC PROFILES" (readiness.ts:61), "READY · BASIC PROFILE" (readiness.ts:79), "BLOCKED" (readiness.ts:85), "CHECKING" (readiness.ts:90); backend verdict words are shown unparaphrased (readiness.ts:18-20). Changing them changes every screen painting readiness. [DERIVED]
- LEGACY_OWNER fallback makes a backend without /auth/me display as owner (auth.ts:63-72) — removing it changes display-only behavior for old backends. [DERIVED]
- Type/dependency edges: `http` from ./api (auth.ts:7), `Turn` from ./chat (chatStore.ts:17), PUBLIC_MODES/PublicMode/ControlPlane/DocSummary/SemanticReadiness from ./contracts (composerSettings.ts:2, readiness.ts:12). Renaming those upstream exports hits this unit; renaming this unit's exports hits App.tsx and lib/deep.ts (FACTS.importers). [DERIVED]
- composerSettings subscribe treats `e.key === null` (storage cleared) as a change (composerSettings.ts:71) — keep that when refactoring the listener. [DERIVED]

## VERIFY
```verify
grep -Fq 'polymath.appearance' frontend-v2/src/lib/appearance.ts
grep -Fq 'polymath-v2.chats' frontend-v2/src/lib/chatStore.ts
grep -Fq 'polymath-v2.chat-settings' frontend-v2/src/lib/composerSettings.ts
grep -Fq 'SEARCHABLE · BASIC PROFILES' frontend-v2/src/lib/readiness.ts
grep -Fq 'chunk:chunk_abc123@365:564' frontend-v2/src/lib/chunkid.ts
grep -Fq 'prn_owner' frontend-v2/src/lib/auth.ts
grep -Fq 'useSyncExternalStore' frontend-v2/src/lib/composerSettings.ts
test "$(grep -c -F '/keys' frontend-v2/src/lib/auth.ts)" -ge 5
```
