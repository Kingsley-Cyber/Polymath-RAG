# unit: shared/polymath_shared/bundle_integrity.py
anchor: shared/polymath_shared/bundle_integrity.py:1-270

## purpose
Enforces SEMANTIC-RUNTIME-INTEGRITY-V1 — "the system must not be able to run wrong" (shared/polymath_shared/bundle_integrity.py:1-35) [DERIVED]. Freezes SHA-256 hashes of 8 declared semantic-authority files into `config/semantic_bundle.lock`, validates the running tree against that lock, and censuses production callers of the admission boundary `llm_extraction.gate` (shared/polymath_shared/bundle_integrity.py:49, shared/polymath_shared/bundle_integrity.py:58-69, shared/polymath_shared/bundle_integrity.py:166-170) [DERIVED]. Violations are FATAL findings; boot runs `--strict` and exits non-zero on them (shared/polymath_shared/bundle_integrity.py:33, shared/polymath_shared/bundle_integrity.py:266) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Finding` | dataclass | fields `level: str, check: str, detail: str` | shared/polymath_shared/bundle_integrity.py:75-78 | — |
| `Report` | dataclass | `findings: list[Finding]`; `add(level, check, detail) -> None`; `fatal -> list[Finding]`; `ok -> bool` | shared/polymath_shared/bundle_integrity.py:82-94 | — |
| `compute_bundle` | def | `() -> dict` | shared/polymath_shared/bundle_integrity.py:105-117 | — |
| `read_lock` | def | `() -> dict \| None` | shared/polymath_shared/bundle_integrity.py:120-126 | — |
| `write_lock` | def | `(label: str = "v5-production-001") -> dict` | shared/polymath_shared/bundle_integrity.py:129-141 | — |
| `call_graph_census` | def | `() -> dict[str, list[str]]` | shared/polymath_shared/bundle_integrity.py:166-170 | — |
| `validate` | def | `(*, require_activation: bool \| None = None) -> Report` | shared/polymath_shared/bundle_integrity.py:183-236 | — |
| `main` | def | `() -> int` — CLI: `--strict`, `--freeze [LABEL]`, `--json` | shared/polymath_shared/bundle_integrity.py:239-266 | boot (`--strict`), per docstring shared/polymath_shared/bundle_integrity.py:33 |

Private: `_sha(path: pathlib.Path) -> str` (shared/polymath_shared/bundle_integrity.py:101-102), `_production_callers(module: str) -> list[str]` (shared/polymath_shared/bundle_integrity.py:148-163).

## contracts

**validate** — shared/polymath_shared/bundle_integrity.py:183-236
- in: keyword-only `require_activation: bool | None = None`
- out: `Report`; `rep.ok` is True iff no FATAL findings (shared/polymath_shared/bundle_integrity.py:93-94)
- pre: none
- post: `require_activation is None` resolves to `bool((lock or {}).get("require_activation", False))` (shared/polymath_shared/bundle_integrity.py:222-223); emits checks `bundle_lock`, `bundle_drift`/`bundle`, `bundle_members`, `<name>_callers` (shared/polymath_shared/bundle_integrity.py:195-235)

**compute_bundle** — shared/polymath_shared/bundle_integrity.py:105-117
- out: `{"members": {rel_path: sha256}, "missing": [rel_path], "bundle_sha256": sha256(json.dumps(members, sort_keys=True))}` (shared/polymath_shared/bundle_integrity.py:115-117)
- post: absent members are excluded from `members` and therefore from the digest (shared/polymath_shared/bundle_integrity.py:110-114)

**read_lock** — shared/polymath_shared/bundle_integrity.py:120-126
- out: parsed lock JSON, or `None` when missing or unparseable
- post: never raises; `Exception` swallowed (shared/polymath_shared/bundle_integrity.py:125)

**write_lock** — shared/polymath_shared/bundle_integrity.py:129-141
- in: `label: str = "v5-production-001"` (shared/polymath_shared/bundle_integrity.py:129)
- out/post: rewrites `config/semantic_bundle.lock` with keys `bundle`, `bundle_sha256`, `members`, `"entity_policy": "E1-E7"`, `"fact_policy": "F1-F8"` (shared/polymath_shared/bundle_integrity.py:133-137, shared/polymath_shared/bundle_integrity.py:139-140); returns the lock dict (shared/polymath_shared/bundle_integrity.py:141)

**main** — shared/polymath_shared/bundle_integrity.py:239-266
- CLI: `--strict` (store_true), `--freeze` metavar LABEL `nargs="?"` `const="v5-production-001"`, `--json` (store_true) (shared/polymath_shared/bundle_integrity.py:240-245)
- out: `0` after freeze (shared/polymath_shared/bundle_integrity.py:248-252); otherwise `1 if (a.strict and rep.fatal) else 0` (shared/polymath_shared/bundle_integrity.py:266)

## effect surface
- files read: `config/semantic_bundle.lock` (shared/polymath_shared/bundle_integrity.py:49, shared/polymath_shared/bundle_integrity.py:121-124); each of the 8 `BUNDLE_MEMBERS` files (shared/polymath_shared/bundle_integrity.py:58-69, shared/polymath_shared/bundle_integrity.py:110-112); every `*.py` under `PRODUCTION_DIRS` via `rglob`, skipping `__pycache__` and `test_*` files (shared/polymath_shared/bundle_integrity.py:150-156, shared/polymath_shared/bundle_integrity.py:154-155)
- files written: `config/semantic_bundle.lock` — `LOCK.parent.mkdir(parents=True, exist_ok=True)` then `LOCK.write_text` (shared/polymath_shared/bundle_integrity.py:139-140)
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty); Qdrant: none; network: none; subprocess: none
- env flags read: none — no `os.environ` in the file; `os` is imported but unused (shared/polymath_shared/bundle_integrity.py:42)

## invariants
INVARIANT: lock `bundle_sha256` == sha256(json.dumps(current `members`, sort_keys=True)) — shared/polymath_shared/bundle_integrity.py:115-116, shared/polymath_shared/bundle_integrity.py:200 [DERIVED]
  fails-if: FATAL `bundle_drift` with changed=/missing= member lists (shared/polymath_shared/bundle_integrity.py:201-210)
INVARIANT: count of BUNDLE_MEMBERS missing on disk == 0 — shared/polymath_shared/bundle_integrity.py:215-217 [DERIVED]
  fails-if: FATAL `bundle_members`; also shrinks `members`, so `bundle_drift` fires too [INFERRED: missing files are excluded from the digest input shared/polymath_shared/bundle_integrity.py:110-114]
INVARIANT: every census entry has >= 1 production caller — shared/polymath_shared/bundle_integrity.py:225-235 [DERIVED]
  fails-if: FATAL `<name>_callers` ("classify as NOT_IMPLEMENTED") when activation required, WARN otherwise (shared/polymath_shared/bundle_integrity.py:229-235)
INVARIANT: `config/semantic_bundle.lock` exists and parses — shared/polymath_shared/bundle_integrity.py:195-198 [DERIVED]
  fails-if: FATAL `bundle_lock` ("Create it with --freeze")
INVARIANT: len(BUNDLE_MEMBERS) == 8 — shared/polymath_shared/bundle_integrity.py:58-69 [DERIVED]
  fails-if: any membership change alters `bundle_sha256`; every existing lock reports drift
INVARIANT: exit code == 1 iff `--strict` and FATAL count >= 1 — shared/polymath_shared/bundle_integrity.py:266 [DERIVED]
INVARIANT: census scope == `PRODUCTION_DIRS = ("workers", "control", "orchestrator", "sidecars")`; `eval/` deliberately excluded — shared/polymath_shared/bundle_integrity.py:51-55 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env; inputs are only file bytes at ROOT-derived paths (shared/polymath_shared/bundle_integrity.py:48-49, shared/polymath_shared/bundle_integrity.py:110-112, shared/polymath_shared/bundle_integrity.py:121-124, shared/polymath_shared/bundle_integrity.py:154) [DERIVED]
idempotency: SAFE — `validate`/census are read-only; `write_lock` rewrites byte-identical lock content for an unchanged tree (deliberate overwrite, shared/polymath_shared/bundle_integrity.py:140) [DERIVED]

## failure behaviour
- `read_lock`: `except Exception: return None` (shared/polymath_shared/bundle_integrity.py:125) — a corrupt/unreadable lock is indistinguishable from no lock; caller sees FATAL `bundle_lock`, never the parse error (shared/polymath_shared/bundle_integrity.py:195-198).
- `_production_callers`: `except Exception: continue` (shared/polymath_shared/bundle_integrity.py:159) — an unreadable `*.py` is silently dropped from the census and can fake "ZERO production callers".
- `validate` raises nothing; failure surfaces only as findings plus exit code 1 under `--strict` (shared/polymath_shared/bundle_integrity.py:266).
- `write_lock` has no handler around mkdir/write (shared/polymath_shared/bundle_integrity.py:139-140); an OSError would propagate to the CLI [INFERRED: no try/except on that path].

## dumb-code flags
- Literal `"v5-production-001"` duplicated: `write_lock` default (shared/polymath_shared/bundle_integrity.py:129) and `--freeze` const (shared/polymath_shared/bundle_integrity.py:243).
- Lock keys `"entity_policy": "E1-E7"` and `"fact_policy": "F1-F8"` are written but never read by `validate` — dead metadata (shared/polymath_shared/bundle_integrity.py:136-137 vs shared/polymath_shared/bundle_integrity.py:195-235).
- `validate` reads lock key `require_activation` (shared/polymath_shared/bundle_integrity.py:222-223) but `write_lock` never emits it (shared/polymath_shared/bundle_integrity.py:133-137) — activation can only be turned on by hand-editing the lock.
- Unused imports: `os` (shared/polymath_shared/bundle_integrity.py:42), `sys` (shared/polymath_shared/bundle_integrity.py:45).
- Empty section header "configuration coherence" with no code (shared/polymath_shared/bundle_integrity.py:173-179); retired rule-pack check left as a comment (shared/polymath_shared/bundle_integrity.py:219).
- Census matches the module name anywhere in raw file text via `re.search` (shared/polymath_shared/bundle_integrity.py:161) — a comment or docstring naming `llm_extraction.gate` counts as a production caller [INFERRED: search runs over full source text, not the import block].

## refactor notes
- Any change to BUNDLE_MEMBERS (the 8 paths, shared/polymath_shared/bundle_integrity.py:58-69) changes `bundle_sha256`; every deployed lock then fails `bundle_drift` until `--freeze` is deliberately re-run (shared/polymath_shared/bundle_integrity.py:200-210, shared/polymath_shared/bundle_integrity.py:248-252).
- Census key `extraction_gate` becomes finding check id `extraction_gate_callers` (shared/polymath_shared/bundle_integrity.py:168-169, shared/polymath_shared/bundle_integrity.py:227, shared/polymath_shared/bundle_integrity.py:230) — report consumers depend on both names.
- `PRODUCTION_DIRS` defines what counts as production (shared/polymath_shared/bundle_integrity.py:51-55); moving code outside those dirs silently drops its callers from the census.
- The `--strict` exit contract (1 iff fatal, shared/polymath_shared/bundle_integrity.py:266) is what boot depends on (shared/polymath_shared/bundle_integrity.py:33).
- Lock schema keys read back by `validate`: `bundle_sha256`, `members`, `require_activation` (shared/polymath_shared/bundle_integrity.py:200-204, shared/polymath_shared/bundle_integrity.py:222-223) — keep in sync with `write_lock` output.

## VERIFY
```verify
grep -Fq 'PRODUCTION_DIRS = ("workers", "control", "orchestrator", "sidecars")' shared/polymath_shared/bundle_integrity.py
grep -Fq '"entity_policy": "E1-E7"' shared/polymath_shared/bundle_integrity.py
grep -Fq 'return 1 if (a.strict and rep.fatal) else 0' shared/polymath_shared/bundle_integrity.py
grep -Eq 'require_activation' shared/polymath_shared/bundle_integrity.py
! grep -Fq 'os.environ' shared/polymath_shared/bundle_integrity.py
test "$(grep -c -F 'v5-production-001' shared/polymath_shared/bundle_integrity.py)" -ge 2
grep -Eq 'except Exception:' shared/polymath_shared/bundle_integrity.py
```
