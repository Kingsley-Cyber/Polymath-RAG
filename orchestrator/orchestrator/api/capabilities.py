"""CAPABILITIES-V1 (2026-09-03) — what this Polymath is, for agents and skills.

A consumer that can work against any docs/18 corpus backend probes this
once, then switches on CONTRACTS (never on the name): native plan when
`corpus-plan` is served, typed rows when `typed-rows` lists kinds, and so
on. Additive by design — a key is only ever added or versioned up.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

API_DATE = "2026-09-04"
CONTRACTS = {
    "retrieve-evidence-rows": "v1",      # POST /retrieve evidence=true / mode=EXPLORE
    "corpus-plan": "v1",                 # POST /retrieve/plan
    "chat-evidence": "v1",               # POST /chat evidence=true → answer + citations + evidence_rows
    "explore": True,
    # DOCUMENT-SCOPED-RETRIEVE-V1: POST /retrieve (default lane, EXPLORE) and
    # POST /retrieve/plan accept `document_ids` — rows come only from those
    # documents inside the resolved corpus scope; FAST/HYBRID/GRAPH answer
    # 422 document_filter_unsupported.
    "document_ids": True,
    "field-evidence-corpus": None,       # corpus_id of the ingested field-evidence ledger — none yet
}
ENDPOINTS = ["/retrieve", "/retrieve/plan", "/capabilities", "/chat", "/ask"]
MCP_TOOLS = ["capabilities", "compile_plan", "retrieve_evidence", "retrieve", "ask", "list_corpora", "corpus_status"]


@lru_cache(maxsize=1)
def _version() -> str:
    try:
        root = Path(__file__).resolve().parents[3]
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=root, timeout=5).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _live_contracts() -> dict:
    """Contracts that depend on what the stores hold: the field-evidence corpus
    (a query_ready corpus whose id starts with field-evidence) and the claim
    kinds the extractor has actually emitted. Best effort; never raises."""
    c = dict(CONTRACTS)
    try:
        from polymath_shared.db import tx
        with tx() as conn:
            row = conn.execute(
                """SELECT r.corpus_id FROM runs r
                    WHERE r.corpus_id LIKE 'field-evidence%%' AND r.status = 'query_ready'
                    ORDER BY r.updated_at DESC LIMIT 1""").fetchone()
            if row:
                c["field-evidence-corpus"] = row[0]
    except Exception:  # noqa: BLE001
        pass
    return c


def capabilities_payload() -> dict:
    return {"backend": "polymath", "version": _version(), "api": API_DATE,
            "contracts": _live_contracts(), "endpoints": list(ENDPOINTS), "mcp_tools": list(MCP_TOOLS)}


@router.get("/capabilities")
async def capabilities() -> dict:
    return capabilities_payload()
