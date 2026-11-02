# unit: shared/polymath_shared/adapter/corpus_seed.py
anchor: shared/polymath_shared/adapter/corpus_seed.py:1-196

## purpose
Resolves a product-search run's CORPUS SCOPE and, when the requester gives no seed, derives its CORPUS SEED at `service.start` (shared/polymath_shared/adapter/corpus_seed.py:1-12) [DERIVED]. The seed is a routing need only — never an evidence row, never citable (skeleton law, shared/polymath_shared/adapter/corpus_seed.py:14-16) [DERIVED]. All DB reads go through the caller-supplied `catalog` (the store module in production, its double in tests), keeping the derivation pure (shared/polymath_shared/adapter/corpus_seed.py:18, 53-54) [DERIVED].

## public surface
Module imported by: `orchestrator/orchestrator/api/adapter.py`, `shared/polymath_shared/adapter/service.py` (FACTS.importers; per-symbol use not stated in FACTS).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `StartRefused` | class | `(code: str, message: str, hint: str \| None = None) -> ValueError` | shared/polymath_shared/adapter/corpus_seed.py:40-49 | adapter.py, service.py (module importers) |
| `resolve_scope` | def | `(conn, catalog, input_payload, options, *, config, corpus_view, seed) -> dict` | shared/polymath_shared/adapter/corpus_seed.py:81-110 | adapter.py, service.py (module importers) |
| `corpus_seed` | def | `(conn, catalog, corpus_ids) -> dict` | shared/polymath_shared/adapter/corpus_seed.py:189-196 | adapter.py, service.py (module importers) |
| `derive_seed` | def | `(profiles, atoms, summaries, corpus_ids) -> dict \| None` | shared/polymath_shared/adapter/corpus_seed.py:118-186 | — |
| `rank_corpora` | def | `(candidates, profiles, seed) -> list[str]` | shared/polymath_shared/adapter/corpus_seed.py:67-78 | — |

Private helpers: `_named` (:58-60), `_tokens` (:63-64), `_norm` (:114-115), `_STOP` word set (:34-37).

## contracts

**`resolve_scope`** (shared/polymath_shared/adapter/corpus_seed.py:81-110)
- in: named ids taken from `input_payload["corpus_ids"]` then `options["corpus_ids"]`, deduped, strings only (:59-60) [DERIVED]
- pre: none; raises on bad state [DERIVED]
- out: `{"corpus_ids": [...], "origin": "named" | "default", "candidates": n, "ranked_by": ...}` (:83, 109-110) [DERIVED]
- post (named): every named id exists in `catalog.corpora(conn, named)` and has `query_ready` truthy, else StartRefused (:88-96) [DERIVED]
- post (default): pool = corpora with `in_all_libraries` truthy, narrowed by `corpus_view(ids)` when given; result ⊆ pool, `len(result) <= cap` where `cap = max(1, min(int(cfg.get("max_corpora") or 32), 32))` (:98-109, 106) [DERIVED]
- raises: `CORPUS_UNKNOWN` (:91), `CORPUS_NOT_READY` (:95), `QUERY_SCOPE_EMPTY` (:103) [DERIVED]

**`corpus_seed`** (shared/polymath_shared/adapter/corpus_seed.py:189-196)
- in: `corpus_ids` sequence [DERIVED]
- out: `derive_seed(catalog.profiles(...), catalog.atoms(...), catalog.summaries(...), corpus_ids)` (:191-192) [DERIVED]
- post: never returns None — raises `SEED_UNAVAILABLE` when `derive_seed` yields None (:193-195) [DERIVED]

**`derive_seed`** (shared/polymath_shared/adapter/corpus_seed.py:118-186)
- in: profile/atom/summary mappings + corpus_ids [DERIVED]
- out: `{"seed": text, "lineage": {derivation, corpora, fields, doc_ids, signals_read, authority, seed_sha256}}` or None (:182-186) [DERIVED]
- post: None ⇔ no topics AND no question AND no tension (:163-164) [DERIVED]
- post: topic order = curated `research_topics` (sorted by corpus_id) first, then `doc_profile.topics` by descending doc count with text-order ties, then `dominant_concepts` only when no profile has topics; capped at `MAX_TOPICS = 3` (:132-147) [DERIVED]
- post: one question (≤300 chars) preferring docs carrying the top topic (:149-155); one tension — first `TENSION` atom, else `LATENT_PATTERN`, text 1–300 chars (:156-162) [DERIVED]
- post: seed text = `"The problems, workarounds and situations people meet around {topics}."` + `"Open question: …?"` + `"Tension: …."`, truncated to `SEED_MAX_CHARS = 600` (:165-174) [DERIVED]

**`rank_corpora`** (shared/polymath_shared/adapter/corpus_seed.py:67-78)
- out: corpus ids sorted by key `(-seed-word overlap with profile topics+terms, -documents, corpus_id)`; overlap term is 0 when no seed (:223-226) [DERIVED]

**`StartRefused`** (shared/polymath_shared/adapter/corpus_seed.py:40-49)
- attrs: `code`, `message`, `hint`, `errors` (one formatted string) (:43-46); `detail() -> {"error_code", "message", "hint", "errors"}` (:48-49) [DERIVED]

## effect surface
- Postgres tables read/written directly: none (FACTS `tables_read: []`, `tables_written: []`); all reads delegated to `catalog.corpora` / `catalog.profiles` / `catalog.atoms` / `catalog.summaries` (shared/polymath_shared/adapter/corpus_seed.py:53-54, 88, 98, 191) [DERIVED]
- Qdrant / files / network / subprocess / env flags: none visible in SOURCE [DERIVED]

## invariants
INVARIANT: `len(resolve_scope().corpus_ids) <= cap <= REQUEST_MAX_CORPORA = 32` — shared/polymath_shared/adapter/corpus_seed.py:106,109 [DERIVED]
  fails-if: run exceeds the request contract's `corpus_ids` maxItems (32) and the request is rejected downstream.
INVARIANT: `origin == "named"` ⇒ every id existed and was `query_ready` — shared/polymath_shared/adapter/corpus_seed.py:88-97 [DERIVED]
  fails-if: a run starts on a corpus with no searchable document and dies later with INPUT_SCOPE_MISSING (the failure this gate exists to prevent, :7-8).
INVARIANT: `len(topics) <= MAX_TOPICS = 3` — shared/polymath_shared/adapter/corpus_seed.py:147 [DERIVED]
  fails-if: seed text grows past intended breadth and hits the 600-char truncation.
INVARIANT: `len(seed) <= SEED_MAX_CHARS = 600` — shared/polymath_shared/adapter/corpus_seed.py:174 [DERIVED]
  fails-if: seed exceeds the storage/contract bound for seed text.
INVARIANT: `len(lineage.doc_ids) <= MAX_LINEAGE_DOCS = 50` and per-field `len(doc_ids) <= 5` — shared/polymath_shared/adapter/corpus_seed.py:176,183 [DERIVED]
  fails-if: receipt lineage grows unboundedly with corpus size.
INVARIANT: `lineage.seed_sha256 == sha256(seed utf-8).hexdigest()` — shared/polymath_shared/adapter/corpus_seed.py:186 [DERIVED]
  fails-if: stored seed and its fingerprint disagree; receipt audit breaks.
INVARIANT: topic keys are normalized (`_norm`) and ≤120 chars; question and tension text ≤300 chars — shared/polymath_shared/adapter/corpus_seed.py:129,152,158-159 [DERIVED]
  fails-if: oversized profile text enters the seed and truncation ordering becomes unstable.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/env reads; every ordering pinned by explicit `sorted()` keys (shared/polymath_shared/adapter/corpus_seed.py:126,132,138,142,151,158) and stable tie-breaks; output is a pure function of the catalog rows passed in [DERIVED]
idempotency: SAFE — read-only (no writes anywhere in SOURCE; FACTS `tables_written: []`); repeated calls on the same catalog state return equal dicts including `seed_sha256` (shared/polymath_shared/adapter/corpus_seed.py:186) [DERIVED]

## failure behaviour
No try/except in the module — nothing is swallowed; `StartRefused` (a `ValueError`) propagates to the caller (shared/polymath_shared/adapter/corpus_seed.py:40, 91, 95, 103, 194) [DERIVED].

| code | trigger | anchor |
|---|---|---|
| `CORPUS_UNKNOWN` | named corpus id absent from `catalog.corpora` | shared/polymath_shared/adapter/corpus_seed.py:91-92 |
| `CORPUS_NOT_READY` | named corpus has `query_ready` falsy | shared/polymath_shared/adapter/corpus_seed.py:95-96 |
| `QUERY_SCOPE_EMPTY` | default pool empty after `in_all_libraries` + `corpus_view` filters | shared/polymath_shared/adapter/corpus_seed.py:103-105 |
| `SEED_UNAVAILABLE` | `derive_seed` returns None (no profile topic/question/atom signal) | shared/polymath_shared/adapter/corpus_seed.py:194-195 |

Each carries `code`/`message`/`hint` and surfaces via `detail()` with keys `error_code`, `message`, `hint`, `errors` (shared/polymath_shared/adapter/corpus_seed.py:48-49) [DERIVED].

## dumb-code flags
- `MAX_QUESTIONS = 1` and `MAX_TENSIONS = 1` are defined but never referenced; the "one each" rule is hardcoded via `next(...)`/`break` — shared/polymath_shared/adapter/corpus_seed.py:28 vs 152,157-162 [DERIVED]
- `cfg.get("max_corpora") or REQUEST_MAX_CORPORA` — `max_corpora = 0` silently becomes 32 (falsy `or` fallback) while a negative value is clamped to 1 by `max(1, ...)`: 0 and -1 take different paths — shared/polymath_shared/adapter/corpus_seed.py:106 [INFERRED: 0 is falsy in Python, so `or` fires]
- predicate `seed and len(pool) > cap` computed at :107 and re-evaluated inside the `ranked_by` conditional at :110 — duplicated condition — shared/polymath_shared/adapter/corpus_seed.py:107,110 [DERIVED]
- magic `doc_ids[:5]` in lineage fields, unrelated to `MAX_LINEAGE_DOCS = 50` — shared/polymath_shared/adapter/corpus_seed.py:176 [DERIVED]
- seed text truncated to 600 chars but lineage field `value` texts are untruncated — seed and lineage can disagree on content — shared/polymath_shared/adapter/corpus_seed.py:174,176-180 [INFERRED: only `seed` gets `[:SEED_MAX_CHARS]`]
- FACTS renders `SEED_ATOM_KINDS` as `["TENSION", "LATENT_PATTERN"]`; SOURCE has the tuple `("TENSION", "LATENT_PATTERN")` — shared/polymath_shared/adapter/corpus_seed.py:31 [DERIVED]

## refactor notes
- `resolve_scope`'s return keys (`corpus_ids`, `origin`, `candidates`, `ranked_by`) and the seed lineage are start-receipt data at `service.start` — shared/polymath_shared/adapter/corpus_seed.py:4,9-12; importers `orchestrator/orchestrator/api/adapter.py` and `shared/polymath_shared/adapter/service.py` (FACTS.importers) [DERIVED]
- Error codes and `detail()` key names are API-visible; renaming breaks both importers — shared/polymath_shared/adapter/corpus_seed.py:48-49,91,95,103,194 [DERIVED]
- `DERIVATION = "corpus-seed-v1"` is persisted in lineage; changing it versions every stored receipt — shared/polymath_shared/adapter/corpus_seed.py:27,183 [DERIVED]
- `authority` literal `"ROUTING ONLY — the seed is a retrieval need derived from document profiles, never evidence"` is contract text enforcing the skeleton law — shared/polymath_shared/adapter/corpus_seed.py:185, and 14-16 [DERIVED]
- The `catalog` reader names (`corpora`, `profiles`, `atoms`, `summaries`) are the store contract; signature changes hit store.py and its test double — shared/polymath_shared/adapter/corpus_seed.py:53-54,88,98,191 [DERIVED]
- `_STOP` and the `len(w) >= 3` token threshold directly change `rank_corpora` ordering — shared/polymath_shared/adapter/corpus_seed.py:34-37,63-64 [DERIVED]

## VERIFY
```verify
grep -Fq 'DERIVATION = "corpus-seed-v1"' shared/polymath_shared/adapter/corpus_seed.py
grep -Fq 'class StartRefused(ValueError):' shared/polymath_shared/adapter/corpus_seed.py
grep -Fq 'SEED_ATOM_KINDS = ("TENSION", "LATENT_PATTERN")' shared/polymath_shared/adapter/corpus_seed.py
grep -Eq 'raise StartRefused\("(CORPUS_UNKNOWN|CORPUS_NOT_READY|QUERY_SCOPE_EMPTY|SEED_UNAVAILABLE)"' shared/polymath_shared/adapter/corpus_seed.py
grep -Fq '"seed_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest()' shared/polymath_shared/adapter/corpus_seed.py
test "$(grep -c -F 'raise StartRefused' shared/polymath_shared/adapter/corpus_seed.py)" -ge 4
```
