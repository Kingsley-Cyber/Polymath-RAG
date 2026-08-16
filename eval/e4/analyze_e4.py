"""E4: entity recall failure analysis (measurement only; no production
changes, no threshold changes, no new models).

Runs the FROZEN GLiNER sidecar (gliner_medium-v2.1 @ 40ec4193, local
mps) over the two frozen documents with:
  - raw proposal inspection per missed concept
  - label schema variants A/B/C (evaluation only)
  - thresholds 0.3/0.4/0.5/0.6 (measurement only)
  - label-guidance experiment (baseline vs guided)
  - cyber-vs-psychology comparison
  - ownership classification table
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "eval" / "e3" / "corpus" / "docs"
PSYCH = DOCS / "metacognition.md"
CYBER = DOCS / "metacognition_copy.md"
GLINER = "http://127.0.0.1:8740"

PRODUCTION_LABELS = [
    "Person", "Organization", "Location", "Product", "Technology",
    "Concept", "Method", "Event", "Document", "Process",
    "Measurement", "TimeReference",
]

SCHEMA_A = ["Concept", "Method", "Process", "Technology", "Event"]
SCHEMA_B = ["Cognitive Process", "Learning Strategy", "Metacognitive Concept",
            "Psychological Mechanism", "Mental State"]
SCHEMA_C = ["Concept", "Process", "Method", "Theory", "Strategy", "Cognitive Function"]

PSYCH_GOLD = [
    "metacognitive monitoring", "metacognitive control",
    "judgments of learning", "processing fluency", "familiarity effect",
    "illusion of competence", "working memory", "cognitive load",
    "retrieval practice", "corrective feedback",
    "self-regulated learning", "local regulation", "global regulation",
]
CYBER_GOLD = [
    "Northstar Digital", "Atlas Identity Gateway", "AWS", "CloudTrail",
    "OAuth 2.0", "Meridian Billing API", "Keycloak 26.2",
    "OpenID Connect", "HTTP Authorization header", "Fluent Bit",
    "Elasticsearch", "Daniel Ortiz", "site reliability engineer",
    "Red Ridge Systems", "bearer token", "mutual TLS", "DPoP", "STRIDE",
    "Amazon GuardDuty", "Security Architecture Council",
]


def infer(text: str, labels: list[str], threshold: float) -> list[dict]:
    r = httpx.post(f"{GLINER}/infer", json={
        "task": "entity", "text": text, "labels": labels, "threshold": threshold,
    }, timeout=300)
    r.raise_for_status()
    return r.json().get("spans", [])


def classify(term: str, proposals: list[dict]) -> tuple[str, list[dict]]:
    """FOUND_EXACT / FOUND_OVERLAP / WRONG_BOUNDARY / MISSED + evidence."""
    term_l = term.lower()
    for p in proposals:
        pt = p["text"].lower()
        if pt == term_l:
            return "FOUND_EXACT", [p]
    overlaps = [p for p in proposals
                if term_l in p["text"] or p["text"] in term_l]
    if overlaps:
        return "FOUND_OVERLAP", overlaps
    # boundary check: proposals overlapping the gold span position
    for p in proposals:
        if any(w in p["text"].lower() for w in term_l.split()):
            return "WRONG_BOUNDARY", [p]
    return "MISSED", []


def measure(doc: Path, gold: list[str], labels: list[str], threshold: float) -> dict:
    text = doc.read_text()
    proposals = infer(text, labels, threshold)
    rows = {}
    for term in gold:
        cls, ev = classify(term, proposals)
        rows[term] = {"class": cls, "evidence": [
            {"text": p["text"], "label": p["label"], "score": round(p["score"], 3)}
            for p in ev]}
    found = sum(1 for v in rows.values() if v["class"] == "FOUND_EXACT")
    overlap = sum(1 for v in rows.values() if v["class"] == "FOUND_OVERLAP")
    return {
        "labels": labels,
        "threshold": threshold,
        "found_exact": found,
        "overlap": overlap,
        "missed": len(gold) - found - overlap,
        "total": len(gold),
        "proposal_count": len(proposals),
        "rows": rows,
    }


def main() -> int:
    out: dict = {"phases": {}}

    psych_text = PSYCH.read_text()
    cyber_text = CYBER.read_text()

    # PART 1: raw proposals per missed concept (production labels/0.5)
    psych_raw = infer(psych_text, PRODUCTION_LABELS, 0.5)
    cyber_raw = infer(cyber_text, PRODUCTION_LABELS, 0.5)
    out["raw_proposals"] = {
        "psychology": [{"text": p["text"], "label": p["label"],
                        "score": round(p["score"], 3), "start": p["start"], "end": p["end"]}
                       for p in psych_raw],
        "cybersecurity": [{"text": p["text"], "label": p["label"],
                           "score": round(p["score"], 3), "start": p["start"], "end": p["end"]}
                          for p in cyber_raw],
    }

    baseline_psych = measure(PSYCH, PSYCH_GOLD, PRODUCTION_LABELS, 0.5)
    baseline_cyber = measure(CYBER, CYBER_GOLD, PRODUCTION_LABELS, 0.5)
    out["baseline"] = {"psychology": {k: v for k, v in baseline_psych.items() if k != "rows"},
                       "cybersecurity": {k: v for k, v in baseline_cyber.items() if k != "rows"}}

    # missed-entity table with per-concept classification
    table = []
    for doc, gold_rows in ((PSYCH, baseline_psych["rows"]), (CYBER, baseline_cyber["rows"])):
        for term, v in gold_rows.items():
            if v["class"] != "FOUND_EXACT":
                table.append({
                    "concept": term,
                    "class": v["class"],
                    "evidence": v["evidence"],
                    "document": doc.name,
                })
    out["missed_entity_table"] = table

    # PART 2: label schema variants
    for name, labels in (("A_generic", SCHEMA_A), ("B_psych_specific", SCHEMA_B),
                         ("C_mixed", SCHEMA_C)):
        m = measure(PSYCH, PSYCH_GOLD, labels, 0.5)
        out[f"schema_{name}"] = {k: v for k, v in m.items() if k != "rows"}

    # PART 4: threshold sweep (production labels)
    out["threshold_sweep"] = {}
    for t in (0.3, 0.4, 0.5, 0.6):
        m = measure(PSYCH, PSYCH_GOLD, PRODUCTION_LABELS, t)
        out["threshold_sweep"][str(t)] = {k: v for k, v in m.items() if k != "rows"}

    # PART 5: label guidance experiment
    guided = [
        "Psychological concept including cognitive processes, learning mechanisms, "
        "mental strategies, self-regulation concepts",
        "Concept", "Method", "Process",
    ]
    m = measure(PSYCH, PSYCH_GOLD, guided, 0.5)
    out["guided_labels"] = {k: v for k, v in m.items() if k != "rows"}

    print(json.dumps({
        "baseline": out["baseline"],
        "schemas": {k: v for k, v in out.items() if k.startswith("schema_")},
        "threshold_sweep": out["threshold_sweep"],
        "guided_labels": out["guided_labels"],
    }, indent=1))
    print("\n== missed entity table (baseline)")
    for row in table:
        print(f"  {row['concept']:28} {row['class']:14} evidence={row['evidence']}")
    (ROOT / "eval" / "e4" / "evidence.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote eval/e4/evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
