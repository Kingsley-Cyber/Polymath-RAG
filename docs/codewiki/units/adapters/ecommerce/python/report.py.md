# unit: adapters/ecommerce/python/report.py
anchor: adapters/ecommerce/python/report.py:1-2298

(anchors below: `report.py:NN` = adapters/ecommerce/python/report.py:NN)

## purpose
- Report layer: `build` produces a deterministic ReportModel JSON from work state + SQLite — "no LLM anywhere in this path — everything reproducible"; `render` turns a ReportModel into "self-contained HTML (no external assets; light+dark)". report.py:2-7 [DERIVED]
- Three entry modes: CLI build/render; governed runs (docs/27) via `build_model_from_governed`; DECISION reports via `build_model_from_bundle` + `render(model, "DECISION")`. report.py:13-28 [DERIVED]
- Laws: "reports never affect the research verdict"; no new facts during presentation; "failures and holds are shown — a report is not sales copy". report.py:8-11 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| build_model | def | state: dict -> dict | report.py:48-117 | CLI `report.py build` (report.py:13); no FACTS importers |
| build_model_from_governed | def | journal: dict -> dict | report.py:186-393 | governed run path, docs/27 (report.py:18-19) |
| build_model_from_bundle | def | decision -> dict | report.py:1020-1040 | DECISION reports (report.py:24-26) |
| render | def | model, layout, summary_md -> self-contained HTML | report.py:1936-2205 | CLI `report.py render` (report.py:14-15) |
| decision_page | def | bundle_path, out, decision_out -> page build or fail(...) | report.py:2221-2256 | CLI `report.py decision` (report.py:16) |
| main | def | () -> CLI dispatch | report.py:2259-2298 | argparse entry (argparse imported report.py:32) |

All other FACTS symbols are `_`-private helpers. Module depends on `graph as graphmod`, `models`, `adapter_receipt.polarity_for` via `sys.path.insert(0, dirname(__file__))`. report.py:41-44

## contracts

build_model(state) — report.py:48-117
- in: `state["data"]` with hypotheses/observations/mechanisms/gaps (report.py:60-62, 80-83, 97); `state["run_id"]`, `["status"]`, `["rounds"]` (report.py:57, 63-68, 113-114).
- effect: optional SQLite read of `events` for the run, `ORDER BY sequence` (report.py:52-59).
- out: ReportModel dict; hard caps signal `[:600]`, quotes `[:14]`, unresolved `[:8]`; `built_at` = `models.now()` (report.py:66, 80-82, 97, 116).
- post: `audit` counts observations, unique sources, queries, research rounds, events, hypotheses (report.py:110-115).

build_model_from_governed(journal) — report.py:186-393
- pre: "Deterministic given the journal; reads nothing else" (report.py:187-189).
- in: journal events of kind `step` / `submission` / `result`; AdapterResultV1 output is authoritative; receipts joined by `(action_id, observation_id)` (report.py:190-211).
- out: same ReportModel; verdict literals `"GOVERNED — TRAIL SCORED"`, `"GOVERNED — TRAIL REFUSED TO SCORE"`, `"GOVERNED — COMPLETED WITHOUT A SCORE"`, `"GOVERNED GAP — {code}"` (report.py:285-288).
- post: field-count provenance labeled `field_counts_from` ∈ {`"ADMISSIONS"`, `"STEP_CONTEXT"`, `"VIEW_SAMPLE"`} (report.py:238, 268, 280).

build_model_from_bundle(decision) — report.py:1020-1040
- in: the decision model `unit_economics.compute(bundle, policy)` returns (plan §4.4) (FACTS doc, report.py:1020; report.py:24-26).
- post: "Every number on that page is the unit-economics engine's (each with its receipt)"; a missing number is UNKNOWN — "never blank, never guessed" (report.py:26-27).

render(model, layout, summary_md) — report.py:1936-2205
- in: layout ∈ FULL_RESEARCH|SOURCING|EXECUTIVE|COMMERCIAL|DECISION (report.py:15); `DECISION_LAYOUT = "DECISION"` (report.py:594, FACTS).
- pre: an executive summary may come ONLY "from the ReportModel" via `--summary FILE.md` (report.py:9-10).
- out: one self-contained HTML page; embedded stylesheet handles light+dark (`_CSS` starts `@media (prefers-color-schem…`, report.py:1044, FACTS).

decision_page(bundle_path, out, decision_out) — report.py:2221-2256
- behaviour: "ONE engine process loads the policy, calls `unit_economics.compute(bundle, policy)` (plan §4.4)" (FACTS doc, report.py:2221).
- out: writes `report.html` and a decision JSON (`--decision-out`, report.py:16); failures surface as codes in DECISION_CLI_ERRORS (report.py:2209, FACTS).

## effect surface
- SQLite (via `memory.connect()`): table `events` READ — `SELECT sequence, event_type, created_at FROM events WHERE run_id=? ORDER BY sequence` (report.py:55-57; FACTS tables_read). Tables written: none (FACTS tables_written = []).
- Files (CLI contract): reads `--state candidates/run.json`, `--model model.json`, `--bundle bundle.json`; writes `--out model.json` / `report.html` and `--decision-out decision.json` (report.py:13-16).
- Network / subprocess / env flags: none visible in FACTS or shown source.

## invariants
INVARIANT: quotes rows ≤ 14 (`[:14]`) — report.py:80-82 [DERIVED]
  fails-if: page renders more quote rows than consumers budget for.
INVARIANT: unresolved questions ≤ 8 (`[:8]`) — report.py:97 [DERIVED]
  fails-if: open-gap list silently grows past the display budget.
INVARIANT: signal length ≤ 600 chars (`[:600]`) — report.py:66 [DERIVED]
  fails-if: header text truncated without notice.
INVARIANT: distinct-question key = whitespace-normalized `[:380]` lowercase — report.py:142 [DERIVED]
  fails-if: questions differing only past char 380 collapse into one.
INVARIANT: qualification stage order market_delta(0) before supply(1) — report.py:133-134 [DERIVED]
  fails-if: supply rows overtake market delta in the manifest.
INVARIANT: delivery verdict ∈ ["PASS", "WARN", "FAIL", "UNKNOWN"] — report.py:600 (FACTS DELIVERY_VERDICTS) [DERIVED]
  fails-if: a new engine verdict renders blank instead of UNKNOWN.
INVARIANT: MAX_URL_CHARS = 2048, AGENT_VERDICT_MAX_CHARS = 1200, REDDIT_COMMENTS_SHOWN = REDDIT_EXCLUDED_SHOWN = 5 — report.py:638, 604-606 (FACTS) [DERIVED]
  fails-if: clipped lists stop declaring themselves via `_showing` (report.py:1220, FACTS: "the ReportModel keeps every item").
INVARIANT: events rows ordered by `sequence` — report.py:57 [DERIVED]
  fails-if: run timeline renders out of order.
INVARIANT: per-hypothesis field counts come from ADMISSIONS when any admission exists (never "the derived view's 24-row sample") — report.py:228-238 [DERIVED]
  fails-if: counts silently fall back to `field_counts_from` STEP_CONTEXT/VIEW_SAMPLE samples.

## determinism & idempotency
determinism: NONDETERMINISTIC (build_model stamps `built_at = models.now()` — report.py:116; the events read depends on the `memory` module/DB being reachable — report.py:52-59). build_model_from_governed is DETERMINISTIC "given the journal; reads nothing else" — report.py:187-189. [DERIVED]
idempotency: SAFE (no DB writes; outputs are fresh JSON/HTML files per `--out` / `--decision-out` — report.py:13-16). [DERIVED]

## failure behaviour
- report.py:58-59 — `except Exception: pass` around the events query: swallowed; caller receives a normal model with no events and `audit.events` 0. [DERIVED]
- report.py:484 — inside `_governed_decision`, an Exception is handled by two assignments (FACTS fallbacks "handled: assign, assign"); the section itself is None "when the run admitted no supplier lead" (FACTS doc, report.py:471). [DERIVED]
- report.py:2241 — `return fail('POLICY_UNAVAILABLE', exc)`: swallowed into a fail result (FACTS fallbacks). [DERIVED]
- report.py:2245 — `return fail('UNIT_ECONOMICS_FAILED', exc)`: same (FACTS fallbacks). [DERIVED]
- Error vocabulary DECISION_CLI_ERRORS = ["DECISION_BUNDLE_UNREADABLE", "DECISION_BUNDLE_INVALID", "UNIT_ECONOMICS_UNAVAILABLE", "POLICY_UNAVAILABLE", "UNIT_ECONOMICS_FAILED"] — report.py:2209 (FACTS). [DERIVED]

## dumb-code flags
- Caps inlined as literals in build_model (600 / 14 / 8 — report.py:66, 82, 97) while sibling caps are named constants (AGENT_VERDICT_MAX_CHARS etc. — report.py:604-606, FACTS): two styles for the same kind of knob. [DERIVED]
- Three overlapping source lists: LINK_SOURCES (cj, alibaba, amazon, ebay, reddit), MARKETS (amazon, ebay), AGENT_REACH_SOURCES (reddit, amazon, alibaba, ebay) — report.py:612, 613, 617 (FACTS). [DERIVED]
- "UNKNOWN" spelled three ways: `_unknown` predicate (report.py:652, FACTS), `_UNK` = `"<span class='unk'>UNKNOWN</span>"` (report.py:1459, FACTS), docstring rule (report.py:27). Rename risk. [DERIVED]
- Full stylesheets as Python strings: `_CSS` (report.py:1044) and `_DECISION_CSS` (report.py:1430) (FACTS). [DERIVED]
- FACTS truncates several constant values mid-string (CHANNELS 596, INBOUND_RULES 629, BEST_CHANNEL_RULE 632, NEEDS_LOCAL_AGENT 618, ASSUMPTION_RULES 870, _MARKS 1106): full text unverified here — read the file before editing them. [DERIVED]

## refactor notes
- Sibling-import coupling: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then `import graph as graphmod`, `import models`, `from adapter_receipt import polarity_for` (report.py:41-44) — the file must stay next to those modules.
- One report system: all three builders must keep the SAME ReportModel shape because the SAME `render` draws all of them (report.py:18-19, 24-26). Key renames break three builders plus the HTML.
- CLI layout names are a public contract (FULL_RESEARCH|SOURCING|EXECUTIVE|COMMERCIAL|DECISION — report.py:15); `DECISION_LAYOUT = "DECISION"` (report.py:594, FACTS).
- DECISION_CLI_ERRORS is a caller-facing vocabulary used by decision_page's fail returns (report.py:2209, 2241, 2245, FACTS).
- Schema dependency on `events` columns (sequence, event_type, created_at, run_id) — report.py:55-57.
- `polarity_for` from adapter_receipt drives governed field counts (report.py:44, 237): signature changes alter field_supporting / field_contradicting.
- BEST_CHANNEL_RULE prose documents `_best_channel` behavior (report.py:632 FACTS; function report.py:708-722 FACTS): text and code must stay in sync.

## VERIFY
```verify
grep -Fq 'def build_model(state: dict) -> dict:' adapters/ecommerce/python/report.py
grep -Fq 'SELECT sequence, event_type, created_at FROM events WHERE run_id=? ' adapters/ecommerce/python/report.py
grep -Fq 'stage_order = {"market_delta": 0, "supply": 1}' adapters/ecommerce/python/report.py
grep -Fq '"built_at": models.now(),' adapters/ecommerce/python/report.py
grep -Eq 'GOVERNED . TRAIL (SCORED|REFUSED TO SCORE)' adapters/ecommerce/python/report.py
grep -Fq 'DECISION_CLI_ERRORS' adapters/ecommerce/python/report.py
test "$(grep -c -F '[:14]' adapters/ecommerce/python/report.py)" -ge 1
```
