"""EP1 entity-proposal qualification harness.

Measures ENTITY proposal quality independently of relation generation,
against gold entity-mention annotations (eval/gold/ep1_*_gold.yaml):

  exact-span precision / recall
  overlap-span recall
  core-type accuracy
  multiword-concept recall
  bare-head rate
  false-span rate
  per-document-class and per-label breakdowns

Separates RAW GLiNER proposals -> mapping/filtering -> final spans.
Supports measurement arms (labels-v2, deterministic span completion)
through a policy callable. Deterministic: identical inputs and policies
produce identical metrics.

Usage:
    .venv/bin/python eval/ep1/harness_entity.py --corpus realistic_smoke_v1 \
        --gold eval/gold/ep1_dev_gold.yaml [--arm baseline|labels-v2|expand|both] \
        [--outdir eval/ep1/artifacts]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import yaml  # noqa: E402

from polymath_shared.clients import GlinerClient  # noqa: E402
from polymath_shared.contracts import CoreType  # noqa: E402
from workers.chunker import materialize_chunks, plan_document  # noqa: E402
from workers.profile_router import chunk_label_set, route_document  # noqa: E402

THRESHOLD = 0.5

# ARM A label inventory: descriptive, semantically coherent, bounded.
LABELS_V2 = [
    "Person", "Organization", "Location", "Product", "Technology",
    "Software component", "Psychological concept", "Scientific concept",
    "Process or activity", "Method or technique", "Measurement or metric",
    "Document or publication", "Event", "Time reference",
    "Field of study", "Hardware device", "Data structure",
    "System role", "Research construct", "Experimental task",
]

LABELS_V2_CORE: dict[str, str] = {
    "Person": "Person", "Organization": "Organization",
    "Location": "Location", "Product": "Product",
    "Technology": "Technology", "Software component": "Technology",
    "Psychological concept": "Concept", "Scientific concept": "Concept",
    "Process or activity": "Process", "Method or technique": "Method",
    "Measurement or metric": "Measurement",
    "Document or publication": "Document", "Event": "Event",
    "Time reference": "TimeReference", "Field of study": "Concept",
    "Hardware device": "Technology", "Data structure": "Concept",
    "System role": "Concept", "Research construct": "Concept",
    "Experimental task": "Measurement",
}

EXPANSION_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "for", "in", "on", "at",
    "to", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "that", "this", "these", "those", "its", "their", "it", "as",
    "than", "into", "over", "under", "between", "after", "before",
    "which", "who", "whose", "when", "where", "also", "still", "not",
}

VERB_STOP = {
    "makes", "make", "made", "does", "do", "did", "uses", "use", "used",
    "has", "have", "had", "can", "may", "will", "would", "could", "should",
    "must", "includes", "include", "included", "allows", "allow", "allowed",
    "requires", "require", "required", "supports", "support", "supported",
    "runs", "run", "keeps", "keep", "becomes", "become", "provides",
    "provide", "describes", "describe", "reports", "report", "suggests",
    "suggest", "helps", "help", "takes", "take", "gives", "give", "shows",
    "show", "finds", "find", "means", "mean", "contains", "contain",
}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.-]*")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower().strip(".,;:!?()[]\"'"))


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def expand_span(text: str, start: int, end: int, max_tokens: int = 4) -> tuple[int, int]:
    """Deterministic conservative NP completion (ARM B).

    Expands over adjacent lowercase-initial tokens that are not
    stopwords, never crossing punctuation/sentence boundaries. Returns
    (new_start, new_end). The original span is preserved by the caller.
    """
    toks = _tokens(text)
    new_start, new_end = start, end

    for _ in range(max_tokens):
        prev = [t for t in toks if t[2] <= new_start]
        if not prev:
            break
        t = prev[-1]
        if t[2] != new_start and text[t[2]:new_start].strip():
            break  # punctuation/sentence gap
        if t[1] > 0 and text[t[1] - 1] in ".!?;:\n":
            break
        word = t[0]
        if word.lower() in EXPANSION_STOP or word.lower() in VERB_STOP or word[0].isupper():
            break
        new_start = t[1]

    # Right expansion: at most ONE token, and only a plural-noun-looking
    # token ("outbox" -> "outbox events"); adjectives/adverbs ("useful")
    # and verb forms never extend the span rightward.
    nxt = [t for t in toks if t[1] >= new_end]
    if nxt:
        t = nxt[0]
        if t[1] == new_end:
            word = t[0]
            if (word.lower() not in EXPANSION_STOP and word.lower() not in VERB_STOP
                    and not word[0].isupper() and word.endswith("s")
                    and not word.endswith("ss")):
                new_end = t[2]

    return new_start, new_end


def propose(
    doc_text: str,
    doc_id: str,
    source_name: str,
    arm: str,
    gliner: GlinerClient,
) -> list[dict]:
    """Propose final entity spans for one document under one arm.

    Returns [{start, end, text, label, core_type, original_text,
    original_label, expansion}]. Deterministic per (text, arm)."""
    plan = plan_document(doc_text, doc_id)
    children = [c for c in materialize_chunks(plan) if c["tier"] == "child"]
    profile = route_document(source_name, doc_text[:4000])
    out: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for chunk in children:
        text = chunk["text"]
        base = chunk["char_start"]
        if arm in ("baseline", "expand"):
            labels = chunk_label_set(text, profile)
            label_core = {}
            for lab in labels:
                label_core[lab] = lab if lab in [t.value for t in CoreType] else None
            from workers.extract_worker import _map_label
            from workers.extract_worker import _pack as _extract_pack

            pack = _extract_pack()
            label_core = {lab: (_map_label(lab, pack) or lab) for lab in labels}
        else:  # labels-v2 / both
            labels = LABELS_V2
            label_core = dict(LABELS_V2_CORE)

        thresh = THRESHOLD
        if arm in ("threshold-v2", "threshold-v2-expand"):
            # ARM D (A/B measured FAIL): per-class thresholds. Entity-like
            # labels keep 0.5; concept/process/measurement-style labels
            # run at 0.35. Never a global lowering.
            def _t(label: str) -> float:
                core = label_core.get(label) or "Concept"
                if core in ("Person", "Organization", "Location", "Product",
                            "Technology", "TimeReference"):
                    return 0.5
                return 0.35
            low = [(lab, _t(lab)) for lab in labels if _t(lab) < THRESHOLD]
            result = gliner.entity_pass(text, labels, threshold=THRESHOLD)
            low_result = gliner.entity_pass(text, [l for l, _ in low],
                                            threshold=0.35) if low else {"spans": []}
            spans = list(result.get("spans", [])) + [
                s for s in low_result.get("spans", [])
                if s.get("score", 0) < THRESHOLD
            ]
        else:
            result = gliner.entity_pass(text, labels, threshold=THRESHOLD)
            spans = result.get("spans", [])
        for item in spans:
            span_text = text[item["start"]:item["end"]]
            raw_label = item["label"]
            core = label_core.get(raw_label) or "Concept"
            # Recover DOC-absolute offsets: chunk text is whitespace-
            # normalized, so locate the span text inside the chunk's
            # document window by normalized search.
            doc_start = _locate(doc_text, span_text, base, base + len(text))
            if doc_start is None:
                continue
            start, end = doc_start, doc_start + len(span_text)
            expanded = arm in ("expand", "both", "threshold-v2-expand")
            new_start, new_end = (start, end)
            expansion = None
            if expanded:
                new_start, new_end = expand_span(doc_text, start, end)
                if (new_start, new_end) != (start, end):
                    expansion = "deterministic-np-v1"
            key = (new_start, new_end, _norm(doc_text[new_start:new_end]))
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "start": new_start,
                "end": new_end,
                "text": doc_text[new_start:new_end],
                "label": raw_label,
                "core_type": core,
                "original_text": span_text,
                "original_label": raw_label,
                "expansion": expansion,
            })
    return sorted(out, key=lambda p: (p["start"], p["end"]))


def _locate(doc_text: str, span_text: str, window_start: int, window_end: int) -> int | None:
    """Locate a chunk-space span in the document by normalized search
    inside the chunk's window (chunk text collapses whitespace, so raw
    offset arithmetic can misalign)."""
    target = _norm(span_text)
    if not target:
        return None
    window = doc_text[max(0, window_start - 40): min(len(doc_text), window_end + 40)]
    base = max(0, window_start - 40)
    idx = _norm(window).find(target)
    if idx < 0:
        idx = _norm(doc_text).find(target)
        return idx if idx >= 0 else None
    return base + idx


def _mention_offsets(doc_text: str, surface: str) -> list[tuple[int, int]]:
    norm_surface = _norm(surface)
    offsets = []
    start = 0
    lowered = doc_text.lower()
    while True:
        idx = lowered.find(norm_surface, start)
        if idx < 0:
            break
        offsets.append((idx, idx + len(norm_surface)))
        start = idx + 1
    return offsets


def score_document(doc_text: str, proposals: list[dict], mentions: list[dict]) -> dict:
    gold_spans: list[dict] = []
    for m in mentions:
        for (s, e) in _mention_offsets(doc_text, m["surface"]):
            gold_spans.append({
                "start": s, "end": e, "surface": m["surface"],
                "core_type": m["core_type"], "multiword": m["multiword"],
                "head": (m.get("head") or "").lower(),
                "matched_by": None,
            })

    counts = {
        "proposals": len(proposals),
        "exact": 0, "overlap": 0, "bare_head": 0, "false": 0,
        "type_correct": 0, "type_wrong": 0,
    }
    per_label = defaultdict(lambda: {"proposals": 0, "exact": 0, "false": 0})

    used: set[int] = set()
    for p in proposals:
        per_label[p["label"]]["proposals"] += 1
        ptext = _norm(p["text"])
        best = None
        for i, g in enumerate(gold_spans):
            if i in used:
                continue
            gtext = _norm(g["surface"])
            overlap = max(0, min(p["end"], g["end"]) - max(p["start"], g["start"]))
            if overlap <= 0:
                continue
            head_ok = g["head"] in ptext or g["head"] in gtext and g["head"] in ptext
            if best is None or overlap > best[1]:
                best = (i, overlap, head_ok)
        if best is None:
            counts["false"] += 1
            per_label[p["label"]]["false"] += 1
            continue
        gi, overlap, head_ok = best
        g = gold_spans[gi]
        used.add(gi)
        if p["start"] == g["start"] and p["end"] == g["end"]:
            counts["exact"] += 1
            per_label[p["label"]]["exact"] += 1
            if p["core_type"] == g["core_type"]:
                counts["type_correct"] += 1
            else:
                counts["type_wrong"] += 1
        else:
            is_bare = p["end"] <= g["end"] and p["start"] >= g["start"] and g["multiword"]
            if is_bare and head_ok:
                counts["bare_head"] += 1
                if p["core_type"] == g["core_type"]:
                    counts["type_correct"] += 1
                else:
                    counts["type_wrong"] += 1
            else:
                counts["overlap"] += 1
                if p["core_type"] == g["core_type"]:
                    counts["type_correct"] += 1
                else:
                    counts["type_wrong"] += 1

    n_mentions = len(gold_spans)
    matched = counts["exact"] + counts["overlap"] + counts["bare_head"]
    multiword_n = sum(1 for g in gold_spans if g["multiword"])
    multiword_matched = sum(
        1 for i, g in enumerate(gold_spans)
        if g["multiword"] and i in used
    )
    total = counts["proposals"]
    return {
        "proposals": total,
        "mentions": n_mentions,
        "exact_precision": counts["exact"] / max(total, 1),
        "exact_recall": counts["exact"] / max(n_mentions, 1),
        "overlap_recall": matched / max(n_mentions, 1),
        "multiword_recall": multiword_matched / max(multiword_n, 1),
        "core_type_accuracy": counts["type_correct"] / max(counts["type_correct"] + counts["type_wrong"], 1),
        "bare_head_rate": counts["bare_head"] / max(total, 1),
        "false_span_rate": counts["false"] / max(total, 1),
        "multiword_n": multiword_n,
        "multiword_matched": multiword_matched,
        "counts": counts,
        "per_label": {k: dict(v) for k, v in sorted(per_label.items())},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True,
                        help="corpus dir name under eval/gold/")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--arm", default="baseline",
                        choices=["baseline", "labels-v2", "expand", "both",
                                 "threshold-v2", "threshold-v2-expand"])
    parser.add_argument("--outdir", default=str(ROOT / "eval" / "ep1" / "artifacts"))
    args = parser.parse_args(argv)

    corpus_dir = ROOT / "eval" / "gold" / args.corpus
    docs = sorted(corpus_dir.glob("*.md"))
    gold = yaml.safe_load(Path(args.gold).read_text())
    gold_by_doc = {d["doc"]: d["mentions"] for d in gold["documents"]}

    gliner = GlinerClient()
    gliner.verify_pin()

    per_doc = {}
    for doc_path in docs:
        doc_text = doc_path.read_text()
        mentions = gold_by_doc.get(doc_path.name, [])
        proposals = propose(doc_text, f"ep1_{doc_path.stem}", doc_path.name,
                            args.arm, gliner)
        per_doc[doc_path.name] = {
            "score": score_document(doc_text, proposals, mentions),
            "proposals": proposals,
        }
    gliner.close()

    totals = defaultdict(int)
    matched_all = 0
    exact_all = 0
    type_c = 0
    type_w = 0
    multi_n = 0
    multi_m = 0
    for d in per_doc.values():
        s = d["score"]
        totals["proposals"] += s["proposals"]
        totals["mentions"] += s["mentions"]
        totals["false"] += s["counts"]["false"]
        exact_all += s["counts"]["exact"]
        matched_all += s["counts"]["exact"] + s["counts"]["overlap"] + s["counts"]["bare_head"]
        type_c += s["counts"]["type_correct"]
        type_w += s["counts"]["type_wrong"]
        multi_n += s["multiword_n"]
        multi_m += s["multiword_matched"]

    summary = {
        "arm": args.arm,
        "documents": len(docs),
        "proposals": totals["proposals"],
        "mentions": totals["mentions"],
        "exact_precision": exact_all / max(totals["proposals"], 1),
        "exact_recall": exact_all / max(totals["mentions"], 1),
        "overlap_recall": matched_all / max(totals["mentions"], 1),
        "multiword_recall": multi_m / max(multi_n, 1),
        "core_type_accuracy": type_c / max(type_c + type_w, 1),
        "bare_head_rate": (matched_all - exact_all) / max(totals["proposals"], 1),
        "false_span_rate": totals["false"] / max(totals["proposals"], 1),
    }
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "per_document": {
            name: {"score": d["score"], "proposals": d["proposals"]}
            for name, d in per_doc.items()
        },
        "arm": args.arm,
        "gold_path": args.gold,
        "gold_sha256": hashlib.sha256(Path(args.gold).read_bytes()).hexdigest(),
        "corpus": args.corpus,
    }
    out = outdir / f"{args.corpus}_{args.arm}.json"
    out.write_text(json.dumps(payload, sort_keys=True, indent=1))
    print(json.dumps(summary, indent=1))
    print(f"\nartifact: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
