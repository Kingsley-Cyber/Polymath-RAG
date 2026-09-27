"""FACET-RETRIEVAL-V1 F5 (register 11.545, plan §3.5) — cross-document synthesis for the chat answer.

The owner (2026-09-27): "abstractions should be elite and document synthesis", "retrieved answers should feel like its
retrieved", "diversity is important". Two pure pieces, no I/O, no model call:

1. `synthesis_block(plan, legend, uncovered)` — the request-block addition for a GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE
   turn (never plain QA / a lookup): principles first, each cited from ≥ 2 documents where the passages allow; then the
   specifics per facet (the plan's `facets`), naming the documents each part draws on; a facet no passage covers gets one
   honest sentence (the gap check, F6, verifies it afterwards). It lists the DOCUMENTS IN EVIDENCE with their [S#] tags so
   the model can name them and cite across them.
2. `synthesis_model(...)` — the graded evidence of the answer, in deep research's shapes (`deep_research.evidence`):
   per facet the cited documents and a `confidence` (strong = ≥ 2 documents · single_source · contested — contested only
   when the evidence itself disagrees: a COUNTERPOINT query attached to the facet found a passage that is in the final
   evidence), `sources` by document ({doc_id, title, cids, findings} — `DeepReportSource`, the cids are the [S#] tags so
   the chat UI's citation chips resolve them) and the answer's document share from `composition.doc_counts`. It rides
   `meta.synthesis` on the answer frame and the receipt (small: ≤ 5 facets, ≤ 48 tags).

Flag `POLYMATH_CHAT_CROSS_SYNTHESIS` (default on): `0` = no block in the prompt and no `meta.synthesis` — the pre-F5 prompt
and receipt byte for byte.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from typing import Any

from .deep_research.evidence import CONTESTED, SINGLE_SOURCE, STRONG, split_sentences

CONTRACT = "chat-synthesis-v1"
FLAG = "POLYMATH_CHAT_CROSS_SYNTHESIS"
SYNTHESIS_TASKS = ("GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE")
COUNTERPOINT = "COUNTERPOINT"
MAX_DOCS_IN_PROMPT = 12          # the legend holds ≤ 48 passages; a dozen books is the realistic ceiling of one answer
MAX_TAGS_PER_DOC = 6
S_TAG = re.compile(r"\[S(\d{1,3})\]")


def enabled(env: Mapping[str, str] | None = None) -> bool:
    raw = (env if env is not None else os.environ).get(FLAG, "1")
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def is_synthesis_task(plan: Any) -> bool:
    """GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE with retrieval — never plain QA, a lookup, a transform or a continuation."""
    return (plan is not None and getattr(plan, "task_type", None) in SYNTHESIS_TASKS
            and bool(getattr(plan, "retrieval_required", True)))


def _title_of(entry: Mapping[str, Any]) -> str:
    crumb = str(entry.get("breadcrumb") or "").strip()
    head = crumb.split("›", 1)[0].strip() if crumb else ""
    return head or str(entry.get("doc_id") or "")[:24] or "document"


def documents_in_evidence(legend: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The documents behind the [S#] legend, in first-tag order: [{doc_id, title, tags}]. A carried passage without a
    document id groups under its own tag."""
    out: dict[str, dict[str, Any]] = {}
    for e in legend or ():
        tag = str(e.get("tag") or "")
        if not tag:
            continue
        key = str(e.get("doc_id") or f"tag:{tag}")
        row = out.setdefault(key, {"doc_id": e.get("doc_id"), "title": _title_of(e), "tags": []})
        row["tags"].append(tag)
    return list(out.values())


def _facet_rows(plan: Any) -> list[dict[str, Any]]:
    return [f for f in (getattr(plan, "facets", None) or []) if isinstance(f, Mapping) and f.get("id")]


def synthesis_block(plan: Any, legend: Iterable[Mapping[str, Any]], *, uncovered: Iterable[str] = ()) -> str | None:
    """The CROSS-DOCUMENT SYNTHESIS block of the request, or None when the turn is not a synthesis task or has no evidence.
    Pure: reads the plan's task type and facets and the legend the prompt already carries — no library input."""
    if not is_synthesis_task(plan):
        return None
    docs = documents_in_evidence(legend)
    if not docs:
        return None
    facets = _facet_rows(plan)
    unc = {str(u) for u in (uncovered or ())}
    task = str(getattr(plan, "task_type", "") or "")
    lines = [(f"CROSS-DOCUMENT SYNTHESIS (TASK {task} over {len(docs)} document{'s' if len(docs) != 1 else ''}; keep the "
              "presentation contract's shape — these rules order the content, they add no sections):")]
    lines.append("1. PRINCIPLES FIRST: open with the principles the passages support — the abstractions that hold across "
                 "documents — each cited from at least two documents where the passages allow (tags of different documents, "
                 "e.g. [S2][S7]). A principle only one document supports is written as that document's (\"<document> only: …\").")
    naming = ("naming the document(s) each part draws on (\"from <document> [S3] and <document> [S9]\"). A part that rests on "
              "one document says so.")
    if facets:
        names = "; ".join(f'{f["id"]} "{str(f.get("name") or "")[:80]}"' for f in facets)
        lines.append(f"2. SPECIFICS PER FACET: then the specifics, one part per facet of the request — {names} — {naming}")
    else:
        lines.append(f"2. SPECIFICS: then the specifics, one part per aspect of the request, {naming}")
    gap = ("3. A facet no passage covers gets ONE sentence — \"The passages found don't cover <facet>.\" — and nothing more: "
           "never a section on what the library lacks, never \"the corpus has nothing on\", never a claim about documents "
           "you were not shown; only the passages in front of you were searched.")
    if unc and facets:
        missing = [f for f in facets if str(f["id"]) in unc]
        if missing:
            gap += " Uncovered by this turn's searches: " + "; ".join(f'{f["id"]} "{str(f.get("name") or "")[:80]}"' for f in missing) + "."
    lines.append(gap)
    if task == "CREATE_FROM_KNOWLEDGE":
        lines.append("For this CREATE task the principles are the short framing before the artifact and the specifics per "
                     "facet live inside it, cited where they are corpus-derived.")
    lines.append("Ground rules: every factual sentence ends with its [S#]; never invent a link between documents the passages "
                 "do not make; never generalize a principle beyond what its cited passages say; a fact from one document is "
                 "that document's fact, named as such.")
    shown = docs[:MAX_DOCS_IN_PROMPT]
    parts = []
    for d in shown:
        tags = d["tags"][:MAX_TAGS_PER_DOC]
        more = len(d["tags"]) - len(tags)
        parts.append(f'{d["title"]} ' + "".join(f"[{t}]" for t in tags) + (f" (+{more})" if more > 0 else ""))
    extra = f" (+{len(docs) - len(shown)} more documents)" if len(docs) > len(shown) else ""
    lines.append("DOCUMENTS IN EVIDENCE: " + " · ".join(parts) + extra)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────── the graded evidence of the answer

def sentence_tags(sentence: str) -> list[str]:
    """The [S#] tags of one sentence, first appearance first, deduped."""
    out: list[str] = []
    for n in S_TAG.findall(sentence or ""):
        t = f"S{n}"
        if t not in out:
            out.append(t)
    return out


def synthesis_model(answer_text: str, legend: Iterable[Mapping[str, Any]], *, plan: Any = None,
                    evidence_paths: Mapping[str, Iterable[str]] | None = None,
                    facets_covered: Iterable[str] | None = None, facets_uncovered: Iterable[str] | None = None,
                    doc_counts: Mapping[str, int] | None = None, doc_share_top: float | None = None) -> dict[str, Any]:
    """`meta.synthesis` — {contract, task_type, facets, sources, documents, share, sentences, uncited}.
    - facets: the plan's facets in order, {id, name, covered, docs, tags, sentences, confidence}: a cited passage belongs to
      the facets whose queries found it (`evidence_paths`: chunk → query ids; the plan's facets: id → query ids); `docs` are
      the distinct documents the answer cites for it; `confidence` = contested when a COUNTERPOINT query of the facet found
      a passage that is in the final evidence, else strong (≥ 2 documents) / single_source; None when the answer cites
      nothing for it.
    - sources: by document, {doc_id, title, cids, findings, facets}: the cited [S#] tags in first-citation order, how many
      sentences cite the document, the facets it serves; most findings first, then first cited.
    - documents: {in_evidence, cited, multi_doc_sentences}: `multi_doc_sentences` = sentences citing ≥ 2 documents (the
      principles the prompt asked for). share: {top_share, doc_counts} from the composer (None when unknown)."""
    entries = [dict(e) for e in (legend or ()) if e.get("tag")]
    by_tag = {str(e["tag"]): e for e in entries}
    doc_of_tag = {t: e.get("doc_id") for t, e in by_tag.items()}
    title_of_doc: dict[str, str] = {}
    for e in entries:
        if e.get("doc_id") and e["doc_id"] not in title_of_doc:
            title_of_doc[str(e["doc_id"])] = _title_of(e)
    facets = _facet_rows(plan)
    paths = {str(k): {str(q) for q in (v or ())} for k, v in (evidence_paths or {}).items()}
    query_type = {q.id: getattr(q, "type", "") for q in (getattr(plan, "queries", None) or []) if getattr(q, "id", None)}
    facet_qids = {str(f["id"]): {str(q) for q in (f.get("query_ids") or ())} for f in facets}

    def facets_of_chunk(cid: str | None) -> list[str]:
        qids = paths.get(str(cid or ""), set())
        return [fid for fid, fq in facet_qids.items() if qids & fq]

    sentences = split_sentences(answer_text or "")
    uncited = 0
    multi_doc = 0
    facet_docs: dict[str, dict[str, None]] = {fid: {} for fid in facet_qids}
    facet_tags: dict[str, dict[str, None]] = {fid: {} for fid in facet_qids}
    facet_sentences: dict[str, int] = dict.fromkeys(facet_qids, 0)
    source_rows: dict[str, dict[str, Any]] = {}
    cited_order: list[str] = []
    for s in sentences:
        tags = [t for t in sentence_tags(s) if t in by_tag]
        if not tags:
            uncited += 1
            continue
        docs_here: dict[str, None] = {}
        fids_here: dict[str, None] = {}
        for t in tags:
            if t not in cited_order:
                cited_order.append(t)
            e = by_tag[t]
            did = e.get("doc_id")
            key = str(did or f"tag:{t}")
            row = source_rows.setdefault(key, {"doc_id": did, "title": _title_of(e), "cids": [], "findings": 0, "facets": []})
            if t not in row["cids"]:
                row["cids"].append(t)
            docs_here[key] = None
            for fid in facets_of_chunk(e.get("chunk_id")):
                fids_here[fid] = None
                facet_tags[fid][t] = None
                if did:
                    facet_docs[fid][str(did)] = None
                if fid not in row["facets"]:
                    row["facets"].append(fid)
        for key in docs_here:
            source_rows[key]["findings"] += 1
        for fid in fids_here:
            facet_sentences[fid] += 1
        if len(docs_here) >= 2:
            multi_doc += 1

    # contested: a COUNTERPOINT query of the facet found a passage that IS in the final evidence (the evidence disagrees)
    counter_qids = {qid for qid, t in query_type.items() if t == COUNTERPOINT}
    contested: set[str] = set()
    if counter_qids:
        for e in entries:
            qids = paths.get(str(e.get("chunk_id") or ""), set())
            hit = qids & counter_qids
            if not hit:
                continue
            for fid, fq in facet_qids.items():
                if hit & fq:
                    contested.add(fid)
    covered = {str(x) for x in (facets_covered or ())}
    uncovered_set = {str(x) for x in (facets_uncovered or ())}
    facet_out = []
    for f in facets:
        fid = str(f["id"])
        docs = list(facet_docs[fid])
        tags = list(facet_tags[fid])
        if not tags:
            conf = None
        elif fid in contested:
            conf = CONTESTED
        else:
            conf = STRONG if len(docs) >= 2 else SINGLE_SOURCE
        cov: bool | None = True if fid in covered else (False if fid in uncovered_set else None)
        facet_out.append({"id": fid, "name": str(f.get("name") or "")[:80], "covered": cov, "docs": docs, "tags": tags,
                          "sentences": facet_sentences[fid], "confidence": conf})
    order = {k: i for i, k in enumerate(source_rows)}
    sources = sorted(source_rows.values(), key=lambda r: (-r["findings"], order[str(r["doc_id"] or f'tag:{r["cids"][0]}')]))
    docs_in_evidence = {str(e["doc_id"]) for e in entries if e.get("doc_id")}
    share = None
    if doc_counts:
        counts = {str(k): int(v) for k, v in doc_counts.items()}
        total = sum(counts.values()) or 1
        top = max(counts, key=lambda k: (counts[k], k)) if counts else None
        share = {"top_doc": top, "top_title": title_of_doc.get(top or "", None),
                 "top_share": (round(float(doc_share_top), 3) if doc_share_top is not None else round(counts[top] / total, 3) if top else None),
                 "doc_counts": counts}
    return {"contract": CONTRACT, "task_type": str(getattr(plan, "task_type", "") or ""),
            "facets": facet_out, "sources": sources,
            "documents": {"in_evidence": len(docs_in_evidence),
                          "cited": len({str(doc_of_tag.get(t)) for t in cited_order if doc_of_tag.get(t)}),
                          "multi_doc_sentences": multi_doc},
            "share": share, "sentences": len(sentences), "uncited": uncited}
