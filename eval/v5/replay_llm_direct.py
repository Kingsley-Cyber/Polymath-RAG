#!/usr/bin/env python3
"""LLM-DIRECT-REPLAY-V1 (LLM-DIRECT-CANON P3, ADR-0017) — deterministic replay
from the ledger of RAW LLM RESPONSES.

The historical replay (`replay_full.py`) proved determinism of the syntax-
interpreter path (sentence-slice manifest → rule pack → compiler), which the
production path does not run. This one proves the LLM-direct claim that
matters: given the stored raw responses (`extraction_call_receipts.raw_text`)
and the stored chunks, sanitize → gate → materialize is a pure function —
the SAME fact-id set comes out, byte for byte (fact ids are content hashes).

  .venv/bin/python eval/v5/replay_llm_direct.py --doc <doc_id>
  .venv/bin/python eval/v5/replay_llm_direct.py --corpus <corpus_id> [--record-evidence]

READ-ONLY: materialize runs against a capturing fake connection; nothing is
written. `--record-evidence` writes eval/v5/release_evidence/exact_replay.json
(release_gates EXACT_REPLAY contract: integer extra / missing +
declared_exceptions). A document extracted under an OLDER gate version
legitimately replays with `extra` facts — the evidence names the gate
version so the two populations are never confused.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

import psycopg  # noqa: E402

DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
OUT = pathlib.Path(__file__).resolve().parent / "release_evidence" / "exact_replay.json"
GATE_VERSION = "attestation-levels-v1"


class _CaptureCursor:
    def __init__(self, sink: dict):
        self.sink = sink; self.rowcount = 1

    def execute(self, sql: str, params=None):
        head = " ".join(sql.split())[:40]
        if head.startswith("INSERT INTO facts"):
            self.sink.setdefault("facts", set()).add(params[0])
        elif head.startswith("INSERT INTO evidence"):
            self.sink.setdefault("evidence", set()).add(params[0])
        elif head.startswith("INSERT INTO entities"):
            self.sink.setdefault("entities", set()).add(params[0])
        elif head.startswith("INSERT INTO mentions"):
            self.sink.setdefault("mentions", set()).add(params[0])
        self.rowcount = 1

    def __enter__(self): return self
    def __exit__(self, *a): return False


class _CaptureConn:
    def __init__(self): self.sink: dict = {}
    def cursor(self): return _CaptureCursor(self.sink)


def _recover_batches(neighborhoods, receipt_ids: set[str]):
    """Recover each receipt's batch WITHOUT trusting today's limiter state:
    production packs CONTIGUOUS neighborhoods (≤ NEIGHBORHOODS_PER_CALL) and
    re-issues single neighborhoods, so every receipt key is the hash of a
    contiguous window. Enumerate the windows, keep the ones whose key exists."""
    from workers import llm_provider as lp
    from polymath_shared.identity import content_hash as _chash   # the provider's own key hash
    ident = _chash({"contract": lp.contract_identity()})
    per_call = int(getattr(lp, "NEIGHBORHOODS_PER_CALL", 8) or 8)
    found = {}
    for i in range(len(neighborhoods)):
        for k in range(1, per_call + 1):
            batch = neighborhoods[i:i + k]
            if len(batch) < k:
                break
            key = "ecr_" + _chash({"ident": ident, "batch": [(n.nid, n.chunks) for n in batch]})[:40]
            if key in receipt_ids:
                found[key] = batch
    return found


def replay_doc(conn, doc_id: str, policy: str | None = None) -> dict:
    """LLM-DIRECT-REPLAY-V1: every stored raw response for the document is
    re-run through the SAME sanitize/alias path as a live call
    (`LLMExtractionClient.extract_from_raw`), items are merged per
    neighborhood with production's rule (a later response for the same
    neighborhood replaces the earlier one), then gate → materialize against
    a capturing connection. No network, no writes."""
    if policy:
        os.environ["POLYMATH_EXTRACTION_ATTESTATION"] = policy
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.gate import ChunkView, attestation_policy, validate_and_normalize
    from workers import llm_direct, llm_provider
    corpus_id = conn.execute("SELECT corpus_id FROM documents WHERE doc_id=%s", (doc_id,)).fetchone()[0]
    cols = ["chunk_id", "doc_id", "parent_id", "chunk_index", "tier", "text", "char_start", "char_end",
            "region_role", "heading_path", "token_count"]
    rows = [dict(zip(cols, r)) for r in conn.execute(
        f"SELECT {', '.join('c.' + c for c in cols)} FROM chunks c WHERE c.doc_id=%s ORDER BY c.char_start, c.chunk_id",
        (doc_id,)).fetchall()]
    children = [r for r in rows if r["tier"] == "child"]
    chunk_rows = {r["chunk_id"]: r for r in rows}
    neighborhoods = llm_provider.build_neighborhoods(children)
    views_by_nid = {n.nid: [ChunkView(cid, text) for cid, text in n.chunks] for n in neighborhoods}
    receipts = conn.execute(
        "SELECT receipt_id, lane, model, raw_text, created_at FROM extraction_call_receipts WHERE doc_id=%s "
        "ORDER BY created_at, receipt_id", (doc_id,)).fetchall()
    batches = _recover_batches(neighborhoods, {r[0] for r in receipts})
    unmatched = [r[0] for r in receipts if r[0] not in batches]
    items: dict[str, object] = {}
    template = None; lane = model = None; quarantined = 0
    for rid_, l, m, raw, _ts in receipts:
        if rid_ not in batches:
            continue
        client = LLMExtractionClient.__new__(LLMExtractionClient)   # no transport: extract_from_raw only reads lane/model
        client.lane, client.model = l, m
        res = client.extract_from_raw([(n.nid, n.chunks) for n in batches[rid_]], raw or "")
        if res.packet is None:
            quarantined += 1; continue
        template = template or res.packet; lane, model = l, m
        for it in res.packet.items:
            if it.neighborhood_id in views_by_nid:
                items[it.neighborhood_id] = it
    ordered = [items[n.nid] for n in neighborhoods if n.nid in items]
    merged = (validate_and_normalize(template.model_copy(update={"items": ordered}), views_by_nid)
              if template is not None and ordered else None)
    cap = _CaptureConn(); stats = {}
    if merged is not None:
        stats = llm_direct.materialize(cap, corpus_id=corpus_id, doc_id=doc_id, chunk_rows=chunk_rows,
                                       merged=merged, lane=lane or "replay", model=model or "replay")
    replayed = cap.sink.get("facts", set())
    prod = {r[0] for r in conn.execute(
        """SELECT DISTINCT f.fact_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
            WHERE ev.doc_id=%s AND f.extractor_version='llm-direct-v1'""", (doc_id,)).fetchall()}
    disp = conn.execute(
        """SELECT a.payload->'llm_extraction'->'neighborhood_dispositions' FROM artifacts a
            JOIN runs r ON r.run_id=a.run_id JOIN documents d ON d.corpus_id=r.corpus_id AND d.source_name=r.metadata->>'source_name'
           WHERE a.stage='extract' AND d.doc_id=%s ORDER BY a.created_at DESC LIMIT 1""", (doc_id,)).fetchone()
    declared = sorted(x.get("nid") for x in (disp[0] if disp and disp[0] else [])
                      if isinstance(x, dict) and x.get("disposition") in ("incomplete_kept", "dropped", "unaccounted"))
    return {"doc_id": doc_id, "corpus_id": corpus_id, "lane": lane, "children": len(children),
            "neighborhoods": len(neighborhoods), "receipts": len(receipts), "receipts_matched": len(batches),
            "receipts_unmatched": unmatched, "receipts_quarantined": quarantined,
            "neighborhoods_with_items": len(ordered), "attestation_policy": attestation_policy(),
            "replayed_facts": len(replayed), "production_facts": len(prod),
            "extra": len(replayed - prod), "missing": len(prod - replayed),
            "declared_exception_neighborhoods": declared,
            "gate_stats": ({k: merged.stats.get(k) for k in ("relations", "relations_rejected", "endpoint_attestation")}
                           if merged is not None else {}),
            "materialize": {k: stats.get(k) for k in ("seen", "endpoint_attestation")}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc"); ap.add_argument("--corpus")
    ap.add_argument("--record-evidence", action="store_true")
    ap.add_argument("--policy", choices=("tiered", "strict"), default=None,
                    help="gate policy for the replay (A/B on the same raw responses)")
    a = ap.parse_args()
    if not (a.doc or a.corpus):
        ap.error("pass --doc or --corpus")
    with psycopg.connect(DSN) as conn:
        docs = [a.doc] if a.doc else [r[0] for r in conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s ORDER BY created_at", (a.corpus,)).fetchall()]
        reports = [replay_doc(conn, d, a.policy) for d in docs]
    extra = sum(r["extra"] for r in reports); missing = sum(r["missing"] for r in reports)
    verdict = "IDENTICAL" if extra == 0 and missing == 0 and reports else "DIVERGENT"
    print(json.dumps({"verdict": verdict, "extra": extra, "missing": missing, "docs": reports}, indent=1, default=str), file=sys.stderr if a.record_evidence else sys.stdout)
    if a.record_evidence:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({
            "contract": "LLM-DIRECT-REPLAY-V1 (raw-response ledger → sanitize → gate → materialize)",
            "gate_version": GATE_VERSION, "attestation_policy": reports[0]["attestation_policy"] if reports else None,
            "corpus": a.corpus, "docs": [r["doc_id"] for r in reports],
            "replayed_facts": sum(r["replayed_facts"] for r in reports),
            "production_facts": sum(r["production_facts"] for r in reports),
            "extra": extra, "missing": missing,
            "declared_exceptions": sorted({n for r in reports for n in r["declared_exception_neighborhoods"]}),
            "verdict": verdict,
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "producer": "eval/v5/replay_llm_direct.py --record-evidence"}, indent=1))
        print(f"evidence written: {OUT}")
    return 0 if verdict == "IDENTICAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
