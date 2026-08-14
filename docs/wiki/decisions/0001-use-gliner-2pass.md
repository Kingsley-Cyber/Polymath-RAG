---
owner: sidecar-gpu
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# ADR-0001: Two-pass GLiNER for entity + evidence proposal

## Context

v3.3 let a model propose graph relations directly. That mixed
nondeterministic span detection with predicate policy and made false graph
edges difficult to audit or reproduce.

## Decision

Decompose extraction into two GLiNER passes and a deterministic
compiler:

- **Pass 1: entity proposal.** GLiNER receives the versioned entity label
  set for the active ontology profile and returns typed spans.
- **Pass 2: evidence proposal.** The same resident GLiNER model receives a
  versioned evidence-label set and returns coarse evidence spans. It does
  not return predicate labels.
- **Compiler.** A YAML-driven decision DAG that maps
  (entity types × evidence class × lexical trigger × argument
  structure) onto a canonical predicate vocabulary. Deterministic. Pure
  function over compiled tables.

Both passes use one host-native `gliner-runtime` process on the Mac. This
avoids loading the same weights twice. A measured experiment and a new ADR
are required before splitting the passes into separate model processes.

The compiler is the only place predicates are decided. GLiNER proposes;
the compiler decides. Silence is a valid answer.

## Consequences

Easier:
- The system can prefer no edge when deterministic evidence is insufficient.
- The compiler is auditable. Every edge carries evidence spans, rule
  IDs, and resource versions.
- The system is deterministic given the same inputs. Re-ingestion is
  a no-op.

Harder:
- Lexical-semantic tables have coverage gaps that must be measured against
  the admitted corpus.
- The rule pack is a curated engineering artifact. Adding a new
  predicate is a PR, not a config change.
- Cross-sentence and implicit relations are out of scope for v1.

New failure modes:
- Polysemous triggers ("run", "support", "have") produce
  AMBIGUOUS decisions. Acceptable, but observable.
- Domain terminology not in any of the four resources produces
  UNSUPPORTED. Also acceptable, but observable.

## Triggered refactors

- `docs/wiki/refactors/0001-compiler-as-pure-function.md`
- `docs/wiki/refactors/0002-gliner-runtime-two-logical-passes.md`
