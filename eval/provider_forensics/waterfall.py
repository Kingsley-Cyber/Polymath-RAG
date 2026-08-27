#!/usr/bin/env python3
"""ENTITY-PROVIDER-FORENSICS-V1 — Output 1: failure waterfall.

READ-ONLY. Replays the extract stage in memory on the CURRENT accepted code
(including the known rescue-deletion defect) and records, for every case,
what existed at each stage:

    raw provider response    gliner.entity_pass(chunk, profile_labels, 0.5)
    after label mapping      _entity_spans (drops unmapped raw labels)
    after rescue             apply_rescue on reconstructed slices
    persisted mention        the mentions table (production truth)
    admission state          anchor_kind / entity_id / reason

The first stage where expected behavior diverges owns the failure. Nothing
is inferred from absence in the final table alone.
"""
import json, os, pathlib, sys
sys.path[:0] = ["shared", "workers"]
os.environ.setdefault("POLYMATH_SYNTAX_PROVIDER", "spacy")
os.environ.setdefault("POLYMATH_RESCUE", "on")
os.environ.setdefault("POLYMATH_WORKER_RULE_PACK_VERSION", "1.3.0")

import psycopg
from polymath_shared.clients import GlinerClient
from polymath_shared.contracts import DocumentProfile
from workers.extract_worker import (_entity_spans, _evidence_spans,
                                    _sentences_of, _slices, _syntax_evidence, _pack)
from workers.rescue import apply_rescue
from polymath_shared.settings import get_settings

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
C = "i4-fresh-acceptance-v1"

# (case_id, doc_tail, surface)
CASES = [
    ("A05s", "01_northvale_health.md", "radiology review board"),
    ("A07s", "02_nimbus_cloud.md", "Nimbus Cloud"),
    ("A09s", "02_nimbus_cloud.md", "Nimbus billing service"),
    ("A09o", "02_nimbus_cloud.md", "Nimbus Cloud platform"),
    ("A10o", "02_nimbus_cloud.md", "load-testing harness"),
    ("A14o", "03_crestline_automation.md", "shift scheduling model"),
    ("A16o", "03_crestline_automation.md", "quality database"),
    ("A12s", "03_crestline_automation.md", "Crestline plant"),
    ("A11s", "03_crestline_automation.md", "Crestline Automation"),
    ("TYP1", "02_nimbus_cloud.md", "Kubernetes"),
    ("LR1", "02_nimbus_cloud.md", "engineering group"),
    ("LR2", "03_crestline_automation.md", "vision system"),
    ("LR3", "03_crestline_automation.md", "pump failure"),
    ("LR4", "03_crestline_automation.md", "production stoppage"),
]

def overlap(spans, surface):
    s = surface.lower()
    hits = [x for x in spans if s in x["text"].lower() or x["text"].lower() in s]
    exact = [x for x in hits if x["text"].lower().strip() == s]
    return hits, exact

def main():
    conn = psycopg.connect(DSN)
    gl = GlinerClient(); gl.verify_pin()
    pack = _pack()
    stages = get_settings().rescue_policy.enabled_stages()
    out = {"stages": list(stages), "cases": []}

    docs = {}
    for doc_id, src, prof in conn.execute(
            "SELECT doc_id, source_name, profile FROM documents WHERE corpus_id=%s", (C,)).fetchall():
        docs[src.split("/")[-1]] = (doc_id, prof)

    per_doc = {}
    for tail in sorted({c[1] for c in CASES}):
        doc_id, prof = docs[tail]
        labels = list(DocumentProfile(**prof).label_set)
        rows = conn.execute("""SELECT chunk_id, text, layout_map FROM chunks
            WHERE doc_id=%s AND tier='child' ORDER BY chunk_index""", (doc_id,)).fetchall()
        raw_all, mapped_all, ordered = [], [], []
        for cid, text, lay in rows:
            r = gl.entity_pass(text, labels, threshold=0.5)
            for item in r.get("spans", []):
                raw_all.append({**item, "chunk_id": cid})
            ents, rejected = _entity_spans(gl, text, cid, doc_id, prof)
            mapped_all.extend({"text": e.text, "label": e.raw_label, "core": e.core_type.value,
                               "score": e.score, "chunk_id": cid} for e in ents)
            ev = _evidence_spans(gl, text, cid, pack, "lexical")
            for sl in _slices(_sentences_of(text), ents, ev, C):
                ordered.append(({"chunk_id": cid, "doc_id": doc_id, "text": text,
                 "layout_map": lay}, sl))
        _syntax_evidence(ordered)
        if stages:
            label_set = tuple(DocumentProfile(**prof).label_set)
            apply_rescue(ordered, stages, label_set, pack)
        post = [{"text": e.text, "core": e.core_type.value, "score": e.score,
                 "pass_kind": e.pass_kind} for _r, sl in ordered for e in sl.entities]
        pers = [{"text": r[0], "core": r[1], "anchor": r[2], "durable": r[3] is not None,
                 "reason": r[4]} for r in conn.execute(
            """SELECT surface, core_type, anchor_kind, entity_id, admission_reason
                 FROM mentions WHERE corpus_id=%s AND doc_id=%s""", (C, doc_id)).fetchall()]
        per_doc[tail] = (raw_all, mapped_all, post, pers)

    for cid_, tail, surface in CASES:
        raw_all, mapped_all, post, pers = per_doc[tail]
        r_hits, r_exact = overlap(raw_all, surface)
        m_hits, m_exact = overlap(mapped_all, surface)
        p_hits, p_exact = overlap(post, surface)
        db_hits, db_exact = overlap(pers, surface)
        rec = {
            "case": cid_, "doc": tail, "surface": surface,
            "raw": ([{"t": x["text"], "l": x["label"], "s": round(x["score"], 2)}
                     for x in (r_exact or r_hits)[:3]] or None),
            "raw_exact": bool(r_exact),
            "mapped_exact": bool(m_exact),
            "post_rescue": ([{"t": x["text"], "k": x.get("pass_kind", "")}
                             for x in (p_exact or p_hits)[:3]] or None),
            "persisted": ([{"t": x["text"], "anchor": x["anchor"], "durable": x["durable"]}
                           for x in (db_exact or db_hits)[:3]] or None),
        }
        out["cases"].append(rec)

    gl.close()
    pathlib.Path("eval/provider_forensics/waterfall_stages.json").write_text(
        json.dumps(out, indent=1) + "\n")
    for rec in out["cases"]:
        raw = "EXACT" if rec["raw_exact"] else ("partial:" + rec["raw"][0]["t"][:22] if rec["raw"] else "ABSENT")
        post = ("yes" if rec["post_rescue"] and any(
            rec["surface"].lower() == x["t"].lower() for x in rec["post_rescue"]) else
            (rec["post_rescue"][0]["t"][:20] if rec["post_rescue"] else "-"))
        db = (f"{rec['persisted'][0]['anchor']}/{'D' if rec['persisted'][0]['durable'] else 'nd'}"
              if rec["persisted"] else "-")
        print(f"{rec['case']:<5} {rec['surface'][:26]:<28} raw={raw:<28} post={post:<22} db={db}")

if __name__ == "__main__":
    main()
