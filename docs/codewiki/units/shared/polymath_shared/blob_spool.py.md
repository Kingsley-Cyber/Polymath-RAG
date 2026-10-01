# unit: shared/polymath_shared/blob_spool.py
anchor: shared/polymath_shared/blob_spool.py:1-164

## purpose
Durable content-addressed byte spool behind intake: upload bytes stream to a spool file on a host-visible volume, and the canonical intake payload carries only a claim-check reference `{store, key, sha256, bytes}` instead of the bytes; the intake worker resolves the reference and fail-closes on any mismatch — shared/polymath_shared/blob_spool.py:3-7 [DERIVED]. Bounds memory at the streaming chunk size and leaves Postgres holding ~200 bytes per document (vs ~54 MB of jsonb for inline base64 of a 20 MB book) — shared/polymath_shared/blob_spool.py:9-14 [DERIVED]. Reference shape maps 1:1 onto S3-compatible storage, so an R2 move is a backend swap behind the same claim check — shared/polymath_shared/blob_spool.py:16-18 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| SpoolError | class | RuntimeError subclass | shared/polymath_shared/blob_spool.py:35-36 | — |
| SpoolMissingError | class | SpoolError subclass | shared/polymath_shared/blob_spool.py:39-40 | — |
| SpoolIntegrityError | class | SpoolError subclass | shared/polymath_shared/blob_spool.py:43-45 | — |
| spool_dir | function | () -> Path | shared/polymath_shared/blob_spool.py:48-55 | — |
| spool_write | function | (stream: BinaryIO) -> dict | shared/polymath_shared/blob_spool.py:62-87 | — |
| spool_read | function | (ref: dict) -> bytes | shared/polymath_shared/blob_spool.py:90-115 | — |
| document_source_ref | function | (document: Mapping) -> dict | shared/polymath_shared/blob_spool.py:143-159 | — |
| read_document_source | function | (document: Mapping) -> bytes | shared/polymath_shared/blob_spool.py:162-164 | — |

Module imported by: orchestrator/orchestrator/api/ui.py, workers/workers/intake_worker.py (FACTS.importers). Per-symbol callers not in FACTS. `_path_for` is private — shared/polymath_shared/blob_spool.py:58-59.

## contracts

**spool_write(stream) -> dict** — shared/polymath_shared/blob_spool.py:62-87
- in: any BinaryIO, read in chunks of `_CHUNK = 1024 * 1024` — shared/polymath_shared/blob_spool.py:32, 73
- out: `{"store": "local", "key": "<sha[:2]>/<sha256>", "sha256": <hexdigest>, "bytes": <n>}` — shared/polymath_shared/blob_spool.py:86-87
- pre: spool root creatable (`mkdir(parents=True, exist_ok=True)`) — shared/polymath_shared/blob_spool.py:54
- post: bytes live at `spool_dir()/<sha[:2]>/<sha>` via tmp+rename (atomic); if that path already exists the tmp is unlinked (dedup) — shared/polymath_shared/blob_spool.py:70, 80-85

**spool_read(ref) -> bytes** — shared/polymath_shared/blob_spool.py:90-115
- pre: `ref["store"] == "local"` else `SpoolError` — shared/polymath_shared/blob_spool.py:97-99
- post: returned bytes satisfy `sha256(raw) == ref["sha256"]` — shared/polymath_shared/blob_spool.py:105-110; and `len(raw) == ref["bytes"]` when `ref.get("bytes") is not None` — shared/polymath_shared/blob_spool.py:111-114
- raises: `SpoolMissingError` if path absent — shared/polymath_shared/blob_spool.py:101-104; `SpoolIntegrityError` on hash or size mismatch — shared/polymath_shared/blob_spool.py:107-114

**document_source_ref(document) -> dict** — shared/polymath_shared/blob_spool.py:143-159
- in: a mapping from the `documents` table (psycopg dict row or any Mapping) — shared/polymath_shared/blob_spool.py:146-147
- pre: `document["source_hash"]` non-empty after strip, else `SpoolMissingError("SOURCE_HASH_MISSING...")` — shared/polymath_shared/blob_spool.py:151-158
- out: `{"store": SPOOL_STORE, "key": f"{sha[:2]}/{sha}", "sha256": sha}` — NO `"bytes"` field — shared/polymath_shared/blob_spool.py:159

**read_document_source(document) -> bytes** — shared/polymath_shared/blob_spool.py:162-164
- post: exactly `spool_read(document_source_ref(document))` — shared/polymath_shared/blob_spool.py:164

**spool_dir() -> Path** — shared/polymath_shared/blob_spool.py:48-55
- post: returns (and creates) the root from `POLYMATH_SPOOL_DIR` — shared/polymath_shared/blob_spool.py:49-54

## effect surface
- env: `POLYMATH_SPOOL_DIR` = `str(Path.home() / "PolymathRuntime" / "polymath-v4" / "spool")` — shared/polymath_shared/blob_spool.py:49-51
- files: mkdir spool root — shared/polymath_shared/blob_spool.py:54; write tmp `spool_dir()/".tmp-{os.getpid()}-{id(stream)}"` — shared/polymath_shared/blob_spool.py:70-71; rename tmp → `<sha[:2]>/<sha>` — shared/polymath_shared/blob_spool.py:80-85; unlink tmp on dedup — shared/polymath_shared/blob_spool.py:83; read `<sha[:2]>/<sha>` — shared/polymath_shared/blob_spool.py:101, 105
- Postgres tables: none (FACTS.tables_read / tables_written empty)
- Qdrant / network / subprocess: none in SOURCE

## invariants
INVARIANT: spool object path == `spool_dir() / sha256[:2] / sha256` for write, read, and ref key — shared/polymath_shared/blob_spool.py:59, 86, 159 [DERIVED]
  fails-if: ref key disagrees with disk layout → CONTENT_REF_MISSING on every read.
INVARIANT: sha256(returned bytes) == ref["sha256"] — shared/polymath_shared/blob_spool.py:105-110 [DERIVED]
  fails-if: substituted or corrupted spool content gets processed; sha256 participates in run identity — shared/polymath_shared/blob_spool.py:93-95.
INVARIANT: identical bytes → exactly one spool file (`if final.exists(): tmp.unlink()`) — shared/polymath_shared/blob_spool.py:82-85, 20-22 [DERIVED]
  fails-if: duplicate blobs; dedup and ~200-bytes-per-doc economics break.
INVARIANT: accepted store value == `"local"` (the only one) — shared/polymath_shared/blob_spool.py:31, 97-99 [DERIVED]
  fails-if: any other store string raises `SpoolError` before lookup.
INVARIANT: document recovery key == `source_hash` (`SOURCE_RECOVERY_KEY = "source_hash"`), never `content_hash` — shared/polymath_shared/blob_spool.py:140, 151 [DERIVED]
  fails-if: content_hash lookup resolves 0 of 12 documents (measured on cysa-study-v1) and reads as total corpus loss — shared/polymath_shared/blob_spool.py:129-135.
INVARIANT: per-read memory bound == `_CHUNK = 1024 * 1024` (1 MiB), never file size — shared/polymath_shared/blob_spool.py:32 [DERIVED]
  fails-if: unbounded buffering reintroduces the memory problem the spool exists to avoid.
INVARIANT: refs from `spool_write` carry `"bytes"`; refs from `document_source_ref` do not, and `spool_read` skips the size check only because of the `is not None` guard — shared/polymath_shared/blob_spool.py:86-87 vs 159, 111 [DERIVED]
  fails-if: removing the guard makes every `document_source_ref` ref fail the size check.

## determinism & idempotency
determinism: DETERMINISTIC (sha256 content addressing and fixed `<sha[:2]>/<sha>` layout — shared/polymath_shared/blob_spool.py:68-79, 59); tmp filenames are NONDETERMINISTIC (`os.getpid()`, `id(stream)` — shared/polymath_shared/blob_spool.py:70) and root is env-dependent (`POLYMATH_SPOOL_DIR` — shared/polymath_shared/blob_spool.py:49-51).
idempotency: SAFE — re-spooling identical bytes converges to one file via exists-check + unlink (shared/polymath_shared/blob_spool.py:82-85); reads are pure. No locking exists; safety relies on tmp+rename atomicity — shared/polymath_shared/blob_spool.py:70-85 [INFERRED: concurrent identical writers both pass `exists()` then rename, which is atomic].

## failure behaviour
No swallow/retry handlers anywhere in SOURCE; the design is fail-loud ("Fail-loud" — shared/polymath_shared/blob_spool.py:36; "refused, never processed" — shared/polymath_shared/blob_spool.py:94-95). Callers see raw exceptions:
- `SpoolError(f"unsupported content_ref store: {store!r}")` — shared/polymath_shared/blob_spool.py:99
- `SpoolMissingError` "CONTENT_REF_MISSING: spool object ... not found" — shared/polymath_shared/blob_spool.py:102-104
- `SpoolIntegrityError` "SPOOL_INTEGRITY_MISMATCH" on hash mismatch — shared/polymath_shared/blob_spool.py:107-110; on byte-count mismatch — shared/polymath_shared/blob_spool.py:111-114
- `SpoolMissingError` "SOURCE_HASH_MISSING: document ... has no source_hash" with an explicit "Do NOT fall back to content_hash" instruction in the message — shared/polymath_shared/blob_spool.py:153-158

## dumb-code flags
- Magic number `_CHUNK = 1024 * 1024` — shared/polymath_shared/blob_spool.py:32.
- Key literal `f"{sha[:2]}/{sha}"` duplicated in `spool_write` and `document_source_ref` — shared/polymath_shared/blob_spool.py:86, 159.
- Asymmetric ref shape: `spool_write` emits `"bytes"`, `document_source_ref` omits it — shared/polymath_shared/blob_spool.py:86-87 vs 159.
- Docstring hardcodes `"store": "local"` as an example while the code uses `SPOOL_STORE` — shared/polymath_shared/blob_spool.py:66 vs 31.
- Tmp name uses `id(stream)`, which can be reused after GC — shared/polymath_shared/blob_spool.py:70 [INFERRED: a recycled id plus same pid could target a stale tmp file].

## refactor notes
- Ref dict shape `{store, key, sha256, bytes?}` is the cross-process contract; the module's importers are orchestrator/orchestrator/api/ui.py and workers/workers/intake_worker.py (FACTS.importers) — renaming fields breaks both.
- On-disk layout `<sha[:2]>/<sha>` is load-bearing for dedup and every existing blob; changing it orphans all prior spool objects — shared/polymath_shared/blob_spool.py:20-22, 59.
- The `store != SPOOL_STORE` gate is the single dispatch point; adding S3/R2 per the design note requires changing it without breaking `"local"` refs — shared/polymath_shared/blob_spool.py:16-18, 97-99.
- `SOURCE_RECOVERY_KEY = "source_hash"` must stay; any caller-side switch to `content_hash` resurrects the 0-of-12 misreported-data-loss bug — shared/polymath_shared/blob_spool.py:140, 129-135.
- Error-code strings "CONTENT_REF_MISSING", "SPOOL_INTEGRITY_MISMATCH", "SOURCE_HASH_MISSING" are observable behavior; renaming classes or messages changes them — shared/polymath_shared/blob_spool.py:103-104, 108-110, 153-158.

## VERIFY
```verify
grep -Fq 'SPOOL_STORE = "local"' shared/polymath_shared/blob_spool.py
grep -Fq '_CHUNK = 1024 * 1024' shared/polymath_shared/blob_spool.py
grep -Fq 'SOURCE_RECOVERY_KEY = "source_hash"' shared/polymath_shared/blob_spool.py
grep -Fq 'return spool_read(document_source_ref(document))' shared/polymath_shared/blob_spool.py
grep -Eq 'spool_dir\(\) / sha256\[:2\] / sha256' shared/polymath_shared/blob_spool.py
test "$(grep -c -F 'SpoolError' shared/polymath_shared/blob_spool.py)" -ge 3
! grep -Eq 'SOURCE_RECOVERY_KEY = "content_hash"' shared/polymath_shared/blob_spool.py
```
