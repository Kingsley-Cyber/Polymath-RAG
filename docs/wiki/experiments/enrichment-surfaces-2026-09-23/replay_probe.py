"""ENRICHMENT-SURFACES-AUDIT (2026-09-23) — two in-process replays of real owner turns. No LLM call (local embedder,
reranker, Qdrant, Postgres only); nothing is written.

1. Resolution lift: for one recent turn per intent, replay its frozen `meta.chat_plan` through
   `chat_retrieval.chat_retrieve_mode("HYBRID", …)` and print the lifted terms and how many lift chunks reach the output.
2. Bridge compiler input: run the Profile Scout on three real questions and print the concept labels
   `bridge_integration.concepts_from_nominations` hands to the bridge compiler.

usage (main checkout; in a worktree use that tree's dirs):
  set -a; . ./.env; set +a
  PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control \
    .venv/bin/python docs/wiki/experiments/enrichment-surfaces-2026-09-23/replay_probe.py [out.json]
"""
import datetime
import json
import os
import sys

import psycopg
from orchestrator.api import chat_retrieval as cr
from orchestrator.api import ui
from polymath_shared.bridge_integration import concepts_from_nominations
from polymath_shared.query_intent import apply_intent_policy, policy_for

BRIDGE_QIDS = ("q_24f4aa2ac2bd46dea6d75022", "q_fce07375af524276b401af96", "q_6a4e34eed36841c093009713")
KINDS = {"THEORY", "CONCEPT", "SEEALSO", "BRIDGE", "ANCHOR", "RECALLQ", "LATENT_PATTERN", "INVERSION", "TENSION", "BOUNDARY"}


def one_turn_per_intent(conn):
    with conn.cursor() as c:
        c.execute("""select distinct on (meta->'chat_plan'->>'intent') query_id from query_receipts
                     where kind='chat_stream' and status='ok' and meta ? 'funnel' and meta->'chat_plan' ? 'intent'
                       and jsonb_array_length(coalesce(meta->'funnel'->'lanes'->'resolution_lift','[]'::jsonb)) > 0
                       and received_at > now() - interval '7 days'
                     order by meta->'chat_plan'->>'intent', received_at desc""")
        return [r[0] for r in c.fetchall()]


def lift_replay(conn, qid):
    with conn.cursor() as c:
        c.execute("select meta->'chat_plan', corpus_ids from query_receipts where query_id=%s", (qid,))
        cp, corpora = c.fetchone()
    corpus = (corpora or ["cinema"])[0]
    budget = apply_intent_policy(cp["intent"], cr.default_budget())
    pol = policy_for(cp["intent"])
    subs = tuple((q["id"], q["type"], q["query"], q["weight"], q.get("origin", "")) for q in cp["queries"] if q["type"] != "PRIMARY")
    bridge_ids = tuple(q["id"] for q in cp["queries"] if q.get("origin", "") in ui.LATENT_ORIGINS)
    out = cr.chat_retrieve_mode("HYBRID", cp["retrieval_query"], corpus, graph_useful=bool(cp.get("graph_useful")),
                                graph_assist=pol.graph if pol else "off", budget=budget,
                                exact_terms=tuple(cp.get("exact_terms") or ()), subqueries=subs, latent_bridge_ids=bridge_ids)
    tr = out.get("trace") or {}
    lift = tr.get("resolution_lift") or {}
    lift_ids = set((tr.get("funnel_lanes") or {}).get("resolution_lift") or [])
    items = out.get("evidence") or out.get("items") or out.get("candidates") or []
    in_out = sum(1 for it in items if (it.get("chunk_id") if isinstance(it, dict) else getattr(it, "chunk_id", None)) in lift_ids)
    return {"query_id": qid, "intent": cp["intent"], "q0": cp["retrieval_query"][:120], "lifted_terms": lift.get("terms"),
            "lift_candidates": lift.get("candidates"), "lift_chunks_in_output": in_out, "lane_ms": lift.get("lane_ms")}


def bridge_labels(conn, qid):
    with conn.cursor() as c:
        c.execute("select question_head from query_receipts where query_id=%s", (qid,))
        head = c.fetchone()[0]
    _titles, scout, _rec = ui._profile_scout(head, ["cinema"])
    noms = getattr(scout, "nominations", None) or (scout or {}).get("nominations") or ()
    labels = [x.label for x in concepts_from_nominations(noms)]
    return {"query_id": qid, "question_head": head[:80], "labels": labels,
            "kind_names": sum(1 for x in labels if x in KINDS), "raw_doc_ids": sum(1 for x in labels if x.startswith("doc_")),
            "other_text": sum(1 for x in labels if x not in KINDS and not x.startswith("doc_"))}


def main():
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"])
    out = {"generated_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
           "resolution_lift": [lift_replay(conn, q) for q in one_turn_per_intent(conn)],
           "bridge_compiler_concepts": [bridge_labels(conn, q) for q in BRIDGE_QIDS]}
    conn.close()
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
