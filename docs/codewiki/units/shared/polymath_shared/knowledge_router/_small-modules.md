# unit: shared/polymath_shared/knowledge_router/_small-modules
anchor: shared/polymath_shared/knowledge_router/__init__.py:1-1

## purpose
Deterministic document-level classifier (KNOWLEDGE-ROUTER-V1.1) that scores a document against yaml-configured knowledge modes and emits extraction-priority tiers `always / preferred / optional / disabled`. The router is a cost optimizer, not a gatekeeper — it sets extraction priority, never whether knowledge exists (classifier.py:1-5, 14-15). Classification runs on full document text; chunks have no context (classifier.py:13-14). Consumed by `workers/workers/knowledge_artifacts.py` (FACTS.importers). `__init__.py`, `confidence.py`, `routing_policy.py` show no SOURCE content.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `classify_document` | def | (text: str, metadata: dict[str, str] \| None = None) -> dict | classifier.py:62-121 | workers/workers/knowledge_artifacts.py |
| `load_config` | def | () -> dict[str, Any] | classifier.py:30-35 | — (internal: classify_document:66) |
| `_front_matter` | def | (text: str) -> dict[str, str] | classifier.py:38-49 | — (private) |
| `_lexicon_density` | def | (text: str, terms: list[list]) -> float | classifier.py:52-59 | — (private) |

## contracts

### classify_document(text, metadata=None) -> dict
- in: full document text; optional `metadata` dict that overrides front-matter values on key collision via `{**_front_matter(text), **(metadata or {})}` — classifier.py:67 [DERIVED]
- out: dict keys `router_version`, `primary_mode`, `modes` (max 5, sorted by confidence desc), `routing` (4 sorted tier lists), `enabled_extractors`, `signals` (nonzero modes only) — classifier.py:107-121 [DERIVED]
- pre: `knowledge_types.yaml` loadable and containing `modes`, else `ValueError` — classifier.py:33-34 [DERIVED]
- post: `primary_mode == "REFERENCE"` when no mode scores — classifier.py:101; policy = `routing_policy[primary]` or default `{"always": ["entity"], "preferred": [], "optional": [], "disabled": []}` — classifier.py:102-104; score = `s["metadata"] * 2 + s["structure"] * 2 + s["linguistic"]` — classifier.py:94-95; confidence = `round(v / total, 2)` — classifier.py:98 [DERIVED]

### load_config() -> dict
- in: none; reads `knowledge_types.yaml` next to the module — classifier.py:26, 31 [DERIVED]
- out: parsed yaml dict, memoized via `@lru_cache(maxsize=1)` — classifier.py:29, 35 [DERIVED]
- pre: file exists and opens — classifier.py:31 [DERIVED]
- post: `cfg["modes"]` truthy, else `ValueError("knowledge_types.yaml missing modes")` — classifier.py:33-34 [DERIVED]

### _front_matter(text) -> dict[str, str]
- in: document text; returns `{}` unless it starts with `---` and matches `^---\n(.*?)\n---\n` (DOTALL) — classifier.py:39-42 [DERIVED]
- out: keys/values from `key: value` lines, values whitespace-stripped and `"`-stripped — classifier.py:105-109 [DERIVED]

### _lexicon_density(text, terms) -> float
- in: text plus `terms` as `[term, weight]` pairs — classifier.py:52, 56-57 [DERIVED]
- out: `round(hits * 100.0 / n_words, 2)` with word-boundary regex `(?<!\w)term(?!\w)` on lowercased text — classifier.py:57-59 [DERIVED]
- pre: `n_words = max(len(low.split()), 1)` guards empty text — classifier.py:54 [DERIVED]

## effect surface
- File read: `knowledge_types.yaml` from module directory (`_HERE`) — classifier.py:26, 31 [DERIVED]
- Postgres tables: none (FACTS.tables_read / tables_written empty)
- Qdrant / network / subprocess / env flags: none visible in SOURCE

## invariants
INVARIANT: score weights == metadata `2`, structure `2`, linguistic `1` — classifier.py:94-95 [DERIVED]
  fails-if: retuning one multiplier silently reorders `primary_mode` and the chosen routing policy.
INVARIANT: `primary_mode` fallback == `"REFERENCE"` when `modes` empty — classifier.py:101 [DERIVED]
  fails-if: unknown primary hits the default policy `{"always": ["entity"], ...}` instead of a configured one.
INVARIANT: `enabled_extractors` == `set(routing.always) ∪ set(routing.preferred)`, both sorted — classifier.py:105-106, 113-114, 119 [DERIVED]
  fails-if: importer's extractor set diverges from the v1.1 tier contract.
INVARIANT: `n_words >= 1` — classifier.py:54 [DERIVED]
  fails-if: ZeroDivisionError on whitespace-only text.
INVARIANT: `total = sum(scored) or 1.0` — classifier.py:96 [DERIVED]
  fails-if: division by zero when no mode scores.
INVARIANT: reported `modes` length <= 5 (`modes[:5]`) — classifier.py:110 [DERIVED]
  fails-if: truncation hides modes whose scores still inflate the confidence denominator.
INVARIANT: explicit `metadata` arg overrides same-key front-matter values — classifier.py:67 [DERIVED]
  fails-if: callers cannot correct bad front matter.
INVARIANT: sum of confidences across scored modes == ~1.0 — classifier.py:96, 98 [INFERRED: each is v/total over the same total]
INVARIANT: `load_config` returns the same cached object per process — classifier.py:29 [DERIVED]
  fails-if: yaml edits mid-process are never observed.

## determinism & idempotency
determinism: DETERMINISTIC (pure regex/arithmetic over `text` plus one file read of `knowledge_types.yaml`; no clock/random/uuid/network/db — classifier.py:31, 57-59, 94-99) [DERIVED]
idempotency: SAFE (classify_document has no side effects; load_config memoized — classifier.py:29) [DERIVED]

## failure behaviour
- `ValueError("knowledge_types.yaml missing modes")` raised to caller when yaml lacks `modes` — classifier.py:33-34 [DERIVED]
- No try/except anywhere in SOURCE; missing yaml file propagates from the unguarded `open()` — classifier.py:31 [INFERRED: Python open semantics]
- Malformed yaml entries raise `KeyError`/unpack errors: `cfg["version"]` — classifier.py:108, `p["weight"]` — classifier.py:81, term tuple unpack — classifier.py:56 [INFERRED: direct indexing with no default]
- Nothing is swallowed; FACTS lists no fallbacks.

## dumb-code flags
- Magic multipliers `2`, `2`, `1` inline in the score formula — classifier.py:94-95 [DERIVED]
- Magic scale `100.0` and precision `2` in density; precision `2` again in confidence — classifier.py:59, 98 [DERIVED]
- Zero-signal dict literal `{"metadata": 0.0, "structure": 0.0, "linguistic": 0.0}` duplicated 3× — classifier.py:71, 78, 85 [DERIVED]
- Weight default asymmetry: metadata hints use `h.get("weight", 1)` — classifier.py:75; structure patterns require `p["weight"]` — classifier.py:81; lexicon weights are positional — classifier.py:56 [DERIVED]
- Inline default policy `{"always": ["entity"], "preferred": [], "optional": [], "disabled": []}` duplicates the yaml `routing_policy` shape and can drift — classifier.py:102-104 [DERIVED]
- `load_config` validates only `modes` but `classify_document` also indexes `cfg["version"]` unguarded — classifier.py:33-34 vs 108 [DERIVED]
- `modes[:5]` truncates after `total` was computed, so hidden modes still shrink every reported confidence — classifier.py:96-99, 110 [INFERRED: denominator includes truncated scores]
- Scoring loops `for mode in cfg["modes"]` only; a mode defined in `lexicons`/`structure_patterns`/`metadata_hints` but absent from `modes` is silently ignored — classifier.py:70-95 [DERIVED]

## refactor notes
- Importer `workers/workers/knowledge_artifacts.py` depends on the return shape: `router_version`, `primary_mode`, `modes`, `routing`, `enabled_extractors` (labelled "backward-compatible view"), `signals` — classifier.py:107-120; FACTS.importers [DERIVED]
- Tier names `always / preferred / optional / disabled` are the v1.1 contract; renaming breaks the routing output and default policy — classifier.py:14-15, 102-104, 112-117 [DERIVED]
- yaml schema consumed: `modes`, `version`, `metadata_hints` (`key`/`equals`/`weight`), `structure_patterns` (`regex`/`weight`), `lexicons` (`[term, weight]`), `routing_policy` — classifier.py:33, 70-75, 77-82, 84, 102, 108 [DERIVED]
- `@lru_cache(maxsize=1)` means config reload requires a new process — classifier.py:29 [DERIVED]
- Default extractor `"entity"` implies downstream extractors must accept that name — classifier.py:103 [DERIVED]
- `confidence.py` and `routing_policy.py` are currently empty; moving policy/confidence logic there must preserve the `classify_document` output contract — SOURCE headers with no content [DERIVED]

## VERIFY
```verify
grep -Fq 'knowledge_types.yaml missing modes' shared/polymath_shared/knowledge_router/classifier.py
grep -Fq 'lru_cache(maxsize=1)' shared/polymath_shared/knowledge_router/classifier.py
grep -Fq 'else "REFERENCE"' shared/polymath_shared/knowledge_router/classifier.py
grep -Eq 's\[.metadata.\] \* 2 \+ s\[.structure.\] \* 2' shared/polymath_shared/knowledge_router/classifier.py
! grep -Fq 'import random' shared/polymath_shared/knowledge_router/classifier.py
test "$(grep -c -F 'setdefault(mode,' shared/polymath_shared/knowledge_router/classifier.py)" -ge 3
```
