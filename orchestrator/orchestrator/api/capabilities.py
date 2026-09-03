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

API_DATE = "2026-09-03"
CONTRACTS = {
    "retrieve-evidence-rows": "v1",      # POST /retrieve evidence=true / mode=EXPLORE
    "corpus-plan": "v1",                 # POST /retrieve/plan
    "explore": True,
    "typed-rows": [],                    # claim kinds EXPLORE can return (friction/behavior/workaround/purchase_language) — none yet
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


def capabilities_payload() -> dict:
    return {"backend": "polymath", "version": _version(), "api": API_DATE,
            "contracts": dict(CONTRACTS), "endpoints": list(ENDPOINTS), "mcp_tools": list(MCP_TOOLS)}


@router.get("/capabilities")
async def capabilities() -> dict:
    return capabilities_payload()
