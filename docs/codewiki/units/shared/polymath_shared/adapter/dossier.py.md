# unit: shared/polymath_shared/adapter/dossier.py
anchor: shared/polymath_shared/adapter/dossier.py:1-318

## purpose
Rebuilds the governed run journal a host never kept (`journal_from_store`) and renders it through the ecommerce engine's own renderer, run OUT OF PROCESS (`governed_run.py report`), then re-serializes the HTML through a fixed allowlist and wraps it in a script-free document for the route — TRAIL-INTERFACE-V1 T5. `render_decision` is the same pattern for the product decision report via `report.py decision` (PRODUCT-DECISION-REPORT-V1 §4.5, B4a). Nothing here writes, scores or decides. — shared/polymath_shared/adapter/dossier.py:1-12 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| NoDossier | class (LookupError) | — | shared/polymath_shared/adapter/dossier.py:52-53 | — (see importers below) |
| DossierError | class (RuntimeError) | `__init__(code: str, message: str) -> None` | shared/polymath_shared/adapter/dossier.py:56-62 | — (see importers below) |
| journal_from_store | def | `(run: dict, steps: list[dict], result: dict \| None) -> dict` | shared/polymath_shared/adapter/dossier.py:96-138 | — (see importers below) |
| safe_href | def | `(value: Any) -> str \| None` | shared/polymath_shared/adapter/dossier.py:157-167 | — (see importers below) |
| sanitize | def | `(fragment: str) -> str` | shared/polymath_shared/adapter/dossier.py:222-230 | — (see importers below) |
| document | def | `(body: str, title: str) -> str` | shared/polymath_shared/adapter/dossier.py:233-235 | — (see importers below) |
| render_dossier | def | `(journal: dict, layout: str = "FULL_RESEARCH", *, title: str \| None = None, timeout_s: float = RENDER_TIMEOUT_S) -> str` | shared/polymath_shared/adapter/dossier.py:238-260 | — (see importers below) |
| render_decision | def | `(bundle: dict, *, title: str \| None = None, timeout_s: float = RENDER_TIMEOUT_S) -> dict` | shared/polymath_shared/adapter/dossier.py:276-317 | — (see importers below) |

Module importers (FACTS): `orchestrator/orchestrator/api/adapter.py`, `orchestrator/orchestrator/api/product_report.py`, `shared/polymath_shared/adapter/run_view.py`. Per-symbol attribution not in FACTS.

## contracts

**journal_from_store(run, steps, result)** — shared/polymath_shared/adapter/dossier.py:96-138
- in: `run` keys run_id, adapter_id, adapter_version, workflow_version, created_at, updated_at, agent_identity, input (:99); `steps` = the run's store.list_steps rows (:100); `result` = terminal AdapterResultV1 or None (:100)
- out: journal dict — journal_version = `"governed-run-journal-v1"` (:38, :116), skill_version, run_id, adapter_id, adapter_version, workflow_version, created_at, agent_identity, harness_id (harness or agent), input, corpus_ids, events, built_at (:115-118, :137)
- post: events = `"start"` (:119) → per agent-answered step (step_type in `_AWAITING` = {"AGENT_REASON", "HARNESS_ACTION"}, :49, :106) one `"step"` event (:128) plus one `"submission"` event per accepted dict submission, kind `reasoning`/`receipt` (:129-134) → `"result"` iff result is not None (:135-136)
- post: built_at = result.terminal_at or run.updated_at or run.created_at — "never now" (:103-104, :137)

**safe_href(value)** — shared/polymath_shared/adapter/dossier.py:157-167
- out: `value` iff isinstance str AND len ≤ MAX_URL_CHARS (`2048`) AND `_HTTP_URL.fullmatch` passes (:161) AND `urlsplit(value).hostname` truthy (:167); else None
- pre: checked on the DECODED attribute value — the parser has already resolved character references (:159-160)

**sanitize(fragment)** — shared/polymath_shared/adapter/dossier.py:222-230
- post: only ALLOWED_TAGS (:144-145) and ALLOWED_ATTRIBUTES = {"class", "style", "title", "colspan"} (:146) survive; text re-escaped (:219); tags in `_DROPPED_WITH_CONTENT` removed WITH their content (:150, :190-191, :205-206)
- post: an anchor survives only with exactly one href that passes `safe_href`, re-written with LINK_ATTRIBUTES (:183-187); any anchor left open is closed where the fragment ends (:230)

**document(body, title)** — shared/polymath_shared/adapter/dossier.py:233-235
- out: `<!doctype html>` page, escaped `<title>` (:234-235)

**render_dossier(journal, layout, \*, title, timeout_s)** — shared/polymath_shared/adapter/dossier.py:238-260
- pre: layout ∈ LAYOUTS = ("FULL_RESEARCH", "SOURCING", "EXECUTIVE", "COMMERCIAL") (:37) else `DossierError("DOSSIER_LAYOUT_UNKNOWN", ...)` (:242-243)
- effect: subprocess `[sys.executable, str(RENDERER), "report", "--journal", ..., "--out", ..., "--layout", layout]` (:251)
- post: returns `document(sanitize(raw), title or f"Dossier · {journal.get('run_id')}")` (:260)

**render_decision(bundle, \*, title, timeout_s)** — shared/polymath_shared/adapter/dossier.py:276-317
- pre: bundle is a dict (:286-287); utf-8 size of the JSON body ≤ MAX_BUNDLE_BYTES (`20_000_000`) (:288-290)
- effect: subprocess `[sys.executable, str(DECISION_RENDERER), "decision", "--bundle", ..., "--out", ..., "--decision-out", ...]` (:298)
- post: returns `{"html": document(sanitize(raw), str(name)), "decision": decision}` with name = title or `f"Decision report · {bundle.get('title') or bundle.get('report_id') or 'products'}"`; decision must be a dict (:314-317)

## effect surface
- subprocess.run ×2: `governed_run.py report` (:251) and `report.py decision` (:298) — check=False, capture_output, timeout=timeout_s, cwd = private TemporaryDirectory
- temp files written: journal.json, dossier.html (:245); bundle.json, decision.html, decision.json (:292); prefixes `"polymath-dossier-"` (:244), `"polymath-decision-"` (:291)
- file read: `ENGINE / "manifest.yaml"` in `_skill_version` (:69); engine paths fixed at `adapters/ecommerce` (:31-33)
- env read: PATH (default `""`), LANG (default `"en_US.UTF-8"`) at :248 and :295; child env set: PYTHONDONTWRITEBYTECODE="1", OPPORTUNITY_RESEARCH_DB=<tmp>/loop.sqlite3 (:248-249, :295-296) — "no DSN, no token" (:247), "no DSN, no token, no key" (:294)
- Postgres tables: none read, none written (FACTS tables_read/tables_written empty); no network calls in SOURCE

## invariants
INVARIANT: JOURNAL_VERSION == "governed-run-journal-v1" == governed_run.JOURNAL_VERSION (mirrored literal) — shared/polymath_shared/adapter/dossier.py:38 [DERIVED]
  fails-if: the engine's journal reader rejects the rebuilt journal.
INVARIANT: MAX_EVIDENCE_ROWS == 60 == governed_run.MAX_EVIDENCE_ROWS (mirrored literal) — shared/polymath_shared/adapter/dossier.py:39 [DERIVED]
  fails-if: rebuilt evidence is trimmed differently than the engine trims it.
INVARIANT: `_HTTP_URL` rule == report.safe_url rule ("a contract test holds the two equal") — shared/polymath_shared/adapter/dossier.py:151-153 [DERIVED]
  fails-if: links one side allows, the other strips.
INVARIANT: rows `_evidence` hydrates have `int(r["sequence"]) < sequence` of the step shown — shared/polymath_shared/adapter/dossier.py:89 [DERIVED]
  fails-if: evidence cites steps stored after the step that displayed it.
INVARIANT: anchor kept only when `len(hrefs) == 1` and safe_href passes — shared/polymath_shared/adapter/dossier.py:184 [DERIVED]
  fails-if: a doubled href smuggles a second, unchecked URL.
INVARIANT: sanitize output appends `"</a>" * sum(p.links)` — every kept anchor closed — shared/polymath_shared/adapter/dossier.py:230 [DERIVED]
  fails-if: an open anchor leaks past the fragment and swallows later markup.
INVARIANT: child env keys ⊆ {PATH, LANG, PYTHONDONTWRITEBYTECODE, OPPORTUNITY_RESEARCH_DB} — shared/polymath_shared/adapter/dossier.py:248-249, shared/polymath_shared/adapter/dossier.py:295-296 [DERIVED]
  fails-if: secrets/DSNs leak into the engine subprocess.
INVARIANT: decision page ≤ MAX_HTML_BYTES (5_000_000) AND decision model ≤ MAX_DECISION_BYTES (5_000_000) — shared/polymath_shared/adapter/dossier.py:307, shared/polymath_shared/adapter/dossier.py:41-42 [DERIVED]
  fails-if: oversized engine output reaches the route.
INVARIANT: `_engine_failure` accepts only codes in `DECISION_ERRORS[:5]` — shared/polymath_shared/adapter/dossier.py:271 [DERIVED]
  fails-if: an unlisted engine code is re-raised as typed instead of generic DECISION_RENDER_FAILED.

## determinism & idempotency
determinism: journal_from_store DETERMINISTIC — "Deterministic: sequence order, every time read from the store, `built_at` = the result's terminal time … never now" (:103-104). render_dossier / render_decision NONDETERMINISTIC (subprocess :251, :298 — external engine process, exit code, timeout, tempdir). `_skill_version` depends on the manifest.yaml file on disk (:69).
idempotency: SAFE — every write goes to a TemporaryDirectory (:244, :291); module docstring: "Nothing here writes, scores or decides" (:8).

## failure behaviour
- `_evidence` swallows any Exception (`# noqa: BLE001`) and returns `ev = {"rows": [], "receipts": [], "error": f"{type(exc).__name__}: {exc}"[:500]}` — "a failed hydration is said, never raised" (:90-91)
- `_skill_version`: OSError → `"unknown"` (:71-72); `safe_href`: ValueError from urlsplit → None (:165-166)
- DossierError codes raised: DOSSIER_LAYOUT_UNKNOWN (:243), DOSSIER_TIMEOUT (:254), DOSSIER_RENDER_FAILED (:256), DOSSIER_TOO_LARGE (:258); DECISION_BUNDLE_INVALID (:287), DECISION_BUNDLE_TOO_LARGE (:290), DECISION_TIMEOUT (:301), engine-typed via `_engine_failure` (:305), DECISION_RENDER_FAILED (:306), DECISION_TOO_LARGE (:308), DECISION_OUTPUT_INVALID (:313, :315); engine-typed codes fixed by DECISION_ERRORS (:45-47)
- DossierError.message may carry the renderer's stderr — "log it, never send it to a caller" (:57-58)
- NoDossier (LookupError) = "The run's adapter has no dossier renderer" (:52-53); no raise site in this file — importers raise it — shared/polymath_shared/adapter/dossier.py:52 [INFERRED: defined and exported, never raised here]

## dumb-code flags
- Magic slice `DECISION_ERRORS[:5]` (:271) — the "engine's own … then the process's" split (:44) is positional; reordering the tuple silently misroutes failures
- Mirrored engine literals kept equal only by comments and a contract test — JOURNAL_VERSION (:38), MAX_EVIDENCE_ROWS (:39), `_HTTP_URL` (:151-153); "the engine never imports `shared`" (:151)
- Three distinct error-text truncations: `[-600:]` on stderr (:256, :306), `[-600:]` on message (:272), `[:500]` on hydration error (:91)
- Near-duplicate env dicts with the LANG default `"en_US.UTF-8"` written twice (:248, :295)
- Default title chains differ per renderer: `f"Dossier · {journal.get('run_id')}"` (:260) vs `f"Decision report · {bundle.get('title') or bundle.get('report_id') or 'products'}"` (:316)
- NoDossier defined but never raised in this file (:52)

## refactor notes
- Blast radius: three importers (`orchestrator/orchestrator/api/adapter.py`, `orchestrator/orchestrator/api/product_report.py`, `shared/polymath_shared/adapter/run_view.py`, FACTS.importers) — any public signature change breaks them
- JOURNAL_VERSION / MAX_EVIDENCE_ROWS / `_HTTP_URL` must move in lockstep with the engine's governed_run and report (:38-39, :151-153); the rebuilt journal must stay in "the exact shape `governed_run.py` writes" (:5-6)
- Minimal child env is a security property (:247, :294) — passing `os.environ` wholesale reintroduces DSN/token exposure
- The sanitizer is "defence in depth behind report.py's own escaping and the route's CSP" (:225-226); the route sends output "under a CSP that allows no script" (:8) — widening ALLOWED_TAGS/ALLOWED_ATTRIBUTES weakens that route contract
- ENGINE/RENDERER/DECISION_RENDERER paths (:31-33) pin the engine's location for both renderers
- DOSSIER_ADAPTERS = `{"ecommerce.product_research", "trail.product_discovery"}` (:36) names the only adapters with a dossier — adding an adapter id touches this set

## VERIFY
```verify
grep -Fq 'JOURNAL_VERSION = "governed-run-journal-v1"' shared/polymath_shared/adapter/dossier.py
grep -Fq 'MAX_EVIDENCE_ROWS = 60' shared/polymath_shared/adapter/dossier.py
grep -Fq 'RENDER_TIMEOUT_S = 30.0' shared/polymath_shared/adapter/dossier.py
grep -Fq 'DECISION_ERRORS[:5]' shared/polymath_shared/adapter/dossier.py
grep -Fq 'rel="noopener noreferrer" target="_blank"' shared/polymath_shared/adapter/dossier.py
! grep -Fq 'env = dict(os.environ)' shared/polymath_shared/adapter/dossier.py
test "$(grep -c -F 'raise DossierError(' shared/polymath_shared/adapter/dossier.py)" -ge 10
```
