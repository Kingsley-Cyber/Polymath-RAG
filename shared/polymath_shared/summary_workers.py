"""SUMMARY-VOCABULARY-LAYER S3-S5: document/corpus summaries +
vocabulary admission. Deterministic composition over upstream artifacts;
consumes ONLY the previous waterfall layer."""
from __future__ import annotations

from collections import Counter

from polymath_shared.summary_layer import build_envelope


def build_document_summary(*, document_id: str, title: str,
                           parent_summaries: list[dict]) -> dict:
    """Input: parent-summary envelopes (payloads). Never raw text."""
    entity_freq: Counter = Counter()
    concept_freq: Counter = Counter()
    summary_lines: list[str] = []
    derived: list[str] = []
    for ps in parent_summaries:
        p = ps.get("payload", ps)
        derived.append(p.get("parent_id") or ps.get("artifact_id", ""))
        for e in p.get("entities", []):
            entity_freq[e] += 1
        for cpt in p.get("concepts", []):
            concept_freq[cpt] += 1
        s = p.get("summary") or ""
        if s:
            summary_lines.append(s)
    top_entities = [e for e, _ in entity_freq.most_common(8)]
    top_concepts = [c for c, _ in concept_freq.most_common(8)]
    lead = f"{title} — " if title else ""
    body = " ".join(summary_lines[:3])
    payload = {
        "summary_type": "document",
        "document_id": document_id,
        "summary": (lead + body).strip(),
        "major_entities": top_entities,
        "major_concepts": top_concepts,
        "derived_from": derived,
    }
    return build_envelope(derived_from=derived, payload=payload)


def build_corpus_summary(*, corpus_id: str,
                         document_summaries: list[dict]) -> dict:
    """Input: document-summary envelopes. Produces the routing map."""
    concepts: Counter = Counter()
    entities: Counter = Counter()
    predicates: Counter = Counter()
    derived: list[str] = []
    for ds in document_summaries:
        p = ds.get("payload", ds)
        derived.extend(p.get("derived_from", []))
        for e in p.get("major_entities", []):
            entities[e] += 1
        for c in p.get("major_concepts", []):
            concepts[c] += 1
        for line in [p.get("summary") or ""]:
            pass
        for pred in p.get("predicates", []):
            predicates[pred] += 1
    payload = {
        "summary_type": "corpus",
        "corpus_id": corpus_id,
        "dominant_concepts": [c for c, _ in concepts.most_common(10)],
        "important_entities": [e for e, _ in entities.most_common(10)],
        "common_predicates": [p for p, _ in predicates.most_common(8)],
    }
    return build_envelope(derived_from=sorted(set(derived)),
                          payload=payload)


def vocabulary_admission(*, document_summaries: list[dict],
                         accepted_facts: list[dict]) -> dict:
    """Concept candidates from summaries; aliases accumulate with
    supporting provenance; no forced merge (alias families)."""
    families: dict[str, dict] = {}
    for fact in accepted_facts:
        key = str(fact.get("predicate") or "").lower()
        if not key:
            continue
        fam = families.setdefault(key, {
            "concept": key, "aliases": set(), "supported_by": set()})
        fam["aliases"].add(key.replace("_", " "))
        fam["supported_by"].add(fact.get("fact_id") or "")
    for ds in document_summaries:
        p = ds.get("payload", ds)
        aid = ds.get("artifact_id", "")
        for cpt in p.get("major_concepts", []):
            key = cpt.lower().replace(" ", "_")
            fam = families.setdefault(key, {
                "concept": key, "aliases": {cpt.lower()},
                "supported_by": set()})
            fam["aliases"].add(cpt.lower())
            fam["supported_by"].add(aid)
    return {"contract": "vocabulary-admission-v1",
            "entries": [
                {"concept": f["concept"],
                 "aliases": sorted(f["aliases"]),
                 "supported_by": sorted(x for x in f["supported_by"] if x)}
                for f in sorted(families.values(),
                                key=lambda x: x["concept"])]}
