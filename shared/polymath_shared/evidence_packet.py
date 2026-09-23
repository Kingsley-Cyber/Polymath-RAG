"""REASONING-BOUNDARY-V1 RB1 — EvidencePacket, the agent-facing evidence contract (pure).

The chat pipeline already computes everything an external agent needs (roles, CA4 grade, provenance,
corpus-explore receipts) BEFORE it synthesizes an answer. This module maps that internal bundle into a
versioned, size-bounded `EvidencePacket` so Claude Code / Hermes can retrieve validated corpus evidence and
do their OWN final reasoning — with NO nested Polymath synthesis LLM. `synthesis_performed=false` is a
first-class field: the packet is evidence, never an answer.

Pure + tolerant: `build_evidence_packet` takes already-extracted, normalized inputs (dict rows + a CA4-grade
map + plan queries + bounded receipts) so it is unit-testable offline. The live short-circuit in the
orchestrator extracts these from the chat bundle and calls this; nothing here imports the runtime.

TEXT IS EVIDENCE, NOT A PREVIEW (RB5, 2026-09-20). The chat pipeline's evidence inventory carries a 240-character
UI preview of each chunk; a packet built from it handed agents snippets and said nothing about it. The packet now
presents a bounded VERBATIM EXCERPT of the retrieved chunk (`full_texts`, resolved by the caller for exactly the rows
already selected) and states what it did: `text_truncated` and `text_chars`. This is presentation only — the rows,
their order, ids, roles, grades, lineage and provenance come from the same inputs as before and are untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = "evidence-packet-v1"
DEFAULT_MAX_ROWS = 40           # bound the packet — agents don't need the whole union
DEFAULT_MAX_TEXT = 900          # per-row excerpt cap (chars): enough passage to reason over, still a bounded packet
DEFAULT_MAX_RECEIPT_ITEMS = 12  # bound receipt lists

_DIRECT = "DIRECT"
#: utility_role vocabulary the packet exposes (owner): the C5 seat role when a latent chunk was seated,
#: else DIRECT for q0/direct evidence. The finer synthesis_role (PRECISION/RELATIONAL/LATENT) rides along
#: as an auxiliary field so nothing is lost.
_SEAT_ROLES = ("COMPLEMENTARY", "DIVERGENT")


def _has(row, name) -> bool:
    return (name in row) if isinstance(row, dict) else hasattr(row, name)


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
    text_truncated: bool | None = None           # True = `text` is a prefix of a longer chunk; None = the chunk length is unknown
    text_chars: int | None = None                # length of the retrieved chunk the excerpt was cut from (None = unknown)

    def to_dict(self) -> dict:
        return {"chunk_id": self.chunk_id, "document_id": self.document_id, "source": self.source,
                "text": self.text, "text_truncated": self.text_truncated, "text_chars": self.text_chars,
                "origin": self.origin, "query_ids": list(self.query_ids),
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
    """id -> {origin, role, inspired_by_profile, target, derived_from, reason} for lineage/provenance joins.
    E7: `derived_from` is its own field. A legacy row (a receipt written before E7, with no `derived_from` key)
    still resolves through `target`, which then held the reference."""
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
            "derived_from": (_get(q, "derived_from", default=None) if _has(q, "derived_from")
                             else _get(q, "target", default=None)),
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


def excerpt(text: str, max_chars: int) -> tuple[str, bool]:
    """A bounded VERBATIM prefix of `text` and whether anything was cut. The cut falls on the last whitespace inside the
    final fifth of the window (never mid-word when a boundary is near); nothing is appended, so the excerpt stays a quote."""
    text = str(text or "")
    cap = max(0, int(max_chars))
    if len(text) <= cap:
        return text, False
    head = text[:cap]
    cut = max(head.rfind(" "), head.rfind("\n"), head.rfind("\t"))
    if cut >= int(cap * 0.8):
        head = head[:cut]
    return head.rstrip(), True


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
    full_texts=None,
) -> EvidencePacket:
    """Map an internal chat evidence bundle → a bounded EvidencePacket. PURE.

    `evidence_rows`: the pre-synthesis evidence dicts (chunk_id/doc_id/source_name/text/query_ids/role/
    latent_role/latent_lineage/...). `ca4_grades`: {chunk_id: DIRECT|PARTIAL|RELATED} from `grade_evidence`.
    `plan_queries`: the compiled plan queries (for origin/lineage/provenance joins). `receipts`: the bounded
    compiler receipts {activation, bridges, corpus_explore, fusion, firing}. Deterministic; row-, text- and
    receipt-bounded; `synthesis_performed` is always False (this is evidence, not an answer).

    `full_texts`: {chunk_id: the retrieved chunk's text}. When present for a row the packet's `text` is a bounded
    verbatim excerpt of THAT text (`text_truncated`, `text_chars` say what was cut). When absent the row's own `text` is
    used as before — and because the chat inventory's text is itself a preview of unknown provenance, the packet then
    says `text_truncated: None`, never a false "complete". Row membership and order never depend on `full_texts`.
    """
    ca4_grades = ca4_grades or {}
    full_texts = full_texts or {}
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
            "derived_from": (prov_src or {}).get("derived_from"),
            "relation_to_q0": (prov_src or {}).get("reason") or (lat.get("proposed_role") if isinstance(lat, dict) else None),
        }
        grade = ca4_grades.get(cid)
        full = full_texts.get(cid)
        if isinstance(full, str) and full:
            text, truncated = excerpt(full, max_text)
            text_chars = len(full)
        else:                                                  # no resolved chunk: present what the row carries, claim nothing
            text, cut = excerpt(str(_get(row, "text", default="") or ""), max_text)
            truncated, text_chars = (True if cut else None), None
        items.append(EvidenceItem(
            chunk_id=cid,
            document_id=str(_get(row, "doc_id", "document_id", default="") or ""),
            source=str(_get(row, "source", "source_name", "human_locator", "title", default="") or ""),
            text=text, origin=origin, query_ids=tuple(qids), lineage=tuple(lineage),
            utility_role=_utility_role(row),
            synthesis_role=(str(_get(row, "role", "synthesis_role", default="")).upper() or None),
            ca4_grade=(grade.upper() if isinstance(grade, str) else grade),
            c4_valid=_c4_valid(grade, row), provenance=provenance,
            text_truncated=truncated, text_chars=text_chars))

    plan = {
        "compiled_queries": [
            {"id": qid, "origin": meta["origin"], "role": meta["role"]}
            for qid, meta in pidx.items()
        ],
        "corpus_explorer_requested": bool(corpus_explorer_requested),
        "corpus_explorer_used": bool(corpus_explorer_used),
    }
    receipts = {k: _bound_receipt(v) for k, v in (receipts or {}).items()
                if k in ("activation", "bridges", "corpus_explore", "fusion", "firing")}
    return EvidencePacket(q0=q0, retrieval_mode=retrieval_mode, plan=plan,
                          evidence=tuple(items), receipts=receipts)
