---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
supersedes: docs/wiki/reports/2026-09-07/BE_AWARE.md (extends it; that file's rules still hold)
---

# BE-AWARE — how this repository actually works, and why

Written for a **less-capable successor model**. Read it before changing anything.
Its job is to teach you how to *think* about Polymath, not to list files. Every
important rule is tagged with one of:

- **OWNER PREFERENCE** — the owner wants this behaviour/style.
- **OPERATIONAL NECESSITY** — required for correctness, durability, provenance,
  concurrency, idempotency, recovery, or performance.
- **MEASURED DESIGN** — chosen because a measurement/test proved it.
- **TEMPORARY MIGRATION CONSTRAINT** — exists only because old + new coexist.
- **LEGACY / DEBT** — historical, not part of the end-state; do not expand.

The one sentence that explains the whole system:

> **The model proposes meaning; deterministic Python owns truth; Postgres records
> what happened; Qdrant/Neo4j are rebuildable projections of it.**

If a change would let a model write truth, or let a projection become the only
record of work, it is wrong no matter how convenient.

---

## 0. The mental model (read this first)

Polymath ingests documents and answers questions over them. It is built as a
**fleet of single-purpose workers** driven by a **control plane**, all
coordinating through **Postgres** (never through each other). A document flows
through a fixed **stage DAG**; each stage is a **ticket** with a lease; each stage
writes an **artifact + a receipt + status + an outbox event in ONE transaction**.
The LLM is called only where *meaning must be produced* (extraction, enrichment,
the document profile, the parent map, the query compiler, the answer synthesizer)
and nowhere else. Everything between those points — identity, dedup, ranking,
composition, admission — is deterministic Python.

Why this shape (**OPERATIONAL NECESSITY**): the system must survive crashes,
restarts, provider 429s, and partial failures without losing work or paying twice
for the same external LLM call. That is only possible if one durable authority
(Postgres) records completion and every mutation is content-addressed so a replay
is a no-op.

---

## 1. Control plane · stage/ticket ownership

`control/control/` owns **census, scheduling, recovery, heartbeat** — nothing
else. It never calls a model and never serves a user request.

- `STAGE_DAG` (`control/control/tickets.py`) is the ordered list of stages, each a
  tuple `(stage, event.vN, artifacts, receipts)`. `DAG_ORDER` derives from it.
- Each stage becomes a **ticket** with a **lease** (`lease_owner`,
  `lease_expires_at`). A worker claims a ticket, does the work, commits, releases.
  A dead worker's lease expires and the ticket is reclaimed — **no work is lost**.
- **The supervisor owns process life** (readiness probes, restart budget, the
  fence quarantine). **The control tick's `medic` phase owns database state**
  (capacity re-arm, deadlock break) — every action receipted in `medic_actions`.

**Rule:** never add a second scheduler or a second workflow authority.
**Category:** OPERATIONAL NECESSITY.
**Why:** two schedulers race on leases and double-dispatch external LLM work.
**Do not:** hand-start a worker or a second orchestrator on :7200 — a bind loop
quarantines the slot (only a supervisor restart clears it). Kill a slot → the
supervisor respawns it.

**The execution-bundle fence (HASH-FENCE-V2):** every edit under `control/`,
`shared/`, or `workers/` changes the fleet's content hash and triggers a ~2-minute
self-quarantine + auto-heal of every slot. **MEASURED DESIGN / OPERATIONAL
NECESSITY.** Consequence of ignoring it: editing those trees while the owner is
testing in the UI restarts the orchestrator mid-request. Batch such edits; docs/,
scripts/, tests/, stores/ do NOT trip the fence.

---

## 2. Postgres authority · Qdrant / Neo4j projections

**Rule:** Postgres owns workflow truth; Qdrant and Neo4j are rebuildable
projections.
**Category:** OPERATIONAL NECESSITY.
**Why:** projection loss must never erase ingestion state or cause external LLM
work to be repeated. A `receipt` in Postgres is proof that semantic work
completed; a Qdrant point is not.
**Do not:** use Qdrant/Neo4j presence as the only record that work happened; do
not rerun a semantic API because a projection failed — re-run the *projection*
stage only (it makes zero LLM calls).

- **Qdrant** holds child vectors, routing points, and the document-profile /
  (coming) parent-map collections. It is a cache of meaning, always reconstructible
  from Postgres rows + the embedder.
- **Neo4j** holds the settled factual graph (Document / Fact / Evidence / Chunk /
  Entity). Only **T2** (admitted) facts land there. **No model ever writes to
  Neo4j** — enforced by `tests/contracts/test_admission_boundary.py`.

---

## 3. Receipts / idempotency (the property everything depends on)

**Rule:** every mutation uses canonical content identity; replaying identical
input must not create a second logical result.
**Category:** OPERATIONAL NECESSITY.
**Why:** restarts, retries, and blue/green re-ingest are only safe if the *k*th
attempt of the same work collapses to the first.

- A stage commits **artifact + receipt + status + outbox event in ONE Postgres
  transaction** (AGENTS.md rule 5).
- Identity is content-addressed: `chunk_id = chunk_<sha256(doc_id|idx|text)>`;
  facts by `(predicate, subject, object)`; parent-map batches by their
  **source-bound `batch_hash`**; parent maps by their **`map_hash`**. Re-running
  the same document's mapping produces the same ids → `ON CONFLICT DO NOTHING` →
  **completed API work is never repeated** (proven live, register 11.136).
- **Do not** key durable identity on `chunk_index` — it is positional
  (`UNIQUE(doc_id, chunk_index)`) and unstable across re-ingest. Durable parent
  identity is the parent `chunk_id`. (This exact bug was fixed in 11.133 before it
  could be persisted.)

---

## 4. Worker boundaries

`workers/workers/` — one durable stage each; never serve user HTTP, never
supervise, never own workflow authority. `orchestrator/orchestrator/api/` — HTTP
intake + reads only; never schedules, never loads models, never runs long jobs.
`sidecars/` — one resident model each (embedder :8742, reranker :8743, local
extractor :8755); untrusted evidence only, hold no state. **Forbidden import
patterns** (orchestrator↔worker↔control internals) are checked by
`scripts/repo_guard.py::check_forbidden_imports`.

**Category:** OPERATIONAL NECESSITY. **Do not** import a worker/control internal
from the orchestrator — cross those boundaries through `contracts/` schemas and
typed clients only. Consequence: a coupling that survives repo_guard locally will
fail CI's `guard` job and can deadlock the fleet.

---

## 5. Retrieval / query runtime

A chat turn is: **compile a plan** (the LLM query compiler turns the conversation
into a PRIMARY query + typed subqueries + exact terms) → **concurrent lanes**
(dense, sparse/BM25, entity-card, hierarchical/summary, optional graph/latent) on
**one embedding** → **fuse** → **one cross-encoder judge** over the fused prefix →
**deterministic composer** picks the evidence → **synthesizer** writes the answer
with `[S#]` citations. Wall-clock budgets emit `degraded` receipts; the judge is
the latency wall on every path.

**Rules that are easy to get wrong:**
- The **cross-encoder is the sole relevance judge.** **MEASURED DESIGN.** Do not
  add an LLM reranker.
- **Vocabulary discovers; source chunks prove.** Profile/map/summary text is
  routing metadata, **never** factual answer evidence. **OPERATIONAL NECESSITY.**
  Consequence of violating: the answer cites a routing signature instead of a
  source passage.
- Quotas (round-robin seats, aspect seats, diversity slots) are present with knobs
  but are **not** the intended composition — the owner wants **pure-rank**
  composition (U7, pending the owner's rule). **OWNER PREFERENCE**, unresolved.

---

## 6. Document profile · profile atoms · parent MAP (the current phase)

This is what this session built. Two semantic scales:

- **Scale A — the global document profile** (DOCUMENT-PROFILE-V1, live; 67/67
  cinema). One strong LLM call per document → a compiled profile (ONE, SUMMARY,
  TOPIC, TERM, Q, SEARCH, THEORY, CONCEPT, SEEALSO) → an artifact with a receipt
  chain → **profile atoms**: one Qdrant point per document with named dense vectors
  (title/identity/theme) + MaxSim multivectors (questions/searches/theories/
  concepts/seealso). The vNext (S5, next) adds an adaptive 500–2,000-token
  fingerprint + research-index surfaces (LATENT-PATTERN/ANCHOR/RECALLQ/TENSION/
  BRIDGE/INVERSION/BOUNDARY).
- **Scale B — the parent MAP** (S1–S4, built this session). Every retrieval-
  eligible parent gets ONE compact routing signature, produced in **packed**
  Compound-Mini calls — **never one LLM call per parent** (register 11.136 proved
  the packed contract live: 22/22 and 11/11 parents mapped in single calls).

**Rules:**
- **Exact identifiers are deterministic Python, not model hooks.** **OPERATIONAL
  NECESSITY / MEASURED DESIGN** (Compound Mini kept `021` in the signature but not
  in the hooks — §9). Consequence of violating: exact retrieval of a code/CVE/id
  silently depends on the LLM having chosen it.
- **The document profile BOOSTS and DEEPENS retrieval; it never GATES it.**
  **OWNER PREFERENCE (explicit).** Consequence of violating (`WHERE doc_id IN
  top_k`): profile nomination silently filters the whole evidence search.
- **Partial map output is durable useful work.** 73 of 90 valid lines persist 73;
  only the missing 17 aliases are repaired; successful lines never re-run.
  **OPERATIONAL NECESSITY.**

Persistence for Scale B is migration **0054** (this session): `document_parent_map_batches`
(resumable, `batch_id` = source-bound hash), `document_parent_maps` (final,
`map_id` = `map_hash`, `parent_id` = chunk_id, **one active map per (doc_id,
parent_id, map_contract)** via a partial unique index), `document_parent_exclusions`.
No worker consumes it yet (S9).

---

## 7. QUERY_READY / readiness

**Rule:** ingested ≠ query_ready. A corpus generation is QUERY_READY only when all
tickets are DONE, projections `desired == actual`, and (Phase B, not yet) the
document profile exists.
**Category:** OPERATIONAL NECESSITY. **Why:** serving a half-projected or
half-old/half-new generation returns wrong or missing evidence.

- Today `doc_profile` is the **last DAG stage and NON-BLOCKING** (phase A) — a
  document serves even without a profile. `control/control/tickets.py` comments
  mark exactly where Phase B moves it: ahead of `verify_projections` and out of
  `NON_BLOCKING_STAGES`. **That flip is S15 / the old U2 and needs the owner's go
  AND every corpus backfilled first** — flipping early makes unprofiled corpora
  un-serveable. **TEMPORARY MIGRATION CONSTRAINT.**
- `502 corpus_not_ready` while a generation converges is **by contract, not a
  fault** — do not "fix" the serving path; wait for query_ready (blue/green
  re-ingest is the outage-free path: `scripts/reingest_corpus.py --execute
  --blue-green`).

---

## 8. Migration dependencies

54 migrations (`stores/postgres/migrations/0001…0054`), applied **in name order**,
each idempotent (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` after 0002). A fresh
clone runs them all; an existing install applies pending files. **0054** (this
session) is additive (three new tables, FK to `documents`) and safe to re-apply.
**Do not** edit an applied migration — append a new one. **OPERATIONAL NECESSITY**
(an edited applied migration diverges environments silently).

---

## 9. Groq routing architecture (ingestion provider layer)

**Policy of record:** `docs/wiki/plans/GROQ-ROUTING-POLICY-V1.md` (register 11.134).
The decision core `shared/polymath_shared/document_profile/groq_router.py` is
built and unit-tested; the **live wiring is NOT done** (gated).

- The six Groq accounts (`GROQ_API_KEY_1..6`) are **six capacity domains**. Each
  exposes `groq/compound` (global profile / strong work) and `groq/compound-mini`
  (parent-map overflow / throughput). **The two models SHARE one account's
  RPD/TPM/RPM budget** — not independent quota pools. **OPERATIONAL NECESSITY.**
  Consequence of violating: two model lanes each assume full account capacity and
  the account 429s / burns its daily quota.
- **No fixed round-robin, no key burning.** The current `pool.py` still uses a
  doc-hash ring (`_ring_pick`); S7 replaces it for these lanes with capacity-aware
  selection and persists shared rate state through the existing `ControllerStore`.
- **Tools disabled during ingestion.** **OPERATIONAL NECESSITY** (§30 injection
  regression + no web/code spend). NOTE: in the live canary compound-mini simply
  did not invoke tools; S7/S8 must set the explicit tools-off parameter, not rely
  on that.

The keys live ONLY in the gitignored `.env`; the assistant never handles them.

---

## 10. Important legacy bridges still alive (do NOT retire during a handoff)

- **Summaries** (`document_summaries`, `parent_summaries`, `section_summary`
  routing points) are measured *unnecessary in chat* (B10/B13/11.123) but are
  **still read** by `candidate_engine.py`, `chat_retrieval.py`, `hybrid.py`,
  `fast.py`, `evidence*.py`, `graph.py`, `/retrieve` Tier-0 routing, and the corpus
  map. **LEGACY / MEASURED**: they still route; retiring them is an owner decision
  with readers to migrate first. **Do not delete the summary tables/lanes.**
- **`parent_enrichment`** is still a live lane (autopilot tail demand, 11.37).
- **`compile_objects`** (concept/procedure compilers, 11.4) is live but
  deliberately ABSENT from `STAGE_DAG` (minted at a button). The §13 per-parent
  latent "parent-semantic-compiler" (1/3/3/4 = 8 vectors/parent) is **DESIGN,
  build-pending** — **LEGACY/DEBT**; the new parent MAP (one packed signature per
  parent) is its intended replacement, and **S16 measures the old parent-semantic
  work for retirement — it is NOT retired yet.**
- **Wildcard** exists (latent bridges) and is **retained** — the next-phase plan
  indexes research surfaces now and defers a Wildcard research executor; do not
  build it, do not delete it.

---

## 11. Retirement hazards (what looks dead but is load-bearing)

- Deleting a document must prune its Neo4j subgraph + projection receipts (a bare
  chunk delete leaves orphans — fixed in 11.114; the hazard recurs if you write a
  new delete path).
- `facts_direct` counts NEW rows; read `facts_existing` beside it before calling an
  extraction empty.
- An era-fenced run (older semantic bundle) refuses stage re-arm by design — repair
  old-era corpora with `--blue-green`, never by flipping tickets.
- `chunk_index` is NOT durable identity (§3).
- The chunker is **frozen for this phase** — do not modify/benchmark/migrate
  chunk generation (owner NON-NEGOTIABLE this handoff). Its child sizing was
  measured healthy (median ~108–140 tok, near the 128 target); the only granular
  cohort is `region_role='stub'` OCR noise, and the cheap fix is a retrieval-side
  `NOISY_ROLES` addition, NOT a chunker change.

---

## 12. Testing / governance conventions

- Guards, run under `.venv/bin/python` (or python3.11 — `agent_preflight` needs
  `tomllib`, absent in the mac default python 3.9): `agent_preflight.py` (may I
  start), `repo_guard.py` (declared==actual files, work-log shape, forbidden
  imports, script registry), `wiki_worm.py --check` (every `docs/wiki/**/*.md` has
  front matter + `last_reviewed`).
- **Every repository file must be declared** in `scripts/scaffold_polymath_v4.py::TREE`
  or repo_guard fails. New file → add a TREE line in the same commit.
- **Work-logs are append-only**, need front-matter fields `change_id/owner/date/
  status/architecture_impact` + `last_reviewed`, and the ordered sections
  `## Contract / Changes / Proof / Rejected claims / Open contract gaps`.
- **Determinism tests** (`tests/determinism/`) are pure OR skip cleanly without a
  DB (`to_regclass` / `SELECT 1` gate) — CI has no Postgres, so DB-touching tests
  skip in CI and run locally with `.env` sourced.
- **Branch policy:** work on `architecture/evidence-first-v5`; push it; wait for
  the **four required checks** (`preflight`, `contracts`, `test`/determinism,
  `guard`); then **fast-forward `main`** to the same green SHA (`git push origin
  <sha>:refs/heads/main`). `main` is protected — a direct push of an unchecked SHA
  is rejected; an ff of an already-green SHA is accepted. Never `git checkout` in
  the live worktree (`../polymath-v4-main` is the main worktree).
- **Proof before commit:** a change is proven by an automated asserting test run
  GREEN, not by a log grep.

---

## 13. How to think when you change something

1. Which invariant does this touch? (this file §"rules")
2. Owner preference or operational necessity? (tag it; you may not override an
   operational necessity for convenience)
3. What reads the artifact I'm changing? (grep the readers — §10 shows the summary
   trap)
4. Does replay stay a no-op? (content identity — §3)
5. What test proves it, and does it run green in a clean shell?

If you cannot answer all five, you are not ready to edit. Write the answer in a
work-log first (AGENTS.md §4), then change the code.
