# CODE-KNOWLEDGE-V1 — owner note 8: code pMAP from complete bodies, units from the deterministic parser (2026-09-24)

The owner wrote, 2026-09-24: "you need to ensure that the codes identifies all proper functions in respect to the code type.
i thinks it should use the same logic used to create th determinisitc graph." The same message pasted the design below
(another assistant's answer, which the owner carried forward as "the decision to carry into your existing plan"). Stored
verbatim. Admitted in register 11.473 as design rule R12 and the "Code pMAP contract" section of
`docs/wiki/plans/CODE-RAG-IMPLEMENTATION-V1.md`; it answers that file's §6 item 7 (keep per-unit descriptions: yes).

---

**Yes: generate code pMAP from the complete code bodies. Its equivalent is a searchable map of functions, formulas, controls and configuration sections, with exact links back to their source.**

**Contract:** Preserve your profile → pMAP → evidence architecture, while replacing heading-based discovery with language-aware structure.

**Changes proposed:** No files changed. These are the units I would map. The GitHub projects provide the underlying structure; the natural-language pMAP remains Polymath’s enrichment layer.

| Language | What a pMAP entry points to | GitHub foundation |
|---|---|---|
| **Python** | A class, function or module initialization block. Methods remain individually addressable. | [LibCST](https://github.com/Instagram/LibCST/blob/main/libcst/_nodes/statement.py) exposes classes, functions and their bodies. |
| **Luau / Roblox** | A script/module’s functions, methods and event-handler bodies. | [Official Luau AST](https://github.com/luau-lang/luau/blob/master/Ast/include/Luau/Ast.h). Roblox instance paths and remote identities additionally need project metadata. |
| **Power Fx inside Power Apps YAML** | A screen/component/control, with exact links to its property formulas: `OnSelect`, `Items`, `Visible`, etc. App-level formulas also get mapped. | [Microsoft’s Power Apps schema](https://github.com/microsoft/PowerApps-Tooling/blob/master/schemas/pa-yaml/v3.0/pa.schema.yaml) supplies the hierarchy; [Power Fx](https://github.com/microsoft/Power-Fx) supplies formula parsing. |
| **YAML configuration** | A meaningful section such as a service, job or resource, linked to its settings. The consuming application determines what those sections mean. | [PyYAML](https://github.com/yaml/pyyaml) supplies structure; application specifications such as [Compose](https://github.com/compose-spec/compose-spec/blob/main/spec.md) supply meaning. |
| **TOML** | A table or array-of-tables entry, linked to its settings. | [Tree-sitter TOML](https://github.com/tree-sitter-grammars/tree-sitter-toml) exposes tables and key/value pairs. |
| **DAX** | A measure, calculated column or calculated table, with its expression and model context. | [Tabular Editor](https://github.com/TabularEditor/TabularEditor) exposes these model objects. |
| **Power Query M** | A query/function, with addressable `let` bindings and their dependencies. | [Microsoft’s M parser](https://github.com/microsoft/powerquery-parser/blob/master/src/powerquery-parser/language/ast/ast.ts) exposes those expressions. |

**The names locate the units; reading their bodies establishes what they do.** You should not generate “handles damage” just because a function is named `ApplyDamage`.

For an illustrative Roblox function, a useful pMAP description could be:

> Applies damage after checking the attacker’s cooldown and target eligibility; updates health and records the attack time.

That entry points to the exact function. Searches about repeated attacks, eligibility or attack timing can find it without knowing its name. The description is valid only if those behaviors appear in the source.

For your **“send the full thing”** decision, I would use this process:

1. **Parse the entire uploaded file.** Record every unit, its enclosing context and its source location. This establishes coverage without relying on headings.
2. **Give the LLM complete code bodies.** Send the whole file when it fits the selected model’s usable context. Otherwise, process every section in separate requests, carrying relevant definitions and dependencies. Oversized functions must be divided along syntax boundaries with their surrounding conditions preserved.
3. **Build the descriptions upward.** Full unit bodies produce grounded descriptions and pMAP entries. Those descriptions produce screen/module/file profiles. Every level retains links to the original code.

For your 400 KB Power Apps file, that means processing the screen/control/formula hierarchy across the whole file, rather than taking its beginning, ending and a few samples. Formula context must include relevant app variables, data sources and referenced controls where available.

**A full file still might reference things outside itself.** Those dependencies need to accompany the request when resolved, or be explicitly marked missing.

**Proof:** The linked GitHub sources establish the structural units above. They do not establish that Polymath already generates or retrieves their semantic maps correctly.

**Rejected claims:** Heading-only sampling is insufficient for your requirement. Requiring the entire upload to fit into one LLM request is unnecessary.

**The decision to carry into your existing plan: complete source coverage, language-aware units, and pMAP descriptions generated from actual bodies.**
