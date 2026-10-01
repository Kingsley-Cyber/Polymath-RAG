# unit: shared/polymath_shared/manifest.py
anchor: shared/polymath_shared/manifest.py:1-164

## purpose
Implements the I1 manifest policy: parse one corpus's YAML ingestion declaration, validate it against a strict closed JSON schema, canonicalize it for an order-stable manifest identity, and resolve sources relative to the manifest file. Pure module — no stores, no writes. Consumed (file-level) by `control/control/manifest_ingest.py`. [DERIVED] — shared/polymath_shared/manifest.py:1-21

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ManifestError` | class (Exception) | message -> Exception | shared/polymath_shared/manifest.py:50-51 | control/control/manifest_ingest.py (file-level import) |
| `ManifestSource` | frozen dataclass | locator, source, resolved_path, title, source_tier, language, enabled; property `media_type -> str` | shared/polymath_shared/manifest.py:54-72 | control/control/manifest_ingest.py (file-level import) |
| `load_manifest` | def | (path: str \| Path) -> dict | shared/polymath_shared/manifest.py:75-84 | control/control/manifest_ingest.py (file-level import) |
| `manifest_id` | def | (doc: dict) -> str | shared/polymath_shared/manifest.py:106-109 | control/control/manifest_ingest.py (file-level import) |
| `resolve_sources` | def | (doc: dict, manifest_path: str \| Path) -> list[ManifestSource] | shared/polymath_shared/manifest.py:138-163 | control/control/manifest_ingest.py (file-level import) |

`_validate` and `_canonical_form` are private helpers. [DERIVED] — shared/polymath_shared/manifest.py:87, shared/polymath_shared/manifest.py:112

## contracts

**load_manifest** — shared/polymath_shared/manifest.py:75-84
- in: `path` to a YAML manifest file.
- out: parsed, validated `dict`.
- pre: file readable (raw `read_bytes`, line 76); content parses as YAML mapping (78-82).
- post: returned doc passed `_validate` (schema + duplicate-source check) at line 83.
- raises `ManifestError` on `yaml.YAMLError` (79-80) or non-mapping root (81-82).

**manifest_id** — shared/polymath_shared/manifest.py:106-109
- in: validated `doc`.
- out: `MANIFEST_ID_PREFIX + content_hash(_canonical_form(doc))` (109), prefix `"manifest_"` (34).
- post: order-stable — canonical form sorts documents by `source` (127), so document order does not change the id.

**resolve_sources** — shared/polymath_shared/manifest.py:138-163
- in: validated `doc`, `manifest_path`.
- out: `list[ManifestSource]` sorted by locator (163).
- pre: duplicate locators re-checked, raise `ManifestError` (158-161).
- post: `resolved_path = str((base / locator).resolve())` where `base` is the manifest file's parent dir (142, 150); defaults applied: `enabled=True`, `source_tier="primary"`, `language="en"` (152-154).

**ManifestSource.media_type** — shared/polymath_shared/manifest.py:65-72
- out: media-type string looked up from `_EXTENSION_MEDIA_TYPES` by lowercase extension (66-67, 72).
- raises `ManifestError` for any extension not in the map (68-71).

## effect surface
- Files read: the manifest at caller `path` (76); schema at `contracts/ingestion/v1/manifest.schema.json`, resolved as `Path(__file__).resolve().parents[2] / ...` (36, 90).
- Imports: `polymath_shared.identity.content_hash` (31); lazy `import jsonschema` inside `_validate` (88); `yaml` at module top (29).
- Postgres tables: none read, none written (FACTS `tables_read`/`tables_written` empty; "pure, no stores" — shared/polymath_shared/manifest.py:1).
- Qdrant, network, subprocess, env flags: none in SOURCE.

## invariants

INVARIANT: canonical document order == sorted by source locator — shared/polymath_shared/manifest.py:127 and shared/polymath_shared/manifest.py:163 [DERIVED]
  fails-if: manifest_id changes when the same documents are declared in a different order (order instability).
INVARIANT: `defaults.get("enabled", True)` identical at shared/polymath_shared/manifest.py:118 and shared/polymath_shared/manifest.py:154 [DERIVED]
  fails-if: manifest_id covers a different enabled set than what resolve_sources actually ingests.
INVARIANT: `defaults.get("source_tier", "primary")` identical at shared/polymath_shared/manifest.py:124 and shared/polymath_shared/manifest.py:152 [DERIVED]
  fails-if: hashed identity and runtime tier disagree.
INVARIANT: `defaults.get("language", "en")` identical at shared/polymath_shared/manifest.py:126 and shared/polymath_shared/manifest.py:153 [DERIVED]
  fails-if: hashed identity and runtime language disagree.
INVARIANT: manifest_id prefix == `"manifest_"` — shared/polymath_shared/manifest.py:34, shared/polymath_shared/manifest.py:109 [DERIVED]
  fails-if: recomputed ids no longer match previously stored manifest ids.
INVARIANT: duplicate normalized source (`str(Path(s))`) → `ManifestError` in both `_validate` and `resolve_sources` — shared/polymath_shared/manifest.py:98-102, shared/polymath_shared/manifest.py:156-161 [DERIVED]
  fails-if: silent dedupe violates the documented loud-failure policy (shared/polymath_shared/manifest.py:12-13).
INVARIANT: supported formats == the 8 keys of `_EXTENSION_MEDIA_TYPES` (`.md`, `.markdown`, `.txt`, `.pdf`, `.epub`, `.docx`, `.html`, `.htm`); all others raise via `media_type` — shared/polymath_shared/manifest.py:38-47, shared/polymath_shared/manifest.py:67-71 [DERIVED]
  fails-if: a format without an I0 materializer is accepted into ingestion.
INVARIANT: resolution base == manifest file's parent, never cwd — shared/polymath_shared/manifest.py:142, policy at shared/polymath_shared/manifest.py:7 [DERIVED]
  fails-if: same manifest resolves to different absolute paths depending on process working directory.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of the manifest bytes and schema file; only file reads (76, 90), no clock/random/uuid/network/db/env anywhere in SOURCE. [DERIVED]
idempotency: SAFE — no writes; repeated calls return equal results (dataclass is `frozen=True`, shared/polymath_shared/manifest.py:54). [DERIVED]

## failure behaviour
All policy failures surface as `ManifestError`; nothing is swallowed:
- `"manifest YAML parse failed: {exc}"` — shared/polymath_shared/manifest.py:79-80
- `"manifest must be a YAML mapping"` — shared/polymath_shared/manifest.py:81-82
- `"manifest validation failed: {exc.message}"` (jsonschema `ValidationError` chained) — shared/polymath_shared/manifest.py:92-94
- `"duplicate source declaration: {s!r} appears more than once"` (two sites) — shared/polymath_shared/manifest.py:100-102, shared/polymath_shared/manifest.py:159-161
- `"unsupported source format for {locator!r}: extension {ext!r} has no I0 materializer"` — shared/polymath_shared/manifest.py:68-71

Unwrapped, caller sees raw errors from: `read_bytes` (76) and schema `read_text` (90) if files are missing; `import jsonschema` (88) if the package is absent. [DERIVED]

## dumb-code flags
- Default literals `True`, `"primary"`, `"en"` duplicated across `_canonical_form` and `resolve_sources` instead of one defaults function — shared/polymath_shared/manifest.py:118/154, 124/152, 126/153 [DERIVED]
- `MANIFEST_VERSION = 1` is defined but never referenced in this file; `_canonical_form` hashes `doc["version"]` directly — shared/polymath_shared/manifest.py:33, shared/polymath_shared/manifest.py:129 [DERIVED]
- Duplicate-source check implemented twice with the same `str(Path(...))` normalization — shared/polymath_shared/manifest.py:98, shared/polymath_shared/manifest.py:146, shared/polymath_shared/manifest.py:158 [DERIVED]
- Import placement inconsistent: `yaml` at module top (29), `jsonschema` lazily inside `_validate` (88) [DERIVED]

## refactor notes
- Any change to a default value or to `_canonical_form` changes every `manifest_id` — blast radius includes control/control/manifest_ingest.py (FACTS.importers) and any stored id. Must be updated in both sites (118/154, 124/152, 126/153).
- `_SCHEMA_PATH` hardcodes repo layout `parents[2] / "contracts" / "ingestion" / "v1" / "manifest.schema.json"` — moving the module or schema breaks validation at read time — shared/polymath_shared/manifest.py:36.
- New source format requires both a `_EXTENSION_MEDIA_TYPES` entry and an existing I0 materializer; otherwise `media_type` raises — shared/polymath_shared/manifest.py:38-47, shared/polymath_shared/manifest.py:67-71.
- Do not add desired-state reconciliation: absent sources are never deleted (documented non-semantics) — shared/polymath_shared/manifest.py:18-20.
- `ManifestSource` is `frozen=True`; callers may rely on immutability — shared/polymath_shared/manifest.py:54.
- Manifest identity != document content identity != run identity; keep these hash domains separate — shared/polymath_shared/manifest.py:16.

## VERIFY
```verify
grep -Fq 'MANIFEST_ID_PREFIX = "manifest_"' shared/polymath_shared/manifest.py
grep -Fq 'MANIFEST_VERSION = 1' shared/polymath_shared/manifest.py
grep -Fq 'docs.sort(key=lambda e: e["source"])' shared/polymath_shared/manifest.py
grep -Fq 'defaults.get("source_tier", "primary")' shared/polymath_shared/manifest.py
grep -Fq 'defaults.get("language", "en")' shared/polymath_shared/manifest.py
test "$(grep -c -F 'duplicate source declaration' shared/polymath_shared/manifest.py)" -ge 2
! grep -Fq 'os.getcwd' shared/polymath_shared/manifest.py
grep -Fq 'from polymath_shared.identity import content_hash' shared/polymath_shared/manifest.py
```
