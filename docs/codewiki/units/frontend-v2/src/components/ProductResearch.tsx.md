# unit: frontend-v2/src/components/ProductResearch.tsx
anchor: frontend-v2/src/components/ProductResearch.tsx:1-266

## purpose
React component rendered under a chat answer to a product question: one section per product hypothesis (library evidence tags, CJ Dropshipping listings, Alibaba via Agent Reach), a decision-report builder, and an offer to start the full governed research run and hand it to the person's own agent. [DERIVED] — doc comment frontend-v2/src/components/ProductResearch.tsx:15-21.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ProductHandlers` | interface | `{ onRunStarted?: (run: ProductRunRef) => void; onOpenResearch?: (runId: string) => void; onReportStarted?: (report: ProductReportRef) => void }` | frontend-v2/src/components/ProductResearch.tsx:23-30 | frontend-v2/src/components/_small-modules |
| `ProductResearch` | function (React component) | `({ data, cites, run = null, report = null, question = "", ...ProductHandlers }) -> JSX.Element \| null` | frontend-v2/src/components/ProductResearch.tsx:32-64 | frontend-v2/src/components/_small-modules |

Internal (not exported): `Hypothesis` 66-95, `CjFinds` 97-124, `CjCard` 126-161, `ReachPanel` 165-205, `Offer` 209-265. [DERIVED]

## contracts

`ProductResearch`
- in: `data: ProductResearchResult | null | undefined`, `cites: Map<string, CiteInfo>`, `run?: ProductRunRef | null` (default `null`), `report?: ProductReportRef | null` (default `null`), `question?: string` (default `""`) — frontend-v2/src/components/ProductResearch.tsx:32-41. [DERIVED]
- out: `null` when `productView(data)` is falsy — frontend-v2/src/components/ProductResearch.tsx:42-44; else `<section className="pr" data-contract={v.contract || undefined}>` — frontend-v2/src/components/ProductResearch.tsx:47. [DERIVED]
- pre: `cites` should contain an entry per hypothesis tag; missing tags resolve to `cites.get(tag)` → `undefined` passed to `CiteRef` — frontend-v2/src/components/ProductResearch.tsx:78. [INFERRED: no guard, `get` may return undefined]
- post: a started run is reported via `onRunStarted(r)` so Chat keeps it on the turn — frontend-v2/src/components/ProductResearch.tsx:25, 229; the report id via `onReportStarted` forwarded to `BuildReport` — frontend-v2/src/components/ProductResearch.tsx:60. [DERIVED]

`ProductHandlers.onRunStarted` — "The run started from the offer: Chat keeps it on the turn, so it persists with the chat." — frontend-v2/src/components/ProductResearch.tsx:24-25. [DERIVED]

## effect surface
- Network: `api.adapterStart({ adapter_id: offer.adapterId, input: offer.input })` — frontend-v2/src/components/ProductResearch.tsx:225. [DERIVED]
- Remote images: `<img src={item.image} ... loading="lazy" referrerPolicy="no-referrer">` — frontend-v2/src/components/ProductResearch.tsx:134-135. [DERIVED]
- Clock: `Date.now()` on run start — frontend-v2/src/components/ProductResearch.tsx:227. [DERIVED]
- File: imports `"../styles/product.css"` — frontend-v2/src/components/ProductResearch.tsx:13. [DERIVED]
- Postgres/Qdrant/subprocess/env: none (FACTS `tables_read`/`tables_written`/`constants` empty).

## invariants
INVARIANT: render output is null ⇔ `productView(data)` falsy — frontend-v2/src/components/ProductResearch.tsx:42-44 [DERIVED]
  fails-if: bad data renders nothing, silently — no error surface.
INVARIANT: displayed run = `kept ?? local`, where `kept` requires `typeof run.run_id === "string" && run.run_id` — frontend-v2/src/components/ProductResearch.tsx:216-217 [DERIVED]
  fails-if: a ref with non-string/empty `run_id` is dropped and the Start button reappears.
INVARIANT: server reply accepted only when `typeof ref.run_id === "string" && ref.run_id` — frontend-v2/src/components/ProductResearch.tsx:226 [DERIVED]
  fails-if: malformed reply would render a "started run" with no id.
INVARIANT: `sending.current` is true for the entire `start()` — frontend-v2/src/components/ProductResearch.tsx:220-233 [DERIVED]
  fails-if: a double click issues two `api.adapterStart` calls (two runs).
INVARIANT: failed image → placeholder `No photo`, never a broken icon — frontend-v2/src/components/ProductResearch.tsx:127, 133-137 [DERIVED]
  fails-if: broken-image glyph in the CJ card grid.

## determinism & idempotency
determinism: NONDETERMINISTIC (network `api.adapterStart` — frontend-v2/src/components/ProductResearch.tsx:225; clock `Date.now()` — :227; remote image loads — :134-135; user clicks — :219, :248)
idempotency: UNSAFE (every Start click calls `api.adapterStart`; the `sending.current` guard is per-click only — frontend-v2/src/components/ProductResearch.tsx:215, 219-221; re-click is only prevented afterwards because the started panel replaces the button — :243-254)

## failure behaviour
- `Offer.start` wraps the whole call in try/catch: `catch (e) { setError(startErrorWords(e)); }`, `finally { sending.current = false; setBusy(false); }` — frontend-v2/src/components/ProductResearch.tsx:230-234. Caller sees `<div className="banner banner--bad" role="alert">Couldn't start the full research. {error}</div>` and Start stays available — :262, :292-294. [DERIVED]
- Missing id: `throw new Error("the server's reply names no run (no run_id)")` — frontend-v2/src/components/ProductResearch.tsx:226 — swallowed by the same catch into the banner. [DERIVED]
- Image load failure: `onError={() => setBroken(true)}` → `<div ...>No photo</div>` placeholder — frontend-v2/src/components/ProductResearch.tsx:135, 137. [DERIVED]
- No error codes raised; FACTS lists no fallbacks.

## dumb-code flags
- `run_id` validity rule written twice in inverse forms: `typeof run.run_id === "string" && run.run_id` (frontend-v2/src/components/ProductResearch.tsx:216) vs `typeof ref.run_id !== "string" || !ref.run_id` (:226). [DERIVED]
- Literal `CJ Dropshipping` repeated 3×: `aria-label="CJ Dropshipping listings"` (:110), `<span className="pr-src__name">CJ Dropshipping</span>` (:138), alt `"CJ Dropshipping product photo"` (:134). [DERIVED]
- sr-only literal `(opens in a new tab)` duplicated at :154 and :189. [DERIVED]
- Fallback title `"Untitled listing"` inline at :140; fallback alt text inline at :134. [DERIVED]
- `price = item.discount || item.price`; original struck through only when both `discount` and `price` exist — frontend-v2/src/components/ProductResearch.tsx:128, 143-145. [DERIVED]

## refactor notes
- `ProductHandlers` and `ProductResearch` are consumed by `frontend-v2/src/components/_small-modules` (FACTS.importers) — renaming props/callbacks ripples there. [DERIVED]
- View construction is delegated: `productView`, `cjStatus`, `cjEmptyWords`, `agentPrompt`, `httpUrl`, `startErrorWords` plus types `HypothesisView`, `ItemView`, `OfferView`, `ProductRunRef`, `ProductView`, `ReachView` all come from `../lib/productResearch` — frontend-v2/src/components/ProductResearch.tsx:5-7, 42. Changing `ProductResearchResult` in `../lib/contracts` hits :3/:33. [DERIVED]
- `BuildReport` (./ProductReport) receives `view`, `question`, `report`, `onReportStarted` — `ProductView` is the shared currency — frontend-v2/src/components/ProductResearch.tsx:60. [DERIVED]
- `cites` keys must match hypothesis tags (`cites.get(tag)`) — contract with ./Citations `CiteRef`/`CiteInfo` — frontend-v2/src/components/ProductResearch.tsx:46, 78. [DERIVED]
- Class names `pr*`, `pill`, `banner`, `btn`, `linklike`, `mono` are bound to `../styles/product.css` — frontend-v2/src/components/ProductResearch.tsx:13. [DERIVED]

## VERIFY
```verify
grep -Fq 'export interface ProductHandlers' frontend-v2/src/components/ProductResearch.tsx
grep -Fq 'if (!v) return null;' frontend-v2/src/components/ProductResearch.tsx
grep -Eq 'names no run \(no run_id\)' frontend-v2/src/components/ProductResearch.tsx
grep -Fq 'api.adapterStart({ adapter_id: offer.adapterId, input: offer.input })' frontend-v2/src/components/ProductResearch.tsx
grep -Fq 'const kept = run && typeof run.run_id === "string" && run.run_id ? run : null;' frontend-v2/src/components/ProductResearch.tsx
test "$(grep -c -F 'useState' frontend-v2/src/components/ProductResearch.tsx)" -ge 3
! grep -Fq 'useEffect' frontend-v2/src/components/ProductResearch.tsx
```
