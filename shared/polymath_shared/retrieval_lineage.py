"""WLK2C C0 — query-anchored retrieval lineage (pure, deterministic, no I/O, no model).

Every non-q0 candidate should remember WHY it was retrieved, so downstream selection can distinguish
DIRECT answer evidence (chunk ↔ q0) from bounded COMPLEMENTARY / DIVERGENT latent knowledge that has an
explainable grounded bridge back to q0. This module is the LINEAGE representation + its derivation from
signals that already exist on the plan and the candidate — the subqueries that retrieved it
(`query_ids` → the compiled plan) and the lanes it arrived on (`arrivals`).

Two invariants the owner locked before C1/C2:

  1. **Many-to-one until admission.** A chunk can be discovered through several legitimate paths
     (a PROFILE bridge, a GRAPH path, a WILDCARD bridge, the primary q0). C0 records EVERY path and
     never collapses to one winner — otherwise we lose exactly the evidence we mean to preserve. C4
     picks the best ADMISSIBLE path at evidence admission.
  2. **Lineage existence ≠ bridge validity.** Recording how a candidate was found says nothing about
     whether that path is strong enough to rescue it. C0 only records; C1 checks bridge admissibility;
     C4/C5 decide the role. A candidate retrieved by the PRIMARY has a q0 path (DIRECT-eligible);
     q0 always stays the answer authority.

Bridge GENERATION is C2; bridge ADMISSIBILITY is C1; role ADMISSION is C5. Here we only stop flattening
every candidate back to `(q0, chunk)`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: discovered_by vocabulary — the retrieval lane a candidate arrived on (mode-independent signal).
DISCOVERY_LANES = ("HIERARCHY", "DENSE", "SPARSE", "GRAPH", "WILDCARD", "NEIGHBOR")
#: origin_query provenance — where an anchoring query came from. Extends chat_plan.ORIGIN_TYPES with the
#: WLK2C bridge sources (WILDCARD/BRIDGE) that C1/C2 populate; C0 only observes USER/PROFILE/GRAPH/….
LINEAGE_ORIGINS = ("USER", "PROFILE", "GRAPH", "WILDCARD", "BRIDGE", "EVIDENCE_GAP")

#: map a candidate's `arrival` stamp (candidate_engine.LANE_* / ARRIVAL_* / pass1 / latent.rescue) to a
#: discovered_by lane. Unknown stamps are ignored (never guessed).
_ARRIVAL_TO_LANE = {
    "HIERARCHICAL_ROUTE": "HIERARCHY", "DOCUMENT_LED": "HIERARCHY", "SECTION_LED": "HIERARCHY",
    "GLOBAL_DENSE_CHILD": "DENSE", "GLOBAL_CHILD_RESCUE": "DENSE", "MULTI_REPRESENTATION": "DENSE",
    "GLOBAL_SPARSE_CHILD": "SPARSE",
    "GRAPH_DEST": "GRAPH",
    "NEIGHBOR_EXPANSION": "NEIGHBOR",
    "LATENT_RESCUE": "WILDCARD",
}


def _qget(q, attr, default=None):
    """Duck-typed read of a compiled-query descriptor (a CompiledQuery object or a plain dict) — the
    module stays dependency-free (no import of chat_plan, no cycle)."""
    if isinstance(q, dict):
        return q.get(attr, default)
    return getattr(q, attr, default)


@dataclass
class DiscoveryPath:
    """ONE legitimate way a candidate was retrieved. C0 records every path and NEVER judges whether it
    is a valid bridge (that is C1) or picks a winner (that is C4)."""
    origin_query: str                     # the query/subquery/bridge text for this path
    origin: str                           # provenance (LINEAGE_ORIGINS)
    query_id: str | None                  # the subquery id (None ⇒ the PRIMARY q0 path)
    bridge_id: str | None                 # == query_id for a non-primary path; None for the q0 path
    inspired_by_profile: list = field(default_factory=list)
    weight: float = 0.0                   # the subquery's plan weight (ordering hint, NOT admission)
    score: float | None = None            # per-query lane contribution (query_scores), when present

    def __post_init__(self) -> None:
        if self.origin not in LINEAGE_ORIGINS:
            self.origin = "USER"
        if not isinstance(self.inspired_by_profile, list):
            self.inspired_by_profile = list(self.inspired_by_profile)

    @property
    def is_primary(self) -> bool:
        """The q0 path — the user's own question retrieved this candidate (DIRECT-eligible)."""
        return self.bridge_id is None

    def to_dict(self) -> dict:
        return {"origin_query": self.origin_query, "origin": self.origin, "query_id": self.query_id,
                "bridge_id": self.bridge_id, "inspired_by_profile": list(self.inspired_by_profile),
                "weight": self.weight, "score": self.score}


@dataclass
class Lineage:
    """WHY a candidate exists in the pool — ALL of its discovery paths (many-to-one), never collapsed.
    JSON-native (round-trips through the receipt)."""
    root_query: str                       # q0 — the primary compiled query (the answer authority)
    paths: list = field(default_factory=list)             # every DiscoveryPath
    discovered_by: list = field(default_factory=list)     # candidate-level lanes (DISCOVERY_LANES)

    def __post_init__(self) -> None:
        if not isinstance(self.paths, list):
            self.paths = list(self.paths)
        if not isinstance(self.discovered_by, list):
            self.discovered_by = list(self.discovered_by)

    @property
    def is_direct(self) -> bool:
        """A q0 (primary) path exists — the candidate was retrieved by the user's own question."""
        return any(p.is_primary for p in self.paths)

    def bridge_paths(self) -> list:
        """Non-primary paths — candidate bridges PRE-admissibility (C1 judges validity, C4 selects)."""
        return [p for p in self.paths if not p.is_primary]

    def to_dict(self) -> dict:
        return {"root_query": self.root_query, "is_direct": self.is_direct,
                "discovered_by": list(self.discovered_by), "paths": [p.to_dict() for p in self.paths]}


def primary_text(queries) -> str:
    """The PRIMARY (q0) compiled query text — the lineage root. Falls back to the first query."""
    for q in (queries or []):
        if _qget(q, "type") == "PRIMARY":
            return _qget(q, "query", "") or ""
    return (_qget(queries[0], "query", "") if queries else "") or ""


def derive_lineage(row: dict, queries, *, primary_id: str = "q0") -> Lineage:
    """Pure lineage of ONE candidate row from the plan's `queries` and the row's own `query_ids` /
    `arrivals` / `query_scores`. `queries` = the plan's compiled queries (CompiledQuery objects or
    dicts, duck-typed). Records ONE DiscoveryPath per retrieving query (many-to-one, never collapsed);
    a candidate with no resolvable retrieving query falls open to a single q0 (DIRECT) path.
    """
    qidx = {str(_qget(q, "id")): q for q in (queries or []) if _qget(q, "id") is not None}
    root = primary_text(queries)
    scores = row.get("query_scores") or {}
    paths: list[DiscoveryPath] = []
    seen: set[str] = set()
    for qid in (row.get("query_ids") or []):
        key = str(qid)
        if key in seen or key not in qidx:
            continue
        seen.add(key)
        q = qidx[key]
        is_primary = (_qget(q, "type") == "PRIMARY") or (key == str(primary_id))
        paths.append(DiscoveryPath(
            origin_query=(root if is_primary else (_qget(q, "query", "") or root)),
            origin=("USER" if is_primary else (_qget(q, "origin", "USER") or "USER")),
            query_id=(None if is_primary else key),
            bridge_id=(None if is_primary else key),
            inspired_by_profile=list(_qget(q, "inspired_by_profile", []) or []),
            weight=float(_qget(q, "weight", 0.0) or 0.0),
            score=(scores.get(key) if isinstance(scores, dict) else None)))
    if not paths:                                          # fail open to q0 — DIRECT lineage, never empty
        paths.append(DiscoveryPath(origin_query=root, origin="USER", query_id=None, bridge_id=None))
    # deterministic order: primary first, then by descending weight, then id
    paths.sort(key=lambda p: (0 if p.is_primary else 1, -(p.weight or 0.0), str(p.query_id or "")))
    arrivals = row.get("arrivals") or ([row["arrival"]] if row.get("arrival") else [])
    lanes: list[str] = []
    for a in arrivals:
        lane = _ARRIVAL_TO_LANE.get(a)
        if lane and lane not in lanes:
            lanes.append(lane)
    return Lineage(root_query=root, paths=paths, discovered_by=lanes)


def annotate_lineage(rows: list[dict], queries, *, primary_id: str = "q0") -> list[dict]:
    """Attach `row['lineage']` = derive_lineage(...).to_dict() to each evidence row in place; returns
    the same list. Pure + deterministic; safe with an empty plan (every row → a single q0/DIRECT path)."""
    for r in rows:
        r["lineage"] = derive_lineage(r, queries, primary_id=primary_id).to_dict()
    return rows
