---
title: "Code RAG implementation file: modules, data contracts, integration points, tests and acceptance per slice"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "IMPLEMENTATION CONTRACT (owner 2026-09-24: 'emphasis on implementation file for code rag. im expanding on current incomplete implementations'). Build from this file; the owner expands it. Anchors verified against production de611e2 (runtime code identical to 69c2704)."
owner: "@king"
scope: "HOW to build code RAG inside the existing pipeline. WHAT each language means: CODE-LANGUAGE-REPRESENTATIONS-V1.md. ORDER across tracks: LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md. Confirmed gaps each slice closes: GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md. Table / payload names follow the packet schema (docs/code-knowledge-v1/03_CODE_KNOWLEDGE_V1_CONTROL_MAP_SCHEMA.md) except where the feasibility review's drift table overrides it."
---

# Code RAG implementation file (V1)

**The one-line architecture:** a question finds a code unit through its DESCRIPTION (profile / pMAP, natural language)
or its IDENTITY (symbol, path, stack trace); the unit's exact source and its verified neighbourhood are then loaded by
stored identity, by rule; book passages join through mentions or one concrete semantic hop; the answer keeps what the
code does, what the book supports and the proposed change apart.

**Slice status:** C0a ✔ (11.458) · C0b ✔ (11.461) · everything below is OPEN. Each slice below lists: goal · gaps closed
· flag · create · modify (file:line) · data · tests · acceptance · rollback. Every slice follows START-HERE §6 (own
worktree, flag default off, impacted tests only with `-k "not test_live_"`, work-log, register row, TREE entries, four
guards, merge + bounce).

## 1. Design rules (binding on every slice)

| # | Rule | Source |
|---|---|---|
| R1 | **pMAP stays the locator, the profile orients, exact source proves.** A code unit competes through its description; once it earns inclusion, its source is loaded by stored identity and is **never re-judged on literal similarity to the question**. Required neighbours load by rule within a budget. | owner 2026-09-24 ("deterministic hydration"); reviews |
| R2 | **Structure comes from parsers and resolvers only.** Unresolved stays `unresolved`; ambiguous stays `ambiguous`; nothing is promoted by an LLM. | spec §1 |
| R3 | **Enrichment keeps the existing outputs** (profile labels ONE / SUMMARY / TOPIC / TERM / Q / SEARCH / THEORY / CONCEPT / SEEALSO + END; the `MAP\|alias\|signature\|h1;h2;h3` line). Mapping: responsibilities → SUMMARY; identifiers → TERM; grounded mechanisms → CONCEPT ("rejects another attack until the cooldown expires; limits how often the action can repeat"); exploration directions and adjacent unimplemented ideas → SEEALSO, labelled hypotheses. Never outcomes the code cannot establish ("creates balanced combat"). | review 2 |
| R4 | **Issues are three different things:** tool diagnostics (facts, layer 3b), demonstrated defects (a test or a trace shows it), suspected problems (hypotheses, labelled). Only the first two are ever stated as facts. | review 2 |
| R5 | **Execution rules are chosen per UNIT, not per language:** Python / Luau functions, state, events, async and framework; Power Fx value formulas vs behavior formulas (`OnSelect`); YAML meaning comes from its consumer; DAX measures vs calculated columns and filter / row context; Power Query M lazy evaluation. | review 2 |
| R6 | **Bridges must be concrete:** a semantic bridge resolves to real source on both ends and survives inspection by the path-aware judge; "both involve feedback" is rejected. At most one semantic hop per walk. | review 2; roadmap §2 |
| R7 | **Freshness follows context, not only the unit's bytes:** a description is refreshed when its unit OR its supporting context (resolved callees' signatures, config values read, types) changes; parent and file profiles roll up. | reviews 1 + 2; amended 11.471 (external audit A5): hash the exact context SUPPLIED — callee bodies or behaviour records used, parser / binder / prompt versions — not only signatures |
| R8 | **Knowledge role is inherited and enforced before planning:** every derived representation of code (children, parents, pMAP, profile, atoms, graph provenance, corpus summaries) carries `knowledge_role=implementation`; Trail ideation requests `reference` only; the scope filters the profile scout, the compiler context and every lane; the scope is part of cache identity; an LLM-generated plan cannot widen it. | owner-shared proposal 2026-09-24 |
| R9 | **One searchable corpus, several collections; no new public mode, no new service, no new scheduler.** | owner defaults |
| R10 | **Documents stay byte-identical with every code flag off** (a test proves it per slice). No fleet-wide `worker_contracts()` key (it would mark every live corpus stale); the code contract travels per document. | feasibility review drift table |
| R11 | **Code never goes through the document heading skeleton or its curation** (`build_parent_skeletons`). The language parser defines code units; each unit's description is written from its complete source (C-12). | owner 2026-09-24: "pmap does a determinsitic parse and curations of docuemnts headings and subheading but for codes i dont want thats" (11.471) |
| R12 | **Code units come from the SAME deterministic parser pass that builds the code graph.** One symbol table per file (`code_symbols`) is both the graph's nodes and the enrichment's unit list: every function, method, class and module-init block (Python); function, method and event-handler bodies (Luau); screen, component, control and property formula (Power Fx); service / job / resource sections (YAML); tables and array-table entries (TOML). No second unit detector; coverage is checked against that table. **Names locate units; bodies establish behaviour** (never describe from a name). | owner 2026-09-24: "ensure that the codes identifies all proper functions in respect to the code type. i thinks it should use the same logic used to create th determinisitc graph" + note 8 (11.473) |

**Amendments admitted 11.471 (external end-to-end audit, reconciled in
`docs/wiki/reports/2026-09-24/CODE-RAG-E2E-AUDIT-RECONCILIATION.md`; they bind the slices below where they differ):**
- C1: branch code BEFORE `normalize_document_bytes` (gap C-28), keep the original bytes, and build the code identity from
  project + repository-relative path + raw hash (snapshot kept separately).
- C2 / C3: the symbol tree nests with exact spans; physical children partition the source; a unit is read by its own
  span.
- C6 / C7: durable per-unit description records (input hash, checkpoint on refusal). The file rollup waits for them;
  pMAP runs from the same full source independently (not "before the profile"); there is no sampling fallback.
- K1: a rollback never widens a reference-only request (fail closed).
- §3: no database / filesystem / subprocess I/O in `shared/`.
- C9 / C10: every route joins one nomination → hydration contract; unit descriptions also reach the base section
  routing, so FAST finds them.
- The audit's V-* verifiers are the slices' exit proofs.

**Code pMAP contract (owner note 8, 2026-09-24, register 11.473; `docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTE_8_CODE_PMAP.md`):**
- A code pMAP entry is a searchable, plain-English map entry for one R12 unit, generated from the unit's COMPLETE body, with
  an exact link (symbol id, file, span, snapshot) back to the source. It replaces heading-based discovery (R11).
- Process:
  1. Parse the entire file: every unit, its enclosing context and its location, from the R12 symbol table (coverage
     without headings).
  2. Give the model complete bodies: the whole file when input + reserved output fit the lane's usable context
     (L-track limits); otherwise every section in separate requests carrying the resolved definitions and dependencies.
     An oversized unit is split on syntax boundaries with its enclosing conditions kept.
  3. Build descriptions upward: unit descriptions and pMAP entries → screen / module / file profiles; every level keeps
     its source links.
- A reference outside the file goes with the request when resolved; otherwise it is named as missing.
- A 400 KB Power Apps file is processed across its whole screen → control → formula hierarchy (with app variables, data
  sources and referenced controls where available), never as samples.
- DAX (measures, calculated columns / tables) and Power Query M (queries, functions, `let` bindings) unit shapes are
  recorded with the note; they stay candidate languages (§6 item 4).

## 2. Data contracts

### 2.1 Migration `0067_code_source_identity.sql` (slice K1 + C1)

```sql
ALTER TABLE documents
  ADD COLUMN source_family   TEXT NOT NULL DEFAULT 'document'     -- document | code | config
      CHECK (source_family IN ('document','code','config')),
  ADD COLUMN knowledge_role  TEXT NOT NULL DEFAULT 'reference'    -- reference | implementation
      CHECK (knowledge_role IN ('reference','implementation')),
  ADD COLUMN source_language TEXT,                                -- python | luau | yaml | toml | powerfx | …
  ADD COLUMN repo_path       TEXT,                                -- repo-relative path (code only)
  ADD COLUMN source_revision TEXT,                                -- git commit, else sha256 of the bytes
  ADD COLUMN structure_contract TEXT;                             -- 'code-structure-v1' (code only)
ALTER TABLE chunks
  ADD COLUMN symbol_id   TEXT,          -- the unit's primary symbol (code only)
  ADD COLUMN line_start  INT,           -- 1-based, inclusive (code only)
  ADD COLUMN line_end    INT,
  ADD COLUMN unit_kind   TEXT,          -- class | function | method | module_block | config_section | …
  ADD COLUMN partial_index INT;         -- NULL = whole unit; 0.. = fragment of an oversized unit
CREATE INDEX chunks_symbol_idx ON chunks (symbol_id) WHERE symbol_id IS NOT NULL;
```

The defaults make every existing document `document` / `reference` with no data rewrite. The importer sets the fields;
an LLM never does.

### 2.2 Migration `0068_code_structure.sql` (slice C2; names from the packet schema §3–§6)

```sql
CREATE TABLE document_structure_manifests (
  manifest_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES documents(doc_id), corpus_id TEXT NOT NULL,
  source_family TEXT NOT NULL, source_language TEXT NOT NULL, structure_contract TEXT NOT NULL,
  parser_name TEXT NOT NULL, parser_version TEXT NOT NULL, source_hash TEXT NOT NULL, manifest_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('complete','degraded','failed')),
  symbol_count INT NOT NULL, edge_count INT NOT NULL, diagnostics JSONB NOT NULL DEFAULT '[]',
  active BOOLEAN NOT NULL DEFAULT true, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
CREATE UNIQUE INDEX one_active_manifest ON document_structure_manifests (doc_id, structure_contract) WHERE active;

CREATE TABLE code_symbols (
  symbol_id TEXT PRIMARY KEY,           -- per revision: sha256(doc_id|qualified_name|symbol_kind|char_start)
  symbol_key TEXT NOT NULL,             -- stable across revisions: sha256(corpus_id|repo_path|qualified_name|symbol_kind)
  manifest_id TEXT NOT NULL REFERENCES document_structure_manifests(manifest_id),
  doc_id TEXT NOT NULL, corpus_id TEXT NOT NULL, symbol_kind TEXT NOT NULL, name TEXT NOT NULL,
  qualified_name TEXT NOT NULL, char_start INT NOT NULL, char_end INT NOT NULL, line_start INT NOT NULL,
  line_end INT NOT NULL, parent_symbol_id TEXT, heading_path JSONB, signature TEXT, attributes JSONB,
  source_hash TEXT NOT NULL, structure_contract TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX code_symbols_lookup ON code_symbols (corpus_id, qualified_name) WHERE active;
CREATE INDEX code_symbols_name ON code_symbols (corpus_id, lower(name)) WHERE active;
CREATE INDEX code_symbols_key ON code_symbols (symbol_key) WHERE active;

CREATE TABLE code_symbol_parent_links (
  symbol_id TEXT NOT NULL, doc_id TEXT NOT NULL, parent_id TEXT NOT NULL,   -- parent_id = chunks.chunk_id (tier parent)
  relation TEXT NOT NULL CHECK (relation IN ('owns','contained_by','primary_parent')),
  structure_contract TEXT NOT NULL, PRIMARY KEY (symbol_id, parent_id, relation, structure_contract));

CREATE TABLE code_edges (
  edge_id TEXT PRIMARY KEY, manifest_id TEXT NOT NULL, doc_id TEXT NOT NULL, corpus_id TEXT NOT NULL,
  source_symbol_id TEXT NOT NULL, relation TEXT NOT NULL,       -- CONTAINS | CALLS | IMPORTS | REQUIRES | INHERITS | …
  target_symbol_id TEXT, target_external_name TEXT,
  resolution TEXT NOT NULL CHECK (resolution IN ('resolved','unresolved','ambiguous','external')),
  confidence NUMERIC NOT NULL, provenance TEXT NOT NULL,        -- parser | static_analysis | powerfx_binding | …
  attributes JSONB NOT NULL,          -- source_revision, span, rule, tool, tool_version (reproducibility, spec §1)
  structure_contract TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX code_edges_out ON code_edges (source_symbol_id) WHERE active;
CREATE INDEX code_edges_in  ON code_edges (target_symbol_id) WHERE active;

CREATE TABLE code_import_ledger (
  corpus_id TEXT NOT NULL, repo_path TEXT NOT NULL, content_hash TEXT NOT NULL, doc_id TEXT,
  source_revision TEXT, status TEXT NOT NULL CHECK (status IN ('active','superseded','skipped','empty')),
  skip_reason TEXT, imported_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (corpus_id, repo_path, content_hash));
```

Later migrations: `0069_code_doc_mentions.sql` (G1: `mention_id, corpus_id, symbol_id, chunk_id, match_kind,
confidence, source_revision, active`), `0070_code_diagnostics.sql` (C13: `rule_id, severity, message, span, tool,
tool_version, symbol_id, doc_id`), `0071_code_enrichment_inputs.sql` (C6 / C7 freshness: `symbol_key, input_hash,
context_hashes JSONB, prompt_version, description_ids`).

Apply order: a throwaway Postgres first (`docker run postgres`), then the live DB in a window (the owner's rule).

### 2.3 Qdrant payloads (packet §8 + scope)

Every point (children, routing cards, profiles, atoms, pMAP) of EVERY document gains `source_family` and
`knowledge_role` (existing points: a one-off idempotent `set_payload` backfill, K1). Code points also carry
`source_language`, `symbol_id`, `symbol_key`, `symbol_kind`, `qualified_name`, `repo_path`, `line_start`, `line_end`,
`source_revision`, `structure_contract`. Payload indexes (keyword) on `knowledge_role`, `source_family`, `symbol_id`.
No separate structural vector collection (packet §8).

### 2.4 Neo4j (C8, G1)

- A code file's existing `:Document` node gains the label `:CodeDocument` (one node, not two: closes C-25's duplicate).
- `(:CodeSymbol {symbol_id, symbol_key, kind, qualified_name, doc_id, corpus_id, knowledge_role})`,
  `(:CodeConfigPath {path, doc_id})`.
- Relationships (resolved edges only; unresolved targets stay properties): `CODE_CONTAINS`, `CODE_CALLS`,
  `CODE_IMPORTS`, `CODE_REQUIRES`, `CODE_INHERITS`, `CODE_READS`, `CODE_WRITES`, `CODE_REFERENCES`, and (G1)
  `(:CodeSymbol)-[:MENTIONED_IN {match_kind, confidence}]->(:Chunk)`.
- Projection name `code_structure`; desired count = actual count, with receipts (packet §7).

### 2.5 The language adapter contract

`shared/polymath_shared/code/contracts.py`:

```python
@dataclass(frozen=True)
class Unit:            # one parent (class / function / module block / config section / screen …)
    unit_kind: str; qualified_name: str; char_start: int; char_end: int; line_start: int; line_end: int
    children: tuple["Block", ...]; symbol: "Symbol"; execution_rules: tuple[str, ...]   # R5, per unit

@dataclass(frozen=True)
class Block:           # one child: an exact, non-overlapping substring
    char_start: int; char_end: int; symbol_id: str | None; partial_index: int | None

@dataclass(frozen=True)
class ParsedFile:
    doc_meta: dict; units: tuple[Unit, ...]; symbols: tuple["Symbol", ...]; raw_edges: tuple["Edge", ...]
    diagnostics: tuple["Diagnostic", ...]; tool: str; tool_version: str; status: str   # complete | degraded | failed

class LanguageAdapter(Protocol):
    language: str
    extensions: tuple[str, ...]
    def detect(self, path: str, text: str) -> "DetectResult": ...                  # never an LLM
    def parse(self, path: str, text: str, revision: str) -> ParsedFile: ...
    def resolve(self, files: Mapping[str, ParsedFile], ctx: "ResolveContext") -> list["Edge"]: ...
```

Language specifics (extensions, dialect detectors, unit kinds, prompt addendum, per-unit execution rules) live as data
in `config/code_languages.yaml`, validated at load. The owner's JSON language draft becomes that file once admitted;
the adapters are code (extraction and resolution cannot be configured into existence).

## 3. Module layout

```
shared/polymath_shared/code/
  __init__.py
  contracts.py        Unit / Block / Symbol / Edge / Diagnostic / ParsedFile; vocabularies (spec §1); CODE_STRUCTURE_CONTRACT
  identity.py         symbol_id(), symbol_key(), edge_id(), manifest_id()
  detect.py           extension + strict-parse promotion + skip receipts (vendored, lock, generated, minified, empty)
  scope.py            RetrievalScope; qdrant_filter(scope, corpus_ids); sql_predicate(scope)          (K1)
  provider.py         ast_code_v1: ParsedFile → chunk rows (parents = units, children = blocks), byte coverage
  store.py            persist manifest / symbols / edges / links in the intake transaction
  languages/python.py LibCST adapter (C3)      languages/yaml.py  PyYAML adapter (C5a)
  languages/toml.py   tree-sitter-toml + tomllib (C5a)          languages/luau.py  luau-ast subprocess (C4)
  enrich_context.py   the code profile / pMAP request builder (spec §11 layout) + token sizing (C6 / C7)
  freshness.py        input hashes over unit + context; dependent invalidation (C6 / C7)
  doors.py            the exact door (symbols, paths, stack frames) + the description door adapter (C9)
  hydrate.py          task rules → exact unit source + bounded neighbourhood within a token budget (C9)
  structure_lane.py   walks code_edges from seeds with readable paths (C10)
  mentions.py         MENTION matcher: symbol / config key / path names inside document chunks (G1)
workers/workers/code_import.py          the repository importer (C1)
orchestrator/orchestrator/api/code_units.py   GET unit by symbol / revision with continuation; symbol lookup (C9)
scripts/code_import.py                  CLI: --repo PATH --corpus ID [--role implementation] [--dry-run]
scripts/fetch_luau_toolchain.sh         checksum-pinned luau-macos.zip 0.739 (C4)
scripts/backfill_knowledge_role.py      idempotent Qdrant set_payload backfill with --dry-run (K1)
```

## 4. Slices

### K1 — knowledge roles and retrieval scope (before C1: the importer must set roles from day one)

- **Goal:** R8. Trail ideation can never see implementation material; coding workflows can.
- **Gaps:** new rows K-01 (Trail's evidence request carries no source-use scope: `evidence_boundary.request_body`,
  `shared/polymath_shared/adapter/evidence_boundary.py:166`, returns only `message, corpus_id, mode, corpus_explorer`;
  `adapter_step_worker._retrieve_legacy`, `workers/workers/adapter_step_worker.py:172`, sends none either), K-02 (no
  `knowledge_role` anywhere; `source_family` exists only as an accepted front-matter key, `frontmatter.py:18`).
- **Flag:** `POLYMATH_KNOWLEDGE_SCOPE=1` (enforcement); the columns and payloads land unconditionally with defaults.
- **Create:** `code/scope.py` (`RetrievalScope(roles=frozenset({"reference","implementation"}))`,
  `qdrant_filter(scope, corpus_ids) -> Filter`, `sql_predicate(scope) -> (sql, params)`);
  `scripts/backfill_knowledge_role.py`.
- **Modify** (each existing corpus filter takes an optional scope; default = both roles = today's behaviour):
  `orchestrator/api/fast.py:214` · `orchestrator/api/hybrid.py:70` · `orchestrator/api/retrieve.py:488` ·
  `orchestrator/api/ask.py:117` · `document_profile/projection.py:49` (`profile_nominate`, used by the scout at
  `ui.py:1758` and the dual-read lanes at `chat_retrieval.py:334, 377`) · `document_profile/profile_atom_projection.py:172,
  190` · `document_profile/parent_map_projection.py:46-55` · `gnn_route.py:82` · the routing collection search inside
  `candidate_engine.py` lanes A / B / C · the compiler's corpus context (profile scout, `document_profile/profile_scout.py`).
  Request contracts `/chat`, `/chat/evidence`, `/retrieve`: an optional `scope: {roles: [...]}`; receipts record it;
  cache keys include it; `chat_plan.validate_plan` never reads or widens it. Trail: `request_body` and `_retrieve_legacy`
  always send `roles: ["reference"]`.
- **Data:** migration 0067 (§2.1); Qdrant backfill (live write: the owner's window).
- **Tests** (`tests/determinism/test_knowledge_scope.py`): a fake Qdrant client records every filter → a
  reference-only request never issues a search without `knowledge_role ∈ {reference}` (profile scout, compiler
  context, lanes A–I, pMAP, atoms, graph attach); Trail bodies carry the scope; two scopes → two cache keys; a plan
  that asks for implementation under a reference scope is ignored.
- **Acceptance** (the proposal's): a highly relevant code profile stays invisible through Trail ideation while the
  same source is retrievable through the coding workflow (in-process replay on a mixed fixture corpus).
- **Rollback:** flag off (filters default to both roles); columns have defaults.

### C1 — the code front door

- **Goal:** code enters the pipeline as code, never through tier_v3.
- **Gaps:** C-01, C-02, C-05, C-06, C-07, C-08, C-26 (documented decision).
- **Flag:** `POLYMATH_CODE_INGEST=1`.
- **Create:** `code/detect.py`, `code/identity.py`, `workers/workers/code_import.py`, `scripts/code_import.py`.
- **Modify:**
  - upload gates: `orchestrator/api/ui.py:457` and `orchestrator/mcp_server.py:60` (`UPLOAD_EXTENSIONS`), `:192`, `:217`
    accept `.py .pyi .luau .lua .yaml .yml .toml` when the flag is on;
  - `shared/polymath_shared/materializer.py:38, 143`: a `code_passthrough` path: UTF-8 decode only (no NFC, no CRLF
    rewrite: spans must map to the original bytes); empty code files go to the ledger as `empty`, never to
    `EmptyExtractionError` (`:171`);
  - `workers/workers/intake_worker.py` `process_event` (`:151`): after materialize (`:186`), `detect()` decides; code →
    `code.provider` (C3; until then a flagged stub refuses with a receipt instead of falling into tier_v3) instead of
    the chunker switch at `:194-219`; skip `_parse_frontmatter` (`:328`), `route_document` (`:193`) and the
    near-duplicate guard (`:73-148`, the path ledger replaces it); skip `classify_region` (`:346-365`, the parser sets
    `region_role`); write the §2.1 columns;
  - `workers/workers/extract_worker.py` `process_event` (`:66`): a code / config document writes an empty manifest
    and the receipt `skipped_source_family`, so the DAG advances without LLM facts (C-05).
- **Importer:** `git ls-files` (or a walk honouring `.gitignore`); per file: `detect()` → skip with a receipt
  (vendored, lock, generated, minified) or compare `(repo_path, content_hash)` with `code_import_ledger` → new / changed
  → intake event with `repo_path`, `source_revision`, `knowledge_role` (default `implementation`); a changed file marks
  the previous row `superseded` and its symbols inactive; retrieval hides superseded code documents (payload
  `active=false`); physical purge stays an owner-run command.
- **C-26 decision (documented):** a reference book shared by two project corpora is copied into each (the
  content-addressed `doc_id` stays single-corpus in V1).
- **Tests:** `test_code_detect.py` (per card, `.txt` promotion, skips); `test_code_import_ledger.py` (a fixture repo:
  add / change / delete / rename; skipped files receipted); `test_intake_code_routing.py` (flag off: a markdown fixture's
  chunk rows are byte-identical to before; flag on: a `.py` never reaches `tier_chunk_layout`, no front matter, no
  near-duplicate guard, columns set); `test_extract_skips_code.py`.
- **Acceptance:** this repository imports with every file receipted (ingested / skipped / empty); documents unchanged.
- **Rollback:** flag off.

### C2 — the structure store

- **Goal:** symbols, edges and symbol ↔ parent links are durable, reproducible and queryable.
- **Gaps:** C-09, C-22 (code sparse text), C-24 (storage).
- **Create:** migration 0068 (§2.2); `code/store.py` (`persist_parsed(conn, doc, parsed)` inside the intake
  transaction; deactivates the previous manifest for the doc).
- **Sparse without touching the frozen tokenizer:** for code chunks, the text sent to BM25 is the exact text plus a
  line of split identifiers (`getUserName` → `get user name`; `snake_case` → `snake case`; qualified names kept whole).
  `sparse_bm25.py:24-33` (`sparse-bm25-v1`) is unchanged.
- **Tests:** `test_code_store.py` (manifest invariants; one active manifest per doc); `test_code_reproducibility.py`
  (parse the same snapshot twice with the pinned tools → identical edge sets; spec §1).
- **Acceptance:** throwaway Postgres migration + round trip; then the live window.

### C3 — the Python card and the `ast_code_v1` provider

- **Goal:** Python files become exact units with symbols and resolved edges.
- **Gaps:** C-03, C-04, C-10, C-23.
- **Create:** `code/languages/python.py` (LibCST 1.9.0: `MetadataWrapper` with PositionProvider,
  QualifiedNameProvider, ScopeProvider); `code/provider.py`.
- **Python adapter:** units = classes, top-level functions, one module block (imports, constants, `__main__`);
  children = methods / functions; symbols per spec §2 (`module, class, function, method, async_function, property,
  constant, type_alias, route, test, entrypoint`); edges `CONTAINS, DEFINES, IMPORTS, CALLS, INHERITS, DECORATED_BY,
  RAISES, REFERENCES_CONFIG, TESTS`. CALLS: QualifiedNameProvider names + the enclosing-class rule for `self.m()` /
  `cls.m()`; anything else `unresolved` with the callee text (C0b: 4,292 product-code callees resolve; C0a: ≤ 293 more
  would need type inference).
- **Provider:** parents = units; children = blocks within a TOKEN budget (tokenizer of the embedder contract);
  a unit's span is extended to its first decorator (C0b: LibCST starts at `def`); every byte of the file belongs to
  exactly one child (comments, docstrings, decorators and blank-line gaps attach to the following unit); an oversized
  unit splits on statement boundaries with `partial_index`; `heading_path` = package › `module.py` › Class › method;
  `region_role='code'` (config files: `'config'`); `chunk_contract_version='code-structure-v1'`, `provider='ast_code_v1'`.
- **Modify:** `candidate_engine.py:1301-1311` (noise-region drop) and `:1541-1559` (`structural_noise_reason`) skip rows
  whose `region_role` is `code` or `config`. Fleet dependency: `libcst==1.9.0` in the shared package metadata.
- **Tests:** `test_code_python_card.py` (fixtures: decorators, nested classes, async, a `dict | None` signature,
  `__init__`; spans exact; 100 % byte coverage; CALLS resolved / unresolved per rule); `test_code_provider_coverage.py`
  (every byte in exactly one child; PARTIAL splits); an opt-in repo check script (944 files, 0 errors, C0b).
- **Acceptance:** this repository parsed and chunked; `CALLS` / `IMPORTS` spot-checked against hand-picked pairs.

### C6 + C7 — code meaning (profile + pMAP)

- **Goal:** natural-language descriptions that rank well and never overclaim (R3, R4, R5).
- **Gaps:** C-10, C-11, C-12, C-13, C-14.
- **Flag:** `POLYMATH_CODE_ENRICH=1`.
- **Create:** `code/enrich_context.py` (`build_unit_request(unit, graph_ctx, lane_limits) -> (system_rules,
  user_text, coverage)` in the spec §11 layout: FILE + revision; LANGUAGE / FRAMEWORK / RUNTIME; STRUCTURE (children
  signatures); RESOLVED RELATIONSHIPS (1 hop from `code_edges` with their resolution); UNKNOWN OR OMITTED CONTEXT; SOURCE
  (exact code, grouped by unit, with locations); PARTIAL marks); `code/freshness.py`; migration 0071.
- **Modify:**
  - `document_profile/prompt.py` and `map_prompt.py`: a `CODE_RULES` block + per-language addenda + per-unit execution
    rules appended to SYSTEM; labels and the MAP line unchanged;
  - `workers/workers/doc_parent_map_stage_worker.py` `_load_inputs` (`:95-109`) / `process_event` (`:208-273`): a code
    document's batches come from `enrich_context`, not `build_parent_skeletons` (`parent_skeleton.py:401`);
  - `workers/workers/doc_profile_worker.py` `process_event` (`:243-367`): a code document's profile is built UPWARD
    from its unit descriptions (unit → group → file; spec §12.5), never from `build_context`'s 500-token sample
    (`context.py:199-262`); for code, pMAP runs before the profile;
  - compilers: `map_compiler.py:78, 236-251` and `compiler.py:267-271` get an identifier-preserving mode for code
    documents (keep `_`, `*`, `.`, `::`; never split inside backticks; the code rules ask for identifiers in backticks).
- **Sizing:** by tokens (spec §12.4): budget = the lane's limits (from the L1 registry) − system − reserved output −
  supplied context; oversized units split on syntax boundaries, PARTIAL.
- **Freshness (R7):** `input_hash = sha256(unit source ‖ sorted signatures of resolved callees ‖ config values read ‖
  prompt version ‖ addendum version)`; unchanged hash → reuse; a callee signature change marks its callers' unit
  descriptions stale (reverse `CALLS` / `IMPORTS`, depth 1) and rolls up to parent and file profiles.
- **Tests:** `test_code_enrich_context.py` (the request contains exact code, signatures, relations, the missing-context
  list, within budget); `test_code_compilers_identifiers.py` (`__init__`, `_pool_complete`, `*args`, `dict | None`
  survive); `test_code_enrichment_freshness.py`; `test_code_prompt_rules.py` (R3 / R4 wording present; labels intact).
- **Acceptance:** spec §12 on this repository: every unit described, batched or skipped with a receipt; every request
  within its lane's limits (measured on the canary the owner authorizes).

### C9 + C10 — the two doors, the hydrator and the structure lane (the walking skeleton)

- **Goal:** R1 end to end, through chat FAST / HYBRID / GRAPH, HTTP `/retrieve` and MCP.
- **Gaps:** C-15, C-16, C-17, C-18, C-19, C-20, C-21, D-02.
- **Flag:** `POLYMATH_CODE_RETRIEVAL=1`.
- **Description door:** pMAP points of code units carry `symbol_id` + the unit's parent `chunk_id`. In lane E
  (`candidate_engine.py:929-990`), a nominated parent whose payload says `source_family=code` becomes a `UnitHit(symbol_id,
  via="description", need=<signature>)` instead of a cosine search over its children. The judge scores (question, unit
  DESCRIPTION): the payload `text` of a unit point is its description, while evidence fetches source by id (the existing
  seam: `rerank.py:134` vs `evidence_assembly.py:333`).
- **Exact door:** `doors.exact_lookup(query, corpus_ids, scope)`: identifier-shaped tokens (dotted, snake, camel,
  paths, stack-trace frames `File "x.py", line N, in f`) → `code_symbols` by `qualified_name` / `lower(name)` /
  `repo_path` → `UnitHit(via="exact")`.
- **FAST:** both doors run inside FAST's own lanes (`chat_retrieval.py:755-764`) and in `fast_retrieve`
  (`api/fast.py:527`) when the corpus holds code documents.
- **Hydrator** (`code/hydrate.py`): `hydrate(hits, task, budget) -> list[EvidenceUnit]` loads each unit's full source by
  `symbol_id` (its chunks via `code_symbol_parent_links`, fragments joined in order), then the neighbourhood by task
  (spec §13): LOCATE = the unit · EXPLAIN = + resolved callees' signatures · DEBUG = + callers, guards, config reads ·
  IMPACT = reverse edges to depth 2 · COMPARE = both units · GENERATE = + interfaces / types. Each neighbour carries its
  path ("called by `X`"). Neighbours do NOT pass the literal floor (R1); the task's token budget bounds them.
- **Seats (C10):** a `code_route` seat class for structure-lane paths that does not depend on
  `POLYMATH_CHAT_CONTEXTUAL_JUDGE=wildcard` (today route seats need `route_score`, `candidate_engine.py:1480, 1756`);
  fairness per file for code (the one-seat-per-document round, `:1620-1641`, assumes books).
- **Prompt:** code units bypass `_EVIDENCE_TEXT_CHARS` (`ui.py:1522-1523`, 2,000 characters) and use the task's token
  budget; citations `[S#]` carry `repo_path:line_start-line_end@revision`; `_resolve_chunk`
  (`orchestrator/api/evidence.py:354`) gets a code branch that returns the whole unit.
- **HTTP + MCP:** `/retrieve` (`api/retrieve.py:199-203`) runs the same doors + hydrator; `api/code_units.py` serves
  `GET /code/unit/{symbol_id}?revision=&offset=` with explicit `continuation` and `GET /code/symbol?q=`; MCP tools
  `polymath_code_lookup` and `polymath_code_unit` (full source, revision-bound, continued never truncated);
  `polymath_search` rows gain `truncated` + `full_chars` (`mcp_server.py:302-303, 323-329`).
- **Task detection:** deterministic first (a stack trace → DEBUG; "what calls / who uses" → IMPACT; "where is / which
  file" → LOCATE; "why / how does" → EXPLAIN); a compiler field later.
- **Tests:** `test_code_doors.py`; `test_code_lane_e_units.py` (a code parent → `UnitHit`, no child cosine);
  `test_code_hydrate.py` (task rules; budgets; neighbours bypass the literal floor but stay bounded);
  `test_code_fast_route.py`; `test_code_units_api.py` (continuation); `test_code_mcp_tools.py`.
- **Acceptance — E2E-1 (the reviews' open gap), in-process replay first:** on a corpus holding this repository plus one
  reference document: "where do we retry a failed provider call?" returns the right unit through its description, with
  its necessary context (the limiter / failover callees) loaded by rule and cited by file and lines; a book passage
  joins when one is relevant; a superficial bridge is rejected with a receipt. Then live on the owner's word.

### C8 — the Neo4j code projection

- **Gaps:** C-24 (projection), C-25.
- **Modify:** `workers/workers/project_neo4j_worker.py` `_graph_rows` (`:126-214`) / `_write_graph` (`:285-294`) /
  `_receipts` (`:297-324`): code documents add `:CodeDocument` to their `:Document` node, write `:CodeSymbol` /
  `:CodeConfigPath` and resolved `CODE_*` relationships from Postgres, with `code_structure` receipts; the delete path
  (`ui.py:782-798`) removes `CodeSymbol` nodes by `doc_id`.
- **Tests:** `test_code_neo4j_projection.py` (desired = actual; idempotent re-projection; delete leaves nothing).

### G1 + C11 — the joint graph walk and the roles in the answer

- **Goal:** walk the code graph with the document graph (roadmap §2), under R6.
- **Create:** migration 0069; `code/mentions.py` (index-time exact matching of qualified names, distinctive
  identifiers — length ≥ 6 or containing `_` / `.` / an inner capital — config key paths and repo paths inside document
  chunks of the same corpus; common words excluded; ambiguous names stay `ambiguous`); `code/structure_lane.py`.
- **Walk:** from code seeds: STRUCTURE hops by task rule → MENTION hops to passages → at most one SEMANTIC hop from
  the unit's descriptions (CONCEPT / SEEALSO / pMAP hooks) to document atoms / entity cards. From document seeds: the
  existing FACT hop (`chat_retrieval.py:446, 825-877`) → MENTION hops to code units → at most one SEMANTIC hop to unit
  descriptions. A SEMANTIC hop is admitted only when its target resolves to real source and the path-aware judge
  scores the (question → path → target) above the connection floor; otherwise dropped with a receipt.
- **Answer (C11, spec §10):** evidence roles `implementation` / `reference`; the synthesis block states observed
  behaviour (cited code), supported guidance (cited passages) and the proposed transfer (labelled, with what to test);
  a code-specific question keeps its implementation seats (a book never displaces the code it asks about).
- **Tests:** `test_code_mentions.py`; `test_joint_walk.py` (one semantic hop max; paths in receipts; the "both involve
  feedback" bridge rejected); `test_code_synthesis_roles.py`.

### C4 — Luau / Roblox

- **Create:** `code/languages/luau.py` (`luau-ast` JSON: functions, methods, locals, type aliases, `require` calls;
  spans are 0-based `line,col`), `scripts/fetch_luau_toolchain.sh` (0.739, sha256 `f66cabc7…3ff3`).
- **Resolution:** an index-chain `require` (`script.Parent.X`) resolves only through a Rojo sourcemap; a computed one
  (`require(v)`) is `unresolved` (C0b fixture: 2 + 2). Remotes pair only by the same resolved instance (spec §5).
- **Validation (C13):** `luau-analyze` needs Roblox definitions (C0b: 10 unknown-global errors without them) → luau-lsp
  with Roblox types when a multi-file project exists.
- **Acceptance:** the Knit fixture (`docs/wiki/experiments/code-knowledge-c0b-2026-09-24/fixtures/`): units, symbols,
  requires classified, one question answered; a real Rojo project later.

### C5a — YAML + TOML

- YAML: PyYAML `compose()` marks → character offsets (C0a: line spans overlap on flow-style files; offsets never do);
  anchors / aliases from the event stream (`ALIASES` edges); dialects (Actions, Compose, Kubernetes, OpenAPI, generic);
  comments kept inside exact slices (gap lines attach to the following section).
- TOML: tree-sitter-toml 0.7.0 spans (C0b: 28 / 28 headers) + tomllib values; `[project.scripts]` entry points →
  resolved `REFERENCES_CODE`; other string matches `ambiguous`.
- **Acceptance:** "where is the retry limit set, and what reads it?" on this repository's configs.

### C12, C13, gate qualification, C5b, C14

- **C12 readiness (C-27):** readiness reports exact lookup (symbols + source) separately from description coverage
  (profile / pMAP), per code corpus.
- **C13 validators + diagnostics:** Ruff, luau-analyze / luau-lsp, selene → `code_diagnostics` with rule, severity,
  span, tool version; exposed to DEBUG hydration and an MCP diagnostics tool (R4: facts, not hypotheses).
- **Gate qualification:** measure the σ floors (0.2 probe, 0.3 connection, 0.5 aspect / latent) on code descriptions
  with real questions (exact symbols, plain-language behaviour, a bug spanning units, an unsupported relation, a
  useful book transfer); change a value only on an observed failure.
- **C5b Power Fx:** the official parser / binder (`Microsoft.PowerFx.Core`, NuGet 1.8.1; `TexlParser`) in a .NET sidecar
  after the owner's .NET approval; two passes (YAML structure → binder with pass 1's symbol table); per-unit rules
  (value vs behavior formulas).
- **Candidate languages (not V1; owner decision):** DAX (measures vs calculated columns, filter / row context) and
  Power Query M (Microsoft's `powerquery-parser`, lazy evaluation). Each needs an adapter (extraction + resolution),
  not only a prompt addendum.
- **C14:** every card's test questions on real code, including a code + book question.

## 5. Verification ladder (every slice)

1. Pure unit tests (fixtures; no DB, no network).
2. In-process replay on a fixture corpus (no receipt written).
3. Throwaway Postgres for migrations.
4. A canary within the owner's word for any model spend.
5. Live turns on the owner's word; receipts must show the code path ran (`LIVE_PATH_PROVEN`).

## 6. What the owner decides

1. Admit the language JSON draft as `config/code_languages.yaml` (or .json) — its fields map onto §2.5.
2. Default role for repository Markdown (proposal: `implementation`, since it documents the implementation).
3. Whether FAST opens the description door (proposal: yes; it is cheap) and the exact door (proposal: yes).
4. Candidate languages beyond V1 (DAX, Power Query M). The external audit (11.471) supplies their contracts; still candidates until the owner promotes them.
6. Reference books across projects (C-26) — **ANSWERED 2026-09-24 (11.474): no book is shared across projects.** Each
   project's reference books go into that project's corpus; no multi-corpus query work is needed for K1.
7. Per-unit plain-English descriptions for code — **ANSWERED 11.473: yes**, generated from complete bodies (owner note 8).
5. The live windows: migrations 0067 / 0068, the Qdrant `knowledge_role` backfill.
