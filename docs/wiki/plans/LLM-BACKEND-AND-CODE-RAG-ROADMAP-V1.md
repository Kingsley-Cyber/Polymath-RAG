---
title: "Roadmap: a clean LLM provider backend, the document defects, and code RAG with a joint code / document graph walk"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "PLAN OF RECORD (owner 2026-09-24: 'fix all of this … implement this in strategic slices and a plan way ahead'). Execution order across tracks. C0b done (11.461); L1 is next."
owner: "@king"
scope: "Closes every row of GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md. Supersedes the slice ORDER in CODE-KNOWLEDGE-V1-START-HERE.md §4 (the C-slice definitions there and in CODE-LANGUAGE-REPRESENTATIONS-V1.md still hold, amended here). The build instructions per slice are CODE-RAG-IMPLEMENTATION-V1.md."
---

# Roadmap: LLM backend, document defects, code RAG, joint graph walk

## 0. The owner's direction (2026-09-24)

- "it shouldnt be 18 or 11 api keys, it should be like 4-6 api keys with multiple models configured … the backend llm api
  seems messy. it doesnt seem indexed and treated with care and proper identification and ownership architecture."
  (There ARE 6 Groq keys; "18" counted key × model combinations. The fix is exactly the owner's picture: accounts first,
  their models under them, and explicit ownership.)
- "cloudflare should be wired and working."
- "we need to fix all of this except the ones you said is good like cosine floor." (The ≤ 20-call canary proposed with
  the key plan is read as included; say so in the slice receipt.)
- "you can download the parsers, you can get a luau roblox code file from github … just use 1 file."
- "we need to find a way to walk code graph with document graph if retrieved."

Standing rules (START-HERE §6): one worktree branch per slice, new behaviour behind a flag (default off), impacted tests
only (`-k "not test_live_"`, never the whole determinism directory), work-log + register row + TREE entries + guards,
merge and bounce by the agent or by the owner's Run button when the classifier blocks, push only on the owner's word.

## 1. Target design: the LLM provider backend (Track L)

### 1.1 Accounts first (one registry)

A new `config/llm_accounts.yaml` is the single source of truth. Secrets stay in `.env`; the registry names them.

```yaml
accounts:
  groq_1:
    provider: groq
    key_env: GROQ_API_KEY_1
    endpoint: https://api.groq.com/openai/v1/chat/completions
    models:
      openai/gpt-oss-120b: {limits: {rpm: 30, rpd: 1000, tpm: 8000, tpd: 200000}, reasoning_effort: low}
      openai/gpt-oss-20b:  {limits: {rpm: 30, rpd: 1000, tpm: 8000, tpd: 200000}, reasoning_effort: low}
      qwen/qwen3.8-27b:    {limits: {rpm: 30, rpd: 1000, tpm: 8000, tpd: 200000, otpm: 1000}, reasoning_effort: none}
  cloudflare_1:
    provider: cloudflare
    key_env: CLOUDFLARE_API_TOKEN_1
    account_id_env: CLOUDFLARE_ACCOUNT_ID_1
    models: {"@cf/qwen/qwen3-30b-a3b-fp8": {limits: {rpm: 300}}}
  # … groq_2..6, cloudflare_2..6, gemini_1..6 (2 models each), openrouter_1..3, nvidia_1..2, siliconflow_1..3,
  #     alibaba_1, ollama_local

assignments:            # OWNERSHIP: which stage (and which worker slot) may call which (account, model)
  doc_profile:     {per_slot: ["groq_{slot}/openai/gpt-oss-120b"], fallbacks: ["openrouter_2/mistralai/mistral-small-2603"]}
  doc_parent_map:  {per_slot: ["groq_{slot}/openai/gpt-oss-20b", "groq_{slot}/qwen/qwen3.8-27b"],
                    fallbacks: ["cloudflare_1/@cf/qwen/qwen3-30b-a3b-fp8", "cloudflare_2/…", "openrouter_3/…"]}
  extract:         {pool: ["gemini_*/*", "cloudflare_3..6/*", "openrouter_1/*", …]}
  parent_enrichment: {pool: [ … ]}
  chat_compiler:   {order: ["ollama_local/gemma4:31b-cloud", … ]}
```

Rules the loader enforces (a validator + `scripts/llm_accounts.py report`):
- every lane is DERIVED as (account, model, stage), and its limiter family is always (account, model);
- a dedicated (account, model) is owned by exactly one (stage, slot); pools list shared pairs explicitly;
- every declared account shows whether its key (and account id) is set, as a boolean, never the value;
- the report prints one table: account → model → owner → limits → key set? → last call → calls / 429s / refusals today.

### 1.2 Limiter semantics

- Admission cost = tokens(system + user) + the reserved output (`max_tokens`), then reconciled with the response's
  `usage` (L-04).
- Windows per (account, model): RPM, TPM (sliding 60 s), RPD, **TPD (rolling 24 h)**, OTPM where declared (L-05,
  L-16).
- Restored state is clamped to the configured limits (L-08).
- A local refusal is transient everywhere (L-09).
- Every attempt row carries stage + account + model (L-17).
- Phase 2 (L5): the budget of each (account, model) lives in Postgres and is shared by every process (L-06), so pools
  and borrowing are exact.

### 1.3 Capacity after L3 (arithmetic from C0a, to be measured in L4)

Profiles ~1.2M tokens/day (6 × gpt-oss-120b); pMAP ~2.4M tokens/day (6 × gpt-oss-20b + 6 × qwen3.8-27b) plus the
Cloudflare fallbacks. This repository's product code: 437 profile requests → about 2 days instead of 11.

## 2. Target design: walking the code graph with the document graph (Track G)

Four link kinds, each with its own authority. They are never mixed up in storage or in the answer.

| Link | Meaning | Made by | Stored |
|---|---|---|---|
| STRUCTURE | what calls / imports / reads / requires / pairs with what | parsers + resolvers (C2–C5), deterministic, with `resolution` and reproducibility attributes | Postgres `code_edges` → Neo4j `CODE_*` (C8) |
| FACT | what a document states | the existing extraction → Entity / REL / Fact / Evidence | unchanged |
| MENTION | this passage names this symbol / config key / file path (exact match) | a deterministic index-time matcher over the code symbol table and document chunks, confidence-tagged | Postgres `code_doc_mentions` → Neo4j `(:CodeSymbol)-[:MENTIONED_IN]->(:Chunk)` |
| SEMANTIC | this code unit and this passage are about the same mechanism | query-time similarity between code DESCRIPTIONS (pMAP hooks, profile CONCEPT / THEORY / SEEALSO) and document atoms / entity cards, judged path-aware | NOT a fact; routing only (optionally a versioned routing cache) |

**The walk (bounded, deterministic order):**
1. Seeds = what retrieval found through both doors: code units (description door, exact door) and document passages.
2. From a code seed: STRUCTURE hops by the task's hydration rule (spec §13) → MENTION hops to passages that name the
   unit → at most ONE semantic hop from the unit's descriptions to document atoms / entities → their passages.
3. From a document seed: the existing FACT hop → MENTION hops to the code units the passage names → at most ONE semantic
   hop from the passage's concepts to code-unit descriptions → units → STRUCTURE hydration.
4. Never chain two SEMANTIC hops. Every hop carries a readable path ("called by `X`", "named in *Book* §3", "same
   mechanism as …") into the path-aware judge, whose seats do not depend on the WILDCARD-only switch (C-19).

**The answer keeps the authorities apart** (spec §10): observed behaviour (code, cited `[S#]` with file, lines,
revision) · guidance (book passages) · the proposed change (labelled as a proposal). A semantic link can suggest
reading a passage; it never becomes "the code implements theory X".

**Per mode:** FAST = exact door + description door + hydration, no walk · HYBRID = + the structure lane + MENTION ·
GRAPH = the full walk (FACT + STRUCTURE + MENTION + one SEMANTIC hop) · WILDCARD = GRAPH + the latent frontier.

## 3. The order (the plan way ahead)

| # | Slice | Closes | Depends on | Proof (exit) | Gates |
|---|---|---|---|---|---|
| 1 | **C0b** tooling runs — **DONE 11.461** | C0 open items | — | LibCST on this repository vs the C0a stdlib numbers; the official Luau zip (checksum, `luau-ast`, `luau-analyze`) on one GitHub Luau file; tree-sitter-toml spans on the 10 TOML files | downloads approved 2026-09-24 |
| 2 | **L1** account registry | L-01, L-10 (families by account) | — | the registry regenerates today's lane roster byte-identically (no behaviour change); validator + ownership report green | none (config compile only) |
| 3 | **L2** limiter correctness | L-04, L-05, L-08, L-09, L-16, L-17 | L1 | unit tests: real-token admission, rolling TPD, OTPM, clamp on restore, transient refusal; ledger rows carry stage / account / model | fence + bounce |
| 4 | **L3** ownership + wiring | L-02, L-07, L-11, L-12, L-13, L-14, L-15, L-18 | L2 | registry: all 18 Groq pairs owned (6 profile + 6 pMAP slots), Cloudflare account ids discovered (read-only API) or supplied by the owner, dead lanes parked, the unused flag removed | `.env` edits (account ids) = owner-visible; fence + bounce |
| 5 | **L4** canary + live proof | L-03 | L3 | ≤ 20 Groq + ≤ 6 Cloudflare calls (OTPM per org, TPM reservation, each pair reachable); then one profile ticket + one small pMAP document land only on their owning pairs | the owner's "fix all of this" (2026-09-24) |
| 6 | **D1** document defects | D-01, D-02 (marker) | — | GRAPH hop-1 facts ranked by seed rank × predicate tier × evidence in the selected set (replay on saved GRAPH plans shows the change); MCP rows say `truncated` + full length | flag; fence + bounce |
| 6b | **K1** knowledge roles + retrieval scope | K-01, K-02 | — | a reference-only request never sees implementation material in any lane, the profile scout or the compiler context; Trail always sends `roles: [reference]`; scope in cache identity (CODE-RAG-IMPLEMENTATION-V1 §4 K1) | Qdrant backfill in a live window |
| 7 | **C1** code front door | C-01, C-02, C-05, C-06, C-07, C-08, C-26 (decision) | C0b | code extensions accepted behind a flag; code never reaches tier_v3; no front matter, no LLM extraction for code; empty files allowed; path → hash ledger with supersession; documents byte-identical with the flag off | fence + bounce |
| 8 | **C2** structure store | C-09, C-22 (code sparse field), C-24 (storage) | C1 | `code_symbols` / `code_edges` / `code_symbol_parent_links` (+ `code_doc_mentions` table shape) on a throwaway Postgres first; the re-extraction reproducibility test | migration in a live window |
| 9 | **C3** Python card | C-03, C-04, C-10, C-23 | C2 | this repository parsed with LibCST; children cover every byte; `region_role=code` set by the parser (exempt from noise drops); token budgets; CALLS / IMPORTS spot-checked | fence + bounce |
| 10 | **L5** shared budget | L-06 | L4 | two processes on one pair never exceed its TPM / TPD (a deterministic two-process test); pMAP may borrow idle gpt-oss-120b budget | migration + bounce |
| 11 | **C6 + C7** code meaning | C-11, C-12, C-13, C-14, C-10 | C3, L4 (capacity) | code prompt variants fed parser units + resolved links + exact code; identifier-safe compilers (labels and the MAP line unchanged); upward file profile; dependency-aware refresh; spec §12 acceptance on this repository | live enrichment of this repository = the owner's word (capacity) |
| 12 | **C9 + C10** doors + hydration + structure lane (walking skeleton) | C-15, C-16, C-17, C-18, C-19, C-20, C-21 | C6 + C7 | the first real questions on this repository answered with cited exact code, through chat (FAST / HYBRID / GRAPH), HTTP `/retrieve` and MCP (a revision-bound unit reader with continuation); in-process replay first | live turns = the owner's word |
| 13 | **C8** Neo4j code projection | C-25, C-24 (projection) | C2, C9 | desired = actual counts; no duplicate Document / CodeDocument per file; delete removes Code* nodes | fence + bounce |
| 14 | **G1 + C11** joint graph walk + roles | C-24 (walk), the owner's joint-walk goal | C8, C10 | MENTION links built; a mixed question returns code (observed), a passage (guidance) and a labelled proposal; one semantic hop max, paths visible in receipts | live turns = the owner's word |
| 15 | **C4** Luau card | Luau rows of the spec | C3 pattern, C0b | the GitHub Luau file: typed syntax parsed by `luau-ast`, requires resolved or `unresolved`, a question answered; Rojo + luau-lsp when a real project exists | — |
| 16 | **C5a** YAML + TOML cards | YAML / TOML rows | C3 pattern | PyYAML offsets + aliases (C0a proved), tree-sitter-toml spans; the repository's configs answerable ("where is the retry limit set, and what reads it?") | — |
| 17 | **C12** readiness | C-27 | C9 | readiness reports exact lookup vs description coverage separately | — |
| 18 | **C13** validators + diagnostics | spec layer 3b | C3, C4, C5a | Ruff / luau-analyze / selene findings stored with rule, severity, span, tool version | — |
| 19 | **Gate qualification** | "Not confirmed" list of the register | C9–G1 | the σ floors measured on code descriptions; a value changes only on an observed failure | live turns = the owner's word |
| 20 | **C5b** Power Fx | Power Fx rows | .NET approval + an owner app | formulas bound; navigation / data links | owner inputs |
| 21 | **C14** qualification | all | everything | every card's test questions on real code, incl. a code + book question | live turns = the owner's word |

Also owned by the gap register (bookkeeping 11.463): D-03..D-09, O-01..O-03, T-01, T-02 wait for small slices or the
owner's decisions; L-19 is proven by L4.

Why this order: the backend first (L1–L4), because code enrichment (C6 / C7) is the first heavy LLM user and today's
limiter cannot hold Groq's limits; the document defects early (D1), because they affect the live book corpora now; then
the code walking skeleton (C1 → C9 / C10) on this repository, then the graph work that needs structure edges (C8 →
G1), then the other languages, then hardening.

## 4. Slice notes (what each must not forget)

- **C0b:** a throwaway venv under the session scratchpad, never the fleet `.venv`; one Luau file from a permissively
  licensed public Roblox repository, recorded with its URL, commit, licence and checksum under
  `docs/wiki/experiments/code-knowledge-c0b-2026-09-24/fixtures/`.
- **L1:** keep the old lane names as aliases so the attempt ledger, `llm_controller_state` keys and receipts stay
  continuous; the generated roster must equal today's before any assignment changes.
- **L3:** Cloudflare account ids: try `GET /client/v4/accounts` with each token (read-only; print only found / not
  permitted); if a token cannot list its account, the owner pastes the id. `.env` lines are appended, never rewritten.
- **L4:** record the per-org OTPM finding in the registry (`otpm` per account), the TPM reservation behaviour, and the
  first live profile / pMAP receipts.
- **D1:** the fact order must stay deterministic (ties broken by `fact_id`).
- **C1:** a reference book shared by two project corpora is a documented limitation in V1 (C-26); the decision (copy
  per corpus vs cross-corpus reference) is the owner's.
- **C9:** FAST gets the exact door and the description door inside the lanes it runs; HTTP `/retrieve` FAST and MCP
  get the same resolver + hydrator; the hydrator replaces `_resolve_chunk` for code and lifts the 2,000-character cap
  for whole units (token budget per task instead).
- **C10:** route seats for structure-lane paths must not depend on `POLYMATH_CHAT_CONTEXTUAL_JUDGE=wildcard`;
  per-file fairness replaces one-seat-per-document for code.
- **G1:** MENTION matching uses exact identifiers (qualified names, split identifiers only with the exact form present),
  config key paths and repo-relative paths; ambiguous names stay `ambiguous`.

## 5. External review (Astra, 2026-09-24) — reconciled

- **Agreed and adopted:** the backbone is reusable and first-class code RAG is not built; select code by meaning, then
  load exact source + dependencies by rule; reuse the profile / pMAP workers with new INPUT builders; no global cosine
  floor; FAST / HYBRID / GRAPH / HTTP `/retrieve` / MCP each need explicit integration; MCP needs a source-complete,
  revision-bound unit reader; keep code structure, book evidence and semantic connections as distinct authorities;
  dependency-aware refresh of descriptions; readiness must separate lookup from discovery coverage.
- **Added by this audit:** tier_v3 loses real lines of code / config; region roles drop code as `noise_ocr`; the
  compilers mangle identifiers; route seats depend on the WILDCARD-only judge; book-shaped fairness; the provider
  backend and limiter gaps (Track L); GRAPH's hash-ordered facts.
- **Nuance:** C0a's 93.8 % measures name-resolution coverage on this repository, not call-graph accuracy (Astra is
  right to flag it); the σ floors are neither endorsed nor changed until measured on code descriptions.
