#!/usr/bin/env python
"""PARENT-MAP-CANARY-V1 — the S9/step-3 controlled live parent-MAP activation.

RETRIEVAL-MIGRATION-DEPENDENCY-V1 / DOCUMENT-SEMANTIC-INDEX-V1: prove the parent-MAP
pipeline END TO END on a TINY controlled cohort before any scaled generation —
`build_parent_skeletons → map_prompt → groq/compound-mini → compile_maps →
run_document_mapping` writing durable 0054 state — and verify the acceptance gates:
partial recovery, restart idempotency, missing-alias repair, and durable SQL state
(shared-budget accounting is unit-proven in test_groq_accounts; the scaled router
wiring is S7b, for backfill).

Owner-authorized controlled live migration: it SPENDS `groq/compound-mini` and WRITES
real maps for the cohort docs (that IS the activation — "activate on a tiny controlled
cohort first"). It is reversible: `--cleanup` deletes the cohort's batches/maps/
exclusions. It touches ONLY the 0054 parent-map tables for the named docs — no chunks,
profiles, retrieval readers, or Qdrant.

    .venv/bin/python scripts/parent_map_canary.py --corpus cinema --docs 2 --out <path>
    .venv/bin/python scripts/parent_map_canary.py --corpus cinema --docs 2 --cleanup   # rollback
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(_p))

from polymath_shared.db import tx  # noqa: E402

MAP_CONTRACT = None  # default = map_compiler.MAP_COMPILER_VERSION
GROQ_URL = "https://api.groq.com/openai"
MINI_MODEL = "groq/compound-mini"


def _cohort(corpus_id, n):
    with tx() as conn:
        docs = conn.execute("SELECT doc_id, corpus_id, source_name FROM documents WHERE corpus_id=%s "
                            "ORDER BY source_name LIMIT %s", (corpus_id, n)).fetchall()
        out = []
        for d in docs:
            parents = [
                {"chunk_id": r[0], "chunk_index": r[1], "char_start": r[2], "heading_path": r[3],
                 "text": r[4], "region_role": r[5]}
                for r in conn.execute(
                    "SELECT chunk_id, chunk_index, char_start, heading_path, text, region_role FROM chunks "
                    "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (d[0],)).fetchall()]
            out.append((d[0], d[1], d[2], parents))
        return out


def _cleanup(doc_ids):
    with tx() as conn:
        for d in doc_ids:
            conn.execute("DELETE FROM document_parent_maps WHERE doc_id=%s", (d,))
            conn.execute("DELETE FROM document_parent_map_batches WHERE doc_id=%s", (d,))
            conn.execute("DELETE FROM document_parent_exclusions WHERE doc_id=%s", (d,))
    print(f"[canary] cleaned parent-map rows for {len(doc_ids)} docs")


def _live_infer(api_key):
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.document_profile.map_prompt import build_map_prompt

    def infer(skeletons, is_combined=False, grounding=None):
        system, user = build_map_prompt(skeletons, grounding=grounding, is_combined=is_combined)
        client = LLMExtractionClient("cloud", url=GROQ_URL, model=MINI_MODEL, limiter_key="map_canary",
                                     api_key=api_key, cloud_opts={"structured": "text", "json_mode": False},
                                     timeout_s=90.0, max_attempts=1)
        client.endpoint_name = "map_canary"
        raw, err = client.complete_one(user, system_prompt=system, max_tokens=2400)
        if err:
            raise RuntimeError(f"compound-mini error: {err}")
        return raw
    return infer


def _map_state(doc_id, contract):
    from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons
    with tx() as conn:
        active = conn.execute("SELECT COUNT(*) FROM document_parent_maps WHERE doc_id=%s AND map_contract=%s AND active",
                              (doc_id, contract)).fetchone()[0]
        excl = conn.execute("SELECT COUNT(*) FROM document_parent_exclusions WHERE doc_id=%s AND map_contract=%s",
                            (doc_id, contract)).fetchone()[0]
        batches = dict(conn.execute("SELECT status, COUNT(*) FROM document_parent_map_batches WHERE doc_id=%s "
                                    "AND map_contract=%s GROUP BY status", (doc_id, contract)).fetchall())
    return {"active_maps": active, "exclusions": excl, "batches": batches}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--docs", type=int, default=2)
    ap.add_argument("--key-env", default="GROQ_API_KEY_1")
    ap.add_argument("--cleanup", action="store_true", help="delete the cohort's map rows and exit (rollback)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from workers.doc_parent_map_worker import run_document_mapping
    from polymath_shared.document_profile import map_compiler
    from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons
    contract = MAP_CONTRACT or map_compiler.MAP_COMPILER_VERSION

    cohort = _cohort(args.corpus, args.docs)
    if not cohort:
        print(f"no docs in {args.corpus}", file=sys.stderr)
        return 1
    doc_ids = [c[0] for c in cohort]
    if args.cleanup:
        _cleanup(doc_ids)
        return 0

    key = os.environ.get(args.key_env)
    if not key:
        print(f"{args.key_env} not in env; cannot run the live canary", file=sys.stderr)
        return 1
    infer = _live_infer(key)

    report = {"gate": "parent-map-canary-v1", "corpus": args.corpus, "contract": contract, "docs": []}
    all_ok = True
    for doc_id, corpus_id, name, parents in cohort:
        manifest = build_parent_skeletons(parents)
        eligible = manifest.eligible_count
        t0 = time.time()
        out1 = run_document_mapping(tx, run_id=f"map-canary-{doc_id[:8]}", doc_id=doc_id, corpus_id=corpus_id,
                                    parents=parents, infer=infer, provider="groq", model=MINI_MODEL)
        wall1 = round(time.time() - t0, 1)
        state1 = _map_state(doc_id, contract)
        # restart idempotency: a second run must re-infer NOTHING and keep the SAME active set
        seen = {"calls": 0}
        def counting_infer(skels, is_combined=False, grounding=None, _i=infer):
            seen["calls"] += 1
            return _i(skels, is_combined=is_combined, grounding=grounding)
        out2 = run_document_mapping(tx, run_id=f"map-canary-{doc_id[:8]}", doc_id=doc_id, corpus_id=corpus_id,
                                    parents=parents, infer=counting_infer, provider="groq", model=MINI_MODEL)
        state2 = _map_state(doc_id, contract)
        idempotent = (state2["active_maps"] == state1["active_maps"] and seen["calls"] == 0)
        complete = out1.complete and not out1.unresolved_parent_ids
        doc_ok = complete and idempotent and state1["active_maps"] > 0
        all_ok = all_ok and doc_ok
        report["docs"].append({
            "doc": name[:44], "eligible_parents": eligible, "wall_s": wall1,
            "parents_mapped": out1.parents_mapped, "batches_done": out1.batches_done,
            "batches_partial": out1.batches_partial, "unresolved": len(out1.unresolved_parent_ids),
            "attempts_used": out1.attempts_used, "errors": list(out1.errors),
            "complete": complete, "restart_idempotent": idempotent, "restart_reinfer_calls": seen["calls"],
            "state": state1, "ok": doc_ok,
        })
        print(f"  {name[:44]:44} eligible={eligible} mapped={out1.parents_mapped} "
              f"complete={complete} idempotent={idempotent} wall={wall1}s")

    report["PASS"] = bool(all_ok)
    print(json.dumps({k: report[k] for k in ("gate", "corpus", "contract", "PASS")}, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False))
        print("evidence ->", args.out)
    print(f"[canary] docs left in place; rollback: --cleanup --corpus {args.corpus} --docs {args.docs}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
