"""ENRICHMENT-SURFACES-AUDIT §10 (2026-09-23) — does WILDCARD's abstract frontier fire on real turns? Replays the most
recent WILDCARD turns that retrieved (turns whose compiler skipped retrieval have an empty plan and are left out)
through `chat_retrieval.chat_retrieve_mode("WILDCARD", …)` in-process. No LLM call (local embedder, reranker, Qdrant);
nothing is written. Records the frontier receipt (candidates, verified / unverified bridges, timings) and each bridge's
principle. Whether the bridges then reach the synthesis prompt as [A#] is NOT observable here or in the receipts.

usage: set -a; . ./.env; set +a
  PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control \
    .venv/bin/python docs/wiki/experiments/enrichment-surfaces-2026-09-23/wildcard_probe.py [n] [out.json]
"""
import datetime
import json
import os
import sys

import psycopg
from orchestrator.api import chat_retrieval as cr
from orchestrator.api import ui
from polymath_shared.query_intent import apply_intent_policy, policy_for

RECEIPT_KEYS = ("returned", "verified_bridges", "unverified_bridges", "degraded", "sweep_ms", "finish_ms",
                "latent_candidates", "atom_candidates")
LATENT_CHANNELS = {"abstraction", "transfer"}


def atom_frontier(q0: str, corpus_id: str) -> dict:
    """The same calls the WILDCARD sweep makes for its atom frontier (chat_retrieval.py:907-920), run directly so a
    failure is visible (in the live path it sits in a bare `except: pass` with no receipt)."""
    from orchestrator.api.fast import _embed_queries
    from polymath_shared.document_profile import parent_map_projection as pmp
    from polymath_shared.document_profile import profile_atom_projection as pap
    from polymath_shared.embedding_contracts import active_contract
    from qdrant_client import QdrantClient
    client = QdrantClient(url="http://127.0.0.1:6334", timeout=60)
    try:
        qvec = tuple(_embed_queries([q0])[0])
        cid = active_contract().contract_id
        atoms = pap.search_atoms(client, pap.collection_name(cid), qvec, cr._WILDCARD_ATOM_KINDS, k=12, corpus_ids=[corpus_id])
        docs = list(dict.fromkeys(a.get("doc_id") for a in atoms if a.get("doc_id")))
        maps = pmp.search_parent_maps(client, pmp.collection_name(cid), qvec, docs, k=16) if docs else []
        parents = cr.merge_atom_frontier({}, atoms, maps)
        return {"atoms": len(atoms), "atom_texts": [f"{a.get('atom_kind')}: {str(a.get('text'))[:70]}" for a in atoms[:4]],
                "maps": len(maps), "atom_nominated_parents": len(parents), "error": None}
    except Exception as exc:  # noqa: BLE001 — the probe reports the failure instead of hiding it
        return {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    finally:
        client.close()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"])
    with conn.cursor() as c:
        c.execute("""select query_id, meta->'chat_plan', corpus_ids from query_receipts
                     where kind='chat_stream' and status='ok' and mode='WILDCARD' and meta->'chat_plan' ? 'intent'
                       and coalesce(meta->'chat_plan'->>'retrieval_query', '') <> ''
                       and received_at > now() - interval '7 days'
                     order by received_at desc limit %s""", (n,))
        rows = c.fetchall()
    conn.close()
    turns = []
    for qid, cp, corpora in rows:
        budget = apply_intent_policy(cp["intent"], cr.default_budget())
        pol = policy_for(cp["intent"])
        subs = tuple((q["id"], q["type"], q["query"], q["weight"], q.get("origin", "")) for q in cp["queries"]
                     if q["type"] != "PRIMARY")
        bridge_ids = tuple(q["id"] for q in cp["queries"] if q.get("origin", "") in ui.LATENT_ORIGINS)
        out = cr.chat_retrieve_mode("WILDCARD", cp["retrieval_query"], (corpora or ["cinema"])[0],
                                    graph_useful=bool(cp.get("graph_useful")), graph_assist=pol.graph if pol else "off",
                                    budget=budget, exact_terms=tuple(cp.get("exact_terms") or ()), subqueries=subs,
                                    latent_bridge_ids=bridge_ids)
        rec = (out.get("meta") or {}).get("wildcard") or {}
        bridges = out.get("wildcard") or []
        turns.append({"query_id": qid, "intent": cp["intent"], "q0": cp["retrieval_query"][:120],
                      "receipt": {k: rec.get(k) for k in RECEIPT_KEYS},
                      "bridges_from_atom_channels": sum(1 for b in bridges if set(b.get("channels") or ()) - LATENT_CHANNELS),
                      "atom_frontier_direct": atom_frontier(cp["retrieval_query"], (corpora or ["cinema"])[0]),
                      "bridges": [{"verified": b.get("verified"), "principle": str(b.get("principle") or "")[:200],
                                   "why_it_may_transfer": str(b.get("why_it_may_transfer") or "")[:200],
                                   "source_name": b.get("source_name"), "channels": b.get("channels")}
                                  for b in bridges]})
    out = {"generated_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"), "turns": turns}
    text = json.dumps(out, indent=1, default=str)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
