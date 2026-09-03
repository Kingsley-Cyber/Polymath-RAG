"""RETRIEVE-EVIDENCE-ROWS-V1 — contract-ready evidence for agent consumers.

The lane response of /retrieve is an ablation view: ids, ranks and scores per
lane, verbatim text only on the reranked `child_evidence`, document profiles
as raw heads, graph facts without provenance, titles nowhere. A downstream
agent (TRAIL OS, docs/18 corpus contract: {id, summary, source}) had to
re-resolve all of it. This module builds ONE list of rows every hit maps to:

  {id, kind: chunk|document|graph_fact|graph_hop, doc_id, corpus_id, title,
   source (human-auditable: title · channel/date · heading or timecode),
   text (verbatim), text_clean (transcript timestamps stripped), timecode,
   heading_path, char_start, char_end, lanes[], score, summary (document
   rows: the document_summaries row when it exists), evidence[] (graph facts:
   the chunks that attest them)}

Transcript awareness is read-time: frontmatter (title, channel, upload_date,
video_id, url) comes from `documents.frontmatter` (migration 0051, stamped at
intake or by scripts/backfill_frontmatter.py) or, failing that, is parsed from
the document's first chunk; `**[m:ss]**` markers become `timecode` and leave
`text_clean`. No re-chunking, no id change.

EXPLORE (ideation) mode: breadth over answer precision — a per-document cap
on chunk rows, round-robin interleaving across documents, and one graph hop:
chunks from OTHER documents that attest facts sharing an entity with the
query's facts. Bounded by `limit`; never a second reranker pass.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Iterable, Optional

_TS = re.compile(r"\*\*\[(\d+):(\d{2})(?::(\d{2}))?\]\*\*\s*")
from polymath_shared.frontmatter import parse_frontmatter  # noqa: E402  (single source, shared with intake)


_SUMMARY_PREFIX = re.compile(r"^\s*(?:/[^\n—]*?|[^\n—/]*?)\.(?:md|txt|pdf|epub|html?|srt|vtt)\s+[—-]\s+", re.I)


_INLINE_TIMECODE = re.compile(r"\s*\*{0,2}\[\d{1,2}:\d{2}(?::\d{2})?\]\*{0,2}\s*")


def clean_summary(text: str) -> str:
    """Document summaries are written as `<source path or file> — <summary>`;
    the path is provenance we already carry in `source`, never evidence text.
    Handles paths with spaces and dots in the file name. Inline transcript
    markers such as `**[16:51]**` are removed (the summary is a reading, not
    a location — chunk rows carry the real timecode)."""
    out = _SUMMARY_PREFIX.sub("", text or "", count=1)
    out = _INLINE_TIMECODE.sub(" ", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def strip_timecodes(text: str) -> tuple[str, Optional[dict]]:
    """Remove transcript markers from the text; report first/last timecode."""
    if not text or "**[" not in text:
        return re.sub(r"\s+", " ", text or "").strip(), None
    marks = [(int(m.group(1)) * 60 + int(m.group(2)) + (int(m.group(3)) if m.group(3) else 0) * 0)
             for m in _TS.finditer(text)]
    # h:mm:ss markers: group(3) present means group1=h, group2=m, group3=s
    fixed = []
    for m in _TS.finditer(text):
        if m.group(3):
            fixed.append(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
        else:
            fixed.append(int(m.group(1)) * 60 + int(m.group(2)))
    clean = re.sub(r"\s+", " ", _TS.sub("", text)).strip()
    if not fixed:
        return clean, None
    fmt = lambda s: f"{s // 60}:{s % 60:02d}"  # noqa: E731
    return clean, {"start": fmt(min(fixed)), "end": fmt(max(fixed)), "start_s": min(fixed), "end_s": max(fixed)}


def display_title(fm: dict, source_name: Optional[str], doc_id: str) -> str:
    if fm.get("title"):
        return fm["title"]
    if source_name and ("/" in source_name or "\\" in source_name):
        base = source_name.replace("\\", "/").rsplit("/", 1)[-1]
        return re.sub(r"\.(md|txt|pdf|epub|html?)$", "", base, flags=re.I) or doc_id
    return source_name or doc_id


def _source_label(title: str, fm: dict, heading_path, timecode: Optional[dict]) -> str:
    parts = [title]
    if fm.get("channel"):
        parts.append(fm["channel"])
    if fm.get("upload_date"):
        d = str(fm["upload_date"])
        parts.append(f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d)
    if timecode:
        parts.append(f"{timecode['start']}–{timecode['end']}")
    elif heading_path:
        hp = heading_path if isinstance(heading_path, (list, tuple)) else None
        if hp is None:
            try:
                hp = json.loads(heading_path)
            except Exception:  # noqa: BLE001
                hp = [str(heading_path)]
        if hp:
            parts.append(" › ".join(str(x) for x in hp if x)[:80])
    return " · ".join(p for p in parts if p)


def _fetch_docs(conn, doc_ids: list[str]) -> dict:
    if not doc_ids:
        return {}
    has_fm = conn.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='frontmatter'"
    ).fetchone() is not None
    cols = "doc_id, corpus_id, source_name" + (", frontmatter" if has_fm else "")
    docs = {}
    for r in conn.execute(f"SELECT {cols} FROM documents WHERE doc_id = ANY(%s)", (doc_ids,)).fetchall():
        fm = (r[3] if has_fm else None) or {}
        if isinstance(fm, str):
            try:
                fm = json.loads(fm)
            except Exception:  # noqa: BLE001
                fm = {}
        docs[r[0]] = {"corpus_id": r[1], "source_name": r[2], "frontmatter": dict(fm)}
    # frontmatter fallback: parse the first chunk of documents that lack it
    missing = [d for d, v in docs.items() if not v["frontmatter"].get("title")]
    if missing:
        for r in conn.execute(
                """SELECT DISTINCT ON (doc_id) doc_id, text FROM chunks
                    WHERE doc_id = ANY(%s) AND tier = 'child' ORDER BY doc_id, chunk_index""",
                (missing,)).fetchall():
            fm = parse_frontmatter(r[1] or "")
            if fm:
                docs[r[0]]["frontmatter"] = {**fm, **docs[r[0]]["frontmatter"]}
    for d, v in docs.items():
        v["title"] = display_title(v["frontmatter"], v["source_name"], d)
    # document summaries when they exist
    try:
        for r in conn.execute(
                """SELECT DISTINCT ON (document_id) document_id, summary, major_entities, major_concepts, questions_answered
                     FROM document_summaries WHERE document_id = ANY(%s) ORDER BY document_id, created_at DESC""",
                (doc_ids,)).fetchall():
            if r[0] in docs:
                docs[r[0]]["summary"] = {"summary": r[1], "major_entities": r[2], "major_concepts": r[3],
                                         "questions_answered": r[4]}
    except Exception:  # noqa: BLE001 — summaries are optional
        pass
    return docs


def _fetch_chunks(conn, chunk_ids: list[str]) -> dict:
    if not chunk_ids:
        return {}
    out = {}
    for r in conn.execute(
            """SELECT c.chunk_id, c.doc_id, c.text, c.heading_path, c.char_start, c.char_end, c.tier, c.chunk_index
                 FROM chunks c WHERE c.chunk_id = ANY(%s)""", (chunk_ids,)).fetchall():
        out[r[0]] = {"chunk_id": r[0], "doc_id": r[1], "text": r[2] or "", "heading_path": r[3],
                     "char_start": r[4], "char_end": r[5], "tier": r[6], "chunk_index": r[7]}
    return out


def _fact_provenance(conn, fact_ids: list[str]) -> dict:
    prov = defaultdict(list)
    if not fact_ids:
        return prov
    for r in conn.execute(
            "SELECT fact_id, doc_id, chunk_id FROM evidence WHERE fact_id = ANY(%s)", (fact_ids,)).fetchall():
        prov[r[0]].append({"doc_id": r[1], "chunk_id": r[2]})
    return prov


def _graph_hop(conn, facts: list[dict], seen_docs: set, corpus_ids: list[str], limit: int) -> list[dict]:
    """Chunks in OTHER documents that attest facts sharing an entity with the
    query's facts — the abduction pool's cross-document reach."""
    ent_ids = []
    for f in facts:
        for k in ("subject_id", "object_id"):
            if f.get(k) and f[k] not in ent_ids:
                ent_ids.append(f[k])
    if not ent_ids or limit <= 0:
        return []
    rows = conn.execute(
        """SELECT DISTINCT ON (e.doc_id) e.chunk_id, e.doc_id, f.fact_id, f.predicate,
                  s.normalized_surface AS subj, o.normalized_surface AS obj
             FROM facts f
             JOIN evidence e ON e.fact_id = f.fact_id
             JOIN documents d ON d.doc_id = e.doc_id
             LEFT JOIN entities s ON s.entity_id = f.subject_id
             LEFT JOIN entities o ON o.entity_id = f.object_id
            WHERE (f.subject_id = ANY(%s) OR f.object_id = ANY(%s))
              AND d.corpus_id = ANY(%s)
              AND NOT (e.doc_id = ANY(%s))
            ORDER BY e.doc_id, f.created_at DESC
            LIMIT %s""",
        (ent_ids[:12], ent_ids[:12], corpus_ids, list(seen_docs) or [""], limit)).fetchall()
    return [{"chunk_id": r[0], "doc_id": r[1], "fact_id": r[2], "predicate": r[3], "subject": r[4], "object": r[5]}
            for r in rows]


def build_evidence_rows(conn, response: dict, corpus_ids: list[str], *, limit: int = 12,
                        explore: bool = False) -> list[dict]:
    limit = max(1, min(int(limit or 12), 60))
    per_doc_cap = 2 if explore else 4
    # 1. gather chunk ids with their lanes + best score
    lanes: dict[str, set] = defaultdict(set)
    score: dict[str, float] = {}
    for lane_key, lane_name in (("child_evidence", "reranked"), ("child_dense_lane", "dense"),
                                ("child_lexical_lane", "lexical"), ("parent_lane", "parent")):
        for h in response.get(lane_key) or []:
            cid = h.get("chunk_id") or h.get("source_id")
            if not cid:
                continue
            lanes[cid].add(lane_name)
            sc = h.get("rerank_score", h.get("raw_score"))
            try:
                sc = float(sc)
            except (TypeError, ValueError):
                sc = 0.0
            score[cid] = max(score.get(cid, float("-inf")), sc)
    ordered = [c["chunk_id"] for c in response.get("child_evidence") or [] if c.get("chunk_id")]
    for lane_key in ("child_dense_lane", "child_lexical_lane", "parent_lane"):
        for h in response.get(lane_key) or []:
            cid = h.get("chunk_id") or h.get("source_id")
            if cid and cid not in ordered:
                ordered.append(cid)
    chunks = _fetch_chunks(conn, ordered)
    doc_ids = list({c["doc_id"] for c in chunks.values()})
    for d in response.get("selected_documents") or []:
        if d.get("doc_id") and d["doc_id"] not in doc_ids:
            doc_ids.append(d["doc_id"])
    facts = response.get("graph_facts") or []
    prov = _fact_provenance(conn, [f.get("fact_id") for f in facts if f.get("fact_id")])
    for plist in prov.values():
        for p in plist:
            if p["doc_id"] not in doc_ids:
                doc_ids.append(p["doc_id"])
    docs = _fetch_docs(conn, doc_ids)

    rows: list[dict] = []
    per_doc: dict[str, int] = defaultdict(int)

    def chunk_row(cid: str, kind: str, extra: Optional[dict] = None) -> Optional[dict]:
        c = chunks.get(cid)
        if not c or not c["text"].strip():
            return None
        doc = docs.get(c["doc_id"], {"title": c["doc_id"], "frontmatter": {}, "corpus_id": None})
        clean, tc = strip_timecodes(c["text"])
        fm = doc.get("frontmatter") or {}
        row = {"id": cid, "kind": kind, "doc_id": c["doc_id"], "corpus_id": doc.get("corpus_id"),
               "title": doc["title"], "source": _source_label(doc["title"], fm, c["heading_path"], tc),
               "text": c["text"], "text_clean": clean, "timecode": tc, "heading_path": c["heading_path"],
               "char_start": c["char_start"], "char_end": c["char_end"], "tier": c["tier"],
               "lanes": sorted(lanes.get(cid) or {kind}), "score": round(score.get(cid, 0.0), 4)}
        if fm.get("channel") or fm.get("url"):
            row["document"] = {k: fm.get(k) for k in ("channel", "upload_date", "video_id", "url") if fm.get(k)}
        if extra:
            row.update(extra)
        return row

    # 2. chunk rows: reranked order first, capped per document; explore interleaves documents
    candidates = []
    for cid in ordered:
        r = chunk_row(cid, "chunk")
        if r:
            candidates.append(r)
    if explore:
        by_doc: dict[str, list] = defaultdict(list)
        for r in candidates:
            by_doc[r["doc_id"]].append(r)
        interleaved = []
        while any(by_doc.values()) and len(interleaved) < limit:
            for d in list(by_doc):
                if by_doc[d]:
                    interleaved.append(by_doc[d].pop(0))
        candidates = interleaved
    for r in candidates:
        if per_doc[r["doc_id"]] >= per_doc_cap or len(rows) >= limit:
            continue
        per_doc[r["doc_id"]] += 1
        rows.append(r)

    # 3. document rows: the summary when it exists (never a raw head)
    for d in response.get("selected_documents") or []:
        doc = docs.get(d.get("doc_id"))
        if not doc or not doc.get("summary") or not (doc["summary"].get("summary") or "").strip():
            continue
        s = doc["summary"]
        s = {**s, "summary": clean_summary(s["summary"] or "")}
        rows.append({"id": f"doc:{d['doc_id']}", "kind": "document", "doc_id": d["doc_id"],
                     "corpus_id": doc.get("corpus_id"), "title": doc["title"],
                     "source": _source_label(doc["title"], doc.get("frontmatter") or {}, None, None) + " · document summary",
                     "text": s["summary"], "text_clean": re.sub(r"\s+", " ", s["summary"]).strip(),
                     "summary": {k: s.get(k) for k in ("major_entities", "major_concepts", "questions_answered")},
                     "lanes": ["document"], "score": round(float(d.get("rerank_score") or 0.0), 4)})

    # 4. graph facts WITH provenance (facts without an attesting chunk are notes, not evidence)
    for f in facts:
        fid = f.get("fact_id")
        p = prov.get(fid) or []
        if not fid or not p:
            continue
        head = p[0]
        doc = docs.get(head["doc_id"], {"title": head["doc_id"], "frontmatter": {}, "corpus_id": None})
        rows.append({"id": f"fact:{fid}", "kind": "graph_fact", "doc_id": head["doc_id"], "corpus_id": doc.get("corpus_id"),
                     "title": doc["title"], "source": f"{doc['title']} · graph fact attested in {len(p)} chunk(s)",
                     "text": f"{f.get('subject')} —{f.get('predicate')}→ {f.get('object')}",
                     "text_clean": f"{f.get('subject')} {f.get('predicate')} {f.get('object')}",
                     "fact": {k: f.get(k) for k in ("subject", "predicate", "object", "subject_id", "object_id")},
                     "evidence": p[:5], "lanes": ["graph"], "score": 0.0})

    # 5. explore: one entity hop into other documents
    if explore and facts:
        seen_docs = {r["doc_id"] for r in rows}
        hop_limit = max(0, limit - len([r for r in rows if r["kind"] == "chunk"]))
        hops = _graph_hop(conn, facts, seen_docs, corpus_ids, min(12, hop_limit or 6))
        hop_chunks = _fetch_chunks(conn, [h["chunk_id"] for h in hops])
        chunks.update(hop_chunks)
        docs.update(_fetch_docs(conn, [h["doc_id"] for h in hops if h["doc_id"] not in docs]))
        for h in hops:
            r = chunk_row(h["chunk_id"], "graph_hop", {"via_fact": {"fact_id": h["fact_id"], "predicate": h["predicate"],
                                                                     "subject": h["subject"], "object": h["object"]}})
            if r:
                r["lanes"] = ["graph_hop"]
                rows.append(r)
    return rows
