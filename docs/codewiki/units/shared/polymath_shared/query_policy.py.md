# unit: shared/polymath_shared/query_policy.py
anchor: shared/polymath_shared/query_policy.py:1-200

## purpose
Versioned translation layer between durable canonical Polymath core types and replaceable provider-facing GLiNER query labels; every GLiNER query (discovery pass 1 and every rescue query) resolves its labels through this policy, and raw provider labels are kept alongside their canonical mapping — shared/polymath_shared/query_policy.py:3-8 [DERIVED]. The compiler, predicate rules, and canonicalizer never see provider aliases — shared/polymath_shared/query_policy.py:7-8 [DERIVED]. Also hosts the domain-module discovery vocabulary (provider-facing query configuration, not canonical semantics) — shared/polymath_shared/query_policy.py:24-26 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| DomainModule | class (frozen dataclass) | module_id: str, version: str, labels: dict[str, CoreType], path_hints: tuple[str, ...] = (), keywords: tuple[str, ...] = () | :38-44 | — |
| active_policy_version | def | () -> str | :134-137 | — |
| provider_alias_map | def | () -> dict[str, str] | :140-144 | — |
| provider_passes | def | () -> list[tuple[str, ...]] | :147-160 | — |
| query_labels_for | def | (core_type: str) -> tuple[str, ...] | :163-168 | — |
| canonical_of | def | (raw_label: str) -> str \| None | :171-186 | — |
| policy_identity | def | () -> dict | :189-199 | — |

Module-level importers (FACTS.importers; per-symbol split not in FACTS): shared/polymath_shared/execution.py, shared/polymath_shared/llm_extraction/gate.py, shared/polymath_shared/observability.py, workers/workers/_small-modules, workers/workers/extract_worker.py, workers/workers/llm_direct.py.
Public constants: CORE_LABELS (:34), MODULES (:47), QUERY_POLICY_V1/V2/V3 (:104-106), QUERY_POLICY_VERSION (:107), SCIENTIFIC_PASS_LABELS (:113-120), PROVIDER_ALIASES_V2 (:122-131).

## contracts

**active_policy_version** (:134-137)
- in: none; `import os` executed inside the function on every call (:135).
- out: env `POLYMATH_QUERY_POLICY` verbatim, or `QUERY_POLICY_V1` (`"semantic-query-policy-v1"`) when unset (:137).
- pre: none.
- post: no validation — any string passes through and drives every version branch downstream (:142, :152, :166, :191-192) [DERIVED].

**provider_alias_map** (:140-144)
- out: `{}` iff active version == QUERY_POLICY_V1; otherwise flattened alias -> canonical from PROVIDER_ALIASES_V2 (:142-144).
- post: non-v1 gate only — under v3 the v2 alias map is returned as well (:142-144) [DERIVED].

**provider_passes** (:147-160)
- out v1: `[tuple(CORE_LABELS)]` — one identity pass (:151-153).
- out v3: `[tuple(t.value for t in CoreType)[:12], core, SCIENTIFIC_PASS_LABELS]` (:154-156).
- out v2 (and any other version string): `[core, enriched]`; enriched = deduped core labels, each followed by its aliases (:157-160).
- post: docstring promises v1 is the "byte-identical baseline" (:148-149).

**query_labels_for** (:163-168)
- in: canonical core type name (single-label-per-request rescue regime, :164-165).
- out: `(core_type,)` under v1; otherwise `(core_type,) + PROVIDER_ALIASES_V2.get(core_type, ())` (:166-168).

**canonical_of** (:171-186)
- in: raw provider label.
- out: the label itself if in `_CORE_LABEL_SET` (:177-178); else alias-map canonical (:179-181); else first MODULES entry containing it, returned as `core.value` (:182-185); else `None` (:186).
- post: alias map is consulted before MODULES (:180 vs :182) [DERIVED]; unknown labels are "rejected loudly downstream — never silently coerced" (:174-176) — this module itself raises nothing.

**policy_identity** (:189-199)
- out: `{"query_policy_version": version, "aliases": {k: list(v)} sorted — non-empty only when version == QUERY_POLICY_V2, "passes": "identity+enriched" | "legacy+core+scientific" | "identity"}` (:191-198).
- post: self-described as "The policy's contribution to the extraction contract identity." (:190).

## effect surface
- env: `POLYMATH_QUERY_POLICY` = `QUERY_POLICY_V1` (`"semantic-query-policy-v1"`) default — :137.
- Postgres tables: none (FACTS.tables_read / tables_written empty).
- Qdrant / network / files / subprocess: none in :1-199.
- imports: `polymath_shared.contracts.CoreType` (:32).

## invariants

INVARIANT: provider_alias_map() under `"semantic-query-policy-v1"` == `{}` — :142-143 [DERIVED]
  fails-if: v1 stops being the byte-identical baseline promised at :21-22.
INVARIANT: len(provider_passes()) == 1 (v1), 2 (v2), 3 (v3) — :152-160 [DERIVED]
  fails-if: GLiNER query fan-out and call count change; the deterministic union contract (:98-102) then mixes passes differently.
INVARIANT: SCIENTIFIC_PASS_LABELS == CoreType values minus exactly {Person, Organization, Location, Product, Technology, Concept, Method, Event, Document, Process, Measurement, TimeReference} — :113-120 [DERIVED]
  fails-if: scientific pass re-queries legacy labels or silently drops new CoreType members.
INVARIANT: canonical_of(x) == x for every x in CORE_LABELS — :177-178 [DERIVED]
  fails-if: a canonical name gets remapped; downstream identity/type checks break.
INVARIANT: MODULES contains 6 modules, each version `"1.0.0"` — :51, :58, :64, :71, :77, :81 [DERIVED]
  fails-if: canonical_of module-label resolution (:182-185) silently changes scope.
INVARIANT: v3 legacy pass (`[:12]`, :155) == the 12-name exclusion set (:115-119) — [INFERRED: holds only if CoreType declaration order matches the literal list]
  fails-if: reordering or inserting into CoreType splits legacy/scientific passes wrong with zero diff in this file.

## determinism & idempotency
determinism: DETERMINISTIC (pure functions of module constants plus env `POLYMATH_QUERY_POLICY`, re-read each call — :135-137; no clock/random/uuid/db/network in :1-199) [DERIVED]
idempotency: SAFE (stateless read-only lookups; the module performs no writes — :1-199) [DERIVED]

## failure behaviour
- No try/except anywhere in :1-199; nothing is swallowed locally [DERIVED].
- canonical_of returns `None` for unknown labels; rejection is delegated downstream ("rejected loudly downstream — never silently coerced", :174-176) [DERIVED].
- FACTS lists no fallbacks and no error codes for this unit.
- An unrecognized `POLYMATH_QUERY_POLICY` value is not rejected anywhere (:134-137) — see dumb-code flags.

## dumb-code flags
- Unvalidated version string: any value besides the three constants takes the v2 else-branches in provider_alias_map/provider_passes/query_labels_for (:142, :152-160, :166-168) while policy_identity reports `passes: "identity"` and `aliases: {}` (:192, :196-198) [INFERRED: branch fall-through, no fourth branch exists].
- v3 identity mismatch: aliases resolve under v3 (only v1 is gated, :142-144) but policy_identity reports `aliases: {}` for v3 (:192) [DERIVED for both lines].
- Magic number `[:12]` (:155) duplicates the 12-name literal exclusion set (:115-119); both silently encode CoreType declaration order (:34) [DERIVED].
- `QUERY_POLICY_VERSION = QUERY_POLICY_V1` is a static back-compat symbol that ignores `POLYMATH_QUERY_POLICY`; comment says "prefer active_policy_version" (:107) [DERIVED].
- "Metric" resolves via two tables: commerce_marketing label -> MEASUREMENT (:75) and Measurement alias (:130); the alias path wins under v2/v3 because it is checked first (:180-182 vs :182-185) [DERIVED].
- The deterministic union described for v2 ("higher raw score wins; identity pass preferred on ties", :98-102) has no implementation in this file — provider_passes only returns pass lists (:147-160) [DERIVED].

## refactor notes
- policy_identity output is extraction-contract identity input (:190); the module is imported by execution.py, llm_extraction/gate.py, observability.py, extract_worker.py, llm_direct.py, workers/_small-modules (FACTS.importers) — changing its keys or values re-keys downstream contract identities.
- v1 must stay byte-identical to the qualified baseline (:21-22, :152-153): do not alter CORE_LABELS derivation (:34) or any v1 branch.
- PROVIDER_ALIASES_V2 is policy data behind the GLINER-QUERY-VOCAB-vN evidence gate — "never a code branch and never a canonical ontology change" (:18-21); edits change v2/v3 pass fan-out (:157-160), rescue label counts (:168), and policy_identity output (:192, :195).
- CoreType declaration order in polymath_shared.contracts is a hidden dependency of v3 (:155, :115-119) — reordering it changes passes with no local diff.
- Adding a MODULES label captures raw labels that previously returned `None` from canonical_of (:182-185).

## VERIFY
```verify
grep -Fq 'QUERY_POLICY_V1 = "semantic-query-policy-v1"' shared/polymath_shared/query_policy.py
grep -Fq 'os.environ.get("POLYMATH_QUERY_POLICY", QUERY_POLICY_V1)' shared/polymath_shared/query_policy.py
grep -Fq '"Organization": ("Company", "Corporation")' shared/polymath_shared/query_policy.py
grep -Eq 'CoreType\)\[:12\]' shared/polymath_shared/query_policy.py
! grep -Fq 'QUERY_POLICY_V4' shared/polymath_shared/query_policy.py
test "$(grep -c -F '"1.0.0"' shared/polymath_shared/query_policy.py)" -ge 6
```
