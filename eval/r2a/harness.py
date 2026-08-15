"""R2A qualification harness: hierarchical packet builder + provider
client + scorer. Builds synthesis packets from production retrieval
output (GRAPH mode hierarchy), renders typed roles with stable IDs,
drives a local OpenAI-compatible generation provider with
temperature=0, and scores deterministic gates + gold judgments.

No production wiring: /chat, EvidenceBundle, retrieval untouched.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "orchestrator"))

from orchestrator.api.graph import graph_retrieve  # noqa: E402
from orchestrator.api.hybrid import hybrid_fast_retrieve  # noqa: E402

PROMPT_PATH = ROOT / "eval" / "r2a" / "synthesis_prompt_v1.txt"
PROMPT_VERSION = "synthesis-prompt-v1"
RESPONSE_CONTRACT = "synthesis-response-v1"


def prompt_hash() -> str:
    return hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()


def build_packet(query: str, corpus: str, mode: str = "GRAPH",
                 hierarchy: str = "hierarchical",
                 include_doc_summaries: bool = True,
                 include_section_summaries: bool = True,
                 include_graph: bool = True) -> tuple[str, dict]:
    """Deterministic synthesis packet from production retrieval."""
    g = graph_retrieve(query, corpus)
    lines = [f"QUERY: {query}", ""]
    ids: dict[str, str] = {}
    counter = {"c": 0, "g": 0}
    documents = g["documents"]

    def add_evidence(doc_id: str, parent_id: str, text_getter, items) -> None:
        for item in items:
            counter["c"] += 1
            cid = f"C{counter['c']}"
            text = text_getter(item)
            ids[cid] = {"kind": "CHILD_EVIDENCE", "doc_id": doc_id,
                        "parent_id": parent_id, "chunk_id": item["chunk_id"]}
            lines.append(f"CHILD_EVIDENCE {cid}:")
            lines.append(text.strip())
            lines.append("")

    with _tx_read() as conn:
        chunk_texts = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT chunk_id, text FROM chunks WHERE chunk_id = ANY(%s)",
                ([c["chunk_id"] for d in documents for s in d["sections"]
                  for c in s["evidence"]] +
                 [c["chunk_id"] for c in g.get("unassigned_rescue_evidence", [])],),
            ).fetchall()
        }
        section_texts = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT chunk_id, summary FROM chunks WHERE chunk_id = ANY(%s)",
                ([s["parent_id"] for d in documents for s in d["sections"]],),
            ).fetchall()
        }

    if hierarchy == "hierarchical":
        for doc in documents:
            lines.append(f"DOCUMENT {doc['doc_id']}:")
            if include_doc_summaries and doc.get("document_summary"):
                lines.append("DOCUMENT_SUMMARY_CONTEXT:")
                lines.append(doc["document_summary"].strip())
                lines.append("")
            for s in doc["sections"]:
                lines.append(f"SECTION {s['parent_id']}:")
                if include_section_summaries and s.get("summary"):
                    lines.append("SECTION_SUMMARY_CONTEXT:")
                    lines.append(s["summary"].strip())
                    lines.append("")
                for c in s["evidence"]:
                    counter["c"] += 1
                    cid = f"C{counter['c']}"
                    ids[cid] = {"kind": "CHILD_EVIDENCE", "doc_id": doc["doc_id"],
                                "parent_id": s["parent_id"], "chunk_id": c["chunk_id"]}
                    lines.append(f"CHILD_EVIDENCE {cid}:")
                    lines.append((chunk_texts.get(c["chunk_id"]) or "").strip())
                    lines.append("")
            if include_doc_summaries:
                for c in doc.get("rescue_evidence", []):
                    counter["c"] += 1
                    cid = f"C{counter['c']}"
                    ids[cid] = {"kind": "CHILD_EVIDENCE", "doc_id": doc["doc_id"],
                                "parent_id": "", "chunk_id": c["chunk_id"]}
                    lines.append(f"CHILD_EVIDENCE {cid}:")
                    lines.append((chunk_texts.get(c["chunk_id"]) or "").strip())
                    lines.append("")
        for c in g.get("unassigned_rescue_evidence", []):
            counter["c"] += 1
            cid = f"C{counter['c']}"
            ids[cid] = {"kind": "CHILD_EVIDENCE", "doc_id": c["doc_id"],
                        "parent_id": c["parent_id"], "chunk_id": c["chunk_id"]}
            lines.append(f"CHILD_EVIDENCE {cid}:")
            lines.append((chunk_texts.get(c["chunk_id"]) or "").strip())
            lines.append("")
    else:  # flat: all children as one list, no summaries
        seen = set()
        for d in documents:
            for s in d["sections"]:
                for c in s["evidence"]:
                    if c["chunk_id"] in seen:
                        continue
                    seen.add(c["chunk_id"])
                    counter["c"] += 1
                    cid = f"C{counter['c']}"
                    ids[cid] = {"kind": "CHILD_EVIDENCE", "doc_id": d["doc_id"],
                                "parent_id": s["parent_id"], "chunk_id": c["chunk_id"]}
                    lines.append(f"CHILD_EVIDENCE {cid}:")
                    lines.append((chunk_texts.get(c["chunk_id"]) or "").strip())
                    lines.append("")

    if include_graph and mode == "GRAPH":
        lines.append("GRAPH_EVIDENCE:")
        for f in g["graph_relationships"]:
            counter["g"] += 1
            gid = f"G{counter['g']}"
            ids[gid] = {"kind": "GRAPH_EVIDENCE", "fact_id": f["fact_id"]}
            lines.append(f"GRAPH_EVIDENCE {gid}:")
            lines.append(f"subject: {f['subject']}")
            lines.append(f"predicate: {f['predicate']}")
            lines.append(f"object: {f['object']}")
            lines.append("")

    packet = "\n".join(lines)
    return packet, {"ids": ids, "retrieval": g}


class Provider:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def generate(self, packet: str, max_output_tokens: int = 512) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PROMPT_PATH.read_text()},
                {"role": "user", "content": packet},
            ],
            "temperature": 0.0,
            "top_p": 1.0,
            "seed": 42,
            "max_tokens": max_output_tokens,
            "thinking": False,
            "response_format": {"type": "json_object"},
        }
        t0 = time.time()
        r = httpx.post(f"{self.base_url}/chat/completions", json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        return {
            "text": data["choices"][0]["message"]["content"],
            "latency_ms": (time.time() - t0) * 1000,
            "usage": data.get("usage", {}),
        }


def parse_response(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"answerable": None, "answer": text, "citations": [],
                "graph_facts_used": [], "abstention_reason": "unparseable",
                "parse_error": True}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"answerable": None, "answer": text, "citations": [],
                "graph_facts_used": [], "abstention_reason": "unparseable",
                "parse_error": True}


def score(gold: dict, parsed: dict, ids: dict) -> dict:
    """Deterministic gates + gold judgments. ids = packet id map."""
    out = {"query_id": gold["query_id"]}
    valid_ids = set(ids.keys())
    cited = set(parsed.get("citations") or [])
    graph_used = set(parsed.get("graph_facts_used") or [])

    out["invalid_citations"] = sorted(cited - valid_ids)
    out["invalid_graph_ids"] = sorted(graph_used - valid_ids)
    answerable = parsed.get("answerable")
    expected = gold.get("answerable")
    out["parse_error"] = bool(parsed.get("parse_error"))
    out["answerable_match"] = answerable == expected
    out["abstained_when_required"] = (
        expected is False and parsed.get("answerable") is False
    )
    out["answered_when_unsupported"] = (
        expected is False and answerable is True
    )
    # grounding: citations must be CHILD/GRAPH evidence, never summaries
    bad_kind = [
        c for c in cited
        if c in ids and ids[c]["kind"] not in ("CHILD_EVIDENCE", "GRAPH_EVIDENCE")
    ]
    out["summary_only_citations"] = bad_kind
    # topic checks on the answer text
    answer = (parsed.get("answer") or "").lower()
    out["required_topics_hit"] = sum(
        1 for t in gold.get("required_topics", []) if t.lower() in answer
    )
    out["required_topics_total"] = len(gold.get("required_topics", []))
    for f in gold.get("forbidden", []):
        if f.lower() in answer:
            out["forbidden_hit"] = out.get("forbidden_hit", []) + [f]
    out.setdefault("forbidden_hit", [])
    return out


def _tx_read():
    from polymath_shared.db import tx
    return tx()
