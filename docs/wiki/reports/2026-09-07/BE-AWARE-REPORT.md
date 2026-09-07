---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# BE AWARE — how Polymath v4 is built, why it is that way, and which parts are the owner's preference versus operational necessity (2026-09-07)

Read this after `docs/wiki/plans/CONTINUITY-REPORT.md` and before touching control/, shared/ or workers/. Every entry carries one tag:

- **[OWNER]** — King's stated design or working rule. Not derivable from the code; do not "improve" it away. Change only on the owner's word.
- **[OPERATIONAL]** — forced by a measured incident, a hardware limit or a provider behaviour. The reason is recorded; if the constraint goes away the rule can be revisited, with a measurement.
- **[DESIGN]** — an engineering choice made under the constraints above. Revisable by a session that proves a better one with the same receipts.

---

## 1. Shape of the repository

| Area | What lives there | Why it is separate |
|---|---|---|
| `orchestrator/` | FastAPI on :7200 — chat runtime (`api/ui.py`: compiler → lanes → judge → composer → presentation), `/retrieve`, `/retrieve/plan`, `/capabilities`, MCP server | **[OPERATIONAL]** it is UNAUTHENTICATED; it must never sit behind a public hostname without the Caddy layer. It is a supervised slot like any worker. |
| `control/` | `process_supervisor.py` (the fleet: slots, readiness, fence quarantine, restart budget, `.env` + runtime-budget overlay per spawn), `fleet_autopilot.py` (demand lanes → desired slots), `tickets.py` (`STAGE_DAG`, `NON_BLOCKING_STAGES`), medic, stall tracer | **[OPERATIONAL]** process life and demand belong to one authority; hand-started processes (a second :7200, an unsupervised worker) caused bind loops and stale-code work. |
| `shared/polymath_shared/` | everything two processes need the same view of: `candidate_engine.py` (lanes A/B/C/D, RRF, region exclusion, composer), `compiler_context.py` (B16 titles), `dedup.py` (B1), `document_profile/` (compiler, prompt, context, projection), `llm_extraction/` (pool, limiter, client), `worker_runtime.py`, `receipts.py`, `document_region.py` | **[DESIGN]** one import path for the fleet and the orchestrator. **[OPERATIONAL]** every edit here trips the execution-bundle fence — expect a ~2-minute restart round of every slot. |
| `workers/workers/` | one module per stage: intake, extract (×3 slots), canonicalize, project_canonical, project_neo4j, project_qdrant, verify, compile_objects, summary (×2), profile, doc_profile (×6) | **[DESIGN]** the runtime executes tickets SERIALLY per process (lease correctness); throughput is added by SLOTS, never by threads inside a worker. |
| `sidecars/` | embedder :8742 (Qwen3-Embedding-0.6B, 1024-d, contract `embed_e794ec4cab197a3f`), reranker :8743 (cross-encoder), cloud-modal, local_extractor | **[OPERATIONAL]** the two MLX sidecars share ONE Metal GPU; they are supervised slots with readiness probes, brought up on demand by the autopilot. |
| `frontend/` | the UI; `frontend/dist` is TRACKED | **[DESIGN]** the orchestrator serves the built assets; after `npm run build` the hashed asset names must be re-declared in `scripts/scaffold_polymath_v4.py` in the same commit. |
| `scripts/` | operator scripts, each declared in `scripts/README.md` AND the scaffold; `repo_guard.py` | **[DESIGN/governance]** a script that is not in the registry is invisible to the next session; the guard refuses the commit. |
| `config/` | `cloud_providers.json` (providers + `stage_pins`), `extraction_models/limiter.yaml` | **[OWNER]** provider KEYS never live here — only `api_key_env` names. **[OPERATIONAL]** the limiter is per PROCESS (threading locks); a row is one process's budget. |
| `docs/wiki/` | `plans/` (CONTINUITY-REPORT — the only hand-off; PLAN-AUTHORITY-REGISTER — the completion contract, rows never deleted; OWNER-BACKLOG; IMPLEMENTATION-TODO), `work-log/` (append-only), `experiments/`, `decisions/`, `refactors/`, `reports/` (dated, this folder) | **[OWNER]** one living bootstrap file, updated in place, never forked into dated copies; history lives in work-logs and the register. |
| `tests/` | `determinism/` (pure pins + Postgres-backed stage tests), `contracts/`, `integration/` | **[OWNER]** assert before commit — an automated test that exits non-zero, run green, then commit. Log greps and curls are not proof. |
| `.env` (gitignored) | every secret and every runtime knob | **[OWNER]** the owner edits it; the assistant never reads, prints or writes keys. **[OPERATIONAL]** never an inline comment on a value line (pydantic keeps it → orchestrator crash). |

CI on `Kingsley-Cyber/Polymath-RAG` (public): four checks — agent-preflight, contracts, determinism (postgres:16 service + migrations), repo-governance. `main` is protected: push the branch, wait for the four checks, fast-forward `main` from `../polymath-v4-main`. **[OWNER]** "I just want the working state and fixes I have to work when I pull it from a different computer."

---

## 2. Laws of operation and where each one came from

| Law | Tag | Origin |
|---|---|---|
| Supervised slots: kill → respawn; never hand-start :7200; a slot that exits 6 times is quarantined | OPERATIONAL | bind loop from a hand-started orchestrator beside the supervised one; stale-code workers doing work against a newer bundle |
| Fence restart on every control/ shared/ workers/ edit | OPERATIONAL | workers executing with a stale execution bundle produced receipts the newer code could not read |
| The supervisor reads `FLEET` at boot; adding a slot needs a fleet boot | DESIGN | simplicity of the slot table; cost = one boot per topology change (twice today) |
| Autopilot demand lanes (a stage's slots exist only while it has open tickets; 30 s grace) | OPERATIONAL | 19.6 GB committed memory when everything ran at once; extraction demand wins |
| Tickets are lease-exclusive, executed serially per worker, `TransientStageHold` hands a ticket back without consuming an attempt | OPERATIONAL | a summaries worker waited 4.2 h on a sweep lock while a ticket sat READY_UNCLAIMED; 429s burned retry budgets |
| 3-minute stall rule: a ticket not advancing for 3 minutes is a defect to trace now | OWNER | "never let it run" |
| One background watcher on the terminal state; never foreground-wait | OWNER | working rule; the assistant keeps building while the pipeline moves |
| Embedder caps `POLYMATH_MAX_BATCH_TEXTS=4` / `TOKENS=8192`; reranker deadline 12 s (was 8) | OPERATIONAL | 2026-09-07: the embedder OOM-split under a 24-book re-projection and starved the judge (`rerank_timeout` on every turn). Return to 8 s when the 24 `project_qdrant` tickets drain. |
| Never rerank parallel support passes | OPERATIONAL | A/B: p50 12 s → 31 s, embed 0.4 → 8.6 s on the shared Metal GPU |
| Postgres `max_parallel_workers_per_gather = 0` | OPERATIONAL | the container's /dev/shm was 64 MB; compose now has `shm_size: 1gb`, flip back at the next recreate |
| Declarations ship in the SAME commit as their files; never earlier; never `git add -A` | DESIGN/governance | CI went red on a declaration whose file was still parked; `-A` would commit `.env`-adjacent junk and research CSVs |
| `research/registry/research_evidence.csv` never committed | OWNER | field evidence with authors and quotes is private |
| Chat model catalog never feeds extraction, enrichment or the compiler | OWNER | 2026-09-06 rule; boundary test `test_chat_model_catalog.py` |
| Provider keys only in `.env`; six pasted keys are to be rotated | OWNER + security | the assistant declined to enter keys anywhere; the owner filled `GROQ_API_KEY_1..6` |
| A missed gate is IMPLEMENTED, never DONE | OWNER | register status vocabulary |

---

## 3. Retrieval and chat — what was decided and by whom

| Implementation | Tag | Why |
|---|---|---|
| Compiler sees the library's TITLES, never summaries; dynamic top-40; ranked by CONTENT (section summaries backward-mapped to documents); fresh every turn (B16, 11.122) | OWNER | "not summaries, they get long"; "top 40 or something, dynamic"; "more deterministic if it's ranked documents" |
| Title ranker default = dense (one message embedding), sparse via `POLYMATH_CHAT_COMPILER_TITLES_RANK=sparse`, per-request `titles_rank` | OPERATIONAL (measured) | only dense put the Laban Workbook in front of a camera question (rank 25 → compiler wrote the Laban query → Workbook cited) |
| Abstraction ladder L0–L6 as compiler VOCABULARY, L3 first (B14 queued) | OWNER | the owner's design; agreed 2026-09-07 |
| Bridge-hop (B15) demoted | OPERATIONAL (probed) | pseudo-relevance feedback only deepens the frame it is given; Laban is unreachable from the punch question's winners |
| Quotas rejected: doc-fair round robin in `judged_prefix`, aspect seats, diversity slots are NOT the design — pure-rank composition pending | OWNER | "the routing is to help precision for HyDE requery… no, this isn't the goal or design" — decision still open |
| REGION-EXCLUSION-V1: TOC / furniture roles dropped at union (`region:<role>`, `toc_links`) | OPERATIONAL | "Timing for Animation › Table of Contents" reached the final evidence |
| INTERACTIVE-RELIEF-V1: presentation length rule, 6 000-token ceiling, carry artifact on rewrite turns (cap 16), rerank deadline 12 s | OPERATIONAL (owner complaints) | "generates too much", "sometimes retrieves nothing", "rerank_timeout major error" |
| Near-duplicate guard: byte hash → normalised hash → containment of incoming parents vs the last 250 docs; refuse only `certain` (≥ 0.95); replay exemption | OWNER (reuse v3.3) + OPERATIONAL (replay) | "polymath 3.3 implemented it… shouldn't take 3 hrs"; the control plane re-delivers intake events after landing |
| Document summaries: 48 stale removed (114 → 66); summaries stay; the PROFILE is additive | OWNER | "you can remove it"; "will it replace current doc summaries? if so go ahead" → it does not replace |
| Child chunks ≈ 73 words median | DESIGN (open) | owner: "wow that's small" — no decision yet |
| Instructions 17 k chars/turn vs 6.5 k evidence → B17 LEAN-PROMPT queued | OPERATIONAL (measured) | owner: "every query the model is injected a large amount of context" |

---

## 4. DOCUMENT-PROFILE-V1 — the owner's architecture and what the day added

| Element | Tag | Note |
|---|---|---|
| Multi-field profile ONE / SUMMARY / TOPIC / TERM / Q / SEARCH / THEORY / CONCEPT / SEEALSO; counts 10 / 10 / 15 / 15 / 10 / 10 / 10 as aims, never quotas | OWNER | the owner's compiler text, ported as `rag-profile-v3` |
| Own Qdrant collection `polymath_document_profiles_<contract>`; named dense title / identity / theme + MaxSim multivectors questions / searches / theories / concepts / seealso; one point per document | OWNER | "named vectors + multivectors, separate collection" |
| Boost, never gate; SEEALSO out of normal answers; receipt chain content → input → raw → compiled → projection | OWNER | verbatim invariants |
| DO NOT: chunk vectors, chunk ids, parent/child identity, graph receipts. DO: artifacts, vectors, a lane, fusion | OWNER | verbatim |
| `ingested != query_ready`; tolerant readiness = semantic core + query hook + vectors; phase A non-blocking now, phase B gates | OWNER | "not free-key-only"; "tolerant QUERY_READY gate" |
| Isolated pool: six dedicated Groq accounts (groq/compound) tier 0 → Gemini fallback 1 → OpenRouter fallback 2 | OWNER | "6 dedicated api keys for this lane, keep gemini as fallback 1" |
| Lean ~500-token context (identity, even-stride headings, opening / ending / samples, terms) | OWNER | "input lean but contextually rich"; "two excerpts per section too expensive" |
| `structured: "text"` on the profile lanes | OPERATIONAL | Groq 400s on `response_format json_object` unless the prompt says "json" |
| Compiler `rag-compiler-v3.1`: unlabeled lines under a list tag are NEW items; inline `Q: a? B?` split | OWNER | "improve the script to compile the output, the model is capable" — the prompt rule (v3.2) is only a backstop |
| `attempt_lanes` = 2 rotated primaries + fallbacks (≤ 4) | DESIGN (bug fix) | with six primaries the fallback tier was unreachable |
| Only transient errors hold a ticket; the rest fail the attempt | OPERATIONAL | 3-minute stall rule — a document that can never be profiled must end as a receipted failure |
| Embedding sliced to the sidecar cap | OPERATIONAL | the first live ticket 422'd on a 63-text request |
| Six `doc_profile` slots, one per open ticket | OWNER | "those are different api accounts, one document at a time is stupid" |
| Each slot starts on ITS key (`POLYMATH_DOC_PROFILE_LANE_OFFSET`); limiter rows rpm 12 / conc 1 per process | OPERATIONAL | six slots on run-hash rotation collided on keys: 18 HTTP 429 + 2 × 503 + 1 × 413 in five minutes; all absorbed by the next lane or the Gemini fallback (3 documents); 0 failed receipts |

Result of the backfill (cinema, 67 documents, 14:43–15:03Z): 67 / 67 profiled, quality p50 1.00, mean 0.975, 65 documents ≥ 0.90, one at 0.13 (see the work-log), LLM p50 7.7 s / p90 26.3 s, mean counts 9.9 / 10.0 / 14.7 / 14.8 / 8.7 / 9.4 / 9.5, 67 points in the profile collection. Self-retrieval gate numbers: `docs/wiki/experiments/document-profile-gate-gate1.json` and the work-log.

---

## 5. What a new session must not assume

1. The repository context (67 cinema books, cinema corpus, B14 / B15 / L6, §3.23) is CONTEXT, not architecture — do not design around it. **[OWNER]**
2. Time estimates are not design inputs. **[OWNER]**
3. Nothing under plan §3.23 without the owner's explicit go; the owner's own architecture (DOCUMENT-PROFILE) counts as go. **[OWNER]**
4. `frontend/dist` is tracked; the chat UI you see is whatever was built last. **[DESIGN]**
5. The limiter does not survive a process restart and is not shared across slots; RPD is therefore advisory. **[OPERATIONAL — open]**
6. `.env`-sourced shells change test outcomes: `POLYMATH_CHAT_RERANK_DEADLINE_S=12` fails the `rerank_deadline_s == 8.0` pin locally; CI does not source `.env`. **[DESIGN — open]**
