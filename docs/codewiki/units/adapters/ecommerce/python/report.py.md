# unit: adapters/ecommerce/python/report.py
anchor: adapters/ecommerce/python/report.py:1-2291

## purpose
Report layer over canonical state for the ecommerce adapter: `build` makes a deterministic ReportModel JSON from the work state + SQLite (no LLM), `render` turns a ReportModel into self-contained HTML (no external assets, light+dark), `decision` runs `unit_economics.compute(bundle, policy)` and renders the DECISION layout. The same ReportModel/render path serves governed run journals (docs/27) — there is no second report system. report.py:2-28 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| build_model | def | (state: dict) -> dict | report.py:48-117 | CLI `build` (report.py:13) |
| build_model_from_governed | def | (journal: dict) -> dict | report.py:186-393 | governed run pipeline (docs/27) |
| build_model_from_bundle | def | (decision, verdicts, admission, meta) -> dict | report.py:1018-1038 | CLI `decision` path (§4.4/§4.5) |
| render | def | (model, layout, summary_md) -> HTML | report.py:1924-2193 | CLI `render` (report.py:14-15) |
| decision_page | def | (bundle_path, out, decision_out) | report.py:2209-2244 | CLI `decision` (report.py:16) |
| safe_url | def | (value) -> str \| None | report.py:639-647 | — |
| main | def | () -> None | report.py:2247-2286 | CLI entry |

No FACTS importers listed; "used by" is — elsewhere.

## contracts

**build_model(state)** — report.py:48-117
- in: `state` dict; requires `state["data"]`, `state["run_id"]`, `state["rounds"]` (direct indexing at report.py:49, :57, :113 — KeyError if missing) [DERIVED]
- out: ReportModel with keys `run, coverage, independence, bridges, l4_receipts, quotes, mechanisms, leads, product_concepts, sourcing_coverage, utilization, provenance, excluded_leads, corpus_packets, corpus_answers, held_rejected, unresolved, intelligence, market_discovery, product_anchored, capability_failures, settings, audit, built_at` — report.py:63-116 [DERIVED]
- post: `quotes` capped `[:14]` (report.py:82); `unresolved` capped `[:8]` (report.py:97); `signal` truncated `[:600]` (report.py:66) [DERIVED]
- pre: θ's executive summary may come ONLY from the ReportModel via `--summary FILE.md`; no new facts during presentation — report.py:8-11 [DERIVED]

**build_model_from_governed(journal)** — report.py:186-393
- in: journal dict with `events` of kinds `step`, `submission`, `result` — report.py:190-193 [DERIVED]
- pre/post: deterministic given the journal; reads nothing else — report.py:187-189 [DERIVED]
- post: `verdict` is one of `"GOVERNED GAP — {code}"`, `"GOVERNED RUN {CANCELLED|FAILED}"`, `"GOVERNED — TRAIL SCORED"`, `"GOVERNED — TRAIL REFUSED TO SCORE"`, `"GOVERNED — COMPLETED WITHOUT A SCORE"` — report.py:284-288 [DERIVED]
- post: TrailSignal's record shown VERBATIM (score, confidence, coverage gaps, refusal reason); nothing re-ranked; standalone `evidence_score` never appears — report.py:18-22 [DERIVED]

**render(model, layout, summary_md)** — report.py:1924-2193
- in: `layout` one of `FULL_RESEARCH|SOURCING|EXECUTIVE|COMMERCIAL|DECISION` (report.py:15); `summary_md` optional [DERIVED]
- out: self-contained HTML, no external assets, light + dark (`@media (prefers-color-schem…` in `_CSS`, report.py:1042) [DERIVED]

**decision_page(bundle_path, out, decision_out)** — report.py:2209-2244
- in: `bundle.json` path; writes `out` HTML and `decision_out` JSON — report.py:16, report.py:2209 [DERIVED]
- behaviour: ONE engine process loads the policy, calls `unit_economics.compute(bundle, policy)`, builds the page — report.py:2209 (FACTS doc) [DERIVED]
- post: every number is the engine's, each with its receipt; a missing number renders as UNKNOWN, never blank, never guessed — report.py:24-27 [DERIVED]

**safe_url(value)** — report.py:639-647
- in: any value; out: the value when an http(s) URL with a host, else None (then shown as text) — report.py:639-647 (FACTS doc) [DERIVED]

## effect surface
- SQLite via `memory.connect()`: reads table `events` — `SELECT sequence, event_type, created_at FROM events WHERE run_id=? ORDER BY sequence` — report.py:52-57; FACTS `tables_read: ["events"]`, `tables_written: []` [DERIVED]
- Files read (CLI): `--state candidates/run.json`, `--model model.json`, `--summary sum.md`, `--bundle bundle.json` — report.py:13-16 [DERIVED]
- Files written (CLI): `--out model.json` (build) / `report.html` (render, decision), `--decision-out decision.json` — report.py:13-16 [DERIVED]
- Local imports `graph` (as `graphmod`), `models`, `adapter_receipt.polarity_for` after `sys.path.insert(0, dir-of-file)` — report.py:41-44 [DERIVED]
- No network calls, subprocesses or env flags visible in the material.

## invariants
INVARIANT: quotes count ≤ 14 — report.py:82 [DERIVED]
  fails-if: more than 14 observation quotes reach the model page.
INVARIANT: unresolved count ≤ 8 — report.py:97 [DERIVED]
  fails-if: more than 8 open-gap questions listed.
INVARIANT: signal length ≤ 600 chars — report.py:66 [DERIVED]
INVARIANT: distinct-question key = whitespace-squashed, lowercased, first 380 chars — report.py:142 [DERIVED]
INVARIANT: DELIVERY_VERDICTS = `["PASS", "WARN", "FAIL", "UNKNOWN"]` — report.py:600 [DERIVED]
INVARIANT: AGENT_VERDICT_MAX_CHARS = 1200 — report.py:604 [DERIVED]
INVARIANT: REDDIT_COMMENTS_SHOWN = 5 and REDDIT_EXCLUDED_SHOWN = 5 — report.py:605-606 [DERIVED]
INVARIANT: MAX_URL_CHARS = 2048 — report.py:636 [DERIVED]
INVARIANT: NOT_READ_ORDER = `["BLOCKED", "HUMAN_CHECK", "EMPTY"]` — report.py:619 [DERIVED]
INVARIANT: DECISION_CLI_ERRORS has 5 codes (`DECISION_BUNDLE_UNREADABLE, DECISION_BUNDLE_INVALID, UNIT_ECONOMICS_UNAVAILABLE, POLICY_UNAVAILABLE, UNIT_ECONOMICS_FAILED`) — report.py:2197 [DERIVED]
INVARIANT: layout enum = `FULL_RESEARCH|SOURCING|EXECUTIVE|COMMERCIAL|DECISION` with `DECISION_LAYOUT = "DECISION"` — report.py:15, report.py:594 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (`built_at` timestamp `models.now()` report.py:116; `events` audit count depends on SQLite state report.py:52-59; build path otherwise documented "no LLM anywhere in this path — everything reproducible" report.py:4-5 and "Deterministic given the journal" report.py:187)
idempotency: SAFE (pure model construction over its input; output files are overwritten via `--out`/`--decision-out` report.py:13-16; no tables written per FACTS)

## failure behaviour
- `build_model`: any Exception around `memory.connect()`/SELECT is SWALLOWED with `pass` → `events = []`, `audit.events = 0`; caller sees a complete model with zero events — report.py:52-59, FACTS fallback line 58 [DERIVED]
- `_governed_decision`: Exception handled with two assigns (degraded fields), caller still gets a decision section — report.py:484, FACTS fallback [DERIVED]
- `decision_page`: Exception while loading policy → swallowed, returns `fail('POLICY_UNAVAILABLE', exc)` — report.py:2229 [DERIVED]; Exception in compute → swallowed, returns `fail('UNIT_ECONOMICS_FAILED', exc)` — report.py:2233 [DERIVED]
- Failure and holds are shown on the page — "a report is not sales copy" — report.py:10-11 [DERIVED]

## dumb-code flags
- O(n²) dedup inside the packet loop: `not any(p["id"] == f"{…}#{…}" for p in packets)` rescans the growing list per receipt — report.py:307 [DERIVED]
- `_context_field` re-implements the binding's tolerant reader (`binding._context_field`) — duplicated parsing logic — report.py:156-160 [DERIVED]
- Dual lead path in `build_model_from_governed`: metric-derived `leads` built at report.py:292-303, then wholly replaced when the result carries `sourcing_coverage` (report.py:320-327) — dead work for consolidation-migration results [INFERRED: the replacement makes the first construction unreachable for those results]
- Stage sort fallback bucket `2` for any stage not `market_delta`/`supply` — silent ordering catch-all — report.py:133-134 [DERIVED]
- `corpus_answers` kept only for LEGACY (< v2.2.0) runs — a synthesis, not evidence — report.py:94 [DERIVED]

## refactor notes
- CLI flags and the layout enum are the public contract (`--state/--model/--out/--layout/--summary/--bundle/--decision-out`) — renaming breaks every caller — report.py:13-16 [DERIVED]
- ReportModel key set (report.py:63-116) is consumed by `render` and by θ's `--summary` path (report.py:8-9) — schema changes require updating render, both builders, and external summary writers [DERIVED]
- `sys.path.insert(0, …)` before local imports (report.py:41-44) — relocating the file breaks `graph`/`models`/`adapter_receipt` imports [DERIVED]
- Governed display law: TrailSignal verdict verbatim, no re-ranking, no standalone `evidence_score` (report.py:18-22) — any render change must preserve it [DERIVED]
- Decision law: every number from unit_economics with a receipt, missing → UNKNOWN (report.py:24-27); `BEST_CHANNEL_RULE` wording (report.py:630) must match `_best_channel` behaviour (report.py:706-720) [DERIVED]
- New `fail(...)` codes in `decision_page` must be added to `DECISION_CLI_ERRORS` — report.py:2197, report.py:2229-2233 [INFERRED: the list names exactly the codes the CLI can emit]

## VERIFY
```verify
grep -Fq 'SELECT sequence, event_type, created_at FROM events WHERE run_id=?' adapters/ecommerce/python/report.py
grep -Fq 'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))' adapters/ecommerce/python/report.py
grep -Fq 'from adapter_receipt import polarity_for' adapters/ecommerce/python/report.py
grep -Fq '"built_at": models.now(),' adapters/ecommerce/python/report.py
grep -Fq 'def build_model_from_governed(journal: dict) -> dict:' adapters/ecommerce/python/report.py
grep -Fq 'stage_order = {"market_delta": 0, "supply": 1}' adapters/ecommerce/python/report.py
! grep -Fq 'INSERT INTO' adapters/ecommerce/python/report.py
test "$(grep -c -F 'GOVERNED' adapters/ecommerce/python/report.py)" -ge 5
```
