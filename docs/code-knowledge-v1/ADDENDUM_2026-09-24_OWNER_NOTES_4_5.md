# CODE-KNOWLEDGE-V1 — two design reviews the owner pasted (2026-09-24)

Pasted together by the owner on 2026-09-24, after the sources list (register 11.454), with no further instruction. They
are reviews of the plan from another assistant. Stored verbatim. Reconciled in
`docs/wiki/reports/2026-09-24/CODE-KNOWLEDGE-V1-NOTES-4-5-RECONCILIATION.md`. The one decision they reopened (Neo4j timing)
was put to the owner and answered the same day.

---

## Review A

**BLUF: Build on your existing pipeline using proven parsers and resolvers, a deterministic Neo4j graph, and AI-generated search representations. Answers should retrieve and cite both actual code and document passages.**

**Contract:** Upload code, find it using ordinary language, follow its real relationships, and combine it with relevant documentation to explain behavior and investigate problems.

**Changes I recommend**

Your architecture should follow this flow:

**Uploaded files → language parsing and resolution → source chunks + structural graph → AI routing representations → combined retrieval → cited synthesis.**

Reuse these GitHub projects:

| Need | Sources to evaluate | What they provide |
|---|---|---|
| Existing code-graph implementation | [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) | Code indexing, graph queries, Neo4j support, and optional SCIP indexing. Evaluate its extraction components before writing equivalents. Its listed Lua support does not establish Luau/Roblox support. |
| Python | [LibCST](https://github.com/Instagram/LibCST), [scip-python](https://github.com/sourcegraph/scip-python) | Source structure and preserved formatting; Pyright-based semantic indexing for symbol references. |
| Luau / Roblox | [tree-sitter-luau](https://github.com/tree-sitter-grammars/tree-sitter-luau), [luau-lsp](https://github.com/JohnnyMorganz/luau-lsp), [rbx-dom](https://github.com/rojo-rbx/rbx-dom) | Syntax parsing; resolution using Roblox sourcemaps and diagnostics; reading Roblox place/model formats. |
| YAML / TOML | [PyYAML](https://github.com/yaml/pyyaml), [tree-sitter-toml](https://github.com/tree-sitter-grammars/tree-sitter-toml) | Existing parsers for configuration structure. Your adapters supply dialect-specific relationships and source locations. |
| Power Fx | [Microsoft Power-Fx](https://github.com/microsoft/Power-Fx) | Microsoft's language implementation and Core package. Formula resolution also needs the app's controls, variables, and data-source context. |

**What makes the graph dependable**

- **Distinguish syntax from resolved meaning.** Seeing `foo()` proves a call expression exists; it doesn't always establish which function runs. Keep unresolved and ambiguous references explicit.
- **Attach provenance to every relationship:** project, source revision, file, source span, and extraction rule. Reprocessing the same snapshot with pinned tools and settings should reproduce the graph.
- **Use language-specific resolution.** Match Roblox remotes by resolved instance identity, not merely matching names. A configuration string matching a function name is a possible reference, not proof that the function reads that configuration.

Keep Postgres as your existing authority and project those records into Neo4j. **Your current plan explicitly defers Neo4j; that deferral conflicts with the outcome you've requested here.** See the [current plan](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/wiki/plans/CODE-KNOWLEDGE-V1.md).

**How natural-language retrieval should work**

Your existing profile and pMAP workers describe each file and meaningful code unit: purpose, behavior, terminology, mechanisms, and questions it answers. Embed those descriptions, while preserving links back to exact source.

A question such as "Why does damage sometimes apply twice?" should retrieve relevant code, follow resolved callers or remote handlers, and retrieve applicable documentation. Preserve each discovery path through ranking, so the literal-query encoder doesn't discard useful indirect evidence again.

For issue identification, ingest actual analyzer diagnostics, such as [Ruff](https://github.com/astral-sh/ruff) findings or Luau diagnostics. Keep AI-suggested failure modes labelled as hypotheses. A graph alone doesn't prove a race condition or missing validation.

**Proof:** I checked the local plans and the upstream projects. This establishes reusable components, not compatibility or retrieval quality on your files.

**Rejected claims:** Writing parsers from scratch, letting AI invent structural edges, treating summaries as source evidence, or assuming a deterministic graph is automatically correct.

**Open contract gaps:** Representative uploaded files still need to prove parsing, resolution, source citations, revision updates, and a query that successfully combines code with documents. Start that qualification with the existing Polymath Python repository.

---

## Review B

**BLUF: Graphify is a useful starting point, but its Luau support is partial. For pMAP, keep one shared system with language-specific units and descriptions.**

**Contract:** Your coding assistant should find relevant code, trace its dependencies, retrieve useful book passages, and distinguish bugs from proposed design improvements.

**Changes I recommend**

**Use Graphify as a component, with proper Luau support.** The Graphify installed on your machine is `graphifyy 0.9.53`. It recognizes `.luau`, but sends those files through its Lua parser. The upstream implementation does the same. That is insufficient for dependable typed-Luau analysis. [Graphify extractor](https://github.com/Graphify-Labs/graphify/blob/v8/graphify/extract.py)

For Roblox, pair a [Luau-specific parser](https://github.com/tree-sitter-grammars/tree-sitter-luau) with [luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) and the project's instance map. This gives you a basis for resolving `require` paths and understanding script locations. Graphify already offers MCP access and Neo4j export/push, so those are capabilities worth evaluating for reuse. [Graphify](https://github.com/Graphify-Labs/graphify)

The separate **graphify-go** project mentioned in your plan currently lists JavaScript/TypeScript, Python, and Go support; it does not list Luau. [graphify-go](https://github.com/ian000/graphify-go)

**Apply pMAP to meaningful code units.** For a book, pMAP says, "This section explains this mechanism." For code, it should say, "This unit implements this behavior; retrieve these source spans to inspect it."

| Language | What a pMAP parent represents | What its routing description explains |
|---|---|---|
| **Python** | Class, top-level function, or module initialization block | Responsibility, inputs/outputs, state, side effects, dependencies |
| **Luau** | Module, method group, function, or event-handler group | Game mechanic, state transitions, client/server context, remotes, timing |
| **Power Fx** | Screen/control context with addressable property formulas | User action, formula behavior, data reads/writes, navigation |
| **YAML** | Job, service, resource, or meaningful configuration section | What it configures, dependencies, conditions, related code |
| **TOML** | Table or package/tool configuration section | Settings, entry points, declared dependencies, affected tooling |

**The structure changes by language; the pMAP contract stays consistent.** Each entry carries:

- A parser-derived address and exact source ranges.
- A concise behavior description and alternate search vocabulary.
- Questions the unit can help answer.
- Resolved relationships from the structural graph.
- Clearly labelled assumptions or suspected risks.

The LLM writes the searchable explanation. It must not invent callers, remote pairings, or confirmed bugs.

**Keep pMAP and the graph complementary.** pMAP answers *"Where should I look?"* The graph answers *"What is connected?"* Exact source answers *"What does the code actually do?"*

For an MCP coding assistant, expose search, source retrieval, relationship traversal, and diagnostics through the existing tool surface. Return source revision and resolution status with results so the assistant can inspect evidence before proposing a change.

**Your books-and-Luau combination is where this becomes useful.** Suppose you ask:

> "Why does dodging feel unfair, and how could we improve it?"

The proposed retrieval flow would:

1. Find dodge, damage, and invulnerability code through their pMAP descriptions.
2. Trace relevant handlers, timing, and client/server relationships.
3. Retrieve book passages about feedback, fairness, and risk/reward.
4. Synthesize **observed implementation**, **relevant design principles**, and **proposed changes** separately.

A book can motivate a better mechanic. It cannot prove that your implementation contains a bug.

**Proof:** A local parser check accepted ordinary Lua but reported errors for typed Luau functions and exported types. That establishes a syntax limitation, not that Graphify extracts nothing useful. No application code changed.

**Rejected claims:** "Supports `.luau`" means complete Roblox understanding; AI descriptions are verified graph facts; one generic summary prompt suits every language.

**Open contract gap:** The next qualification should use a real Roblox module and its callers to verify typed syntax, instance resolution, exact source retrieval, and a relevant book connection together.
