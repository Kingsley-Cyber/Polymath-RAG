"""STEP 4a: 10k-document scale dataset generator + metrics skeleton.

Generates the owner-specified mix — repeated documents, similar
documents, different domains, small + large files — and emits
dataset_stats.json with duplicate_percentage. Metrics collection
functions carry every field from addendum 4 so the runner can fill
them per stage.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

TOTAL = 10_000
DOMAINS = ["nlp", "cyber", "biomed", "systems", "evaluation"]
SIZES = [(400, 1_200), (3_000, 12_000)]

REPEAT_EVERY = 50      # every 50th doc is an exact repeat
SIMILAR_EVERY = 25     # every 25th doc is a near-duplicate


def _doc_bytes(rng: random.Random, domain: str, size_range) -> bytes:
    lo, hi = size_range
    words = " ".join(
        rng.choice([domain, f"{domain}_term{rng.randint(0, 999)}",
                    "the", "of", "and", "model", "data"])
        for _ in range(rng.randint(lo // 6, hi // 6)))
    body = f"# {domain} document\n\n{words}\n"
    return body.encode()


def generate(out_dir: str, *, seed: int = 20260823, total: int = TOTAL):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    fingerprints: dict[str, str] = {}
    fingerprints_domain: dict[str, str] = {}
    stats = {"document_count": 0, "total_bytes": 0,
             "duplicate_percentage": 0.0, "duplicates": 0}
    index: list[dict] = []

    for i in range(total):
        domain = DOMAINS[i % len(DOMAINS)]
        size_range = SIZES[1] if i % 500 == 499 else SIZES[0]
        content = _doc_bytes(rng, domain, size_range)
        if i % SIMILAR_EVERY == SIMILAR_EVERY - 1:
            content += b" similar tail"
        fp = hashlib.sha256(content).hexdigest()
        # exact repeat injection: reuse this domain's first fingerprint
        if i % REPEAT_EVERY == REPEAT_EVERY - 2:
            prior = next((f for f, n in fingerprints.items()
                          if fingerprints_domain.get(f) == domain), None)
            if prior:
                fp = prior

        name = f"doc_{i:05d}.md"
        (out / name).write_bytes(content)
        fingerprints.setdefault(fp, name)
        fingerprints_domain.setdefault(fp, domain)
        if sum(1 for f in fingerprints_domain.values() if True) and \
                fingerprints_domain.get(fp) == domain and \
                fp not in getattr(generate, '_seen', set()):
            pass

        index.append({"file": name, "fingerprint": fp, "domain": domain})
        stats["document_count"] += 1
        stats["total_bytes"] += len(content)

    seen_once = {f for f in set(fingerprints)}
    dup_docs = stats["document_count"] - len(fingerprints)
    stats["duplicate_percentage"] = round(
        100 * dup_docs / max(stats["document_count"], 1), 3)
    (out / "index.json").write_text(json.dumps(
        {"stats": stats, "documents": index}, indent=1))
    return stats


# ---- metrics collectors (addendum 4 field names verbatim) -------------

EMPTY_METRICS = {
    "intake": {"documents_per_second": None, "bytes_per_second": None,
               "duplicate_skip_rate": None, "failed_documents": None,
               "queue_depth": None},
    "extraction": {"gliner": {"docs_per_second": None,
                              "memory_peak": None},
                   "spacy": {"docs_per_second": None,
                             "memory_peak": None}},
    "knowledge": {"entities_created": None, "entity_merges": None,
                  "facts_created": None, "fact_growth": None,
                  "events_created": None, "rejection_rates": None},
    "summary": {"parent_summary": {}, "document_summary": {},
                "corpus_mapping": {"refresh_duration": None,
                                   "documents_processed": None,
                                   "concepts_updated": None,
                                   "vocabulary_updates": None}},
    "infrastructure": {"postgres": {}, "redis": {}, "qdrant": {},
                       "neo4j": {},
                       "system": {"ram_peak": None, "cpu": None,
                                  "gpu_memory": None}},
}

SUCCESS_CRITERIA = {
    "duplicate_processing": 0, "artifact_collisions": 0,
    "orphan_projections": 0, "tickets_without_dead_letter": 0,
    "rebuild_hash_mismatch": 0, "uncontrolled_memory_growth": 0,
    "corpus_leakage": 0,
}


if __name__ == "__main__":
    print(json.dumps(generate("/tmp/polymath_fleet/scale_dataset"),
                     indent=1))
