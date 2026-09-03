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


def _window_keys(neighborhoods, ident: str | None = None) -> dict:
    """key -> contiguous window (≤ NEIGHBORHOODS_PER_CALL) under the provider's
    key rule, for the given contract identity (default: the live one)."""
    from workers import llm_provider as lp
    from polymath_shared.identity import content_hash as _chash
    ident = ident or _chash({"contract": lp.contract_identity()})
    per_call = int(getattr(lp, "NEIGHBORHOODS_PER_CALL", 8) or 8)
    out = {}
    for i in range(len(neighborhoods)):
        for k in range(1, per_call + 1):
            batch = neighborhoods[i:i + k]
            if len(batch) < k:
                break
            out["ecr_" + _chash({"ident": ident, "batch": [(n.nid, n.chunks) for n in batch]})[:40]] = batch
    return out


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
    """LLM-DIRECT-REPLAY-V1: run the provider's OWN `run_proposals` with its
    receipt-cache seam — the same batching, alias maps, dispositions and
    reissue rules as production — with every call answered from
    `extraction_call_receipts` and the network forbidden; then gate →
    materialize against a capturing connection. No network, no writes.
    `_recover_batches` is the coverage diagnostic (which receipts exist)."""
    if policy:
        os.environ["POLYMATH_EXTRACTION_ATTESTATION"] = policy
    from polymath_shared.llm_extraction import client as _client_mod
    from polymath_shared.llm_extraction.gate import attestation_policy
    from workers import llm_direct, llm_provider
    corpus_id, byte_length = conn.execute(
        "SELECT corpus_id, byte_length FROM documents WHERE doc_id=%s", (doc_id,)).fetchone()
    cols = ["chunk_id", "doc_id", "parent_id", "chunk_index", "tier", "text", "char_start", "char_end",
            "region_role", "heading_path", "token_count"]
    rows = [dict(zip(cols, r)) for r in conn.execute(
        f"SELECT {', '.join('c.' + c for c in cols)} FROM chunks c WHERE c.doc_id=%s ORDER BY c.char_start, c.chunk_id",
        (doc_id,)).fetchall()]
    children = [r for r in rows if r["tier"] == "child"]
    chunk_rows = {r["chunk_id"]: r for r in rows}
    neighborhoods = llm_provider.build_neighborhoods(children)
    receipts = conn.execute(
        "SELECT receipt_id, lane, model, contract_ident FROM extraction_call_receipts WHERE doc_id=%s "
        "ORDER BY created_at, receipt_id", (doc_id,)).fetchall()
    lane = receipts[0][1] if receipts else "cloud"
    windows = _window_keys(neighborhoods)                       # live-era keys (what run_proposals will ask for)
    receipt_ids = {r[0] for r in receipts}
    # ERA TRANSLATION: a receipt is keyed under the identity that was live
    # when it was written. Map every live-era key to the same window's key
    # under each era present on this document (NULL = the live era).
    eras = {r[3] for r in receipts if r[3]} or set()
    era_keys: dict[str, str] = {}
    for era in eras:
        for k_old, w in _window_keys(neighborhoods, era).items():
            if k_old in receipt_ids:
                k_live = next((k for k, w2 in windows.items() if [n.nid for n in w2] == [n.nid for n in w]), None)
                if k_live:
                    era_keys[k_live] = k_old
    batches = {k: w for k, w in windows.items() if k in receipt_ids or k in era_keys}
    # finish_reason per response: the ledger column (new receipts) or the
    # extract artifact's per-call record matched by raw_head (older ones)
    fr_by_head: dict[str, str] = {}
    art = conn.execute(
        """SELECT a.payload->'llm_extraction'->'calls' FROM artifacts a
            JOIN runs r ON r.run_id=a.run_id JOIN documents d ON d.corpus_id=r.corpus_id AND d.source_name=r.metadata->>'source_name'
           WHERE a.stage='extract' AND d.doc_id=%s ORDER BY a.created_at DESC LIMIT 1""", (doc_id,)).fetchone()
    for call in (art[0] if art and isinstance(art[0], list) else []):
        if isinstance(call, dict) and call.get("raw_head"):
            fr_by_head[call["raw_head"]] = call.get("finish_reason")
    hits = {"n": 0, "miss": [], "fr_from_ledger": 0, "fr_from_artifact": 0}

    def cache_get(key):
        row = conn.execute("SELECT raw_text, finish_reason FROM extraction_call_receipts WHERE receipt_id=%s",
                           (era_keys.get(key, key),)).fetchone()
        if row:
            hits["n"] += 1
            raw, fr = row[0], row[1]
            if fr is not None:
                hits["fr_from_ledger"] += 1
            elif raw and raw[:200] in fr_by_head:
                fr = fr_by_head[raw[:200]]; hits["fr_from_artifact"] += 1
            return (raw, fr)
        hits["miss"].append([n.nid[-10:] for n in windows.get(key, [])] or key[:16])
        return None

    def cache_put(*a, **k):
        return None

    def _no_network(*a, **k):
        raise RuntimeError("replay attempted a network call — no receipt for that batch")

    saved = (_client_mod.LLMExtractionClient.extract, getattr(_client_mod.LLMExtractionClient, "extract_batched", None))
    _client_mod.LLMExtractionClient.extract = _no_network
    if saved[1] is not None:
        _client_mod.LLMExtractionClient.extract_batched = _no_network
    error = None; results = []; merged = None
    try:
        results, merged = llm_provider.run_proposals(
            neighborhoods, lane=lane, source_bytes=int(byte_length or 0), doc_id=doc_id,
            call_cache=(cache_get, cache_put))
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {str(exc)[:200]}"
    finally:
        _client_mod.LLMExtractionClient.extract = saved[0]
        if saved[1] is not None:
            _client_mod.LLMExtractionClient.extract_batched = saved[1]
    cap = _CaptureConn(); stats = {}
    if merged is not None:
        model = next((r.model for r in results if getattr(r, "model", None)), "replay")
        stats = llm_direct.materialize(cap, corpus_id=corpus_id, doc_id=doc_id, chunk_rows=chunk_rows,
                                       merged=merged, lane=lane, model=model)
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
            "cache_hits": hits["n"], "cache_misses": len(hits["miss"]), "missed_batches": hits["miss"][:6],
            "finish_reason_sources": {"ledger": hits["fr_from_ledger"], "artifact": hits["fr_from_artifact"]},
            "eras_on_document": sorted(eras), "era_translated_keys": len(era_keys),
            "error": error,
            "attestation_policy": attestation_policy(),
            "replayed_facts": len(replayed), "production_facts": len(prod),
            "extra": len(replayed - prod), "missing": len(prod - replayed),
            "declared_exception_neighborhoods": declared,
            "dispositions": (dict(__import__("collections").Counter(d["disposition"] for d in merged.dispositions))
                             if merged is not None and getattr(merged, "dispositions", None) else {}),
            "gate_stats": ({k: merged.stats.get(k) for k in ("relations", "relations_rejected", "endpoint_attestation",
                                                              "neighborhoods_sent", "neighborhoods_reissued", "neighborhoods_dropped")}
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
