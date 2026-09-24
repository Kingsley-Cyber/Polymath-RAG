---
title: "Code RAG and provider-key audit: how keys, indexing and retrieval behave today, and what code needs"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "COMPLETE — read-only audit against production 69c2704; nothing changed, no model called; proposals wait for the owner"
owner: "@king"
scope: "Provider keys / models / lanes / rate limiting (every stage), the indexing path (parents, children, pMAP, profile, graph) and the retrieval path (modes, lanes, floors, graph) — each judged for CODE-KNOWLEDGE-V1. Evidence: docs/wiki/experiments/code-rag-key-audit-2026-09-24/ plus three read-only analysis runs whose decision-driving claims were re-verified by hand."
---

# Code RAG and provider-key audit (2026-09-24)

The owner asked (2026-09-24): configure each API key "smart"; "each api key is a individual seperate account"; "3
models per api key" to maximize token use. Also: how information is indexed and retrieved (parent / child links, pMAP
routing), "is the cosine similarity floor good, does code rag work?", how the code semantic LLM calls are handled, whether
it works with FAST / HYBRID / GRAPH, and "how does graph work for a corpus with code and document queries".

Evidence classes: **E** = executed and observed; **R** = read in code or config (file:line); **I** = inferred.
"Verified" marks the claims re-checked by hand after the analysis runs.

## 0. Answers first

| Question | Answer |
|---|---|
| Are the keys used well? | **No.** Of 18 Groq (key, model) pairs, 11 are switched on and 7 are idle, which is 1.4M tokens/day left unused (E, verified). The new Groq setup from the 09-23 model swap has **never run**: 0 calls on gpt-oss-120b / gpt-oss-20b / qwen3.8-27b; the last Groq call was 09-21 05:20 UTC (E, verified). The rate limiter cannot enforce Groq's real limits (§1.3). |
| Does code RAG work? | **Not today; it is not built.** Code uploads are refused (`.py/.yaml/.toml/.luau` → 422, ui.py:457, R). If code were renamed `.txt`, the book chunker would cut it on comment lines and **leave real lines out of every chunk**: 10 real settings lines of `config/runtime_budget.yaml` and an import block of `doc_profile_worker.py` (E, verified, §2.3). |
| Is the cosine floor good? | **There is no cosine floor on the chat path, and that is right.** The cuts are rank caps and cross-encoder σ floors (§3.2). The repo recorded cosine ranking an author bio (0.5955) above the real answer (0.4894). For code the risks are elsewhere: the σ 0.5 floor judging raw code under a "web search" instruction, the 384-token judge window, the 2,000-character evidence cap and the one-seat-per-document fairness rule. |
| How are parents, children and pMAP used? | pMAP **nominates parents by rank**; a cosine search on the question picks the children inside them; the cross-encoder judges the **child text**; no parent text is ever added to the answer prompt (§3.1). For code, spec §13 turns this around: rank the unit's description, then hydrate the exact code unit by rule. |
| How are the code semantic LLM calls handled? | Today code would get the BOOK prompts: the profile sees ~6 % of a file (the filename, comment "headings", the first 320 and last 240 characters); the pMAP skeleton carries a comment as its heading and no signatures. The compilers split signatures on `|` and strip `_` / `*` from identifiers (§2.2). The planned code prompts (spec §11) fix the inputs; the compilers need an identifier-safe normalizer. |
| FAST / HYBRID / GRAPH? | FAST runs lanes A + B only (no sparse lane, no skeleton doors), so neither code door would run. HYBRID has every door but judges raw code today. GRAPH = HYBRID + Entity facts, and code has no Entity facts by design (§3.4). |
| Graph for code + documents? | GRAPH mode reads only `(:Entity)-[:REL]->(:Entity)` facts. Code gets no LLM extraction (owner decision), so a code question in GRAPH gets the documents' facts only. The C8 Neo4j code projection changes nothing at query time until C10's structure lane reads code edges. |

## 1. Provider keys, models and lanes

### 1.1 Groq: account × model (E, verified: `audit_evidence.json` → `groq`)

| Account | gpt-oss-120b | gpt-oss-20b | qwen3.8-27b |
|---|---|---|---|
| GROQ_API_KEY_1 | `profile_groq1` **on** → doc_profile | `map_groq1` off (idle) | no lane (idle) |
| GROQ_API_KEY_2…6 | `profile_groq2…6` off (5 idle) | `map_groq2…6` **on** → pMAP | `map_groq2q…6q` **on** → pMAP |

Each pair has its own limits: 30 RPM / 1K RPD / 8K TPM / 200K TPD (owner, 2026-09-23). The daily token limit binds
first: per pair about 86 document profiles, or 66–70 pMAP batches of 15 parents (canary sizes), which is roughly 35
minutes of full-speed work.

### 1.2 The other accounts (E / R)

| Account | Use | Problem |
|---|---|---|
| Gemini 1–6 (2 models each, 12 lanes) | extraction pool | lanes at the front of the pool get most calls (gemini1: 155; gemini5 / 6: 0–4) |
| OpenRouter 1–3 | extraction, parent enrichment, the profile and pMAP fallbacks, the chat compiler's `compiler_alt` | **one limiter family for 7 lanes on 3 accounts** (verified): after 140 real 429s on openrouter1, 4,210 local refusals hit all four enrichment lanes |
| Cloudflare 1–6 | 2 pMAP lanes + 4 extraction lanes | **only `CLOUDFLARE_ACCOUNT_ID_2` is set** (verified): 5 of 6 accounts park silently |
| NVIDIA 1–2, SiliconFlow 1–3 | extraction | NVIDIA median ~100 s per call; SiliconFlow 31 of 72 calls timed out (E, verified) |
| Ollama `primary` (lane `default`, qwen3.5:397b-cloud) | extraction default | 38 attempts, 0 successes, 34 × HTTP 402 (E, verified) |
| Alibaba token plan | chat compiler | 510 of 530 calls timed out (E, verified); the chat compiler depends on the Ollama gemma lane (1,856 of 1,890 calls succeed) |

### 1.3 How rate limiting works, and why it cannot hold Groq's limits (R, verified)

- **Admission counts `len(user_prompt) / 4`** (`client.py:510`). The system prompt and the output are not counted;
  real calls use 2.0–3.6K tokens.
- **No daily-token budget exists.** `ProviderLimit` has `rpm`, `tpm` and `rpd` only (`limiter.py:62-80`). The 09-13
  forensic audit already named TPD as the binding limit; it was never built.
- **The limiter lives in each process.** Six doc_profile workers all start on `profile_groq1` (a pin with one primary,
  `doc_profile_worker.py:143`): up to about 28K tokens/min against an 8K pair (I).
- **Old ceilings come back on restart.** `llm_controller_state` still holds `adopted_tpm: 70000` (compound-era headers)
  for `profile_groq1` and `map_groq2…6`, and `provider_rpd_limit: 250` on the map lanes (E). The restore path adopts it
  without clamping to the configured 8K (`limiter.py:526-531`, `:483`) until fresh headers correct it.
- **A local refusal fails a profile attempt for good.** The limiter returns `LIMITER_REFUSED`
  (`client.py:528-530`); doc_profile's transient pattern does not include it (`doc_profile_worker.py:48-49`), so a
  refusal uses one of the document's three attempts. pMAP treats the same refusal as transient.
- **pMAP runs stick to one lane.** `_pmap_lanes` rotates the 12 active lanes by a hash of the run and only moves on
  after an error (`doc_parent_map_stage_worker.py:112-154`); fallbacks rotate in as equals.
- The old "~8.2 attempts per finished pMAP batch" is two populations: batches created 09-08/09 (Groq accounts out of
  daily tokens, every backfill re-leased every pending batch) versus about 1 since 09-11. `attempt_count` counts
  passes, not requests (E).

### 1.4 Proposal: three models on every Groq key (NOT applied; the owner decides)

**Phase 1: config + small code changes; each (key, model) pair belongs to exactly one worker, so a per-process limiter
is correct.**

| Key N (1–6) | gpt-oss-120b | gpt-oss-20b | qwen3.8-27b |
|---|---|---|---|
| Owner | doc_profile worker N (`profile_groqN`) | pMAP worker N (`map_groqN`) | pMAP worker N (`map_groqNq`, new for key 1; output cap ≤ 900 where OTPM 1000 applies) |

- doc_profile: each worker tries its own key, then the OpenRouter fallback (`PRIMARY_ATTEMPTS=1`); add
  `LIMITER_REFUSED` to the transient pattern.
- pMAP: 6 workers (today 4), each owning its key's two pairs; fallbacks last; never another worker's pair.
- Limiter per pair: 8K TPM, 2–3 RPM, 950 RPD, and a NEW rolling daily-token budget (about 190K); real-token admission
  (prompt + system + reserved output); clamp restored ceilings to the configured values; reset the six stale
  `llm_controller_state` rows (a database write: owner's step).
- Capacity: profiles ~1.2M tokens/day (about 520 documents or 240 code-profile requests); pMAP ~2.4M tokens/day
  (about 800 batches, 12K parents). All 18 pairs used. For CODE-KNOWLEDGE-V1: this repository's product code (437
  profile requests) drops from 11.0 days to about 2.

**Phase 2: one shared budget per (account, model) in Postgres, used by every process:** reserve up front, correct to
actual usage, a rolling daily total, profiles before pMAP. pMAP could then borrow unused 120b budget (up to ~3.4M
tokens/day), and a Groq gpt-oss-20b lane could back up the chat compiler (0.6–0.9 s in the canary).

**Other providers:** fill the 5 missing Cloudflare account ids; give each OpenRouter account its own limiter family
and stop sharing lanes between extraction and enrichment; spread extraction across the whole Gemini pool; drop or
cap NVIDIA, SiliconFlow and the Ollama `primary` lane (402); raise or drop the Alibaba compiler timeout.

**Prove first (≤ 20 calls, ~50K tokens, the owner's word):** one call on each unused pair; qwen on keys 2, 3, 6 at
max_tokens 2400 (which accounts enforce OTPM 1000) and on key 5 at 900; three calls within 20 s on one pair (does Groq
reserve max_tokens against TPM?); then one profile ticket and one small pMAP document, checking in the ledger that
calls land only on the owning pairs.

**Files a Phase 1 slice touches:** `config/cloud_providers.json`, `config/extraction_models/limiter.yaml`,
`shared/polymath_shared/llm_extraction/{pool,limiter,client}.py`, `workers/workers/doc_profile_worker.py`,
`workers/workers/doc_parent_map_stage_worker.py`, `control/control/process_supervisor.py` (6 pMAP slots + offsets).
Shared / workers code → fence + one bounce.

## 2. Indexing: documents today, and code

### 2.1 Data model (R)

```
documents(doc_id = sha256(bytes), media_type, frontmatter)
 ├─ document_layout (heading | dropped_stub | dropped_empty spans)
 ├─ chunks: parent (chunk_id, heading_path, char_start/end, region_role, chunk_contract_version)
 │   ├─ chunks: child (parent_id → parent.chunk_id) → corpus collection, dense (+ bm25 sparse)
 │   │     └─ LLM extraction → Neo4j Entity / REL / Fact / Evidence
 │   ├─ retrieval_summaries (section card, parent_id) → routing collection
 │   └─ document_parent_maps (parent_id, alias, routing_signature, 3 hooks, exact_identifiers)
 │        → pMAP collection (dense "routing" vector; exact_identifiers not projected)
 ├─ retrieval_summaries (document card)
 └─ doc_profile artifact → profiles collection (title / identity / theme + 5 multivectors); atoms → atoms collection
```

The chunker (`tier_v3`, `chunk-structure-v3.1`) is one global setting, not chosen per document. Budgets are in words:
parents ~850 (max 1,400), children ~120 (max 250). A heading is any stripped line matching `^#{1,6}\s+`. Sections under
15 words are dropped (recorded in `document_layout` as `dropped_stub`, never searchable).

### 2.2 The two semantic calls (R)

| | Profile `doc-profile-v3.2` | pMAP `map-prompt-v2` |
|---|---|---|
| Input | TITLE, HEADINGS, OPENING, ≤ 3 SAMPLES, ENDING, KNOWN TERMS in a 500-token context | ≤ 90-token grounding + per parent: HEADING, OPENING (≤ 50 words), EXCERPT (≤ 30 words), ≤ 5 TERMS, regex IDENTIFIERS |
| Output | labelled lines ONE … SEEALSO, END; 2,400-token cap | `MAP\|alias\|signature\|h1;h2;h3`, every alias once; batch cap 15 |
| Failure handling | transient HTTP errors hold the ticket; others (incl. a local refusal, §1.3) count as a failed attempt | valid lines kept; partial replies retried for missing aliases only (3 tries) |
| Reuse | no input-hash skip; a thinner result never overwrites a richer one | skips parents that already have an active map (the parent id is content-addressed) |

### 2.3 What code gets today (E; verified with `audit_evidence.json` → `tier_v3_on_code`)

| File | Non-blank lines | Lines in no child | Real (non-comment) lines lost |
|---|---|---|---|
| `config/runtime_budget.yaml` | 152 | 98 | 10: `total_gb: 29.0`, `max_batch_tokens: 8192`, `max_batch_texts: 8`, `mps_gb`, the `control_plane:` block, `enforce_preflight: true`, `reserve_gb` |
| `workers/workers/doc_profile_worker.py` | 332 | 21 | 3: lines 334–336 (`try:` + two imports) |
| `.github/workflows/determinism.yml` | 46 | 7 | 1: `name: determinism` |

The analysis run also measured, over 125 files: 1,300 comment lines turned into headings (indented ones too), 885 stub
sections dropped, 62 of 1,822 code children tagged `noise_ocr` (the chat path drops those), functions split across
parents, decorators kept with their function. The pMAP model would see a comment as a unit's HEADING and acronyms as
"IDENTIFIERS", with no function names or signatures. The profile request for a 21,984-character file is 1,361
characters. On a synthetic reply, the MAP compiler cut a signature at `dict | None`, and both compilers turned
`__init__` into `init` and `_pool_complete` into `pool_complete`. The BM25 tokenizer keeps camelCase whole
(`HumanoidRootPart` is one token) and drops tokens shorter than 2 characters.

### 2.4 Indexing gaps for code (each closed by a planned slice)

| # | Gap | Severity | Slice |
|---|---|---|---|
| 1 | The upload gate refuses code; the chunker is global, not per document | High | C1 |
| 2 | tier_v3 on code: comment headings, split functions, **lines in no chunk**, mid-line cuts | Critical | C1 routing + C3 provider |
| 3 | `doc_id = sha256(bytes)`: an edit is a new document; a ≥ 0.95-containment edit is refused as a duplicate; an empty `__init__.py` fails (`materializer.py:171`) | High | C1 (path → hash ledger, supersession) |
| 4 | Front-matter harvesting runs on code | Medium | C1 |
| 5 | Region roles guessed from prose shape: `code` gets no section card; `noise_ocr` gets no pMAP and is dropped at query time | High | C3 (the parser sets the role) |
| 6 | LLM entity / fact extraction runs on code and writes into the shared Entity graph | High | C1 / C3 skip it |
| 7 | Chunk rows carry no line span, symbol id, qualified name, language, revision or tool version | High | C2 |
| 8 | MAP line breaks on `\|` and `;`; compilers strip `_` and `*` | High | C6 / C7 (identifier-safe normalizer; labels unchanged) |
| 9 | Budgets in words, not tokens | Medium | C3 / C6 / C7 (spec §12.4) |
| 10 | No exact lookup: pMAP is dense-only; BM25 keeps camelCase whole | Medium | C2 symbol table + C9 exact door |

## 3. Retrieval: modes, floors, graph

### 3.1 Mode × lane (R; live flags E)

| Mode | Lanes | Notes |
|---|---|---|
| FAST | A (hierarchy: document + section summaries + entity cards) + B (dense children) | no sparse lane, no skeleton doors, no probe gate |
| HYBRID | A + B + C (BM25) + E (profile → pMAP → children) + D (latent) + G on probes | probe gate σ 0.2 |
| GRAPH | HYBRID + G + H (entity cards → Neo4j hop 1 → pMAP → children) | facts attached after evidence |
| WILDCARD | HYBRID + the latent frontier + bridges | contextual (path-aware) judge ON |
| GNN | lane I only (offline parent vectors; cinema only) | — |

Fusion is RRF; one cross-encoder call (Qwen3-Reranker-0.6B, yes/no log-odds) judges a document-fair prefix of 32, plus
seats for subqueries and routes; the composer keeps 15. Measured on the owner's 117 HYBRID turns of the last 5 days
(E): union p50 161 (p90 212) → judged 32 → selected 15 → cited p50 10. About 80 % of the union is never judged: the
caps cut, not the floors.

### 3.2 Floors (R; verified where marked)

| Floor | Value | For code |
|---|---|---|
| Cosine / Qdrant `score_threshold` | **none** on the chat path | right: keep none |
| Rank caps | dense 50, sparse 40, union 120, judged 32, final 15 | code children compete with book prose for the same 50 dense slots |
| Document-fair prefix | round 1 = one seat per document | a file is a document: with > 32 files, one unit per file gets judged |
| Noise-region drop | front matter, toc, index, bibliography, `noise_ocr` | 3.4 % of code children tagged `noise_ocr` |
| `structural_noise_reason` | ≥ 45 % bare numbers over ≥ 40 tokens | hits numeric YAML / TOML |
| Judge input | 384 tokens, 4,000 characters | code is token-dense: the tail of a unit is never seen |
| Judge instruction | "Given a web search query, retrieve relevant passages" | never tuned for code |
| Main-query / aspect floor | σ ≥ 0.5 (below: "NO RELEVANT EVIDENCE … say so") | the floor most exposed to raw code |
| Probe gate | σ ≥ 0.2 (HYBRID / GRAPH), calibrated on 5 cinema plans | probes are English; recalibrate |
| Contextual judge | at-risk 0.5, connection 0.3; WILDCARD only | see risk 1 |

Spec §13 puts the judge on (question, English description), which is what the reranker and these σ floors were fitted
on, and hydrates the exact code by rule. The engine already separates the two: the judge scores the Qdrant payload
text while the prompt fetches `chunks.text` by chunk id (`rerank.py:134`, `evidence_assembly.py:333`), so a unit point
whose payload is the description and whose chunk id is the unit gives "rank the description, cite the code". The
hydrator must replace `_resolve_chunk` and lift the 2,000-character evidence cap.

### 3.3 Parent ↔ child ↔ pMAP (R)

Every route that reaches a parent (section summary, pMAP, graph destination, latent, GNN) turns it into children with a
parent-filtered cosine search on the question vector. pMAP never scores relevance; it nominates. The prompt carries
child text only (≤ 2,000 characters), a book › section breadcrumb and ORIENTATION (≤ 3 profiles, ≤ 6 pMAP signatures).
Only the WILDCARD contextual judge reuses a pMAP signature, as a path "need".

### 3.4 Graph (E counts; R mechanics; verified: the hop-1 query)

- Built by LLM extraction at ingest → Postgres entities / facts / evidence → Neo4j: Entity 50,095, Fact 27,998,
  Evidence 28,665, Chunk 95,392, REL 27,910. Nodes carry no corpus; Postgres authorizes.
- GRAPH seeds up to 8 entities (entity cards, query tokens, tokens of the first evidence chunks), expands one hop over
  HIGH/MEDIUM predicates and keeps **`ORDER BY fact_id LIMIT 20`** (`retrieve.py:712`, verified). `fact_id` is a hash,
  so the 20 facts are an arbitrary pick, not the most relevant. This predates the code work and affects documents
  today.
- A fact is shown only when its proving child is already in the evidence.
- **Code + documents in one corpus:** today (code as `.txt`) GRAPH would serve LLM-guessed "facts" read from code, which
  the owner ruled out. After C1: code has no Entity facts, so GRAPH = HYBRID + book facts. After C8: unchanged at query
  time (every chat Cypher query matches `(:Entity)-[:REL]->(:Entity)`). After C10: the structure lane is the first
  reader of code edges. Which modes open it is not yet specified.
- Collision risks for C8: code files are also `documents` rows, so the existing projection would add `:Document` /
  `:Chunk` next to `:CodeDocument` (two nodes per file); the document delete path knows only Chunk / Evidence / Fact /
  REL / Document (`ui.py:782-798`), so Code* nodes would be orphaned.
- All five modes require one corpus (`ui.py:3757-3765`), so project = corpus is forced; a content-addressed `doc_id`
  belongs to one corpus, so one reference book cannot join two project corpora.

### 3.5 Retrieval risks for code

| # | Risk | Severity | Where / slice |
|---|---|---|---|
| 1 | Route seats need `route_score`, which only the contextual judge sets (`candidate_engine.py:1480, 1756`); with `CONTEXTUAL_JUDGE=wildcard`, structure-lane callers / callees in HYBRID / GRAPH must beat the literal question on σ, contradicting spec §1 ("each discovery path survives ranking") | High | C10 |
| 2 | Fairness rules assume a document is a book (6-document lane A, document-fair prefix, per-document caps) | High | C9 / C10 |
| 3 | Until §13 lands, the σ 0.5 floors judge raw code under a web-search instruction | High | C9, then recalibrate |
| 4 | Content-addressed, single-corpus `doc_id` + the duplicate guard vs project = corpus | High | C1 |
| 5 | BM25 keeps camelCase whole; changing the tokenizer changes a frozen contract | Medium | C2 / C9 (a separate code sparse field) |
| 6 | GRAPH's 20 facts in hash order | Medium | independent fix (documents too) |
| 7 | FAST has neither an exact door nor skeleton doors | Medium | C9 decision |
| 8 | 384-token judge window, 2,000-character evidence cap | Medium | C9 hydrator |

## 4. What this adds to the CODE-KNOWLEDGE-V1 plan

- **C1** also owns: the upload gate; per-document chunker routing; front-matter skip; empty files; the path → hash
  ledger with supersession (the duplicate guard refuses small edits today); skipping LLM extraction for code; a
  decision for reference books shared by two project corpora.
- **C3**: the parser sets `region_role=code`; code is exempt from the noise-region drop and `structural_noise_reason`;
  children cover every byte (a new coverage check; today's validator checks exactness, not coverage).
- **C6 / C7**: an identifier-safe normalizer in both compilers (keep `_`, `*`, dotted names; signatures never split on
  `|`); token-based request sizing.
- **C8**: no duplicate `:Document` / `:CodeDocument` node per file; the delete path removes Code* nodes.
- **C9**: rank the description payload, cite the unit by chunk id; replace `_resolve_chunk`; lift the 2,000-character
  cap; decide FAST's doors; recalibrate σ floors on code descriptions.
- **C10**: route seats for structure-lane paths without depending on the WILDCARD-only contextual judge; per-file
  fairness instead of per-book.

## 5. Independent defects found (not code-RAG work; each needs the owner's word to fix)

1. doc_profile counts a local limiter refusal as a failed attempt (`doc_profile_worker.py:48-49`).
2. Stale `adopted_tpm: 70000` restored without clamping (`limiter.py:526-531`).
3. One OpenRouter limiter family across 3 accounts / 7 lanes.
4. 5 Cloudflare account ids missing in `.env`.
5. GRAPH hop-1 facts `ORDER BY fact_id LIMIT 20` (`retrieve.py:712`).
6. Dead or slow extraction lanes (`primary` 402, NVIDIA, SiliconFlow); the Alibaba compiler lanes time out.
7. `POLYMATH_GROQ_ROUTER=1` is set live, but its only reader, `document_profile/groq_routing.py:40`, has no production caller.

## 6. Owner decisions

1. Phase 1 key plan (all 18 Groq pairs, one owner per pair, 6 pMAP workers, the limiter fixes) — and the ≤ 20-call
   canary before it.
2. Fill the Cloudflare account ids (the owner's step: secrets).
3. Which of the §5 defects to fix now.
4. For code: which modes open the code doors (FAST included or not).
