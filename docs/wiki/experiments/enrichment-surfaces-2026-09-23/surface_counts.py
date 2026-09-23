"""ENRICHMENT-SURFACES-AUDIT (2026-09-23) — what the profile and atom stores hold, per corpus. Read-only, $0.

Counts profile points by corpus and prompt version, the size of each profile multivector on the corpus's points, atom
points by corpus and kind, parent-map (pMAP) points by corpus, and the concept families / aliases the resolution lift reads
(Postgres, the same query as `LiveLiftSources.aliases`). The question it answers: which items can reach a lane at all.

usage: set -a; . ./.env; set +a; .venv/bin/python docs/wiki/experiments/enrichment-surfaces-2026-09-23/surface_counts.py [out.json]
"""
import collections
import datetime
import json
import os
import statistics
import sys

import psycopg
from qdrant_client import QdrantClient, models

QDRANT = "http://127.0.0.1:6334"   # settings.qdrant_url
PROFILES = "polymath_document_profiles_embed_e794ec4cab197a3f"
ATOMS = "polymath_document_profile_atoms_embed_e794ec4cab197a3f"
PARENT_MAPS = "polymath_document_parent_maps_embed_e794ec4cab197a3f"


def scroll(q, col, fields, flt=None, vectors=False):
    out, off = [], None
    while True:
        pts, off = q.scroll(col, scroll_filter=flt, limit=256, offset=off, with_payload=fields, with_vectors=vectors)
        out += pts
        if off is None:
            return out


def main():
    q = QdrantClient(url=QDRANT, timeout=60)
    prof = scroll(q, PROFILES, ["corpus_id", "prompt_version", "profile_version"])
    by_corpus = collections.Counter(p.payload.get("corpus_id") for p in prof)
    versions = collections.Counter((p.payload.get("corpus_id"), str(p.payload.get("prompt_version") or p.payload.get("profile_version")))
                                   for p in prof)
    multivec = {}
    for corpus in sorted(by_corpus, key=str):
        flt = models.Filter(must=[models.FieldCondition(key="corpus_id", match=models.MatchValue(value=corpus))])
        sizes = collections.defaultdict(list)
        for p in scroll(q, PROFILES, False, flt, vectors=True):
            for name, v in (p.vector or {}).items():
                sizes[name].append(len(v) if v and isinstance(v[0], list) else 1)
        multivec[corpus] = {name: {"points": len(v), "mean_items": round(statistics.mean(v), 1), "total_items": sum(v)}
                            for name, v in sorted(sizes.items())}
    atoms = scroll(q, ATOMS, ["corpus_id", "atom_kind", "kind", "doc_id"])
    atom_kinds = collections.defaultdict(collections.Counter)
    atom_docs = collections.defaultdict(set)
    for p in atoms:
        corpus = p.payload.get("corpus_id")
        atom_kinds[corpus][p.payload.get("atom_kind") or p.payload.get("kind")] += 1
        atom_docs[corpus].add(p.payload.get("doc_id"))
    pmap = collections.Counter(p.payload.get("corpus_id") for p in scroll(q, PARENT_MAPS, ["corpus_id"]))
    with psycopg.connect(os.environ["POLYMATH_PG_DSN"]) as conn, conn.cursor() as c:
        c.execute("""select f.corpus_id, count(distinct f.concept_id), count(a.alias)
                     from concept_families f left join concept_aliases a on a.concept_id=f.concept_id group by 1""")
        vocab = {r[0]: {"concept_families": r[1], "aliases": r[2]} for r in c.fetchall()}
    out = {"generated_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
           "parent_map_points_by_corpus": dict(pmap),
           "lift_vocabulary_by_corpus": vocab,
           "profiles": {"points_by_corpus": dict(by_corpus),
                        "versions": {f"{c}|{v}": n for (c, v), n in sorted(versions.items(), key=str)},
                        "multivector_items_by_corpus": multivec},
           "atoms": {c: {"docs": len(atom_docs[c]), "points": sum(k.values()), "by_kind": dict(sorted(k.items(), key=str))}
                     for c, k in sorted(atom_kinds.items(), key=str)}}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
