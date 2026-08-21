#!/usr/bin/env python3
"""ENTITY-PROVIDER-FORENSICS-V1 — stage 2: analysis of both arms.

Identical downstream for both models: raw label -> core mapping (production
pack), slice reconstruction, spaCy syntax, frozen admission-harbor-v2.
Rescue is deliberately HELD OUT of both arms: its re-queries go to the
resident medium sidecar, which would inject medium into the gliner2 arm.
Nothing is persisted.
"""
import json, os, pathlib, statistics as st, sys
sys.path[:0] = ["shared", "workers"]
os.environ.setdefault("POLYMATH_SYNTAX_PROVIDER", "spacy")

from polymath_shared.contracts import CoreType, EntitySpan
from polymath_shared.execution import SEMANTIC_CONTRACT_V2
from workers.extract_worker import (_allocate_identities, _map_label, _pack,
                                    _sentences_of, _slices, _syntax_evidence)

F = pathlib.Path("eval/provider_forensics")
INP = json.loads((F / "cf_inputs.json").read_text())
GOLD = json.loads(pathlib.Path("eval/i4/gold/fact_gold.json").read_text())
PACK = _pack()

def norm(s): return " ".join(s.lower().split())

def spans_for(doc, raw_spans_by_chunk):
    out, unmapped, bad_off = [], 0, 0
    for ch in doc["chunks"]:
        best = {}
        for it in raw_spans_by_chunk.get(ch["chunk_id"], []):
            s, e, txt = it["start"], it["end"], it["text"]
            if not (0 <= s < e <= len(ch["text"])) or ch["text"][s:e] != txt:
                i = ch["text"].find(txt)
                if i < 0: bad_off += 1; continue
                s, e = i, i + len(txt)
            k = (s, e)
            if k not in best or it["score"] > best[k]["score"]:
                best[k] = {**it, "start": s, "end": e}
        for it in best.values():
            core = _map_label(it["label"], PACK)
            if core is None: unmapped += 1; continue
            out.append(EntitySpan(doc_id=doc["doc_id"], chunk_id=ch["chunk_id"],
                                  start=it["start"], end=it["end"], text=it["text"],
                                  core_type=CoreType(core), score=it["score"],
                                  extractor_version="cf", raw_label=it["label"]))
    return out, unmapped, bad_off

def harbor(doc, ents):
    by_chunk = {}
    for e in ents: by_chunk.setdefault(e.chunk_id, []).append(e)
    ordered = []
    for ch in doc["chunks"]:
        for sl in _slices(_sentences_of(ch["text"]), by_chunk.get(ch["chunk_id"], []), [], "cf"):
            ordered.append(({"chunk_id": ch["chunk_id"], "doc_id": doc["doc_id"],
                             "text": ch["text"], "layout_map": ch.get("layout_map")}, sl))
    if not ordered: return [], 0
    _syntax_evidence(ordered)
    # FINDING (recorded in REPORT): a span nested INSIDE one syntax token
    # (e.g. 'instagram' inside a URL token) has zero covering tokens, and
    # identity_evidence(require_syntax=True) then raises "syntax unavailable"
    # even though syntax IS present — in production this fails the extract
    # stage deterministically. Held out of BOTH arms identically here, with
    # the count reported, so the comparison can proceed.
    dropped = 0
    for _r, sl in ordered:
        keep = []
        for span in sl.entities:
            rs, re_ = span.start - sl.sentence_start, span.end - sl.sentence_start
            toks = [t for t in (sl.syntax or {}).get("tokens", [])
                    if t.get("char_start") is not None
                    and t["char_start"] >= rs and t["char_end"] <= re_]
            if toks: keep.append(span)
            else: dropped += 1
        object.__setattr__(sl, "entities", keep)
    ids = _allocate_identities(ordered, "cf-" + MODEL, doc["doc_id"],
                               contract_version=SEMANTIC_CONTRACT_V2)
    return sorted({(i.admission.proposal_surface, i.admission.core_type,
                    i.admission.anchor_kind, i.admission.scope)
                   for i in ids.values() if i.durable}), dropped

def gold_rows(doc_name):
    rows = []
    for g in GOLD["supported_positive"]["facts"]:
        if doc_name.endswith(g["doc"]):
            rows += [g["subject"], g["object"]]
    return sorted(set(rows))

results = {}
for MODEL in ("medium", "gliner2"):
    arm = json.loads((F / f"cf_{MODEL}.json").read_text())
    r = {"docs": {}}
    for doc in INP["docs"]:
        spans_raw = arm["docs"][doc["name"]]["spans"]
        ents, unmapped, bad = spans_for(doc, spans_raw)
        flat = [x for v in spans_raw.values() for x in v]
        durable, subtok = harbor(doc, ents)
        grows = gold_rows(doc["name"]) if doc["kind"] == "i4" else []
        gm = {}
        for gsurf in grows:
            n = norm(gsurf)
            ex = [x for x in flat if norm(x["text"]) == n]
            part = [x for x in flat if (n in norm(x["text"]) or norm(x["text"]) in n)
                    and norm(x["text"]) != n]
            gm[gsurf] = ("EXACT:" + ex[0]["label"] if ex else
                         ("PARTIAL:" + part[0]["text"] if part else "ABSENT"))
        r["docs"][doc["name"]] = {
            "ms": arm["docs"][doc["name"]]["chunk_ms_median"],
            "proposals": len(flat), "unmapped_labels": unmapped, "bad_offsets": bad,
            "score_median": round(st.median([x["score"] for x in flat]), 2) if flat else None,
            "durable": [list(d) for d in durable],
            "subtoken_spans_dropped": subtok,
            "gold": gm,
        }
    results[MODEL] = r

(F / "cf_analysis.json").write_text(json.dumps(results, indent=1) + "\n")

print("=== gold endpoint availability (i4), medium vs gliner2 ===")
for doc in INP["docs"]:
    if doc["kind"] != "i4": continue
    gm = results["medium"]["docs"][doc["name"]]["gold"]
    gg = results["gliner2"]["docs"][doc["name"]]["gold"]
    for surf in gm:
        a, b = gm[surf], gg[surf]
        flag = " <<<" if a.split(":")[0] != b.split(":")[0] else ""
        print(f"  {surf[:30]:<32} medium={a[:26]:<28} gliner2={b[:26]}{flag}")
print("\n=== durable identities after frozen Harbor (counts) ===")
for doc in INP["docs"]:
    m = results["medium"]["docs"][doc["name"]]; g = results["gliner2"]["docs"][doc["name"]]
    print(f"  {doc['name'][:44]:<46} medium={len(m['durable']):<3} gliner2={len(g['durable']):<3} "
          f"props {m['proposals']}/{g['proposals']}  ms {m['ms']}/{g['ms']}")
