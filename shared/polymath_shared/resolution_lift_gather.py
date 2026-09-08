"""RESOLUTION-LIFT gatherer — turn the corpus's precision surfaces into ranked LiftCandidates.

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §10–§12: given the query + its initial evidence documents,
read the SOURCE-DERIVED precision surfaces (§11) — TERM/TOPIC, MAP semantic_hooks[] /
exact_identifiers[], entity/canonical aliases, heading paths, and profile-atom terminology —
build `LiftCandidate`s, and rank them (`resolution_lift.rank_lift_candidates`, ≤3). The
GATHERING is separated from the ranking so the reads (which store each surface lives in) can be
faked in tests and swapped without touching the §11 scoring. NO hardcoded domain vocabulary:
every candidate term comes from a corpus record.

`gather_lift_candidates` is pure over an injected `sources` object (any duck-typed provider of
the reader methods). `LiveLiftSources` implements those reads against Postgres + Qdrant.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from polymath_shared.resolution_lift import LiftCandidate, rank_lift_candidates


def gather_lift_candidates(query: str, *, doc_ids: Sequence[str], corpus_id: str, sources,
                           top_evidence_docs: Iterable[str] = (), query_exact_terms: Iterable[str] = (),
                           k: int = 3, corpus_doc_count: int | None = None,
                           atom_kinds: Sequence[str] | None = None) -> list[LiftCandidate]:
    """Read the §11 surfaces for `doc_ids`, plus corpus-level aliases, into ranked
    LiftCandidates (top `k`). `sources` provides: profile_terms(doc)->(topics,terms);
    map_terms(doc)->(hooks,ids); atom_terms(doc,kinds)->[(kind,text)]; headings(doc)->[str];
    aliases(corpus)->[(canonical,[alias,...])]; doc_frequency(term)->int|None."""
    tev = set(top_evidence_docs)
    cands: list[LiftCandidate] = []

    def _df(t: str):
        try:
            return sources.doc_frequency(t)
        except Exception:  # noqa: BLE001 — DF is optional (rarity falls back to mid)
            return None

    for d in doc_ids:
        local = d in tev
        try:
            topics, terms = sources.profile_terms(d)
        except Exception:  # noqa: BLE001
            topics, terms = [], []
        for t in terms:
            cands.append(LiftCandidate(t, "TERM", doc_id=d, in_top_evidence=local, doc_frequency=_df(t)))
        for t in topics:
            cands.append(LiftCandidate(t, "TOPIC", doc_id=d, in_top_evidence=local, doc_frequency=_df(t)))
        try:
            hooks, ids = sources.map_terms(d)
        except Exception:  # noqa: BLE001
            hooks, ids = [], []
        for t in ids:
            cands.append(LiftCandidate(t, "MAP_ID", doc_id=d, in_top_evidence=local, doc_frequency=_df(t)))
        for t in hooks:
            cands.append(LiftCandidate(t, "MAP_HOOK", doc_id=d, in_top_evidence=local, doc_frequency=_df(t)))
        try:
            for _kind, t in sources.atom_terms(d, atom_kinds):
                cands.append(LiftCandidate(t, "ATOM", doc_id=d, in_top_evidence=local, doc_frequency=_df(t)))
        except Exception:  # noqa: BLE001
            pass
        try:
            for t in sources.headings(d):
                cands.append(LiftCandidate(t, "HEADING", doc_id=d, in_top_evidence=local))
        except Exception:  # noqa: BLE001
            pass

    try:
        for canonical, aliases in sources.aliases(corpus_id):
            if canonical:
                cands.append(LiftCandidate(canonical, "ENTITY", canonical=True, doc_frequency=_df(canonical)))
            for a in (aliases or []):
                cands.append(LiftCandidate(a, "ALIAS", canonical=True, doc_frequency=_df(a)))
    except Exception:  # noqa: BLE001
        pass

    return rank_lift_candidates(cands, query, query_exact_terms=query_exact_terms, k=k,
                                corpus_doc_count=corpus_doc_count)


class LiveLiftSources:
    """The §11 reads against the live stores (P3 physical map). Read-only.

    Reuses the durable stores directly: the profile Qdrant payload (topics/terms), the
    `document_parent_maps` Postgres rows (semantic_hooks/exact_identifiers), the new
    `document_profile_atoms` rows (atom terminology), `chunks.heading_path`, and the
    `concept_families`/`concept_aliases` vocabulary bridge. Corpus DF is computed on the fly
    (a bounded lexical COUNT), memoized per instance.
    """

    def __init__(self, conn, client, *, corpus_id: str, embedding_contract_id: str,
                 map_contract: str | None = None, profile_contract: str | None = None,
                 compute_df: bool = False):
        self.conn = conn
        self.client = client
        self.corpus_id = corpus_id
        self.embedding_contract_id = embedding_contract_id
        self.map_contract = map_contract
        self.profile_contract = profile_contract
        #: corpus DF (rarity) has NO persisted inverted index (P3 map); the on-the-fly ILIKE
        #: scan is too slow for query time, so DF is OFF by default (rarity falls back to mid;
        #: the source prior / locality / identifier-form / canonicality signals carry ranking).
        #: GATED: a persisted corpus vocabulary index would let rarity contribute at query time.
        self.compute_df = compute_df
        self._df_cache: dict[str, int] = {}
        self._alias_cache = None

    def profile_terms(self, doc_id: str):
        from polymath_shared.document_profile import projection as PJ
        try:
            recs = self.client.retrieve(PJ.collection_name(self.embedding_contract_id),
                                        ids=[PJ.point_id(doc_id)], with_payload=["topics", "terms"])
        except Exception:  # noqa: BLE001
            return [], []
        if not recs:
            return [], []
        pl = recs[0].payload or {}
        return list(pl.get("topics") or []), list(pl.get("terms") or [])

    def map_terms(self, doc_id: str):
        clause = "AND map_contract=%s" if self.map_contract else ""
        params = [doc_id] + ([self.map_contract] if self.map_contract else [])
        rows = self.conn.execute(
            "SELECT semantic_hooks, exact_identifiers FROM document_parent_maps "
            "WHERE doc_id=%s AND active " + clause, tuple(params)).fetchall()
        hooks, ids = [], []
        for h, i in rows:
            hooks.extend(h or [])
            ids.extend(i or [])
        return hooks, ids

    def atom_terms(self, doc_id: str, kinds):
        from polymath_shared.document_profile.profile_atom import active_atoms
        atoms = active_atoms(self.conn, doc_id=doc_id, kinds=kinds)
        return [(a.kind, a.text) for a in atoms]

    def headings(self, doc_id: str):
        rows = self.conn.execute(
            "SELECT DISTINCT heading_path FROM chunks WHERE doc_id=%s AND heading_path IS NOT NULL",
            (doc_id,)).fetchall()
        out: list[str] = []
        for (hp,) in rows:
            for h in (hp or []):
                if h and h not in out:
                    out.append(h)
        return out

    def aliases(self, corpus_id: str):
        if self._alias_cache is None:
            try:
                rows = self.conn.execute(
                    "SELECT f.canonical_name, COALESCE(array_agg(a.alias) FILTER (WHERE a.alias IS NOT NULL),'{}') "
                    "FROM concept_families f LEFT JOIN concept_aliases a ON a.concept_id=f.concept_id "
                    "WHERE f.corpus_id=%s GROUP BY f.concept_id, f.canonical_name", (corpus_id,)).fetchall()
                self._alias_cache = [(r[0], list(r[1] or [])) for r in rows]
            except Exception:  # noqa: BLE001 — the concept-family layer may legitimately be empty
                self._alias_cache = []
        return self._alias_cache

    def doc_frequency(self, term: str):
        if not self.compute_df:
            return None                                   # fast path: rarity falls back to mid
        t = (term or "").strip()
        if not t:
            return None
        if t in self._df_cache:
            return self._df_cache[t]
        try:
            n = self.conn.execute(
                "SELECT count(DISTINCT doc_id) FROM chunks WHERE doc_id IN "
                "(SELECT doc_id FROM documents WHERE corpus_id=%s) AND text ILIKE %s",
                (self.corpus_id, f"%{t}%")).fetchone()[0]
        except Exception:  # noqa: BLE001
            n = None
        if n is not None:
            self._df_cache[t] = n
        return n
