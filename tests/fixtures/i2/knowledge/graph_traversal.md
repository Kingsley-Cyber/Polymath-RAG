# Graph Traversal Policy

Graph traversal policy bounds how graph evidence is gathered. Expansion starts from authorized seeds and follows a directed relation set with a fixed hop limit.

Seed authorization is corpus-scoped. Seeds resolve from entities attached to evidence within the active corpus, never from raw surface matching against the unrestricted graph.

Directed expansion preserves stored orientation. An incoming edge only makes the existing fact eligible; it never reverses or invents a relation.

Traversal policy is frozen until measured qualification demonstrates a defect. Hop limits and predicate allowlists change only with evidence.
