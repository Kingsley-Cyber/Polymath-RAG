# Reranking and Fusion

Reranking reorders candidate results using a cross-representation model that reads the query and candidate together. The fused candidate set is reranked, but per-lane ablations stay untouched.

Reciprocal-rank fusion combines lanes before reranking. Each lane contributes its ranking, and the fusion favors items that multiple lanes agree on.

Rerankers fail loudly. If the reranker is unavailable, the request fails with an explicit error rather than silently falling back to unfiltered candidates.

Reranking improves precision without changing recall: the candidate set is fixed before reranking, and only the ordering changes.
