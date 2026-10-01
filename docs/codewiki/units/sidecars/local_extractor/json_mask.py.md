# unit: sidecars/local_extractor/json_mask.py
anchor: sidecars/local_extractor/json_mask.py:1-403

## purpose
Logits mask for the local extraction lane: a permissive-JSON state machine compiled to per-state token bitmasks over each token's decoded text; at each decode step the prefix state is tracked incrementally and clearly-illegal tokens get `-inf`. String contents stay free; the sanitize->validate gate enforces the full contract after generation — sidecars/local_extractor/json_mask.py:16-26 [DERIVED].
STATUS (2026-08-30): EXPERIMENTAL, env-gated OFF (`POLYMATH_JSON_MASK=off` in the sidecar env); parked failure class is shape-legal-but-schema-illegal JSON from the 4B, fix named as schema-aware masking (xgrammar), "not more permissive-grammar patches" — sidecars/local_extractor/json_mask.py:3-14 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `make_json_mask` | function | `(tokenizer)` -> processor or None | sidecars/local_extractor/json_mask.py:396-402 | — |
| `JsonGrammarMask` | class | `(tokenizer)` -> mask holder | sidecars/local_extractor/json_mask.py:62-393 | — |
| `JsonGrammarMask.processor` | method | `(tokens, logits)` -> logits | sidecars/local_extractor/json_mask.py:317-367 | mlx_lm logits_processor list, documented usage `make_logits_processors(...) + [mask]` — sidecars/local_extractor/json_mask.py:28-31 |

## contracts
**make_json_mask(tokenizer)** — sidecars/local_extractor/json_mask.py:396-402
- in: tokenizer with `len()` or `get_vocab()` (83-86) and `batch_decode` (91-92)
- out: bound `JsonGrammarMask(tokenizer).processor` (400) or `None` on any `Exception` (401-402)
- pre: `polymath_shared.llm_extraction.ontology.RELATION_ONTOLOGY` importable (59)
- post: fail-open — `None` means unmasked generation; prompt + gate enforcement still apply (397-398)

**processor(tokens, logits)** — sidecars/local_extractor/json_mask.py:317-367
- in: mlx_lm signature `(mx tokens, mx logits) -> logits` (318); numpy logits handled by `is_mx=False` path (323, 452)
- out: logits with disallowed ids at `-inf` — `mx.where(mx_m, neg, logits)` (391) or in-place `logits[m] = float("-inf")` (452)
- pre: first call per sequence happens at prefill (0 generated); prompt length captured then, keyed by `tuple(ids[:16])` (66-70, 325-331)
- post: per-sequence tracker advanced by only the newly sampled tokens (342-347); predicate strings masked to the enum trie only while on-trie (356-363); EOS unmasked only at `S_DONE` (380-384)

## effect surface
- Postgres: none (FACTS `tables_read`/`tables_written` empty)
- Qdrant / network / subprocess / file writes: none in this unit
- import: `polymath_shared.llm_extraction.ontology.RELATION_ONTOLOGY` — sidecars/local_extractor/json_mask.py:59
- env: `POLYMATH_JSON_MASK` referenced as `off` in the sidecar env — sidecars/local_extractor/json_mask.py:3-4; not read inside this file [DERIVED]
- memory caches only: `_prompt_lens` (70), `_seq_state` (75), `_cache` (65), `_enum_mask_cache` (78); `_prompt_lens`/`_seq_state` cleared when > `8192` entries (330-331, 337-340)

## invariants
INVARIANT: `_FREE_STATES = (S_STR_BODY, S_KEY_BODY, S_STR_ESC, S_KEY_ESC)` are never masked — sidecars/local_extractor/json_mask.py:53,96-101 [DERIVED]
  fails-if: over-masking string bodies; measured degeneration when first-char checks over-masked (81-83)
INVARIANT: EOS unmasked only at `S_DONE` (`m[self._stop] = False`); `S_DONE` pattern is `\s*$` — sidecars/local_extractor/json_mask.py:51,383-384 [DERIVED]
  fails-if: everywhere-exempt → model stops mid-object; never-exempt → `'}'` soup (380-382)
INVARIANT: enum trie constrains only while `pred_buf` is a prefix of some id in `_enum_ids` (`on_trie`); off-trie returns raw logits — sidecars/local_extractor/json_mask.py:356-363 [DERIVED]
  fails-if: off-trie strings boxed into near-empty legal set → whitespace/letter soup (350-355)
INVARIANT: `_enum_ids = sorted(set(list(RELATION_ONTOLOGY) + [p.lower() for p in RELATION_ONTOLOGY]))` — original + lowercase ids — sidecars/local_extractor/json_mask.py:105-106 [DERIVED]
  fails-if: case-variant predicates fall off-trie and rely on gate normalization
INVARIANT: seq key `tuple(ids[:16])` shared by `_prompt_lens` and `_seq_state` — sidecars/local_extractor/json_mask.py:325-333 [DERIVED]
  fails-if: two concurrent sequences with identical first 16 tokens share prompt length + tracker → wrong state [INFERRED]
INVARIANT: logits-width padding pads the tail as masked: `pad = np.ones(width, dtype=bool)` — sidecars/local_extractor/json_mask.py:376-379 [DERIVED]
  fails-if: vocab-size vs logits-width mismatch masks nothing or errors
INVARIANT: both cache-clear thresholds are `8192` — sidecars/local_extractor/json_mask.py:330,337 [DERIVED]
  fails-if: unbounded memory; clear mid-sequence resets the tracker to `S_START` (334-340)

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/env/db/network reads; output is a pure function of tokenizer vocab + token stream; caches are memo tables keyed by content (65, 78, 293, 372) — sidecars/local_extractor/json_mask.py:62-402 [DERIVED]. Dict caches are unguarded — [INFERRED] single-lane assumption.
idempotency: SAFE — re-calling `processor` with the same token stream advances nothing (`consumed == len(gen)`, 342-347) and re-masking is monotone (`-inf` stays `-inf`, 391-392); numpy path mutates logits in place (452).

## failure behaviour
- `make_json_mask`: bare `except Exception:` → `return None` (FACTS fallbacks: SWALLOWED) — sidecars/local_extractor/json_mask.py:401-402; caller sees `None` and proceeds unmasked, gate still enforces (397-398, 22-26)
- off-trie predicate value: logits returned unmasked, gate normalizes — sidecars/local_extractor/json_mask.py:363,353-355
- all-allowed state: logits returned untouched (`allowed.all()` short-circuit) — sidecars/local_extractor/json_mask.py:364-366
- vocab-size probe fallback: `len(self.tok)` TypeError → `len(self.tok.get_vocab())` — sidecars/local_extractor/json_mask.py:83-86

## dumb-code flags
- Dead code: `conts` set built, never read — sidecars/local_extractor/json_mask.py:298-301
- Dead attribute: `self._tok_vocab` assigned, never used — sidecars/local_extractor/json_mask.py:104
- Comment/code drift: `_stop_ids` docstring says stop ids "NEVER masked" (110-111), but `_apply` exempts them only at `S_DONE` (380-384)
- Magic numbers: `16` in `tuple(ids[:16])` (325); `8192` twice (330, 337); `CH = 4096` (89); slice `len(buf)+8` (301)
- Duplicated parser: `_Tracker.feed` (140-218) vs `_state_for` (221-285) — same state machine written twice
- `break` after first match: only the first token whose text starts with `"` may close a predicate string, even if the vocab has several — sidecars/local_extractor/json_mask.py:308-312
- `_apply` cache key uses `id(allowed)` — ids can be reused after GC — sidecars/local_extractor/json_mask.py:372 [INFERRED]

## refactor notes
- `processor` signature `(tokens, logits) -> logits` is the mlx_lm logits_processor contract; documented usage appends it to `make_logits_processors(...)` — sidecars/local_extractor/json_mask.py:28-31,318
- Ontology coupling: `RELATION_ONTOLOGY` ids define the trie (59, 105-106); renaming predicates changes the masked set
- Per-sequence keying by first-16-token tuple and prefill prompt-length capture must survive any batching refactor — sidecars/local_extractor/json_mask.py:66-70,325-340
- `_compile` mutates `self._texts`/`self._tok_vocab`/`self._enum_ids` as side effects (103-106); `__init__` order feeds `_enum_allowed_cont` (303-308)
- `_state_for` is retained "for tests/offline use" (124); any `feed()` change must be mirrored or tests diverge
- Stated direction: schema-aware masking (xgrammar in an isolated venv), not more permissive-grammar patches — sidecars/local_extractor/json_mask.py:11-13

## VERIFY
```verify
grep -Fq 'POLYMATH_JSON_MASK=off' sidecars/local_extractor/json_mask.py
grep -Fq 'def make_json_mask(tokenizer):' sidecars/local_extractor/json_mask.py
grep -Fq 'key = tuple(ids[:16])' sidecars/local_extractor/json_mask.py
grep -Fq 'm[self._stop] = False' sidecars/local_extractor/json_mask.py
grep -Fq 'return mx.where(mx_m, neg, logits)' sidecars/local_extractor/json_mask.py
test "$(grep -c -F 'self._enum_ids' sidecars/local_extractor/json_mask.py)" -ge 4
! grep -Fq 'import os' sidecars/local_extractor/json_mask.py
```
