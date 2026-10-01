# unit: shared/polymath_shared/document_profile/profile_atom.py
anchor: shared/polymath_shared/document_profile/profile_atom.py:1-226
## purpose
Lifts routing atoms (THEORY / CONCEPT / LATENT-PATTERN / BOUNDARY / SEEALSO / BRIDGE / ANCHOR / TENSION / INVERSION / RECALLQ) out of a compiled document profile into first-class `document_profile_atoms` rows — "one atom = one dense vector" — for the atom retrieval lane (semantic routing/expansion, never factual evidence) — shared/polymath_shared/document_profile/profile_atom.py:1-10 [DERIVED].
Atoms from three families (`base`, `vnext`, `section`) live side by side; supersession is scoped per family/section so a fresh profile of one family never deactivates another's atoms — shared/polymath_shared/document_profile/profile_atom.py:17-29 [DERIVED].
Consumers: orchestrator/orchestrator/api/chat_retrieval.py, shared/polymath_shared/document_profile/profile_atom_projection.py, shared/polymath_shared/resolution_lift_gather.py, workers/workers/doc_profile_worker.py (FACTS.importers, module-level; per-symbol split not in FACTS).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `atom_id` | def | (doc_id, profile_contract, kind, text, section_key=None) -> str | 52-59 | — |
| `ProfileAtom` | class | frozen dataclass, 10 fields | 62-76 | — |
| `extract_atoms` | def | (compiled, *, doc_id, corpus_id, profile_contract, section_key=None, parent_ids=()) -> list[ProfileAtom] | 79-102 | — |
| `source_tag` | def | (family, compiled_hash, section_key=None) -> str | 110-119 | — |
| `family_of` | def | (source) -> str \| None | 122-125 | — |
| `section_key_of` | def | (source) -> str \| None | 128-133 | — |
| `persist_atoms` | def | (conn, *, doc_id, profile_contract, atoms, source=None) -> dict | 136-189 | — |
| `active_atoms` | def | (conn, *, corpus_id=None, doc_id=None, kinds=None) -> list[ProfileAtom] | 192-220 | — |
| `active_atom_count` | def | (conn, *, corpus_id) -> int | 223-226 | — |
| `PROFILE_ATOM_VERSION` | const | `"profile-atom-v1"` | 41 | — |
| `SCOPE_DOCUMENT` / `SCOPE_SECTION` | const | `"document"` / `"section"` | 48-49 | — |
| `PROFILE_FAMILIES` | const | `("base", "vnext", "section")` | 107 | — |

## contracts
**atom_id** — 52-59
- in: doc_id, profile_contract, kind, text, optional section_key.
- out: `"atom_" + sha256(f"{doc_id}|{profile_contract}|{kind}|{_norm(text).lower()}")[:24]` — 56-59.
- post: with `section_key`, key gains `|section:{section_key}` (57-58); without it the id is byte-identical to pre-F4 behaviour (docstring 55-56).
- post: same inputs ⇒ same id (idempotent) — 53.

**extract_atoms** — 79-102
- in: `compiled` = `doc_profile.compiled` dict (or compiler Record's dict) — 83.
- pre: text normalized via `_norm` (whitespace collapse, 44-45); empty normalized text skipped (91-92).
- out: one `ProfileAtom` per non-empty item across the 10 kinds in `_ATTR_TO_KIND` order, deduped by `atom_id` (i.e. by (kind, normalized text)) — 82, 88-96.
- post: with `section_key`, atoms get `scope=SCOPE_SECTION`, the key, and `parent_ids` (97-99); ordinal = enumerate index `i` within the attr list (89, 98, 101).

**source_tag** — 110-119
- pre: `family in PROFILE_FAMILIES` else `ValueError` (113-114); `family == "section"` requires non-empty `section_key` else `ValueError` (115-117).
- out: `"family:compiled_hash"` or `"section:<section_key>:<compiled_hash>"`; empty hash → empty string after the colon (118-119).

**family_of** — 122-125
- in: a `source_profile_hash` string or None.
- out: text before the first `":"` if it is in PROFILE_FAMILIES, else None (untagged/legacy/unknown) — 124-125.

**section_key_of** — 128-133
- out: `parts[1]` of `section:<key>:<hash>` when non-empty; None for every other source (130-133).

**persist_atoms** — 136-189
- pre: if `source` is given, `family_of(source)` must be non-None else `ValueError` (144-147).
- with source: reads the doc's active rows for `(doc_id, profile_contract)` (148-152); deactivates only same-family rows — or untagged legacy rows — for document families (157-158); for `section`, only rows of the SAME `section_key` (153-156); upserts each atom `ON CONFLICT (atom_id) DO UPDATE SET active=TRUE` recording `source_profile_hash` (164-172).
- without source: deactivates ALL active rows for `(doc_id, profile_contract)` (174-178), then upserts without a source tag (180-188).
- out: `{"active": len(atoms), "deactivated": len(doomed), "family": fam}` (173) or `{"active": len(atoms), "deactivated": deactivated}` (189). Idempotent (139).

**active_atoms** — 192-220
- in: optional corpus_id / doc_id / kinds filters (197-206).
- out: rows `ORDER BY doc_id, atom_kind, ordinal` (209-210); section rows re-projected with `scope=SCOPE_SECTION` + `section_key` from `source_profile_hash` (215-218); `parent_ids` not restored (empty tuple) — docstring admits this at 73-74.

**active_atom_count** — 223-226
- out: `count(*)` where `active AND corpus_id=%s` (225).

## effect surface
- Postgres `document_profile_atoms`: SELECT 149-150, 208-209, 225; UPDATE 161, 175; INSERT ... ON CONFLICT 166-171, 182-187. [DERIVED]
- FACTS.tables_written also lists `"set"` — [INFERRED] scanner artifact of the SQL keyword `SET` in the UPDATE statements (161, 175), not a real table.
- Reads taxonomy constants from `polymath_shared.surface_registry`: `ATOM_KINDS`, `ATTR_TO_KIND`, `MECHANISM_KINDS`, `REDISCOVERY_KINDS`, `RELATIONAL_KINDS` — 37-39 (only `ATTR_TO_KIND` is used in the body, as `_ATTR_TO_KIND` at 88).
- No files, network, subprocess, or env flags anywhere in SOURCE.

## invariants
INVARIANT: atom_id == `"atom_" +` sha256 hex `[:24]` — shared/polymath_shared/document_profile/profile_atom.py:59 [DERIVED]
  fails-if: changing prefix or truncation re-keys every existing row; re-persists duplicate instead of reactivating.
INVARIANT: same (doc_id, profile_contract, kind, normalized lower text [, section_key]) ⇒ same atom_id — shared/polymath_shared/document_profile/profile_atom.py:53-59 [DERIVED]
  fails-if: persist stops being idempotent; ON CONFLICT never fires; atom lane accumulates dead duplicates.
INVARIANT: PROFILE_FAMILIES == `("base", "vnext", "section")`, len == 3 — shared/polymath_shared/document_profile/profile_atom.py:107 [DERIVED]
  fails-if: a new family not added here makes `family_of` return None for its tags → those rows get swept by ANY family's supersession (158).
INVARIANT: tagged deactivated set ⊆ {rows with family_of(r) ∈ (fam, None)}; for `section` additionally section_key_of(r) == skey — shared/polymath_shared/document_profile/profile_atom.py:153-158 [DERIVED]
  fails-if: cross-family deactivation — exactly the 2026-09-08 regression named at 21-22.
INVARIANT: extract_atoms output has no duplicate atom_id — shared/polymath_shared/document_profile/profile_atom.py:93-96 [DERIVED]
  fails-if: duplicate dense vectors per doc/kind in the atom lane.
INVARIANT: section atom_id ≠ document atom_id for identical text (suffix `|section:{section_key}`) — shared/polymath_shared/document_profile/profile_atom.py:57-58 [DERIVED]
  fails-if: a section rebuild would ON CONFLICT-clobber the document's own atom row.
INVARIANT: section atoms keep the DOCUMENT's doc_id — shared/polymath_shared/document_profile/profile_atom.py:26-28 [DERIVED]
  fails-if: routing no longer lands on the document; payload parent chains break.
INVARIANT: every atom read back by active_atoms has `parent_ids == ()` — shared/polymath_shared/document_profile/profile_atom.py:217,219 (acknowledged at 73-74) [DERIVED]
  fails-if: any consumer relying on the parent chain after re-projection silently gets empty tuples.
INVARIANT: every upserted row ends `active=TRUE` — shared/polymath_shared/document_profile/profile_atom.py:168-170, 184-186 [DERIVED]
  fails-if: fresh profiles leave stale inactive rows; atom lane starves.

## determinism & idempotency
determinism: DETERMINISTIC (atom_id/extract_atoms/source_tag/family_of/section_key_of are pure — hashlib + input dicts, 33, 44-133; persist/read depend on db state; `updated_at=now()` stamps wall clock at 161, 170, 175, 186) [DERIVED]
idempotency: SAFE (same atoms re-persisted hit `ON CONFLICT (atom_id) DO UPDATE SET active=TRUE` — 169-170, 185-186; docstring states idempotent at 15 and 139) [DERIVED]

## failure behaviour
- `ValueError(f"source must be family:compiled_hash, got {source!r}")` when a `source` has no known family prefix — 145-147.
- `ValueError(f"unknown profile family {family!r}")` from source_tag — 113-114.
- `ValueError("a section source needs its section_key")` from source_tag — 116-117.
- No try/except anywhere; SQL/driver errors propagate raw to the caller — 136-226. FACTS lists no fallbacks.

## dumb-code flags
- Magic truncation `[:24]` in atom_id — 59; baked into every stored row.
- `getattr(cur, "rowcount", 0) or 0` only guards missing/0; a driver rowcount of `-1` propagates as `-1` into the return dict — 179 [INFERRED: psycopg-style drivers can return -1].
- Legacy branch (source=None) deactivates ALL families' rows (175-176) but its ON CONFLICT update never sets `source_profile_hash` (185-186) — a previously family-tagged atom re-activated this way keeps its stale tag, so a later family-scoped persist skips it (158) [INFERRED: mixed-mode callers hit this].
- `family_of` maps ANY unknown/no-colon prefix (typos) to legacy None — 124-125; a mistyped source widens supersession to untagged rows silently.
- Two near-identical INSERT ... ON CONFLICT blocks (tagged 166-171 vs legacy 182-187) — drift risk on any schema/column change.
- FACTS.tables_written includes `"set"` — scanner artifact, not a table (161, 175) [INFERRED].

## refactor notes
- atom_id grammar (`doc|contract|kind|normtext[|section:key]`, sha256[:24]) is the durable primary key of `document_profile_atoms`; any change orphans every row. All four FACTS.importers touch this module: orchestrator/orchestrator/api/chat_retrieval.py, shared/polymath_shared/document_profile/profile_atom_projection.py, shared/polymath_shared/resolution_lift_gather.py, workers/workers/doc_profile_worker.py.
- `source_profile_hash` grammar is round-tripped by family_of/section_key_of and the active_atoms re-projection (215-218); changing the tag format makes every existing row read as legacy None → whole-contract supersession regression (157-158, 174-178).
- Extending PROFILE_FAMILIES requires family_of/section_key_of/persist_atoms to agree (107, 124-125, 153-158) or new-family rows get legacy semantics.
- Kind taxonomy and extraction order come from `surface_registry.ATTR_TO_KIND` (37-39, 88); registry edits change extracted atom sets with zero diff in this file.
- Section rows keep the document's doc_id by design (26-28); re-keying them to section ids changes atom_id collision behaviour (57-58) and routing.

## VERIFY
```verify
grep -Fq 'PROFILE_ATOM_VERSION = "profile-atom-v1"' shared/polymath_shared/document_profile/profile_atom.py
grep -Fq 'PROFILE_FAMILIES = ("base", "vnext", "section")' shared/polymath_shared/document_profile/profile_atom.py
grep -Fq 'return "atom_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]' shared/polymath_shared/document_profile/profile_atom.py
grep -Fq 'ON CONFLICT (atom_id) DO UPDATE SET active=TRUE' shared/polymath_shared/document_profile/profile_atom.py
! grep -Fq 'import uuid' shared/polymath_shared/document_profile/profile_atom.py
grep -Eq 'UPDATE document_profile_atoms SET active=FALSE, updated_at=now\(\)' shared/polymath_shared/document_profile/profile_atom.py
```
