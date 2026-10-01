# unit: shared/polymath_shared/code/_small-modules
anchor: shared/polymath_shared/code/__init__.py:1-6

## purpose
Package initializer for `polymath_shared.code` — home of CODE-KNOWLEDGE-V1, "code as a first-class knowledge source" (shared/polymath_shared/code/__init__.py:1) [DERIVED].
Currently a docstring-only stub: records the plan of record (`docs/wiki/plans/CODE-RAG-IMPLEMENTATION-V1.md`) and the K1/C1 sequencing for whoever implements it (shared/polymath_shared/code/__init__.py:1-4) [DERIVED].
Audience: retrieval-path implementers — every retrieval path must honour the knowledge-role scope before any code is ingested (shared/polymath_shared/code/__init__.py:3-4) [DERIVED].

## effect surface
- Postgres tables read/written: none — `tables_read: []`, `tables_written: []` (FACTS) [DERIVED].
- Qdrant collections, files, network, subprocess, env flags: none — module body is a docstring only (shared/polymath_shared/code/__init__.py:1-5) [DERIVED].

## invariants
INVARIANT: executable statements in `__init__.py` = 0 (entire body is one docstring) — shared/polymath_shared/code/__init__.py:1-5 [DERIVED]
  fails-if: any import or call added here runs on every `import polymath_shared.code` and changes import cost / failure modes for all importers.
INVARIANT: `knowledge_role` for code = `implementation`, set by C1 "from day one" — shared/polymath_shared/code/__init__.py:4 [DERIVED]
  fails-if: ingest tagging or retrieval filtering using a different literal breaks the knowledge-role scope K1 is supposed to enforce.
INVARIANT: K1 register = `11.485` — shared/polymath_shared/code/__init__.py:3 [DERIVED]
  fails-if: register-number mismatch desyncs this package's tracking from the plan-of-record doc.

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env/concurrency; no executable code, docstring only — shared/polymath_shared/code/__init__.py:1-5) [DERIVED]
idempotency: SAFE (import performs no assignments, calls, or I/O; nothing to repeat — shared/polymath_shared/code/__init__.py:1-5) [DERIVED]

## dumb-code flags
- Magic number `11.485` embedded in prose (K1 register) — shared/polymath_shared/code/__init__.py:3 [DERIVED].
- Version tag `CODE-KNOWLEDGE-V1` duplicated conceptually with the plan file name `CODE-RAG-IMPLEMENTATION-V1.md`; they must be renamed in lockstep — shared/polymath_shared/code/__init__.py:1 [INFERRED: both literals name the same initiative in one line].

## refactor notes
- `scope.py` is promised to land "first" under K1 but is not present yet; when it lands, this docstring must be updated or it misdescribes the package — shared/polymath_shared/code/__init__.py:3 [DERIVED].
- The exact string `knowledge_role=implementation` is named here as a day-one contract; changing it anywhere (ingest, retrieval filters) desyncs from this declaration — shared/polymath_shared/code/__init__.py:4 [DERIVED].
- Renaming or moving `docs/wiki/plans/CODE-RAG-IMPLEMENTATION-V1.md` breaks the plan-of-record pointer hardcoded in this docstring — shared/polymath_shared/code/__init__.py:1 [DERIVED].

## VERIFY
```verify
grep -Fq 'CODE-KNOWLEDGE-V1' shared/polymath_shared/code/__init__.py
grep -Fq 'docs/wiki/plans/CODE-RAG-IMPLEMENTATION-V1.md' shared/polymath_shared/code/__init__.py
grep -Fq 'knowledge_role=implementation' shared/polymath_shared/code/__init__.py
grep -Fq '11.485' shared/polymath_shared/code/__init__.py
grep -Fq 'scope.py' shared/polymath_shared/code/__init__.py
! grep -Fq 'def ' shared/polymath_shared/code/__init__.py
```
