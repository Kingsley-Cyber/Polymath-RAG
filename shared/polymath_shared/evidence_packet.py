"""REASONING-BOUNDARY-V1 RB1 — EvidencePacket, the agent-facing evidence contract (pure).

The chat pipeline already computes everything an external agent needs (roles, CA4 grade, provenance,
corpus-explore receipts) BEFORE it synthesizes an answer. This module maps that internal bundle into a
versioned, size-bounded `EvidencePacket` so Claude Code / Hermes can retrieve validated corpus evidence and
do their OWN final reasoning — with NO nested Polymath synthesis LLM. `synthesis_performed=false` is a
first-class field: the packet is evidence, never an answer.

Pure + tolerant: `build_evidence_packet` takes already-extracted, normalized inputs (dict rows + a CA4-grade
map + plan queries + bounded receipts) so it is unit-testable offline. The live short-circuit in the
orchestrator extracts these from the chat bundle and calls this; nothing here imports the runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = "evidence-packet-v1"
DEFAULT_MAX_ROWS = 40           # bound the packet — agents don't need the whole union
DEFAULT_MAX_TEXT = 1200         # per-row text cap (chars)
DEFAULT_MAX_RECEIPT_ITEMS = 12  # bound receipt lists

_DIRECT = "DIRECT"
#: utility_role vocabulary the packet exposes (owner): the C5 seat role when a latent chunk was seated,
#: else DIRECT for q0/direct evidence. The finer synthesis_role (PRECISION/RELATIONAL/LATENT) rides along
#: as an auxiliary field so nothing is lost.
_SEAT_ROLES = ("COMPLEMENTARY", "DIVERGENT")


def _get(row, *names, default=None):
    for n in names:
        v = row.get(n) if isinstance(row, dict) else getattr(row, n, None)
        if v is not None:
            return v
    return default


@dataclass(frozen=True)
class EvidenceItem:
    chunk_id: str
    document_id: str
    source: str
    text: str
    origin: str                                  # provenance of the primary retrieving query (USER/PROFILE/BRIDGE/CORPUS_EXPLORE/GRAPH)
    query_ids: tuple[str, ...]
    lineage: tuple[dict, ...]                     # [{query_id, origin, role}] many-to-one
    utility_role: str                            # DIRECT / COMPLEMENTARY / DIVERGENT
    synthesis_role: str | None                   # DIRECT / PRECISION / RELATIONAL / LATENT (auxiliary)
    ca4_grade: str | None                        # DIRECT / PARTIAL / RELATED
    c4_valid: bool
    provenance: dict                             # {origin, inspired_by_profile[], derived_from, relation_to_q0}

    def to_dict(self) -> dict:
        return {"chunk_id": self.chunk_id, "document_id": self.document_id, "source": self.source,
                "text": self.text, "origin": self.origin, "query_ids": list(self.query_ids),
                "lineage": [dict(l) for l in self.lineage], "utility_role": self.utility_role,
                "synthesis_role": self.synthesis_role, "ca4_grade": self.ca4_grade,
                "c4_valid": self.c4_valid, "provenance": dict(self.provenance)}


@dataclass(frozen=True)
class EvidencePacket:
    q0: str
    retrieval_mode: str
    plan: dict
    evidence: tuple[EvidenceItem, ...]
    receipts: dict
    schema_version: str = SCHEMA_VERSION
    synthesis_performed: bool = False

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "q0": self.q0,
                "retrieval_mode": self.retrieval_mode, "synthesis_performed": self.synthesis_performed,
                "plan": self.plan, "evidence": [e.to_dict() for e in self.evidence],
                "receipts": self.receipts}


def _plan_index(plan_queries):
    """id -> {origin, role, inspired_by_profile, target, reason, query} for lineage/provenance joins."""
    out = {}
    for q in (plan_queries or ()):
        qid = str(_get(q, "id", default=""))
        if not qid:
            continue
        out[qid] = {
            "origin": _get(q, "origin", default="USER") or "USER",
            "role": _get(q, "role", "type", default=""),
            "inspired_by_profile": list(_get(q, "inspired_by_profile", default=[]) or []),
            "target": _get(q, "target", default=None),
            "reason": _get(q, "reason", default=None),
        }
    return out


def _utility_role(row) -> str:
    seat = str(_get(row, "latent_role", "seat_role", default="") or "").upper()
    if seat in _SEAT_ROLES:
        return seat
    syn = str(_get(row, "role", "synthesis_role", default="") or "").upper()
    return _DIRECT if syn == _DIRECT else (seat or _DIRECT)


def _c4_valid(grade, row) -> bool:
    """A chunk is treated as C4-valid for answerability when it graded DIRECT/PARTIAL or was C5-seated as a
    COMPLEMENTARY/DIVERGENT latent. A RELATED-only chunk that was never seated is NOT answerability-valid."""
    g = (grade or "").upper()
    if g in ("DIRECT", "PARTIAL"):
        return True
    return str(_get(row, "latent_role", "seat_role", default="") or "").upper() in _SEAT_ROLES


def _bound_receipt(value, max_items=DEFAULT_MAX_RECEIPT_ITEMS):
    """Keep receipts small: dicts pass through (already summaries); lists are truncated."""
    if isinstance(value, list):
        return value[:max_items]
    return value


def build_evidence_packet(
    *,
    q0: str,
    retrieval_mode: str,
    plan_queries,
    evidence_rows,
    ca4_grades=None,
    receipts=None,
    corpus_explorer_requested: bool = False,
    corpus_explorer_used: bool = False,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_text: int = DEFAULT_MAX_TEXT,
) -> EvidencePacket:
    """Map an internal chat evidence bundle → a bounded EvidencePacket. PURE.

    `evidence_rows`: the pre-synthesis evidence dicts (chunk_id/doc_id/source_name/text/query_ids/role/
    latent_role/latent_lineage/...). `ca4_grades`: {chunk_id: DIRECT|PARTIAL|RELATED} from `grade_evidence`.
    `plan_queries`: the compiled plan queries (for origin/lineage/provenance joins). `receipts`: the bounded
    compiler receipts {activation, bridges, corpus_explore, fusion}. Deterministic; row-, text- and
    receipt-bounded; `synthesis_performed` is always False (this is evidence, not an answer).
    """
    ca4_grades = ca4_grades or {}
    pidx = _plan_index(plan_queries)

    items: list[EvidenceItem] = []
    for row in list(evidence_rows or ())[:max(0, int(max_rows))]:
        cid = str(_get(row, "chunk_id", "id", default="") or "")
        if not cid:
            continue
        qids = [str(x) for x in (_get(row, "query_ids", "source_query_ids", default=[]) or [])]
        lineage = [{"query_id": qid, "origin": pidx.get(qid, {}).get("origin", "USER"),
                    "role": pidx.get(qid, {}).get("role", "")} for qid in qids]
        # primary origin = the first non-USER origin among the row's queries, else USER (q0-direct)
        origin = next((l["origin"] for l in lineage if l["origin"] != "USER"), None) \
            or (lineage[0]["origin"] if lineage else "USER")
        prov_src = next((pidx[qid] for qid in qids if qid in pidx and pidx[qid]["origin"] != "USER"), None)
        lat = _get(row, "latent_lineage", default=None) or {}
        provenance = {
            "origin": origin,
            "inspired_by_profile": (prov_src or {}).get("inspired_by_profile", []),
            "derived_from": (prov_src or {}).get("target"),
            "relation_to_q0": (prov_src or {}).get("reason") or (lat.get("proposed_role") if isinstance(lat, dict) else None),
        }
        grade = ca4_grades.get(cid)
        text = str(_get(row, "text", default="") or "")[: max(0, int(max_text))]
        items.append(EvidenceItem(
            chunk_id=cid,
            document_id=str(_get(row, "doc_id", "document_id", default="") or ""),
            source=str(_get(row, "source", "source_name", "human_locator", "title", default="") or ""),
            text=text, origin=origin, query_ids=tuple(qids), lineage=tuple(lineage),
            utility_role=_utility_role(row),
            synthesis_role=(str(_get(row, "role", "synthesis_role", default="")).upper() or None),
            ca4_grade=(grade.upper() if isinstance(grade, str) else grade),
            c4_valid=_c4_valid(grade, row), provenance=provenance))

    plan = {
        "compiled_queries": [
            {"id": qid, "origin": meta["origin"], "role": meta["role"]}
            for qid, meta in pidx.items()
        ],
        "corpus_explorer_requested": bool(corpus_explorer_requested),
        "corpus_explorer_used": bool(corpus_explorer_used),
    }
    receipts = {k: _bound_receipt(v) for k, v in (receipts or {}).items()
                if k in ("activation", "bridges", "corpus_explore", "fusion")}
    return EvidencePacket(q0=q0, retrieval_mode=retrieval_mode, plan=plan,
                          evidence=tuple(items), receipts=receipts)
