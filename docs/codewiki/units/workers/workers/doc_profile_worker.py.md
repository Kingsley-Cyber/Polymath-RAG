# unit: workers/workers/doc_profile_worker.py
anchor: workers/workers/doc_profile_worker.py:1-574

## purpose
DOCUMENT-PROFILE-V1 step 3: the `doc_profile` stage worker. Per run: lean context → enrichment LLM (isolated `doc_profile` pool) → deterministic compiler (rag-profile-v3) → profile artifact → vector projection in its own Qdrant collection, all committed in ONE stage transaction with receipt chain `content hash → input hash → raw response hash → compiled hash → projection hash` — workers/workers/doc_profile_worker.py:1-9 [DERIVED]
Giant documents (more than `giant_profile.GIANT_PARENT_THRESHOLD` parents) additionally get one SECTION profile per top-level heading, built before the document profile in short per-section transactions — workers/workers/doc_profile_worker.py:14-23 [DERIVED]
Never touches chunk vectors, chunk ids, parent/child projection identity or graph receipts; it only ADDS an artifact and a point in its own collection — workers/workers/doc_profile_worker.py:8-9 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| process_event | def | (conn: Connection, event: dict) -> None | workers/workers/doc_profile_worker.py:420-564 | run_worker via main (workers/workers/doc_profile_worker.py:569) |
| build_section_profiles | def | (tx_factory, *, run_id, doc_id, corpus_id, document, groups, vnext, per_pass=None, force=False, budget_tokens=GP.SECTION_BUDGET_TOKENS, client=None) -> dict | workers/workers/doc_profile_worker.py:318-417 | — |
| contract | def | () -> str | workers/workers/doc_profile_worker.py:102-114 | — |
| lane_order | def | (pin: list[str], run_key: str, owners: list[list[str]] | None = None) -> list[str] | workers/workers/doc_profile_worker.py:171-192 | — |
| attempt_lanes | def | (pin: list[str], run_key: str, owners: list[list[str]] | None = None) -> list[str] | workers/workers/doc_profile_worker.py:205-214 | — |
| transient_pool_error | def | (pool_rec: dict, err: str | None) -> bool | workers/workers/doc_profile_worker.py:217-220 | — |
| sections_per_pass | def | () -> int | workers/workers/doc_profile_worker.py:81-83 | — |
| embed_batch_size | def | () -> int | workers/workers/doc_profile_worker.py:254-260 | — |
| main | def | () -> None | workers/workers/doc_profile_worker.py:567-569 | — |
| HOOKS | const | dict with keys `complete`, `embed`, `qdrant`, `tx` (all None) | workers/workers/doc_profile_worker.py:70 | tests (comment: tests inject) |

Module-level importer (symbol unknown): workers/workers/doc_parent_map_stage_worker.py — FACTS.importers [DERIVED]

## contracts
**process_event(conn, event) -> None** — workers/workers/doc_profile_worker.py:420-564
- in: `event["run_id"]` — workers/workers/doc_profile_worker.py:421 [DERIVED]
- pre: document must have landed; else `RuntimeError("DOC_PROFILE_NO_DOCUMENT: ...")` — workers/workers/doc_profile_worker.py:138, 148 [DERIVED]
- out: artifacts `doc_profile`, `doc_profile_sections`, `doc_profile_qdrant`, `doc_profile_atoms` written via `stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract())` — workers/workers/doc_profile_worker.py:442, 501-503, 551, 557-559 [DERIVED]
- post: raise `TransientStageHold` on pending sections or transient pool outage; `RuntimeError` on pool failure / invalid profile / incomplete vectors — workers/workers/doc_profile_worker.py:439, 476-477, 505, 561 [DERIVED]

**build_section_profiles(tx_factory, ...) -> dict** — workers/workers/doc_profile_worker.py:318-417
- in: `groups` from `GP.section_groups(parents)`; per_pass defaults to `sections_per_pass()` — workers/workers/doc_profile_worker.py:331, 428 [DERIVED]
- out: receipt dict with keys `version`, `threshold`, `scope`, `sections_total`, `budget_tokens`, `prompt_version`, `built`, `skipped`, `failed`, `pending`, `transient_error`, `orphans_purged` — workers/workers/doc_profile_worker.py:339-341 [DERIVED]
- post: at most `per_pass` sections built per call, rest reported `pending`; transient pool error stops the pass and is reported, never raised — workers/workers/doc_profile_worker.py:324-326, 358-360 [DERIVED]

**contract() -> str** — workers/workers/doc_profile_worker.py:102-114
- out: `stage_contract_hash(STAGE, {...})` over schema/prompt/compiler/builder/projection versions and budget; adds `"giant": GP.GIANT_PROFILE_VERSION` when `_giant_enabled()`, `vnext: True` + `FP.DEFAULT_BUDGET_TOKENS` when `_vnext_enabled()` — workers/workers/doc_profile_worker.py:103-114 [DERIVED]

**attempt_lanes(pin, run_key, owners) -> list[str]** — workers/workers/doc_profile_worker.py:205-214
- out: first `PRIMARY_ATTEMPTS` rotated primaries, then fallbacks, capped at `MAX_LANE_ATTEMPTS`; owning slot path returns `order[:MAX_LANE_ATTEMPTS]` only — workers/workers/doc_profile_worker.py:210-214 [DERIVED]

**transient_pool_error(pool_rec, err) -> bool** — workers/workers/doc_profile_worker.py:217-220
- out: True when every attempt error matches `_TRANSIENT_ERR` (or there were no attempts); non-matching errors (e.g. empty_response default) make it False — workers/workers/doc_profile_worker.py:219-220, 62-64 [DERIVED]

## effect surface
Postgres reads (no direct writes; FACTS.tables_written = []):
| table | query | anchor |
| outbox_events | payload of `event_type='chunked.v1'` by run_id | workers/workers/doc_profile_worker.py:124-126 |
| runs | metadata by run_id | workers/workers/doc_profile_worker.py:131 |
| documents | doc_id by corpus_id+source_name; doc row (doc_id, corpus_id, source_name, media_type, frontmatter, content_hash) | workers/workers/doc_profile_worker.py:135-136, 143-145 |
| chunks | parent-tier rows by doc_id ORDER BY chunk_index | workers/workers/doc_profile_worker.py:151-156 |
| document_summaries | latest `major_concepts` (skipped when vnext: `want_terms=not vnext`) | workers/workers/doc_profile_worker.py:159-162, 426 |

Commits go through `stage_transaction` writer.artifact (workers/workers/doc_profile_worker.py:442) and the section/atom transactions via `tx_factory` (workers/workers/doc_profile_worker.py:400-404, 431-432).

Qdrant: profile collection point per document (workers/workers/doc_profile_worker.py:516-524); section points (`scope: section`, list/project/purge) (workers/workers/doc_profile_worker.py:343, 386-394, 413); atom collection (`PAP.ingest_section_atoms`, `PAP.ingest_document_atoms`) (workers/workers/doc_profile_worker.py:401-404, 535-540); client timeout=60 (workers/workers/doc_profile_worker.py:316).

Network: `LLMExtractionClient` per lane, `timeout_s=90.0, max_attempts=1` (workers/workers/doc_profile_worker.py:238-239); `EmbedderClient.embed` modes `"doc_profile"` and `"query"` (workers/workers/doc_profile_worker.py:268, 288).

Env flags:
| flag | default | anchor |
| POLYMATH_DOC_PROFILE_GIANT | `'1'` (ON) | workers/workers/doc_profile_worker.py:78 |
| POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS | `''` → 8 | workers/workers/doc_profile_worker.py:82 |
| POLYMATH_DOC_PROFILE_FORCE_SECTIONS | `''` | workers/workers/doc_profile_worker.py:89 |
| POLYMATH_DOC_PROFILE_VNEXT | `''` (OFF) | workers/workers/doc_profile_worker.py:99 |
| POLYMATH_DOC_PROFILE_LANE_OFFSET | `''` → None | workers/workers/doc_profile_worker.py:199 |
| POLYMATH_MAX_BATCH_TEXTS | `'4'` | workers/workers/doc_profile_worker.py:258 |

## invariants
INVARIANT: lanes tried per pass ≤ MAX_LANE_ATTEMPTS = 4 — workers/workers/doc_profile_worker.py:54, 214 [DERIVED]
  fails-if: fallback tier unreachable or budget overrun per attempt pass
INVARIANT: primaries tried per pass = PRIMARY_ATTEMPTS = 2 before fallbacks — workers/workers/doc_profile_worker.py:55, 213 [DERIVED]
  fails-if: six primaries would starve the fallback tier (comment, line 55)
INVARIANT: sections built per call ≤ per_pass, and sections_per_pass() ≥ 1 — workers/workers/doc_profile_worker.py:358, 83 [DERIVED]
  fails-if: zero/negative cap stalls the resumable section loop forever
INVARIANT: section skip requires input_hash AND prompt_version equality with the existing point — workers/workers/doc_profile_worker.py:354 [DERIVED]
  fails-if: a stale section point survives a prompt bump (wrong profile served)
INVARIANT: orphan purge runs only when `pending` is empty — workers/workers/doc_profile_worker.py:412-413 [DERIVED]
  fails-if: a re-cut document loses live section points while some are still unbuilt
INVARIANT: len(embedded vectors) == len(texts) — workers/workers/doc_profile_worker.py:276-277 [DERIVED]
  fails-if: vectors misaligned with representation texts
INVARIANT: atoms embedded in mode `"query"`, profiles in mode `"doc_profile"` — one mode per collection — workers/workers/doc_profile_worker.py:281-288, 268 [DERIVED]
  fails-if: doc-mode atom scores on a different scale than its neighbours (cos parity argument, lines 282-284)
INVARIANT: atom ingest only when NOT `kept_last_known_good` — workers/workers/doc_profile_worker.py:398, 525 [DERIVED]
  fails-if: thinner atoms overwrite a richer last-known-good atom set
INVARIANT: giant document profile built from `GP.build_giant_fingerprint` (stratified sample across ALL sections), never the first pages — workers/workers/doc_profile_worker.py:445, 21-22 [DERIVED]
  fails-if: giant profile biased to front matter
INVARIANT: section/document LLM calls never run inside a stage transaction (pMAP rule §28; `conn.commit()` before the section loop) — workers/workers/doc_profile_worker.py:423-427 [DERIVED]
  fails-if: idle-held transaction across a 90s LLM call
INVARIANT: chunk vectors, chunk ids, parent/child identity and graph receipts are never written — workers/workers/doc_profile_worker.py:8-9 [DERIVED]
  fails-if: breaks the pipeline owner invariant

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.perf_counter` at workers/workers/doc_profile_worker.py:236 and :248; network: LLM lanes 236-248, embedder 271-272, Qdrant 316; db reads 124-162; env: 6 flags above) [DERIVED]
idempotency: SAFE — sections skipped when input_hash+prompt_version unchanged (workers/workers/doc_profile_worker.py:353-357); pending sections hand the ticket back as `TransientStageHold` and the next pass resumes (workers/workers/doc_profile_worker.py:435-441); last-known-good projection guard refuses thinner overwrites (workers/workers/doc_profile_worker.py:548-555); `--force` rebuilds but projection still supersedes by key (workers/workers/doc_profile_worker.py:86-89, 413) [DERIVED]

## failure behaviour
| handler | line | swallowed | caller sees |
| except Exception (terms load) | workers/workers/doc_profile_worker.py:166 | terms read failure | `terms = []` — terms are an optional surface |
| except Exception (one lane) | workers/workers/doc_profile_worker.py:244-245 | any lane exception | `raw=""`, `err = exc class name`; next lane tried, attempt receipted, never a crash |
| except Exception (section atoms) | workers/workers/doc_profile_worker.py:405-408 | atom ingest failure | `entry["atoms"] = {"ok": False, ...}` + log.warning; projected section point stands |
| except Exception (document atoms) | workers/workers/doc_profile_worker.py:541-544 | atom ingest failure | `atom_receipt = {"ok": False, ...}` + log.warning; already-projected profile still succeeds |

Raised codes: `DOC_PROFILE_NO_DOCUMENT` (workers/workers/doc_profile_worker.py:138, 148), `TransientStageHold DOC_PROFILE_SECTIONS_PENDING` (:439-441), `TransientStageHold DOC_PROFILE_POOL_UNAVAILABLE` (:476), `RuntimeError DOC_PROFILE_POOL_FAILED` (:477), `RuntimeError DOC_PROFILE_INVALID` (:382, 505), `RuntimeError DOC_PROFILE_VECTORS_INCOMPLETE` (:561), embedder errors at :274, :277.
Transient taxonomy `_TRANSIENT_ERR`: `HTTP_408/413/425/429/5xx`, `TRANSPORT_*`, `Timeout`, `Connect`, `RemoteProtocolError`, `ReadError`, `WriteError`, `rate_limited`, `pool_dark`, `circuit_open`, `no_active_lane`, `no_attempt`, `LIMITER_REFUSED` — hold the ticket; anything else (HTTP 400/401/403/404, 200-empty) is a receipted failure so an unprofilable document ends as a failure instead of holding forever — workers/workers/doc_profile_worker.py:57-64 [DERIVED]

## dumb-code flags
- Comment math: `MAX_OUTPUT_TOKENS = 2400  # ~80 labelled lines at the v3.1 aims (10 / 10 / 15 / 15 / 10 / 10 / 10)` — the aims sum to 75, not 80 — workers/workers/doc_profile_worker.py:53 [DERIVED]
- Budget 500 from two sources: legacy `CONTEXT_BUDGET_TOKENS = 500` vs vNext `FP.DEFAULT_BUDGET_TOKENS` (comment: "canary-selected default (500)") — same value, two constants — workers/workers/doc_profile_worker.py:52, 108, 452 [DERIVED]
- `embed_batch_size` hardcodes `4` twice: env default `"4"` and `except ValueError: return 4` — workers/workers/doc_profile_worker.py:258-260 [DERIVED]
- Raw truncation sizes differ: `raw[:2000]` per section vs `raw[:8000]` per document — workers/workers/doc_profile_worker.py:380, 499 [DERIVED]
- `_complete` drops `run_key` when `HOOKS["complete"]` is wired (test hook path loses lane rotation input) — workers/workers/doc_profile_worker.py:302-306 [DERIVED]
- Owned-slot path in `attempt_lanes` ignores `PRIMARY_ATTEMPTS`; caps only by `MAX_LANE_ATTEMPTS` — workers/workers/doc_profile_worker.py:210-211 [DERIVED]
- `owned` assigned twice in `build_section_profiles`: `owned = client is None` then immediately reassigned by `_open_qdrant()` — workers/workers/doc_profile_worker.py:335-337 [DERIVED]
- `issues` list truncated to `[:24]`, error strings to `[:160]`/`[:200]`/`[:300]` — silent detail loss at each site — workers/workers/doc_profile_worker.py:496, 406, 543, 474 [DERIVED]

## refactor notes
- Importer blast radius: workers/workers/doc_parent_map_stage_worker.py imports this module (FACTS.importers); renaming any public symbol requires checking that file — [DERIVED]
- `HOOKS` keys `complete`/`embed`/`qdrant`/`tx` are a test-injection contract (comment at workers/workers/doc_profile_worker.py:68-70); renaming breaks tests — workers/workers/doc_profile_worker.py:70 [DERIVED]
- `contract()` hashes version constants from `C`, `PP`, `PROMPT_VERSION`, `CX.BUILDER_VERSION`, `FP.FINGERPRINT_BUILDER_VERSION`, `PJ.PROJECTION_VERSION`, budget tokens and the giant/vnext flags — any change alters `stage_contract_hash` and the receipt chain — workers/workers/doc_profile_worker.py:104-113 [DERIVED]
- `FALLBACK_MARK = "fallback"` is a lane-naming convention shared with `pool.owned_lane_order` (workers/workers/doc_profile_worker.py:182-183); renaming lanes breaks primary/fallback tiering — workers/workers/doc_profile_worker.py:56 [DERIVED]
- `_TRANSIENT_ERR` is a string contract with the pool's error surface; a new pool error code not listed there becomes a permanent failure, not a hold — workers/workers/doc_profile_worker.py:62-64 [DERIVED]
- Rollback switches `POLYMATH_DOC_PROFILE_GIANT=0` and vNext OFF must stay byte-identical to pre-feature behavior — "a config change, never a re-ingest" — workers/workers/doc_profile_worker.py:76-78, 96-99 [DERIVED]

## VERIFY
```verify
grep -Fq 'MAX_OUTPUT_TOKENS = 2400' workers/workers/doc_profile_worker.py
grep -Fq 'DEFAULT_SECTIONS_PER_PASS = 8' workers/workers/doc_profile_worker.py
grep -Fq 'PRIMARY_ATTEMPTS = 2' workers/workers/doc_profile_worker.py
grep -Eq 'POLYMATH_DOC_PROFILE_GIANT.*not in' workers/workers/doc_profile_worker.py
grep -Fq 'DOC_PROFILE_VECTORS_INCOMPLETE' workers/workers/doc_profile_worker.py
! grep -Fq 'DELETE FROM chunks' workers/workers/doc_profile_worker.py
test "$(grep -c -F 'time.perf_counter' workers/workers/doc_profile_worker.py)" -ge 2
```
