# CODE-KNOWLEDGE-V1 — owner's third design note (2026-09-24)

Pasted by the owner into the session on 2026-09-24 ("now since the rag for regular retrieval works i want to implement multi
code language rag. there's already a md plan i believe and i want to add upon it"). It is a design conversation the owner
collected. The "Would you like …?" closings are part of the paste, not instructions to the agent.

Stored verbatim, with formatting normalized to Markdown: bullets, tables, fenced code. Reconciled against the packet, the
second note and the repository in `docs/wiki/reports/2026-09-24/CODE-KNOWLEDGE-V1-NOTE-3-RECONCILIATION.md`.

---

Implementation stack (recommended):
- FastAPI or FastMCP / official MCP Python SDK
- Background workers (Celery / RQ / or simple asyncio) for heavy ingestion
- Auth if multi-user

5. Retrieval & Reasoning Strategies that make it "elite"

1. Hybrid + Graph-augmented retrieval
   - Dense + sparse + graph expansion (1–2 hops on call/dependency graph).
   - Re-rank with a cross-encoder or LLM re-ranker (Cohere Rerank, or local BGE-Reranker).
2. Abstractive + Extractive mix
   - Return both raw code chunks and LLM-generated summaries of larger subsystems.
3. Multi-hop reasoning prompts
   - When the agent calls implement_from_theory, the MCP internally does: a. Retrieve relevant theory sections b. Retrieve
     existing code patterns that partially implement similar ideas c. Retrieve call-graph neighbors d. Package a rich context
     window that already bridges the gap
4. Debugging mode
   - Parse stack traces → map to exact functions → pull callers/callees + related docs about the underlying mechanic (e.g.,
     "replication lag compensation").
5. Continual improvement
   - Log successful agent interactions and use them as hard-negative / preference data to fine-tune the embedding or
     re-ranker later.

6. Concrete Tech Stack Recommendation (2025–2026)

Yes — for code you can (and should) extract the graph almost entirely deterministically without an LLM. That is one of the
biggest advantages of working with source code versus free-form technical documents.

## 1. Deterministic Graph Extraction from Code (No LLM Needed)

Modern language tooling gives you a perfect structured representation:

| What you extract | How (deterministic) | Tools for Luau / general |
|---|---|---|
| Functions, methods, classes, modules | AST walk | Tree-sitter (Luau grammar), luau-analyze, Roblox LSP / Selene |
| Calls / call graph | Resolve function references in AST | Tree-sitter + simple name resolution or luau-lsp |
| Imports / requires / dependencies | Parse require, import, ModuleScript paths | AST + path resolution |
| Inheritance / composition | Class extends, metatables, OOP patterns | AST pattern matching |
| Variable definitions & usages | Scope analysis | Tree-sitter scopes or language server |
| Types (if available) | Type annotations / inferred types | Luau type checker output |
| Control-flow edges (basic) | If/while/for → basic blocks | Control-flow graph from AST |

Resulting triples look like this (completely deterministic):

```
(Function:PlayerController.update) --[calls]--> (Function:Character:Move)
(Module:AI) --[requires]--> (Module:Pathfinding)
(Class:Enemy) --[inherits]--> (Class:NPC)
(Function:StateMachine.transition) --[defined_in]--> (File:StateMachine.luau)
(Function:replicatePosition) --[uses]--> (RemoteEvent:PositionUpdate)
```

You only need an LLM for the optional higher-level abstractions that the AST cannot see, for example:
- "This function implements a finite-state machine"
- "This is a replication pattern for lag compensation"
- "This module is the central game loop"

Those can be generated later (or on-demand) and attached as additional edges or node properties. Everything structural stays
free of API costs and is 100 % reproducible.

Recommended pipeline for Luau:
1. Parse with Tree-sitter Luau grammar → full AST.
2. Walk the AST and emit nodes + edges into a graph (NetworkX, Neo4j, FalkorDB, or even a simple SQLite + edge table).
3. Optionally run the official Luau type checker / analyzer and merge its output.
4. Store the original source span so you can always jump back to the exact code.

This is exactly what tools like Sourcegraph, GitHub's code navigation, and most modern code intelligence systems do under the
hood.

## 2. Retrieving Technical Documents Alongside Code

You keep two parallel indexes that are queried together (or fused):

```
Query
│
├─► Code Index (vector + BM25 + graph)
│     • function-level / module-level chunks
│     • call-graph expansion
│
└─► Document Index (vector + BM25 + hierarchical)
      • chapter / section / paragraph chunks from Luau manuals, game-design books, Roblox docs, etc.
```

How the combined retrieval works (elite version)
1. Hybrid search on both indexes in parallel.
2. Optional cross-linking (still mostly deterministic or light LLM):
   - After ingestion, run a cheap pass that links document sections to code symbols when there is clear overlap (e.g., a
     manual page titled "RemoteEvents" gets linked to every RemoteEvent usage in the codebase).
   - Or simply rely on the query-time fusion — no pre-linking required.
3. Fusion & ranking strategies (pick one or combine):
   - Reciprocal Rank Fusion (RRF) — simple and very effective.
   - Weighted score: 0.6 * code_score + 0.4 * doc_score (tune per use-case).
   - Graph-aware expansion: from the top code hits, walk 1 hop on the call/dependency graph, then re-retrieve documents that
     mention those neighboring symbols.
   - LLM re-ranker (only at the end, on the top 20–30 candidates) if you want maximum quality.
4. What the agent actually receives:

```json
{
  "code_context": [
    { "symbol": "StateMachine.transition", "code": "...", "callers": [...], "callees": [...] },
    ...
  ],
  "document_context": [
    { "source": "Roblox Networking Guide p.42", "text": "When using RemoteEvents for position replication..." },
    { "source": "Game Programming Patterns – State", "text": "A robust FSM should..." }
  ],
  "cross_links": [ "StateMachine.transition ↔ FSM chapter 7" ]
}
```

This is exactly what you need for debugging / assessing issues against technical documents: the LLM sees the relevant code and
the authoritative explanation of the underlying mechanic side-by-side.

Practical Recommendations
- Code graph → 100 % deterministic (Tree-sitter + AST walk). No LLM required.
- Document graph / triples → you will still want an LLM (or a strong information-extraction model) because technical manuals
  are natural language.
- Retrieval → keep the two indexes separate and fuse at query time. This is cleaner, cheaper, and more flexible than forcing
  everything into one giant graph.
- When you do want cross-links → run a lightweight, batched LLM job after ingestion (or even a simple embedding similarity +
  keyword filter) to create implements_concept edges. You can do this offline and infrequently.

Would you like me to give you:
1. A concrete Tree-sitter + NetworkX skeleton for Luau graph extraction, or
2. The exact retrieval fusion code (RRF + graph expansion) that returns both code and documents in one MCP tool response?

Either of those will get you to an elite setup very quickly.

---

No, you do not need to delete the older game's code.

You design the system with project / repository isolation (also called namespaces, collections, or tenants). This is standard
practice in any serious multi-codebase RAG.

Recommended Way to Handle Multiple Game Repos

Treat every uploaded game as its own Project (or Repo / Codebase).

1. Data Model

Every node and chunk carries metadata like this:

```
{
  "project_id": "game_alpha_v1",      // or "roblox_obby_2025"
  "project_name": "Obby Adventure",
  "repo_type": "code",                // vs "docs"
  "language": "luau",
  "file_path": "src/Server/AI/StateMachine.luau",
  "symbol": "StateMachine.transition",
  ...
}
```

Technical documents stay in a shared (or also project-scoped) space:

```
{
  "project_id": "shared_technical",   // or null / "global"
  "doc_type": "theory" | "roblox_manual" | "game_design",
  ...
}
```

2. Storage Layout (practical options)

| Approach | Vector DB (Qdrant / Weaviate / etc.) | Graph DB | Best for |
|---|---|---|---|
| Collection / Namespace per project | One collection per game + one shared docs collection | Separate graph or labeled subgraph | Cleanest isolation, easy deletion |
| Single collection + strong filtering | One big collection, filter by project_id | One graph with project_id property on every node/edge | Simpler ops, still very good |
| Hybrid | Shared docs collection + per-game code collections | Shared concept graph + per-game code graphs | Most flexible |

Most people start with single collection + metadata filtering and move to separate collections later if the number of games
grows large.

3. Upload Flow

When you upload a new game:

```
upload_code(
  files = [...],
  project_id = "game_beta_2026",   # you choose or auto-generate
  project_name = "Horror Game",
  overwrite = false                # or true if re-uploading same project
)
```

- The system creates (or reuses) the project namespace.
- All extracted nodes, edges, embeddings, and chunks are tagged with that project_id.
- Existing projects remain completely untouched.

4. Retrieval – How the correct game is selected

Your MCP tools accept an optional (or required) project filter:

```
search_code(
  query = "finite state machine for enemy AI",
  project_id = "game_beta_2026",   # ← this is the key
  include_shared_docs = true,
  top_k = 12
)
```

What happens internally:
1. Retrieve from the code index only where project_id == "game_beta_2026".
2. Retrieve from the shared technical documents (always available).
3. Optionally expand via the call graph within the same project.
4. Fuse the results and return them together.

You can also support:
- project_id = null → search across all games (useful for cross-game pattern mining).
- Multiple project_ids at once.
- Default project (the last one uploaded or the one set in the session).

5. Practical Recommendations for Your Use Case
- Keep the 100 technical + game theory documents in a shared/global space. They enrich every game.
- Give every game its own project_id.
- When the agent is working on a specific game, always pass the corresponding project_id (your coding agent can remember the
  current project).
- If you later want to delete a game, just drop everything with that project_id — the shared documents stay.

6. Bonus: Project Management Tools in the MCP

Expose a few extra tools:

```
list_projects()
create_project(name, description)
delete_project(project_id)          # optional, careful
set_active_project(project_id)      # so subsequent calls don't need the id every time
get_project_stats(project_id)       # number of files, symbols, etc.
```

This makes the whole system feel like a proper multi-repo code intelligence platform.

Summary
- Upload as many games as you want.
- Never delete the previous one unless you explicitly want to.
- Tag everything with a project_id.
- Filter by project_id at retrieval time.
- Keep the technical documents shared so they enrich every codebase.

Would you like the concrete metadata schema + example Qdrant / Neo4j filter code, or the MCP tool signatures that enforce
project isolation?

---

Yes — you can (and should) enrich the code with LLM-generated semantic/abstract layers. This is one of the highest-leverage
things you can do for elite retrieval. Done correctly, it stays fully project-isolated by default, while still letting you
deliberately pull reference implementations from other projects when useful.

1. What "LLM Enrichment" Looks Like on Code

For every important symbol (function, class, module, or even a whole file), you generate and store extra fields once at
ingestion time:

| Enrichment Type | Example Output | Purpose |
|---|---|---|
| Abstract summary | "Implements a finite-state machine for enemy AI with enter/update/exit hooks" | Semantic search |
| Design intent / pattern | "Classic State pattern + Observer for state changes. Used for combat & movement" | Abstract retrieval |
| Key mechanics | "Handles dynamic damage calculation with armor, crit, and status multipliers" | User questions like "healthbar + damage math" |
| Dependencies & assumptions | "Relies on CharacterController and NetworkReplicator. Assumes server-authoritative" | Debugging context |
| Potential issues / smells | "No validation on negative health. Race condition possible on rapid damage events" | Agent debugging |
| Natural language queries it answers | "How does the health system work?", "Implement damage with armor" | Improves recall |

These become additional text that you embed (alongside or instead of the raw code) and also store as node properties in the
graph.

2. How to Keep Isolation While Still Gaining Value from Other Projects

Use a clear visibility / scope model:

```
project_id = "game_horror_2026"                  # ownership
visibility = "private" | "reference" | "public"
enrichment_scope = "project" | "cross_project_allowed"
```

Recommended policy
- Default (agent debugging a specific game): retrieval is strictly filtered to project_id == current_project. The LLM
  enrichments of that project are used. Other projects are invisible unless explicitly requested.
- Reference mode (agent or user wants inspiration): you allow a controlled cross-project search:

  ```
  search_code(
    query = "...",
    project_id = "game_horror_2026",              # primary
    include_references = true,                     # pull from other projects
    reference_filter = {"visibility": "reference"},  # only marked ones
    max_references = 5
  )
  ```

- User general questions ("how to create a healthbar with dynamic damage…"): search across all projects + shared technical
  documents, ranked by relevance of the LLM enrichments. The system can return:
  - Best matching implementation from any game
  - The abstract description
  - Linked theory documents
  - Side-by-side comparison if multiple good examples exist

3. Practical Enrichment Pipeline (efficient & cheap)
1. After deterministic AST + graph extraction, select nodes worth enriching:
   - All public/exported functions and classes
   - Modules above a certain size
   - Anything with non-trivial control flow or domain logic
2. Batch LLM calls (very important for cost). Prompt skeleton:

   ```
   "You are analyzing Roblox Luau code.
   Given the following function/module and its immediate callers/callees,
   produce:
   - One-sentence abstract summary
   - Design patterns used
   - Core game mechanics it implements
   - 3-5 natural language questions this code answers
   - Any notable assumptions or edge cases

   Code:
   {code + signature + docstring + 1-hop graph context}"
   ```

3. Store the outputs as:
   - Extra text fields → embedded with a strong model (Voyage Code / Jina / etc.)
   - Structured properties on the graph node
   - Optionally a separate "enrichment" vector for pure semantic search
4. Re-enrich only when the code changes (hash the source).

4. Retrieval Behavior by Use Case

| Use Case | Primary Filter | Secondary / References | What the agent/user sees |
|---|---|---|---|
| Agent debugging one game | project_id = current | None by default | Only that game's code + its enrichments + shared docs |
| Agent wants reference patterns | project_id = current | Other projects (limited) | Current code + 3–5 good examples from past games with their abstract summaries |
| User: "how to make dynamic healthbar damage math" | None (or all projects) | Shared theory docs | Best matching enriched code snippets + theory + explanations |
| Cross-game learning | All projects | Ranked by enrichment quality | Multiple implementations side-by-side |

5. MCP Tool Design Suggestion

```
search_code(
  query: str,
  project_id: str | None = None,   # None = current or all
  mode: "strict" | "with_references" | "global",
  include_enrichments: bool = True,
  max_references: int = 5
)

get_enriched_symbol(symbol, project_id)
compare_implementations(query, project_ids: list[str])
```

This gives the coding agent precise control: it can stay laser-focused on the current project for debugging, then
deliberately open the aperture for reference implementations when it needs inspiration.

Bottom line
- Enrich every important code symbol with LLM-generated abstract/semantic descriptions → much better retrieval.
- Keep strict project_id isolation by default.
- Add an explicit "include_references" flag so the agent (or user) can pull valuable patterns from previous games without
  polluting the primary context.
- Shared technical documents always remain available as grounding.

Would you like a ready-to-use prompt template for the enrichment step, the exact metadata schema, or example retrieval logic
that implements the three modes (strict / with_references / global)?

---

Yes — multi-language support must be designed in from the start. Your stack (Qdrant + SQL + Neo4j) is excellent for this.
Here's how to make the entire ecosystem work cleanly when a repo contains Luau + Python + YAML + TOML (or any other languages).

1. Core Principle: Language-Agnostic Graph + Language-Specific Parsers

Everything hangs off two ideas:
- Deterministic structural representation first (AST / CST / schema) → this is language-specific.
- Uniform enrichment + embedding layer second → this is language-agnostic.

The graph (Neo4j) and the vector store (Qdrant) never care what language a node came from. Only the ingestion parsers do.

2. Ingestion = One Big Indexing Chain (Recommended Design)

```
Upload (files or zip/repo)
│
▼
┌─────────────────────────────────────────┐
│ 1. Language Detection & Routing         │ (by extension + content)
└─────────────────────────────────────────┘
│
├── Luau ──► Tree-sitter Luau / luau-analyze
├── Python ─► Tree-sitter Python / Jedi / libcst
├── YAML ───► ruamel.yaml or Tree-sitter YAML + schema awareness
├── TOML ───► tomlkit or Tree-sitter TOML
└── ... (easy to add more)
│
▼
┌─────────────────────────────────────────┐
│ 2. Deterministic Extraction             │
│    - Symbols (functions, classes, keys) │
│    - Relations (calls, imports, requires, includes, anchors)
│    - Hierarchy (file → module → symbol) │
│    - Source spans                       │
└─────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────┐
│ 3. Graph Construction (Neo4j)           │ ← language-agnostic
│    Nodes: File, Module, Function, Class, ConfigKey, etc.
│    Edges: CALLS, IMPORTS, DEFINES, CONTAINS, REFERENCES, ...
│    Properties: language, project_id, ...
└─────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────┐
│ 4. LLM Enrichment (optional but powerful)│
│    Abstract summary, design intent,     │
│    mechanics, questions it answers...   │
│    (same prompt template for all langs) │
└─────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────┐
│ 5. Embedding & Indexing                 │
│    - Raw code / config chunk            │
│    - LLM abstract summary               │
│    - Hybrid (dense + sparse)            │
│    → Qdrant (with payload filters)      │
│    → SQL (metadata, hashes, versions)   │
└─────────────────────────────────────────┘
```

This single chain works for pure Luau games, pure Python services, or mixed repos.

3. Handling Different Languages Cleanly

| Language | Parser Recommendation | What you extract deterministically | Special notes |
|---|---|---|---|
| Luau | Tree-sitter Luau + Roblox-aware | Functions, ModuleScripts, Remotes, metatables | Roblox path resolution |
| Python | Tree-sitter Python or libcst + Jedi | Functions, classes, imports, decorators, calls | Very mature |
| YAML | ruamel.yaml or Tree-sitter + schema | Keys, nested structures, anchors, values | Treat keys as symbols |
| TOML | tomlkit or Tree-sitter | Tables, keys, arrays | Same as YAML |
| Others | Tree-sitter grammars (most languages) | Same pattern | Easy to extend |

Unified node types in Neo4j (examples):

```
(:File {path, language, project_id})
(:Module {name, language, project_id})
(:Function {name, signature, language, project_id})
(:Class {name, language, project_id})
(:ConfigKey {key_path, language, project_id})      # for YAML/TOML
(:ConfigValue {value, ...})

(f:Function)-[:CALLS]->(g:Function)
(m:Module)-[:IMPORTS]->(n:Module)
(file)-[:CONTAINS]->(symbol)
(config)-[:REFERENCES]->(code_symbol)              # when YAML points to a Python function, etc.
```

Cross-language edges are possible and valuable (e.g. a YAML config key that references a Python entrypoint or a Luau
RemoteEvent name).

4. Retrieval When the Embedding Model Isn't Code-Specialist

You already have the right intuition: rely on deterministic representations first.

Strategy that works extremely well:
1. Primary retrieval signal = deterministic structure + metadata filters
   - Filter by project_id, language, file_type, symbol_type in Qdrant payload + Neo4j.
   - Expand via graph (1–2 hops on CALLS / IMPORTS / CONTAINS).
2. Secondary signal = embeddings on multiple representations
   - Embed the LLM abstract summary (this is language-agnostic and usually the strongest semantic signal).
   - Embed a cleaned version of the code/config (strip comments or keep them).
   - Optionally embed the signature + docstring only.
3. Hybrid search in Qdrant
   - Dense vector (from whatever embedding model you have) + BM25/sparse on the text representations.
   - Even a general-purpose embedding model performs surprisingly well when the text it sees is a high-quality abstract
     summary + signature instead of raw noisy code.
4. Fallback / boost
   - If the query looks code-specific, boost results that have strong graph connectivity.
   - Always return the original source span so the LLM can read the real code.

Result: you can use a solid general embedding model (or a good code model when available) and still get excellent retrieval
because the heavy lifting is done by the deterministic graph + enrichments.

5. Project Isolation Still Works Perfectly
- Every node and every Qdrant point carries project_id + language.
- Default retrieval: project_id = current (all languages inside that project).
- Reference mode: allow other projects, optionally filtered by language.
- User general questions: search across projects + shared technical docs.

A mixed-language repo is just one project_id containing nodes of different language values.

6. Concrete Stack Mapping
- Neo4j: Canonical knowledge graph (symbols + relations across all languages).
- Qdrant: Multiple vectors per point (code chunk, abstract summary, etc.) + rich payload for filtering (project_id, language,
  symbol_type, file_path…).
- SQL:
  - Project registry
  - File hashes (for incremental re-indexing)
  - Enrichment cache
  - Upload jobs / versions

7. Pre-planning Checklist for the Ecosystem
- Language detection router at the start of the chain.
- Pluggable parser interface (parse(file) → list[Symbol] + list[Relation]).
- Uniform graph schema (add new languages without changing Neo4j queries).
- Enrichment prompt that works for code and config files.
- Qdrant collection design: one collection with strong payload indexing (or one per major language if you prefer).
- Incremental updates: re-parse + re-enrich only changed files.

Summary
- One indexing chain with language-specific front-ends and a language-agnostic back-end.
- Deterministic graph extraction for every language → reliable structure.
- LLM enrichment on top → strong semantic/abstract retrieval.
- Embeddings become secondary and can be "good enough" because you retrieve through high-quality representations + graph.
- Full project isolation remains, while cross-project and cross-language references stay available when explicitly requested.

Would you like the exact Neo4j schema constraints + indexes, a sketch of the parser interface in Python, or the Qdrant
payload + hybrid search example that supports multi-language filtering?

---

Yes — you can create the exact equivalent of your "parent chunk maps + LLM enrichment" for code. The difference is that code's
hierarchy is structural (AST / schema), not heading-based. You still produce rich parent-level representations that enable
excellent routing, retrieval, and abstract synthesis.

1. Mapping Your Document Approach → Code Approach

| Document World | Code World Equivalent | Purpose |
|---|---|---|
| Heading + Subheading hierarchy | File → Module/Class → Function/Method (or YAML key path) | Parent chunks |
| Parent chunk map | Symbol tree / hierarchical map | Routing |
| LLM enrichment (aliases, questions…) | Same prompt family, but fed structured code context | Semantic + abstract retrieval |
| Abstract document synthesis | Abstract module/file synthesis | High-level understanding |

2. Hierarchical Parent Map for Code (Deterministic First)

For every file you build a clean tree:

```
File: src/Server/Combat/HealthSystem.luau      ← Level 0 (File parent)
├── Module / Main chunk
├── Class: HealthSystem                        ← Level 1
│   ├── Function: constructor
│   ├── Function: ApplyDamage                  ← Level 2 (leaf)
│   ├── Function: GetHealthPercentage
│   └── Function: OnHealthChanged
└── Local helpers...
```

For YAML / TOML / Power Fx the hierarchy is key-path based:

```
File: config/game_settings.yaml
├── combat:
│   ├── damage:
│   │   ├── base: 10
│   │   ├── multipliers: ...
│   └── healthbar:
│       ├── dynamic: true
│       └── ...
```

You store this tree in Neo4j (or as nested JSON in SQL) so you always know the parent–child relationships.

3. LLM Enrichment Strategy for Code (Mirrors Your Document Flow)

You enrich at multiple levels, just like headings:
1. Leaf level (individual function / method / deep YAML key) → Detailed summary, inputs/outputs, edge cases, questions it
   answers.
2. Mid level (class / module / major YAML section) → "This class implements X pattern and is responsible for Y mechanic."
3. File / top-level parent → High-level abstract: "This file owns the entire dynamic health & damage calculation system,
   including replication and UI binding."

Recommended enrichment fields (produce the same richness you already do for documents):
- Abstract summary (1–3 sentences)
- Alias concepts / alternative names
- Design patterns & mechanics implemented
- Questions this code answers
- Key assumptions & dependencies
- Potential failure modes
- Natural-language search phrases

Because you already have the deterministic tree, you can feed the LLM:
- The symbol's own code
- Its immediate children (summaries or signatures)
- Its parent context
- 1-hop graph neighbors (callers/callees)

This produces far better abstract representations than enriching isolated chunks.

4. Robust Language Detection & Pipeline Routing (Critical for Your Case)

You need a reliable router so that even a YAML file saved as .txt is handled correctly.

Recommended detection order (cheap → expensive):
1. File extension (fast path)
2. Content-based detection (very important)
   - YAML: starts with ---, key-value patterns, indentation, presence of anchors
   - TOML: [section], key = value
   - Python: def , class , import , shebang
   - Luau / Roblox: local, function, game:GetService, --!strict, .luau patterns
   - Power Fx: formulas starting with =, specific function names, canvas-app style
3. Fallback / confidence score: if confidence is low → flag for human review or run a tiny LLM classifier (rare).

Implementation sketch:

```python
def detect_language(file_path: str, content: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext in {".luau", ".lua"}: return "luau"
    if ext in {".py"}: return "python"
    if ext in {".yaml", ".yml"}: return "yaml"
    if ext in {".toml"}: return "toml"
    if ext in {".fx", ".powerfx"}: return "powerfx"

    # Content sniffing
    if is_probably_yaml(content): return "yaml"
    if is_probably_toml(content): return "toml"
    if is_probably_python(content): return "python"
    if is_probably_luau(content): return "luau"
    if is_probably_powerfx(content): return "powerfx"

    return "unknown"  # or "text"
```

Then the big indexing chain routes:

```
detect_language()
│
├── luau    → Luau AST pipeline
├── python  → Python AST pipeline
├── yaml    → YAML hierarchical key pipeline
├── toml    → TOML pipeline
├── powerfx → Power Fx expression / formula pipeline
└── unknown → generic text + warning
```

5. How This Enables the Behaviors You Want
- Document-style routing & retrieval: Query → matches against enriched parent summaries (file/module level) first → then drills
  into children. Exactly like your heading maps.
- Abstract code representation retrieved: The mid- and top-level enrichments are what get retrieved for high-level questions
  ("how does dynamic damage work?").
- Agent focused on one project: Still filtered by project_id. The hierarchical enrichments stay inside that project.
- Cross-project reference: When allowed, the abstract parent summaries from other projects become excellent "how others
  implemented X" examples.
- Mixed-language repos: Each file goes through its own parser, but all land in the same Neo4j graph and Qdrant collection with
  language + project_id tags.

6. Practical Tips for Your Stack (Qdrant + SQL + Neo4j)
- Store the hierarchical map in Neo4j ((:File)-[:CONTAINS*]->(:Symbol)).
- Store the LLM enrichments both as node properties and as separate embeddable texts in Qdrant.
- In Qdrant payload include: project_id, language, symbol_type, hierarchy_level, parent_id.
- For YAML-as-.txt: the content sniffer protects you from the bug you mentioned.

Bottom line

Treat code exactly like you treat documents: build a clean hierarchical parent map (deterministically), then run multi-level LLM
enrichment to produce aliases, questions, abstract summaries, etc. Route every file through a robust language detector →
language-specific structural parser → common enrichment + indexing stages.

This gives you the same high-quality routing, retrieval, and abstract synthesis you already enjoy with documents, while
correctly handling Luau, Python, YAML (even as .txt), TOML, and Power Fx.

Would you like:
1. A concrete multi-level enrichment prompt template that works across these languages, or
2. The Python skeleton for the language detector + hierarchical map builder, or
3. How to store and query the parent maps in Neo4j + Qdrant most efficiently?
