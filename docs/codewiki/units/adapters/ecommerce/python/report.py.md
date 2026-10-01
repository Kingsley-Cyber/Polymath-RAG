# unit: adapters/ecommerce/python/report.py
anchor: adapters/ecommerce/python/report.py:1-1171

## purpose
Report layer for the ecommerce adapter: freezes canonical run state into a ReportModel JSON (`build`, no LLM in the path) and renders it to one self-contained HTML file (`render`, no external assets, light+dark) — adapters/ecommerce/python/report.py:2-6 [DERIVED]. A second entry point, `build_model_from_governed`, builds the SAME ReportModel from a governed run journal (docs/27); TrailSignal's verdict and per-hypothesis numbers are shown VERBATIM, nothing re-ranked — adapters/ecommerce/python/report.py:17-21 [DERIVED]. Laws (docs/05 §13-22): reports never affect the research verdict; no new facts during presentation; failures and holds are shown — adapters/ecommerce/python/report.py:8-11 [DERIVED]. Consumers: CLI `main()` and readers of `model.json` / `report.html` — adapters/ecommerce/python/report.py:13-15, 1132-1166 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| build_model | def | (state: dict) -> dict | adapters/ecommerce/python/report.py:40-109 | — |
| build_model_from_governed | def | (journal: dict) -> dict | adapters/ecommerce/python/report.py:178-381 | — |
| render | def | (model, layout, summary_md) -> HTML | adapters/ecommerce/python/report.py:865-1129 | — |
| main | def | () -> exit | adapters/ecommerce/python/report.py:1132-1166 | — |

All other symbols are underscore-private helpers (FACTS.symbols). `render` is shared by both build paths — "there is no second report system" — adapters/ecommerce/python/report.py:17-18 [DERIVED].

## contracts

**build_model(state: dict) -> dict — adapters/ecommerce/python/report.py:40-109**
- in required: `state["run_id"]`, `state["status"]`, `state["rounds"]["research"]`, `state["data"]` with `hypotheses`, `observations`, `mechanisms`, `gaps` — adapters/ecommerce/python/report.py:41, 52-54, 78, 89, 105 [DERIVED]
- in optional: `satisfaction`, `created_at`, `verdict`, `corpus`, `l4_receipts`, `settings`, `capability_failures` — adapters/ecommerce/python/report.py:42, 56-59, 71, 93-94 [DERIVED]
- side read: `SELECT sequence, event_type, created_at FROM events WHERE run_id=? ORDER BY sequence` via `memory.connect()` — adapters/ecommerce/python/report.py:46-49 [DERIVED]
- out: ReportModel with keys `run, coverage, independence, bridges, l4_receipts, quotes, mechanisms, leads, product_concepts, sourcing_coverage, utilization, provenance, excluded_leads, corpus_packets, corpus_answers, held_rejected, unresolved, intelligence, market_discovery, product_anchored, capability_failures, settings, audit, built_at` — adapters/ecommerce/python/report.py:55-108 [DERIVED]
- post: `built_at = models.now()` — adapters/ecommerce/python/report.py:108 [DERIVED]

**build_model_from_governed(journal: dict) -> dict — adapters/ecommerce/python/report.py:178-381**
- pre: deterministic given the journal; "reads nothing else" — adapters/ecommerce/python/report.py:179-180 [DERIVED]
- in: journal events filtered by kind `step` / `submission`; last `result` event wins — adapters/ecommerce/python/report.py:183-185 [DERIVED]
- join: receipt payloads supply quote/URL/metric, joined to the result by `(action_id, observation_id)` — adapters/ecommerce/python/report.py:181, 202, 206 [DERIVED]
- out: same ReportModel shape plus a `governed` block; `coverage` `{}`, `independence` `None`, `intelligence`/`market_discovery`/`product_anchored` `None` — adapters/ecommerce/python/report.py:341-377, 344, 353 [DERIVED]
- post: `verdict` is exactly one of `GOVERNED GAP — <code>`, `GOVERNED RUN CANCELLED|FAILED`, `GOVERNED — TRAIL SCORED`, `GOVERNED — TRAIL REFUSED TO SCORE`, `GOVERNED — COMPLETED WITHOUT A SCORE`, or `None` when no result event — adapters/ecommerce/python/report.py:278-280, 185 [DERIVED]
- post: `built_at = journal["built_at"] or models.now()` — adapters/ecommerce/python/report.py:380 [DERIVED]

**render(model, layout, summary_md) — adapters/ecommerce/python/report.py:865-1129**
- in: ReportModel + layout + optional summary markdown; summary must be written only from the ReportModel (`--summary FILE.md`) — adapters/ecommerce/python/report.py:9, 15 [DERIVED]
- out: self-contained HTML; dark mode via `prefers-color-scheme` and `data-theme="dark"` — adapters/ecommerce/python/report.py:6, 486-490 [DERIVED]

**main() — adapters/ecommerce/python/report.py:1132-1166**
- CLI: `build --state candidates/run.json [--out model.json]`; `render --model model.json --out report.html [--layout FULL_RESEARCH|SOURCING|EXECUTIVE] [--summary sum.md]` — adapters/ecommerce/python/report.py:13-15 [DERIVED]

## effect surface
- SQLite (via `memory.connect()`): table `events` read, filtered by `run_id`, ordered by `sequence` — adapters/ecommerce/python/report.py:46-49 [DERIVED]; tables written: none (FACTS.tables_written = [])
- Files: CLI reads `--state` run.json / `--model` model.json / `--summary` md; writes `--out` model.json or report.html — adapters/ecommerce/python/report.py:13-15 [DERIVED]
- Local module imports: `graph as graphmod`, `models`, `adapter_receipt.polarity_for` after `sys.path.insert(0, dirname)` — adapters/ecommerce/python/report.py:33-36 [DERIVED]; lazy `import memory` — adapters/ecommerce/python/report.py:45 [DERIVED]; lazy `import intelligence` — adapters/ecommerce/python/report.py:424 [DERIVED]
- Network calls / subprocesses / env flags: none visible in lines 1-895

## invariants
INVARIANT: `run.signal` length ≤ 600 chars in both builders — `[:600]` at adapters/ecommerce/python/report.py:58 and :342 [DERIVED]
  fails-if: longer signals silently truncated in the report header.
INVARIANT: `quotes` length ≤ 14 — plain `[:14]` adapters/ecommerce/python/report.py:74; governed `_alternate(..., 14)` adapters/ecommerce/python/report.py:338 [DERIVED]
  fails-if: field quotes beyond the cap never enter the model.
INVARIANT: plain `unresolved` ≤ 8 open gaps — `[:8]` adapters/ecommerce/python/report.py:89; governed `unresolved` is uncut (renderer announces cuts) — adapters/ecommerce/python/report.py:321-324 [DERIVED]
  fails-if: asymmetric truncation between plain and governed dossiers.
INVARIANT: qualification stage order `market_delta=0 < supply=1 < other=2` — adapters/ecommerce/python/report.py:125-126 [DERIVED]
  fails-if: manifest rows shown out of stage sequence.
INVARIANT: question identity = whitespace-normalized lowercase prefix of 380 chars — adapters/ecommerce/python/report.py:134 [DERIVED]
  fails-if: two questions differing only past char 380 collapse into one.
INVARIANT: governed hypothesis state precedence `RESULT` view > `MATERIALS@<step_id>` > `STEP_CONTEXT_4_FIELDS` — adapters/ecommerce/python/report.py:243-249, 257, 366 [DERIVED]
  fails-if: stale four-field step context (empty mechanism/population/friction) shown as authoritative.
INVARIANT: `evidence_absent` set only when result present ∧ `admissions` empty ∧ `lineage.admitted_evidence_ids` non-empty — adapters/ecommerce/python/report.py:328-329 [DERIVED]
  fails-if: absent evidence reported as zero instead of absent (gap B-14).
INVARIANT: `held_rejected` statuses ⊆ `("killed", "contradicted", "merged", "weakened")` — adapters/ecommerce/python/report.py:339, 352 [DERIVED]
  fails-if: a dead hypothesis disappears from the failures section.
INVARIANT: DB writes = 0 (FACTS.tables_written = []) — required by "reports never affect the research verdict" adapters/ecommerce/python/report.py:8 [DERIVED]
  fails-if: any write makes the report layer observable by the run.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `models.now()` at adapters/ecommerce/python/report.py:108 and :380 fallback; db: live `events` read adapters/ecommerce/python/report.py:46-49 whose absence is swallowed at :50-51). Otherwise pure functions of state/journal; no LLM — adapters/ecommerce/python/report.py:4-5 [DERIVED]
idempotency: SAFE (no table writes, FACTS.tables_written; outputs are whole-file rewrites via `--out` — adapters/ecommerce/python/report.py:13-15) [DERIVED]

## failure behaviour
- `except Exception: pass` around the events read (FACTS.fallbacks: "SWALLOWED: pass") — adapters/ecommerce/python/report.py:50-51 [DERIVED]. Caller sees `audit.events = 0`; "no events" is indistinguishable from "events unreadable" — adapters/ecommerce/python/report.py:43, 106 [DERIVED]
- Governed journal with no `result` event: `result = None` → `verdict = None`, `status` falls back to `"running"` — adapters/ecommerce/python/report.py:185, 278, 341 [DERIVED]
- No other broad handlers in lines 1-895; render half (lines 896-1171) is not in the material — no claims made for it

## dumb-code flags
- Magic caps duplicated across both builders: `600` (:58, :342), `14` (:74, :338); plain-only `8` (:89) vs governed uncut (:323); `[:160]` product_name clip — adapters/ecommerce/python/report.py:292 [DERIVED]
- Metric literals `"unit_price_low"` / `"minimum_order_quantity"` appear in both the raw-metric exclusion list (:291) and the metric map (:293) — rename one, drift the other [DERIVED]
- `_named_supplier` uses `re.match(r"(?:none|unknown|unresolved)\b", ...)` on the lowercased string — a supplier literally named "Unknown Trading Co." is treated as unnamed — adapters/ecommerce/python/report.py:158 [INFERRED: regex anchors at string start]
- `corpus_answers` kept only for LEGACY (< v2.2.0) runs — adapters/ecommerce/python/report.py:86 [DERIVED]
- Two `leads` shapes: metric-derived synthesis (:284-295) wholesale-replaced when `sourcing_coverage` is a list (:313-319); fallback `governed_concept` synthesized when only `product_opportunity.title` exists — adapters/ecommerce/python/report.py:349-350 [DERIVED]
- `import graph as graphmod` (:34) has no use in lines 1-895 — adapters/ecommerce/python/report.py:34 [INFERRED: may be used in render lines 896+; not visible in material]

## refactor notes
- Both builders must keep ReportModel key parity — `render(model, layout, summary_md)` at adapters/ecommerce/python/report.py:865 consumes it and docs/27 forbids a second report system (:17-18). Adding/renaming a key in one builder only blanks the other path's page.
- `polarity_for` from `adapter_receipt` (:36) decides `field_supporting`/`field_contradicting` (:228-230) and quote contradiction labels (:336) — changing adapter_receipt's polarity rules changes governed report counts; blast radius spans both files.
- The state-precedence chain and `state_from` labels (`"RESULT"`, `"MATERIALS@…"`, `"STEP_CONTEXT_4_FIELDS"`, plus `field_counts_from` values `"ADMISSIONS"`/`"STEP_CONTEXT"`/`"VIEW_SAMPLE"`) are contract data consumed by `_render_governed` — adapters/ecommerce/python/report.py:230, 257, 614, 626, 366, 773-862 [DERIVED]
- `sys.path.insert(0, dirname)` + sibling imports: the file must stay colocated with `graph.py`, `models.py`, `adapter_receipt.py`, and lazily `memory.py` / `intelligence.py` — adapters/ecommerce/python/report.py:33-36, 45, 424 [DERIVED]
- `_CSS` inline (:483), `_MARKS` (:545), `AUTHORITY` (:648) define the rendered vocabulary; statuses/authorities outside these maps render raw — keep the CSS inline to preserve the no-external-assets law (:6)

## VERIFY
```verify
grep -Fq 'def build_model_from_governed(journal: dict) -> dict:' adapters/ecommerce/python/report.py
grep -Fq 'FROM events WHERE run_id=?' adapters/ecommerce/python/report.py
grep -Fq 'stage_order = {"market_delta": 0, "supply": 1}' adapters/ecommerce/python/report.py
grep -Fq 'dead = ("killed", "contradicted", "merged", "weakened")' adapters/ecommerce/python/report.py
grep -Fq 'GOVERNED — TRAIL REFUSED TO SCORE' adapters/ecommerce/python/report.py
test "$(grep -c -F '[:600]' adapters/ecommerce/python/report.py)" -ge 2
grep -Fq 'except Exception:' adapters/ecommerce/python/report.py
! grep -Fq 'INSERT INTO' adapters/ecommerce/python/report.py
```
