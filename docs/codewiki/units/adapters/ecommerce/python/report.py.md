# unit: adapters/ecommerce/python/report.py
anchor: adapters/ecommerce/python/report.py:1-2331

## purpose
Report layer over canonical state — "Facts frozen, prose optional" (adapters/ecommerce/python/report.py:2). Builds a ReportModel JSON from three inputs — work state + SQLite (`build`), a governed run journal (docs/27), or a unit_economics decision bundle (§4.4) — then renders self-contained HTML (no external assets; light+dark) (adapters/ecommerce/python/report.py:4-28). Laws: reports never affect the research verdict; θ may write an executive summary ONLY from the ReportModel (`--summary FILE.md`); no new facts during presentation; failures and holds are shown (adapters/ecommerce/python/report.py:8-11). Governed dossiers show TrailSignal's record VERBATIM — nothing re-ranked, `evidence_score` never appears (adapters/ecommerce/python/report.py:18-22).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| build_model | def | (state: dict) -> dict | adapters/ecommerce/python/report.py:48-117 | CLI `build` (:13) [INFERRED — main body not shown] |
| build_model_from_governed | def | (journal: dict) -> dict | adapters/ecommerce/python/report.py:186-393 | governed dossier path (:18) |
| build_model_from_bundle | def | (decision) -> dict | adapters/ecommerce/python/report.py:1028-1048 | decision_page (:2249) |
| render | def | (model, layout, summary_md) -> HTML | adapters/ecommerce/python/report.py:1964-2233 | CLI `render` (:14-15) [INFERRED] |
| decision_page | def | (bundle_path, out, decision_out) -> ? | adapters/ecommerce/python/report.py:2249-2284 | CLI `decision` (:16) [INFERRED] |
| safe_url | def | (value) -> str \| None | adapters/ecommerce/python/report.py:645-653 | — |
| main | def | () -> ? | adapters/ecommerce/python/report.py:2287-2326 | CLI entry |

No FACTS.importers given; "used by" beyond the module's own CLI docstring is unknown.

## contracts

**build_model(state)** — adapters/ecommerce/python/report.py:48-117
- in: `state` dict with `run_id`, `data` (`hypotheses`, `observations`, `mechanisms`, `gaps`), `rounds`; optional `satisfaction`, `settings`, `l4_receipts` — adapters/ecommerce/python/report.py:49-50 [DERIVED]
- in: SQLite `events` rows for `run_id` via `memory.connect()`; any failure swallowed → `events = []` — adapters/ecommerce/python/report.py:52-59 [DERIVED]
- out: ReportModel dict; `quotes` capped `[:14]`, `unresolved` capped `[:8]`, `signal` capped `[:600]`, `built_at = models.now()` — adapters/ecommerce/python/report.py:66,82,97,116 [DERIVED]
- pre: `state["data"]`, `state["run_id"]`, `state["rounds"]` accessed without guards — KeyError if missing — adapters/ecommerce/python/report.py:49,64,113 [DERIVED]

**build_model_from_governed(journal)** — adapters/ecommerce/python/report.py:186-393
- in: journal dict with `events` of kinds `step`, `submission`, `result`; adapter's AdapterResultV1 is the authority; receipts joined by `(action_id, observation_id)` — adapters/ecommerce/python/report.py:187-189,190-193,210 [DERIVED]
- out: same ReportModel; verdict is one of `GOVERNED GAP — {code}`, `GOVERNED RUN {STATUS}`, `GOVERNED — TRAIL SCORED`, `GOVERNED — TRAIL REFUSED TO SCORE`, `GOVERNED — COMPLETED WITHOUT A SCORE` — adapters/ecommerce/python/report.py:286-288 [DERIVED]
- post: supplier name = who the LISTING names (`supplier:` in observation context), never the independence group (that is the platform/channel) — adapters/ecommerce/python/report.py:296-297,303 [DERIVED]
- post: hypothesis state precedence: result's derived semantic view → newest materials view shown the agent → four-field step context — adapters/ecommerce/python/report.py:248-258 [DERIVED]

**build_model_from_bundle(decision)** — adapters/ecommerce/python/report.py:1028-1048
- in: decision model from `unit_economics.compute(bundle, policy)` (plan §4.4) — adapters/ecommerce/python/report.py:24-26,1028 [DERIVED]
- post: missing numbers shown as UNKNOWN — never blank, never guessed — adapters/ecommerce/python/report.py:26-27 [DERIVED]

**render(model, layout, summary_md)** — adapters/ecommerce/python/report.py:1964-2233
- in: layouts `FULL_RESEARCH|SOURCING|EXECUTIVE|COMMERCIAL|DECISION`; summary only from the ReportModel — adapters/ecommerce/python/report.py:9-10,15 [DERIVED]
- out: self-contained HTML, no external assets — adapters/ecommerce/python/report.py:6 [DERIVED]

**decision_page(bundle_path, out, decision_out)** — adapters/ecommerce/python/report.py:2249-2284
- ONE engine process loads the policy, calls `unit_economics.compute(bundle, policy)`, writes HTML `out` and decision JSON `decision_out` — adapters/ecommerce/python/report.py:2249,13-16 [DERIVED]

## effect surface
| effect | detail | anchor |
|---|---|---|
| SQLite read | table `events`: `SELECT sequence, event_type, created_at FROM events WHERE run_id=? ORDER BY sequence` via `memory.connect()` | adapters/ecommerce/python/report.py:54-59 |
| SQLite written | none | FACTS `tables_written: []` |
| files read | `--state candidates/run.json`, `--model model.json`, `--bundle bundle.json`, policy (loaded in decision_page) | adapters/ecommerce/python/report.py:13-16,2249 |
| files written | `--out model.json` / `report.html`, `--decision-out decision.json` | adapters/ecommerce/python/report.py:13-16 |
| network / subprocess / env | none visible in FACTS or shown SOURCE | — |

## invariants
INVARIANT: DELIVERY_VERDICTS == ["PASS", "WARN", "FAIL", "UNKNOWN"] — adapters/ecommerce/python/report.py:600 [DERIVED]
  fails-if: verdict cells outside this set render as UNKNOWN (_unknown/:656).
INVARIANT: len(quotes) ≤ 14 in build_model output — adapters/ecommerce/python/report.py:82 [DERIVED]
  fails-if: more evidence quotes claimed than the model can carry.
INVARIANT: len(unresolved) ≤ 8 and len(signal) ≤ 600 chars — adapters/ecommerce/python/report.py:97,66 [DERIVED]
  fails-if: page shows more open gaps / signal text than the model froze.
INVARIANT: OFFER_MODELS == {"dropship": "Dropship", "inventory": "Inventory"} — adapters/ecommerce/python/report.py:630 [DERIVED]
  fails-if: a supply model key outside these two has no display label.
INVARIANT: MAX_URL_CHARS == 2048, AGENT_VERDICT_MAX_CHARS == 1200 — adapters/ecommerce/python/report.py:642,604 [DERIVED]
  fails-if: oversized URLs / agent verdicts break layout or are clipped inconsistently.
INVARIANT: REDDIT_COMMENTS_SHOWN == REDDIT_EXCLUDED_SHOWN == 5 — adapters/ecommerce/python/report.py:605-606 [DERIVED]
  fails-if: Reddit sections exceed their caps without a "showing" note (gap B-16, :1228).
INVARIANT: len(DECISION_CLI_ERRORS) == 5 — adapters/ecommerce/python/report.py:2237 [DERIVED]
  fails-if: a decision error path returns a code the CLI does not know.
INVARIANT: governed receipt join key is exactly (action_id, observation_id) — adapters/ecommerce/python/report.py:210,214 [DERIVED]
  fails-if: receipts fail to join; claim/quote/url fall back to empty.
INVARIANT: placeholder supplier names matching `(?:none|unknown|unresolved)\b` are treated as unnamed — adapters/ecommerce/python/report.py:166 [DERIVED]
  fails-if: placeholder text is displayed as a real supplier name (gap S-06).
INVARIANT: _distinct_questions dedup key = whitespace-normalized, first 380 chars, lowercased — adapters/ecommerce/python/report.py:142 [DERIVED]
  fails-if: duplicate questions reappear in open-gap lists.

## determinism & idempotency
determinism: NONDETERMINISTIC for `build_model` — `built_at = models.now()` (clock) and the optional SQLite `events` read (db presence) — adapters/ecommerce/python/report.py:52-59,116 [DERIVED]. `build_model_from_governed` claims "Deterministic given the journal; reads nothing else" — adapters/ecommerce/python/report.py:187-189 [DERIVED]. `render` is pure formatting of the model dict — [INFERRED: no clock/random/network in the shown helpers].
idempotency: SAFE — build paths write nothing; `decision_page` overwrites its two output files in one engine process — adapters/ecommerce/python/report.py:2249 [DERIVED].

## failure behaviour
| handler | behaviour | caller sees | anchor |
|---|---|---|---|
| `except Exception: pass` | events DB read swallowed | `events = []`, `audit.events` = 0 | adapters/ecommerce/python/report.py:58 |
| handled: assign, assign | _governed_decision fallback on exception | decision section None when no supplier lead admitted | adapters/ecommerce/python/report.py:484,160 |
| `return fail('POLICY_UNAVAILABLE', exc)` | swallowed, returns failure record | POLICY_UNAVAILABLE code | adapters/ecommerce/python/report.py:2269 |
| `return fail('UNIT_ECONOMICS_FAILED', exc)` | swallowed, returns failure record | UNIT_ECONOMICS_FAILED code | adapters/ecommerce/python/report.py:2273 |

Decision CLI error vocabulary: `["DECISION_BUNDLE_UNREADABLE", "DECISION_BUNDLE_INVALID", "UNIT_ECONOMICS_UNAVAILABLE", "POLICY_UNAVAILABLE", "UNIT_ECONOMICS_FAILED"]` — adapters/ecommerce/python/report.py:2237 [DERIVED].

## dumb-code flags
- Inline magic caps with no named constant: `[:600]` (:66), `[:14]` (:82), `[:8]` (:97), `[:380]` (:142), `[:160]` (:300) — adapters/ecommerce/python/report.py:66,82,97,142,300 [DERIVED]
- Layout names `FULL_RESEARCH|SOURCING|EXECUTIVE|COMMERCIAL|DECISION` exist only in the CLI docstring; only `"DECISION"` has a constant (DECISION_LAYOUT) — adapters/ecommerce/python/report.py:15,594 [DERIVED]
- `_UNK` embeds raw HTML with single quotes: `"<span class='unk'>UNKNOWN</span>"` — adapters/ecommerce/python/report.py:1468 [DERIVED]
- Contract-code literals repeated in helper docstrings rather than referencing constants: `SUPPLIER_TIER_BELOW_MARKET` (:613 vs :858,:869), `REQUIRES_US_STOCK` (:631 vs :1561) — adapters/ecommerce/python/report.py:613,858,869,631,1561 [DERIVED]
- Two same-valued caps kept as separate names (5 and 5) — adapters/ecommerce/python/report.py:605-606 [DERIVED]

## refactor notes
- `sys.path.insert(0, dirname(__file__))` then sibling imports `graph as graphmod`, `models`, `adapter_receipt.polarity_for` — moving this file or its siblings breaks all three imports — adapters/ecommerce/python/report.py:41-44 [DERIVED]
- `--layout` strings are a CLI-facing contract; renaming one breaks every caller passing it — adapters/ecommerce/python/report.py:15 [DERIVED]
- Governed rendering law: TrailSignal record VERBATIM, no re-ranking, `evidence_score` never shown — any change to `_render_governed` (:1342-1431) or `_row` (:213) must preserve this — adapters/ecommerce/python/report.py:18-22,1342-1431 [DERIVED]
- Receipts join key `(action_id, observation_id)` — schema changes to submission receipts silently blank claim/quote/url and the supplier leads built from them — adapters/ecommerce/python/report.py:210,214,293-303 [DERIVED]
- `DECISION_CLI_ERRORS` is the CLI error contract; renaming a `fail(...)` code desynchronizes it — adapters/ecommerce/python/report.py:2237,2269,2273 [DERIVED]
- `render` consumes the full ReportModel key set built by all three builders; dropping a build key blanks a section with no error — adapters/ecommerce/python/report.py:63-116,1964-2233 [INFERRED: render reads model keys, no schema guard visible]

## VERIFY
```verify
grep -Fq 'SELECT sequence, event_type, created_at FROM events WHERE run_id=?' adapters/ecommerce/python/report.py
grep -Fq 'GOVERNED — TRAIL REFUSED TO SCORE' adapters/ecommerce/python/report.py
grep -Fq 'SUPPLIER_TIER_BELOW_MARKET' adapters/ecommerce/python/report.py
grep -Fq 'DECISION_BUNDLE_UNREADABLE' adapters/ecommerce/python/report.py
grep -Fq 'from adapter_receipt import polarity_for' adapters/ecommerce/python/report.py
test "$(grep -c -F 'def _render' adapters/ecommerce/python/report.py)" -ge 8
test "$(grep -c -F 'UNIT_ECONOMICS_FAILED' adapters/ecommerce/python/report.py)" -ge 2
```
