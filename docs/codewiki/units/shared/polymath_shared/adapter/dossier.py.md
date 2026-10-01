# unit: shared/polymath_shared/adapter/dossier.py
anchor: shared/polymath_shared/adapter/dossier.py:1-209

## purpose
Rebuilds a stored run's governed journal from the run row, its steps and the terminal result (`journal_from_store`), so the ecommerce engine's own renderer (`adapters/ecommerce/python/governed_run.py report`) runs unchanged — dossier.py:1-8 [DERIVED]. Renders it out of process, keeps only the renderer's own tags/attributes, wraps it in a document the route sends under a no-script CSP — dossier.py:6-8 [DERIVED]. Nothing here writes, scores or decides — dossier.py:8 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| journal_from_store | def | (run: dict, steps: list[dict], result: dict \| None) -> dict | dossier.py:83-125 | — (see note) |
| sanitize | def | (fragment: str) -> str | dossier.py:172-178 | — |
| document | def | (body: str, title: str) -> str | dossier.py:181-183 | — |
| render_dossier | def | (journal: dict, layout: str = "FULL_RESEARCH", *, title: str \| None = None, timeout_s: float = RENDER_TIMEOUT_S) -> str | dossier.py:186-208 | — |
| NoDossier | class(LookupError) | — | dossier.py:39-40 | — |
| DossierError | class(RuntimeError) | __init__(code: str, message: str) -> None | dossier.py:43-49 | — |
| DOSSIER_ADAPTERS | const | frozenset({"ecommerce.product_research", "trail.product_discovery"}) | dossier.py:29 | — |
| LAYOUTS | const | ("FULL_RESEARCH", "SOURCING", "EXECUTIVE", "COMMERCIAL") | dossier.py:30 | — |

Module importers (FACTS.importers, module-level, per-symbol use not distinguished): `orchestrator/orchestrator/api/adapter.py`, `shared/polymath_shared/adapter/run_view.py`.

## contracts
### journal_from_store(run, steps, result)
- in: `run` keys used: run_id, adapter_id, adapter_version, workflow_version, created_at, updated_at, agent_identity, input — dossier.py:86-87, 98-101 [DERIVED]
- in: `steps` = store.list_steps rows; `result` = terminal AdapterResultV1 or None (None ⇒ journal reads as in progress) — dossier.py:86-87 [DERIVED]
- pre: run["run_id"], run["adapter_id"] subscripted directly — dossier.py:103 [INFERRED: direct subscript raises KeyError if absent]
- post: journal_version == "governed-run-journal-v1"; skill_version read from `ENGINE / "manifest.yaml"` — dossier.py:103, 53-59 [DERIVED]
- post: events = one "start" (status "running") + per row with step_type in _AWAITING one "step" (status "awaiting_agent"/"awaiting_harness", with evidence) and, if accepted, one "submission" (kind "reasoning"/"receipt") + optional "result" — dossier.py:106, 108-121, 122-123 [DERIVED]
- post: submission event response = {"status": "running", "current_step_id": step_id, "steps_accepted": done, "gap": None, "failure": None}; done counts rows with status in ("accepted", "executed") — dossier.py:109-110, 120-121 [DERIVED]
- post: agent_identity = run.agent_identity or first identity named by an accepted AGENT_REASON submission; harness_id = first payload harness_id else agent — dossier.py:96-99 [DERIVED]
- post: built_at = result.terminal_at or run.updated_at or run.created_at; no clock read — dossier.py:124 [DERIVED]

### render_dossier(journal, layout, *, title, timeout_s)
- pre: layout ∈ LAYOUTS else DossierError("DOSSIER_LAYOUT_UNKNOWN", ...) — dossier.py:190-191 [DERIVED]
- effect: subprocess `[sys.executable, str(RENDERER), "report", "--journal", ..., "--out", ..., "--layout", layout]`, capture_output, text, timeout=timeout_s, cwd=tmp, check=False — dossier.py:199-200 [DERIVED]
- post: returns document(sanitize(raw), title or f"Dossier · {journal.get('run_id')}") — dossier.py:208 [DERIVED]
- raises: DossierError codes "DOSSIER_TIMEOUT", "DOSSIER_RENDER_FAILED", "DOSSIER_TOO_LARGE" — dossier.py:202, 204, 206 [DERIVED]

### sanitize(fragment)
- post: re-serialized HTML keeping only ALLOWED_TAGS (19 tags) and ALLOWED_ATTRIBUTES ("class", "style", "title", "colspan"); text re-escaped; script/noscript/template/iframe/object/embed/svg/math dropped WITH content; style bodies kept raw with "<" removed — dossier.py:130-134, 144-169 [DERIVED]
- post: comments, doctypes, links, images, event handlers removed — dossier.py:172-174 [DERIVED]

### document(body, title)
- post: fixed shell starting `<!doctype html>` + `<html lang="en">`, title html-escaped — dossier.py:181-183 [DERIVED]

## effect surface
- Files read: `adapters/ecommerce/manifest.yaml` (via ENGINE = _REPO / "adapters" / "ecommerce") — dossier.py:25, 56 [DERIVED]
- Files written (temp only): journal.json, dossier.html under TemporaryDirectory(prefix="polymath-dossier-") — dossier.py:192-194 [DERIVED]
- Subprocess: subprocess.run of RENDERER = ENGINE / "python" / "governed_run.py" — dossier.py:26, 199 [DERIVED]
- Env read for child: PATH = os.environ.get("PATH", ""), LANG = os.environ.get("LANG", "en_US.UTF-8") — dossier.py:196 [DERIVED]
- Env set for child: PYTHONDONTWRITEBYTECODE="1", OPPORTUNITY_RESEARCH_DB=<tmp>/loop.sqlite3 (no DSN, no token) — dossier.py:196-197 [DERIVED]
- Postgres/Qdrant/network: none (FACTS tables_read/tables_written empty) [DERIVED]

## invariants
INVARIANT: journal event seq == len(journal["events"]) + 1 at each append — dossier.py:68 [DERIVED]
  fails-if: seq gaps/collisions break the renderer's journal ordering.
INVARIANT: evidence rows count ≤ MAX_EVIDENCE_ROWS == 60 — dossier.py:79, 32 [DERIVED]
  fails-if: journal carries more rows than governed_run.record_next would trim; no longer matches a native journal.
INVARIANT: every row fed to evidence hydration has int(sequence) < the current step's sequence — dossier.py:76 [DERIVED]
  fails-if: step shows evidence the agent could not yet have read.
INVARIANT: accepted submissions are exactly rows with status == "accepted" and isinstance(submission, dict) — dossier.py:94 [DERIVED]
  fails-if: fabricated submission events governed_run never wrote.
INVARIANT: rendered output size ≤ MAX_HTML_BYTES == 5_000_000 bytes else DossierError — dossier.py:205-206, 34 [DERIVED]
  fails-if: unbounded renderer output shipped to callers.
INVARIANT: subprocess timeout == timeout_s, default RENDER_TIMEOUT_S == 30.0 — dossier.py:186-187, 200, 33 [DERIVED]
  fails-if: hung renderer pins the caller indefinitely.
INVARIANT: built_at ∈ {result.terminal_at, run.updated_at, run.created_at} — dossier.py:124 [DERIVED]
  fails-if: two rebuilds of the same stored run produce different journals.
INVARIANT: child env keys ⊆ {PATH, LANG, PYTHONDONTWRITEBYTECODE, OPPORTUNITY_RESEARCH_DB} — dossier.py:196-197 [DERIVED]
  fails-if: renderer inherits credentials or reaches the real loop database.

## determinism & idempotency
determinism: journal_from_store DETERMINISTIC for fixed store rows (sorted by sequence, all times from the store, built_at never "now" — dossier.py:92, 124) except skill_version re-read from manifest.yaml each call — dossier.py:56 [DERIVED]. sanitize/document DETERMINISTIC (pure string ops) — dossier.py:144-183 [DERIVED]. render_dossier NONDETERMINISTIC (subprocess.run — dossier.py:199, FACTS.nondeterminism) [DERIVED].
idempotency: SAFE — no persistent writes; staging happens in a TemporaryDirectory discarded on exit — dossier.py:192 [DERIVED].

## failure behaviour
- EB.hydrate Exception swallowed into ev = {"rows": [], "receipts": [], "error": f"{type(exc).__name__}: {exc}"[:500]}; caller sees a step event with empty rows, no raise — dossier.py:77-78 [DERIVED]
- OSError reading manifest.yaml swallowed; skill_version becomes "unknown" — dossier.py:58-59 [DERIVED]
- DossierError raised with codes: DOSSIER_LAYOUT_UNKNOWN — dossier.py:191; DOSSIER_TIMEOUT — dossier.py:202; DOSSIER_RENDER_FAILED (message may carry renderer stderr tail, last 600 chars) — dossier.py:204; DOSSIER_TOO_LARGE — dossier.py:206 [DERIVED]
- DossierError docstring: log the message, never send it to a caller — dossier.py:44-45 [DERIVED]
- NoDossier defined for adapters without a renderer (DOSSIER_ADAPTERS); never raised in this file — dossier.py:29, 39-40 [DERIVED]

## dumb-code flags
- JOURNAL_VERSION = "governed-run-journal-v1" and MAX_EVIDENCE_ROWS = 60 duplicate governed_run.py's own constants (comments say so) — dossier.py:31-32 [DERIVED]
- _skill_version and _payload_hash re-implement governed_run internals (docstrings: "governed_run._skill_version", "governed_run._hash") — dossier.py:53-59, 62-64 [DERIVED]
- Magic truncations: error string [:500] — dossier.py:78; stderr tail [-600:] — dossier.py:204 [DERIVED]
- DOSSIER_ADAPTERS and NoDossier are never referenced elsewhere in this file; only importers can use them — dossier.py:29, 39-40 [DERIVED]
- handle_endtag never emits `</br>` while `<br>` start tags are emitted — dossier.py:162 vs 151-153 [DERIVED]
- handle_startendtag refuses to open `style` — dossier.py:156 [DERIVED]

## refactor notes
- Importers orchestrator/orchestrator/api/adapter.py and shared/polymath_shared/adapter/run_view.py break on any public rename (FACTS.importers) [DERIVED]
- Journal shape is the wire contract of the out-of-process renderer: journal_version, event kinds start/step/submission/result, 60-row evidence trim must stay compatible with governed_run.py — dossier.py:31-32, 106-123, 199 [DERIVED]
- DossierError.code values are caller-facing API — dossier.py:191, 202, 204, 206 [DERIVED]
- ALLOWED_TAGS / ALLOWED_ATTRIBUTES / _DROPPED_WITH_CONTENT gate report.py markup; tightening silently drops renderer content — dossier.py:130-134, 172-174 [DERIVED]
- Child env is a security boundary (no DSN/token, engine DB redirected into tmp); widening it revisits the route's no-script CSP claim — dossier.py:195-197, 8 [DERIVED]
- RENDER_TIMEOUT_S = 30.0 and MAX_HTML_BYTES = 5_000_000 are request-path budgets — dossier.py:33-34 [DERIVED]

## VERIFY
```verify
grep -Fq 'MAX_EVIDENCE_ROWS = 60' shared/polymath_shared/adapter/dossier.py
grep -Fq 'RENDER_TIMEOUT_S = 30.0' shared/polymath_shared/adapter/dossier.py
grep -Fq 'JOURNAL_VERSION = "governed-run-journal-v1"' shared/polymath_shared/adapter/dossier.py
grep -Fq '"seq": len(journal["events"]) + 1' shared/polymath_shared/adapter/dossier.py
grep -Fq 'raise DossierError("DOSSIER_TOO_LARGE", f"the dossier is larger than {MAX_HTML_BYTES} bytes")' shared/polymath_shared/adapter/dossier.py
grep -Fq 'OPPORTUNITY_RESEARCH_DB": str(Path(tmp) / "loop.sqlite3")' shared/polymath_shared/adapter/dossier.py
! grep -Fq 'import requests' shared/polymath_shared/adapter/dossier.py
test "$(grep -c -F 'DossierError' shared/polymath_shared/adapter/dossier.py)" -ge 5
```
