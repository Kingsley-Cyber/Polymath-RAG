"""CORPUS-MAP-PLANNING-V1: the stored corpus map becomes an ACTIVE,
scoped query-planning prior.

The map (corpus_summaries + the vocabulary layer's concept_families/
concept_aliases) answers "what does this corpus contain and what does
it call it?" — it is navigation and candidate priors, NEVER factual
authority, NEVER evidence, NEVER a source of invented relationships
(D4 charter, unchanged). Before this module the map was built and
persisted but no production retrieval consumer read it (SMART
verification REQ-008): the intended layer was inactive.

What planning contributes, deterministically:
  - matched neighborhoods: which mapped concepts/entities/predicates
    and document clusters the query's own terms touch, with the map
    row id and the supporting document-summary ids (provenance);
  - vocabulary expansion: a query term that matches a concept-family
    ALIAS contributes the family's canonical name (and vice versa) as
    EXPANSION TERMS — latent-neighborhood discovery ("RAG" finds the
    corpus that says "retrieval augmented generation");
  - scope is the resolved QUERY-SCOPE-V1 corpus set and only narrows.

Consumers use expansion terms as ADDITIONAL scoring terms against the
same stored objects; every answer element still resolves to persisted
rows with their own provenance. The map changes where retrieval LOOKS,
never what counts as knowledge.
"""
from __future__ import annotations

from polymath_shared.retrieval import tokens

CORPUS_MAP_PLANNING_VERSION = "corpus-map-planning-v1"


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _term_matches(term: str, surface: str) -> bool:
    """Bidirectional substring containment — the existing seed-surface
    convention (_surface_matches)."""
    t, s = _norm(term), _norm(surface)
    return bool(t) and bool(s) and (t in s or s in t)


def plan_with_corpus_map(conn, scope, question: str) -> dict:
    """Deterministic scoped map consultation. Pure read; no writes."""
    terms = sorted(t for t in tokens(question) if len(t) >= 3)
    corpus_ids = list(scope.corpus_ids)

    maps = conn.execute(
        """SELECT DISTINCT ON (corpus_id)
                  summary_id, corpus_id, important_entities,
                  dominant_concepts, common_predicates, document_clusters
             FROM corpus_summaries
            WHERE corpus_id = ANY(%s)
            ORDER BY corpus_id, created_at DESC""",
        (corpus_ids,)).fetchall()

    fam_rows = conn.execute(
        """SELECT f.concept_id, f.corpus_id, f.canonical_name,
                  COALESCE(array_agg(a.alias) FILTER (WHERE a.alias IS NOT NULL),
                           '{}') AS aliases
             FROM concept_families f
             LEFT JOIN concept_aliases a ON a.concept_id = f.concept_id
            WHERE f.corpus_id = ANY(%s)
            GROUP BY f.concept_id, f.corpus_id, f.canonical_name""",
        (corpus_ids,)).fetchall()

    neighborhoods: list[dict] = []
    expansion_terms: list[str] = []
    seen_expansions: set[str] = set()

    def _expand(term: str, source: str, corpus_id: str, reason: str):
        key = _norm(term)
        if key and key not in seen_expansions and key not in set(terms):
            seen_expansions.add(key)
            expansion_terms.append(term)
        neighborhoods.append({
            "corpus_id": corpus_id,
            "source": source,
            "matched": term,
            "reason": reason,
        })

    for summary_id, corpus_id, entities, concepts, predicates, clusters in maps:
        for kind, values in (("entity", entities or []),
                             ("concept", concepts or []),
                             ("predicate", predicates or [])):
            for surface in values:
                hit = [t for t in terms if _term_matches(t, surface)]
                if hit:
                    neighborhoods.append({
                        "corpus_id": corpus_id,
                        "source": f"corpus_map_{kind}",
                        "map_summary_id": summary_id,
                        "matched": surface,
                        "query_terms": hit,
                        "reason": f"query term(s) {hit} touch mapped "
                                  f"{kind} {surface!r}",
                    })
        for cluster in (clusters or []):
            label = cluster.get("label") if isinstance(cluster, dict) else None
            if label and any(_term_matches(t, label) for t in terms):
                neighborhoods.append({
                    "corpus_id": corpus_id,
                    "source": "corpus_map_cluster",
                    "map_summary_id": summary_id,
                    "matched": label,
                    "document_summary_ids": (cluster.get(
                        "document_summary_ids") or []),
                    "reason": f"query touches document cluster {label!r}",
                })

    for concept_id, corpus_id, canonical, aliases in fam_rows:
        surfaces = [canonical] + list(aliases or [])
        for surface in surfaces:
            hit = [t for t in terms if _term_matches(t, surface)]
            if not hit:
                continue
            # vocabulary bridge: every OTHER surface of the family is a
            # candidate expansion term for the same neighborhood.
            for other in surfaces:
                if _norm(other) != _norm(surface):
                    _expand(other, "vocabulary_family", corpus_id,
                            f"family {concept_id} bridges {surface!r} "
                            f"→ {other!r} (matched {hit})")
            break

    return {
        "contract": CORPUS_MAP_PLANNING_VERSION,
        "consulted": bool(maps) or bool(fam_rows),
        "scope_corpus_ids": corpus_ids,
        "query_terms": terms,
        "neighborhoods": neighborhoods,
        "expansion_terms": expansion_terms,
    }
