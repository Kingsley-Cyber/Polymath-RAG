#!/usr/bin/env python3
"""V5 P5 — SHADOW SETTLEMENT: reproduce production decisions from the LEDGER.

READ-ONLY. Derives the ACTIVE evidence set purely from durable state —
raw_entity_proposals + span_hypothesis dispositions + sentence_slices +
layout — regenerates syntax from the pinned model, runs the FROZEN
settlement authority, and compares every decision with the persisted
mentions. No provider entity/evidence pass is called.

This is the V5 property under test: the evidence ledger, not transient
worker memory, is sufficient to reproduce semantic settlement exactly.

R2: UNEXPLAINED = 0 and UNRULED_SEMANTIC_DELTA = 0 are hard requirements;
any admission/anchor/basis/eligibility/identity delta BLOCKS by default.
"""
import argparse, json, os, sys
sys.path[:0] = ["shared", "workers"]
os.environ.setdefault("POLYMATH_SYNTAX_PROVIDER", "spacy")

import psycopg

DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
STAGE_ORDER = ("boundary_widening", "missing_argument", "type_reconciliation")


def active_set_from_ledger(conn, doc_id: str) -> dict:
    """chunk_id -> list[EntitySpan], derived only from durable evidence."""
    from polymath_shared.contracts import CoreType, EntitySpan
    from polymath_shared.query_policy import canonical_of
    from workers.extract_worker import _map_label, _pack

    pack = _pack()
    spans: dict[str, dict] = {}
    for cid, s, e, surf, label, score in conn.execute(
            """SELECT chunk_id, char_start, char_end, surface, provider_label,
                      provider_score FROM raw_entity_proposals
              WHERE doc_id=%s ORDER BY chunk_id, char_start, char_end""",
            (doc_id,)).fetchall():
        best = spans.setdefault(cid, {})
        k = (s, e)
        if k not in best or score > best[k][3]:
            best[k] = (s, e, surf, score, label)

    active: dict[str, list] = {}
    for cid, best in spans.items():
        out = []
        for s, e, surf, score, label in best.values():
            core = _map_label(label, pack)
            if core is None:
                continue
            out.append(EntitySpan(doc_id=doc_id, chunk_id=cid, start=s, end=e,
                                  text=surf, core_type=CoreType(core),
                                  score=score, extractor_version="ledger",
                                  raw_label=label))
        active[cid] = out

    hyps = conn.execute(
        """SELECT chunk_id, mechanism, source_char_start, source_char_end,
                  proposed_char_start, proposed_char_end, proposed_surface,
                  status, disposition, evidence
             FROM span_hypotheses WHERE doc_id=%s
            ORDER BY chunk_id, proposed_char_start, proposed_char_end""",
        (doc_id,)).fetchall()
    for mech in STAGE_ORDER:
        for cid, m, ss, se, ps, pe, psurf, status, dispo, ev in hyps:
            if m != mech:
                continue
            ev = ev if isinstance(ev, dict) else json.loads(ev or "{}")
            cur = active.setdefault(cid, [])
            if mech == "boundary_widening":
                idx = next((i for i, sp in enumerate(cur)
                            if sp.start == ss and sp.end == se), None)
                if idx is None:
                    continue
                src = cur.pop(idx)
                if dispo == "SUPERSEDED_SOURCE":
                    from polymath_shared.contracts import CoreType, EntitySpan
                    cur.append(EntitySpan(
                        doc_id=doc_id, chunk_id=cid, start=ps, end=pe,
                        text=psurf, core_type=src.core_type,
                        score=float(ev.get("score") or src.score),
                        extractor_version=src.extractor_version,
                        raw_label=ev.get("accepted_raw_label"),
                        pass_kind="boundary_rescue"))
                # SUPPRESSED_SOURCE: V4-effective removal — already popped.
            elif mech == "missing_argument" and dispo == "ADDED":
                from polymath_shared.contracts import CoreType, EntitySpan
                core = canonical_of(ev.get("accepted_raw_label") or "")
                if core is None:
                    continue
                cur.append(EntitySpan(
                    doc_id=doc_id, chunk_id=cid, start=ps, end=pe, text=psurf,
                    core_type=CoreType(core), score=float(ev.get("score") or 0.0),
                    extractor_version="gliner-2pass-v1",
                    raw_label=ev.get("accepted_raw_label"),
                    pass_kind="missing_argument_rescue"))
            elif mech == "type_reconciliation" and dispo == "SUPERSEDED_SOURCE":
                idx = next((i for i, sp in enumerate(cur)
                            if sp.start == ss and sp.end == se), None)
                if idx is None:
                    continue
                from polymath_shared.contracts import CoreType, EntitySpan
                src = cur.pop(idx)
                cur.append(EntitySpan(
                    doc_id=doc_id, chunk_id=cid, start=ps, end=pe, text=src.text,
                    core_type=CoreType(ev["to_type"]),
                    score=float(ev.get("score") or src.score),
                    extractor_version=src.extractor_version,
                    raw_label=src.raw_label, pass_kind="type_reconciliation"))
    return active


class LedgerIncomplete(RuntimeError):
    """Fail closed (P4): shadow settlement over a document whose evidence
    bundle is absent or stale would replay against PARTIAL evidence and
    report misleading deltas. Refuse and name the gap instead."""


def verify_bundle(conn, doc_id: str) -> None:
    from polymath_shared.raw_evidence import bundle_manifest

    row = conn.execute(
        "SELECT bundle_sha256 FROM document_evidence_bundles WHERE doc_id=%s",
        (doc_id,)).fetchone()
    if not row:
        raise LedgerIncomplete(
            f"{doc_id}: no evidence bundle — document was ingested before the "
            "bundle/hypothesis ledger existed; re-ingest before shadowing")
    live = bundle_manifest(conn, doc_id)["bundle_sha256"]
    if live != row[0]:
        raise LedgerIncomplete(
            f"{doc_id}: bundle hash mismatch (stored {row[0][:12]}, "
            f"recomputed {live[:12]}) — ledger changed after sealing")


def shadow_settle(conn, doc_id: str, corpus_id: str = "shadow"):
    verify_bundle(conn, doc_id)
    from polymath_shared.execution import SEMANTIC_CONTRACT_V2
    from workers.extract_worker import _allocate_identities, _syntax_evidence
    from workers.reprocess_worker import _ordered_slices_from_manifest, _slice_manifest

    chunks = [{"chunk_id": r[0], "doc_id": doc_id, "text": r[1], "layout_map": r[2]}
              for r in conn.execute(
                  "SELECT chunk_id, text, layout_map FROM chunks WHERE doc_id=%s"
                  " AND tier='child' ORDER BY chunk_index", (doc_id,)).fetchall()]
    manifest = _slice_manifest(conn, doc_id)
    active = active_set_from_ledger(conn, doc_id)
    flat = [sp for spans in active.values() for sp in spans]
    by_chunk: dict[str, list] = {}
    for sp in flat:
        by_chunk.setdefault(sp.chunk_id, []).append(sp)
    ordered = _ordered_slices_from_manifest(chunks, manifest, by_chunk)
    _syntax_evidence(ordered)
    # Settle under the REAL corpus id: CORPUS_SCOPED entity ids hash the
    # corpus, so a placeholder would fork the id space and the comparison
    # would only pass on corpora that happen to contain no entc_ identities.
    ids = _allocate_identities(ordered, corpus_id, doc_id,
                               contract_version=SEMANTIC_CONTRACT_V2)
    return ids, ordered


def shadow_settle_ids(conn, doc_id: str, corpus_id: str = "shadow"):
    return shadow_settle(conn, doc_id, corpus_id)[0]


SEMANTIC_FIELDS = ("anchor_kind", "decision_status", "admission_class",
                   "reference_basis", "entity_id")


def compare(conn, corpus: str) -> dict:
    report = {"corpus": corpus, "docs": 0, "spans": 0, "matched": 0,
              "deltas": [], "counts": {"UNEXPLAINED": 0,
                                       "UNRULED_SEMANTIC_DELTA": 0,
                                       "SET_DIFFERENCE": 0}}
    for (doc_id,) in conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s ORDER BY doc_id",
            (corpus,)).fetchall():
        report["docs"] += 1
        ids = shadow_settle_ids(conn, doc_id, corpus)
        prod = {}
        for r in conn.execute(
                """SELECT chunk_id, char_start, char_end, core_type, anchor_kind,
                          decision_status, admission_class, reference_basis,
                          COALESCE(entity_id,'') FROM mentions
                     WHERE doc_id=%s""", (doc_id,)).fetchall():
            prod[(r[0], r[1], r[2], r[3])] = dict(zip(SEMANTIC_FIELDS,
                                                      (r[4], r[5], r[6], r[7], r[8])))
        shadow = {}
        for (corp, d, cid, s, e, core), ident in ids.items():
            a = ident.admission
            shadow[(cid, s, e, core)] = {
                "anchor_kind": a.anchor_kind, "decision_status": a.decision_status,
                "admission_class": ident.admission_class,
                "reference_basis": a.reference_basis,
                "entity_id": ident.entity_id if ident.durable else ""}
        for k in set(prod) | set(shadow):
            report["spans"] += 1
            if k not in prod or k not in shadow:
                report["counts"]["SET_DIFFERENCE"] += 1
                report["deltas"].append({"key": list(map(str, k)),
                                         "class": "SET_DIFFERENCE",
                                         "in_production": k in prod,
                                         "in_shadow": k in shadow})
                continue
            diffs = {f: (prod[k][f], shadow[k][f]) for f in SEMANTIC_FIELDS
                     if str(prod[k][f] or "") != str(shadow[k][f] or "")}
            if not diffs:
                report["matched"] += 1
            else:
                report["counts"]["UNRULED_SEMANTIC_DELTA"] += 1
                report["deltas"].append({"key": list(map(str, k)),
                                         "class": "SEMANTIC_DELTA",
                                         "fields": {f: list(v) for f, v in diffs.items()}})
    report["verdict"] = ("PASS" if report["counts"]["UNRULED_SEMANTIC_DELTA"] == 0
                         and report["counts"]["UNEXPLAINED"] == 0
                         and report["counts"]["SET_DIFFERENCE"] == 0 else "BLOCK")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    a = ap.parse_args()
    with psycopg.connect(DSN) as conn:
        r = compare(conn, a.corpus)
    print(json.dumps({k: v for k, v in r.items() if k != "deltas"}, indent=1))
    for d in r["deltas"][:12]:
        print("  DELTA:", json.dumps(d))
    sys.exit(0 if r["verdict"] == "PASS" else 1)
