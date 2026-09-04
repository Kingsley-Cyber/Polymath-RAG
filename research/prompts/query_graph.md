# Query Graph Construction (shared: MARKET_DISCOVERY / PRODUCT_ANCHORED)

Build `query_nodes` — an evolving terminology graph with lineage, never a bag
of keywords. Each node: `id`, `query`, `origin` (TREND_RELATED |
COMMUNITY_LANGUAGE | PRODUCT_TITLE | CORPUS | THETA | SEARCH_SUGGESTION |
USER), `parent_ids`, `semantic_cluster`.

Laws:
1. Expansion uses MULTIPLE mechanisms: related/rising search terms, community
   vocabulary, product titles, marketplace terminology, registry grammars,
   and only then θ-generated candidates. Provenance stays on every node.
2. Cluster queries by SEMANTIC CONCEPT. Query migration is real: "jogging
   shorts → running shorts → split shorts" is one concept moving, not a
   dying market. The market signal belongs to the cluster, not the string.
3. Stop on saturation — one more useful expansion, not every expansion.
