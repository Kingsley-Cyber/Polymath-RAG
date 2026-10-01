# unit: adapters/ecommerce/python/governed_run.py
anchor: adapters/ecommerce/python/governed_run.py:1-260

## purpose
Append-only journal for ONE governed product-discovery run (GOVERNED-CONVERGENCE-V1 TG4) — adapters/ecommerce/python/governed_run.py:2-10 [DERIVED]. The agent (Hermes / Claude Code / Codex) drives the run via the adapter's MCP tools; this module records the tool outputs it is handed (steps + evidence, submissions + adapter answers, receipts, final AdapterResultV1) without driving anything or talking to anything — adapters/ecommerce/python/governed_run.py:6-8 [DERIVED]. The journal is the only input of the governed report (`report.build_model_from_governed`) — adapters/ecommerce/python/governed_run.py:9-10,249 [DERIVED]. Laws: append-only, no score computed/copied/re-ranked, rejections kept, no credential stored — adapters/ecommerce/python/governed_run.py:20-21 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| now_iso | def | () -> str | adapters/ecommerce/python/governed_run.py:40-41 | — |
| default_path | def | (run_id: str) -> str | adapters/ecommerce/python/governed_run.py:44-45 | — |
| new_journal | def | (run_ref: dict, input_payload: dict, *, agent_identity: str, harness_id: str\|None=None, corpus_ids: list\|None=None, at: str\|None=None) -> dict | adapters/ecommerce/python/governed_run.py:61-69 | — |
| record_next | def | (journal: dict, payload: dict, at: str\|None=None) -> dict\|None | adapters/ecommerce/python/governed_run.py:97-121 | — |
| record_submission | def | (journal: dict, step_id: str, kind: str, payload: dict, response: dict, *, receipt_report: dict\|None=None, at: str\|None=None) -> dict | adapters/ecommerce/python/governed_run.py:124-133 | — |
| record_result | def | (journal: dict, result: dict, at: str\|None=None) -> dict | adapters/ecommerce/python/governed_run.py:136-137 | — |
| current_action | def | (journal: dict) -> dict\|None | adapters/ecommerce/python/governed_run.py:140-148 | — |
| summary | def | (journal: dict) -> dict | adapters/ecommerce/python/governed_run.py:151-165 | — |
| load | def | (path: str) -> dict | adapters/ecommerce/python/governed_run.py:168-173 | — |
| save | def | (journal: dict, path: str) -> None | adapters/ecommerce/python/governed_run.py:176-181 | — |
| main | def | (argv: list[str]\|None=None) -> int | adapters/ecommerce/python/governed_run.py:190-255 | — |

## contracts

**new_journal** — adapters/ecommerce/python/governed_run.py:61-69
- in: `run_ref` (AdapterRunRefV1 dict), `input_payload`, kw `agent_identity` required; `harness_id`, `corpus_ids`, `at` optional.
- out: dict with keys `journal_version`, `skill_version`, `run_id`, `adapter_id`, `adapter_version`, `workflow_version`, `created_at`, `agent_identity`, `harness_id`, `input`, `corpus_ids`, `events`.
- post: events == exactly one `"start"` event — :68 [DERIVED].
- post: `harness_id or agent_identity` — :66; `corpus_ids` falls back arg → `input_payload["corpus_ids"]` → `[]` — :67 [DERIVED].

**_append** (internal, backs every event) — adapters/ecommerce/python/governed_run.py:72-76
- pre: `kind in KINDS` (assert) — :73.
- post: `ev = {"seq": len(events)+1, "at": at or now_iso(), "kind": kind, "data": data}` — :74.

**record_next** — adapters/ecommerce/python/governed_run.py:97-121
- in: one `adapter_next` payload.
- out: appended event dict, or `None`.
- post: payload with `error` → `"note"` event `{"what": "adapter_next returned an error", ...}` — :100-101.
- post: duplicate `(step_id, sequence)` → `None`, no event — :104-106.
- post: evidence rows truncated to `MAX_EVIDENCE_ROWS` (60); receipts, coverage, allocation, error kept — :109-111.
- post: `"status"` event only when the 8-key view (`status, current_step_id, steps_issued, steps_accepted, branch_loops, gap, failure`) differs from the last one — :117-121.

**record_submission** — adapters/ecommerce/python/governed_run.py:124-133
- in: `kind` is `"reasoning"` or `"receipt"` (CLI choices) — :247.
- post: `accepted = not bool(response.get("error"))`; rejected response stored verbatim, accepted response reduced to keys `status, current_step_id, steps_accepted, gap, failure` — :128-130.
- post: `payload_hash` = `_hash(payload)` = sha256, sorted keys, first 16 hex chars — :129, :57.
- post: `receipt_report` reduced to keys `action_kind, items_in, observations, sources, omitted, omitted_by_reason, notes, roles, source_classes, queries_recorded` — :132.

**current_action** — adapters/ecommerce/python/governed_run.py:140-148
- out: `harness_action` of the latest `step_type == "HARNESS_ACTION"` step, else `None`.
- post: returns `None` once an accepted `receipt` submission whose `payload.action_id` equals the action's `action_id` exists — :145-147.

**summary** — adapters/ecommerce/python/governed_run.py:151-165
- out: keys `run_id, adapter, events, steps_issued, agent_reason_steps, harness_actions, steps_with_readable_evidence, submissions, rejected_submissions, receipts, observations_submitted, observations_admitted, observations_rejected, terminal, gap, awaiting_action`.
- pre: admissions counted from the last `result` event's `output.evidence_admissions` — :156.

**load / save** — adapters/ecommerce/python/governed_run.py:168-181
- pre(load): `journal_version == "governed-run-journal-v1"`, else `SystemExit(f"{path}: not a {JOURNAL_VERSION} journal")` — :171-172.
- post(save): creates parent dir, writes `path + ".tmp"`, then `os.replace` (atomic), `indent=1` — :177-181.

**main** — adapters/ecommerce/python/governed_run.py:190-255
- subcommands: `start, record-next, action, record-submit, record-result, status, report` — :193.
- `start`: refuses `run_ref` with `error`/no `run_id` (exit 1) and refuses an existing journal file (exit 1, "a journal is append-only; never restarted") — :218-222.
- `report`: `sys.path.insert` of own dir, imports sibling `report`, `_report.build_model_from_governed(journal)`, writes `_report.render(model, args.layout)`; `--layout` default `"FULL_RESEARCH"`, choices `FULL_RESEARCH, SOURCING, EXECUTIVE, COMMERCIAL` — :247-254, :213.

## effect surface
- Files read: `ROOT/manifest.yaml` (version line) — :48-53; `ROOT = dirname(dirname(abspath(__file__)))` — :32, so `adapters/ecommerce/manifest.yaml` [INFERRED: two dirnames from `python/governed_run.py`]; journal JSON in `load`/`_read` — :169, :186; CLI JSON inputs `--run-ref --input --file --payload --response --receipt-report` — :217-239.
- Files written: journal (`save`, tmp + `os.replace`) — :176-181; default journal path `ROOT/state/<run_id>.governed.json` — :44-45; `--out` action JSON — :233-234; `--out` report HTML and optional `--model-out` JSON — :251-254.
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty). Qdrant/network/subprocess: none visible.
- Env flags read: none visible.

## invariants
INVARIANT: JOURNAL_VERSION == "governed-run-journal-v1" and load() rejects any other — adapters/ecommerce/python/governed_run.py:33,171-172 [DERIVED]
  fails-if: every existing journal becomes unreadable (`SystemExit` on load).
INVARIANT: evidence rows per recorded step ≤ MAX_EVIDENCE_ROWS (60) — adapters/ecommerce/python/governed_run.py:35,109 [DERIVED]
  fails-if: journal stores more rows than the adapter ever issued (comment: 60 == the adapter's own adapter_next cap).
INVARIANT: kept materials bytes per step ≤ MAX_MATERIALS_BYTES (300_000) and each kept value ≤ MAX_MATERIAL_VALUE_BYTES (120_000); larger values recorded name+size only — adapters/ecommerce/python/governed_run.py:36-37,85-92 [DERIVED]
  fails-if: journal bloat; oversized values silently lose content (name/size kept).
INVARIANT: event seq == (index in events)+1, strictly increasing — adapters/ecommerce/python/governed_run.py:74 [DERIVED]
  fails-if: replay/ordering consumers of the append-only log break.
INVARIANT: a `(step_id, sequence)` pair appears at most once as a step event — adapters/ecommerce/python/governed_run.py:104-106 [DERIVED]
  fails-if: polling `adapter_next` duplicates steps and inflates `summary().steps_issued`.
INVARIANT: every rejected submission stored with `accepted: false` and full response — adapters/ecommerce/python/governed_run.py:128-130 [DERIVED]
  fails-if: rejected-and-corrected history disappears; dossier can't reconstruct the run.
INVARIANT: `start` never overwrites: journal file exists → exit 1 — adapters/ecommerce/python/governed_run.py:221-222 [DERIVED]
  fails-if: append-only law (:20-21) violated.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `_dt.datetime.now` at adapters/ecommerce/python/governed_run.py:41, per FACTS nondeterminism; affects `created_at` and event `at` only when caller omits `at`; `_skill_version` reads manifest.yaml so it varies with the checkout — :48-53) [DERIVED]
idempotency: SAFE for `record-next` (dedup by `(step_id, sequence)` :104-106; status dedup by view equality :119-120) and `save` (atomic tmp+replace :178-181); UNSAFE for `record-submit`/`record-result` (no dedup — replaying the same CLI call appends a second event) [INFERRED: no dedup path exists for kinds `submission`/`result`]

## failure behaviour
- `_skill_version`: swallows `OSError` → returns `"unknown"` — adapters/ecommerce/python/governed_run.py:52-53.
- `load`: version mismatch → `SystemExit(f"{path}: not a {JOURNAL_VERSION} journal")` — :171-172.
- `_append`: unknown kind → `AssertionError` (assert, not error return) — :73.
- `record_next`: adapter error payload → recorded as `"note"`, never raised — :100-101.
- `main start`: bad run_ref → stdout `{"ok": false, "error": "adapter_start did not return a run reference", ...}`, exit 1 — :218-219.
- `main start`: existing journal → stdout `{"ok": false, "error": "journal already exists: ...", ...}`, exit 1 — :221-222.
- `main action`: nothing awaiting → stdout `{"ok": false, "error": "no HARNESS_ACTION step is awaiting a receipt in this journal"}`, exit 1 — :231-232.
- No other handlers: malformed JSON input files and journal corruption propagate raw to the caller.

## dumb-code flags
- Magic number `hexdigest()[:16]` — hash truncated to 16 hex chars, unexplained — adapters/ecommerce/python/governed_run.py:57.
- Cross-file constant duplication: `MAX_EVIDENCE_ROWS = 60` comment claims "== the adapter's own adapter_next cap" with no code link — :35.
- Hand-rolled YAML parse: `_skill_version` matches only lines starting exactly with `version:` — breaks on any other YAML layout — :50-51.
- Two unrelated "kind" namespaces: event `KINDS` tuple (:34) vs submission `--kind` choices `["reasoning", "receipt"]` (:247); both land in `data["kind"]` of events (:129).
- Stringly field: `summary()["adapter"] = f"{adapter_id} {adapter_version}"` — reassembly needed by any consumer — :157.
- `--journal` optional only for `start` via `required=(name != "start")` — asymmetric CLI contract — :195.

## refactor notes
- `report` subcommand dynamically imports a sibling module: `sys.path.insert(0, dirname(abspath(__file__)))` + `import report` — renaming `report.build_model_from_governed` or `report.render` breaks the CLI at adapters/ecommerce/python/governed_run.py:247-254.
- Bumping `JOURNAL_VERSION` invalidates every stored journal (`load` SystemExit) — :33,171-172.
- Changing `KINDS` breaks `_append`'s assert and the `e["kind"] ==` filters in `current_action`/`summary` — :73,143,145,153-155.
- CLI stdout keys are the driver-agent protocol (`ok, journal, run_id, seq, accepted, awaiting_action, action_id, action_kind, budget, search_intents, hypothesis_ids, verdict`) — the docstring's agent loop consumes them — :224,228,235-236,241,255,252-258 [INFERRED: agent drives via these commands per :12-18].
- The key-filter lists in `record_submission` (:130, :132) and the status-view key list (:118) must track the adapter's response/receipt schema or fields are silently dropped.

## VERIFY
```verify
grep -Fq 'JOURNAL_VERSION = "governed-run-journal-v1"' adapters/ecommerce/python/governed_run.py
grep -Fq 'MAX_EVIDENCE_ROWS = 60' adapters/ecommerce/python/governed_run.py
grep -Fq 'MAX_MATERIALS_BYTES = 300_000' adapters/ecommerce/python/governed_run.py
grep -Fq 'os.replace(tmp, path)' adapters/ecommerce/python/governed_run.py
grep -Fq 'hexdigest()[:16]' adapters/ecommerce/python/governed_run.py
! grep -Fq 'import random' adapters/ecommerce/python/governed_run.py
test "$(grep -c -F 'record-next' adapters/ecommerce/python/governed_run.py)" -ge 2
```
