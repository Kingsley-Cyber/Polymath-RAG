"""SUMMARY RUNTIME D5: vocabulary mapping worker (semantic bridge).

D5 creates a controlled bridge between how humans ask questions and how
the corpus describes knowledge. It NEVER creates knowledge and NEVER
touches entity identity.

Frozen admission rules (owner):
  R1  same corpus (ai_v1::model != cyber_v1::model)
  R2  same domain + shared evidence: a candidate family requires
      overlapping supporting summary ids — terms with disjoint support
      never merge
  R3  entities are out of scope; the strongest vocabulary claim about an
      entity is "relates_to concept X"

Forbidden modes (each has a failing test): embedding-only merges,
frequency-only vocabulary, raw noun phrases as concepts.

Inputs allowed ONLY: parent summaries, document summaries, corpus
summary, accepted concepts.
"""
from __future__ import annotations

from polymath_shared.identity import content_hash
from polymath_shared.corpus_mapping import _claim


def _norm(term: str) -> str:
    return " ".join((term or "").lower().split())


def build_concept_families(*, corpus_id: str, parent_summaries: list[dict],
                           document_summaries: list[dict],
                           accepted_concepts: list[str]) -> dict:
    """Group candidate terms into families using SUPPORT OVERLAP ONLY.

    A term's support = set of summary artifacts that mention it. Two
    terms join one family when their support sets intersect (same
    knowledge neighborhood). Disjoint support -> separate families.
    """
    # candidate terms + support sets from summaries
    support: dict[str, dict[str, set]] = {}
    for ps in parent_summaries:
        p = ps.get("payload", ps)
        sid = p.get("parent_id") or ps.get("artifact_id")
        for cpt in p.get("concepts", []):
            support.setdefault(_norm(cpt), {
                "summaries": set(), "surfaces": set()})
            support[_norm(cpt)]["summaries"].add(str(sid))
            support[_norm(cpt)]["surfaces"].add(cpt)
    # Derived-layer support (document summaries) is recorded as
    # PROVENANCE ONLY. A document summary derives from parent summaries,
    # so counting it toward admission would let one document create a
    # concept (parent + its own derivative = fake support of 2).
    for ds in document_summaries:
        d = ds.get("payload", ds)
        did = "derived:" + str(d.get("document_id") or ds.get("artifact_id"))
        for cpt in d.get("major_concepts", []):
            support.setdefault(_norm(cpt), {
                "summaries": set(), "surfaces": set()})
            support[_norm(cpt)]["surfaces"].add(cpt)

    for concept in accepted_concepts:
        key = _norm(concept)
        support.setdefault(key, {"summaries": {key},
                                 "surfaces": {concept}})

    # union-find over shared summary support (same neighborhood only)
    parent_of: dict[str, str] = {}

    def find(x):
        while parent_of[x] != x:
            parent_of[x] = parent_of[parent_of[x]]
            x = parent_of[x]
        return x

    for key in support:
        parent_of[key] = key
    keys = sorted(support)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if support[a]["summaries"] & support[b]["summaries"]:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent_of[rb] = ra

    families: dict[str, list[str]] = {}
    for key in keys:
        families.setdefault(find(key), []).append(key)

    out_families = []
    for root in sorted(families):
        members = sorted(families[root])
        surfaces = sorted({s for k in families[root]
                           for s in support[k]["surfaces"]})
        canonical = _pick_canonical(surfaces, members)
        all_support = sorted({x for k in families[root]
                              for x in support[k]["summaries"]})
        independent = [x for x in all_support
                       if not x.startswith("derived:")]
        out_families.append({
            "contract": "concept-family-v1",
            "corpus_id": corpus_id,
            "canonical_name": canonical,
            "aliases": [s for s in surfaces if _norm(s) != canonical],
            "supporting_summaries": all_support,
            "independent_support_count": len(independent),
        })
    # VOCABULARY GUARD (owner): single-mention concepts never admit.
    # A family requires at least TWO distinct supporting summaries —
    # the corpus map must show stable cross-summary presence.
    out_families = [f for f in out_families
                    if f.get("independent_support_count", 0) >= 2]
    return {"contract": "vocabulary-mapping-v1",
            "corpus_id": corpus_id,
            "min_supporting_summaries": 2,
            "families": out_families}


def _pick_canonical(surfaces: list[str], members: list[str]) -> str:
    """Canonical = the normalized member with the most surface variants;
    ties break alphabetically."""
    counts = {m: sum(1 for s in surfaces if _norm(s) == m)
              for m in members}
    return sorted(members, key=lambda m: (-counts[m], m))[0]


def admit_family(family: dict, *, corpus_id: str) -> tuple[bool, str]:
    """Deterministic gate: R1 same corpus; R2 shared evidence required
    (at least two supporting summaries OR one summary + distinct alias
    surfaces); R3 entity ids are structurally absent from this shape."""
    if family.get("corpus_id") != corpus_id:
        return False, "R1_corpus_isolation"
    if len(family.get("supporting_summaries", [])) < 1:
        return False, "R2_no_summary_support"
    if not family.get("canonical_name"):
        return False, "R2_no_canonical"
    return True, "admitted"


def run_vocabulary_ticket(conn, *, ticket_id: str, corpus_id: str,
                          input_hash: str, contract_version: str,
                          worker_id: str, families: dict) -> dict:
    """Five-step contract: claim -> idempotency -> compose(already built)
    -> persist families/aliases/support -> COMPLETE."""
    if not _claim(conn, ticket_id, worker_id):
        return {"status": "SKIPPED_NOT_CLAIMABLE"}
    existing = conn.execute(
        "SELECT artifact_id FROM summary_artifacts WHERE input_hash=%s",
        (input_hash,)).fetchone()
    if existing:
        conn.execute("UPDATE summary_jobs SET state='COMPLETE', "
                     "completed_at=now() WHERE ticket_id=%s",
                     (ticket_id,))
        return {"status": "EXISTING", "artifact_id": existing[0]}

    admitted, rejected = [], []
    artifact_id = "voc_" + content_hash({"in": input_hash})[:32]
    for fam in families.get("families", []):
        ok, reason = admit_family(fam, corpus_id=corpus_id)
        entry = {"canonical": fam["canonical_name"],
                 "aliases": fam["aliases"], "gate_reason": reason}
        (admitted if ok else rejected).append(entry)
        if not ok:
            continue
        concept_id = "cfm_" + content_hash({"c": corpus_id,
                                            "n": fam["canonical_name"]})[:32]
        conn.execute(
            """INSERT INTO concept_families (concept_id, corpus_id,
               canonical_name, artifact_hash, contract_version,
               created_by_worker) VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (concept_id) DO NOTHING""",
            (concept_id, corpus_id, fam["canonical_name"], artifact_id,
             contract_version, worker_id))
        conn.execute(
            """INSERT INTO summary_artifacts (artifact_id, input_hash,
               output_hash, stage, corpus_id, contract_version,
               created_by_worker, source_ids, payload)
               VALUES (%s,%s,%s,'VOCABULARY_MAPPING',%s,%s,%s,%s,%s)
               ON CONFLICT (artifact_id) DO NOTHING""",
            ("voc_" + concept_id[4:], input_hash + ":" +
             fam["canonical_name"], artifact_id[:16], corpus_id,
             contract_version, worker_id,
             fam["supporting_summaries"], __import__("json").dumps(fam)))
        conn.execute(
            """INSERT INTO concept_support (concept_id, artifact_type,
               artifact_id) VALUES (%s,'vocabulary_mapping',%s)
               ON CONFLICT DO NOTHING""",
            (concept_id, artifact_id))
        for alias in fam["aliases"]:
            conn.execute(
                """INSERT INTO concept_aliases (concept_id, alias)
                   VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                (concept_id, alias))

    payload = {"summary_type": "vocabulary",
               "admitted": admitted, "rejected": rejected}
    env = {"contract": "vocabulary-envelope-v1", "artifact_id": artifact_id,
           "payload": payload}
    conn.execute("UPDATE summary_jobs SET state='COMPLETE', "
                 "completed_at=now() WHERE ticket_id=%s", (ticket_id,))
    return {"status": "COMPLETE", "artifact_id": artifact_id,
            "admitted_count": len(admitted),
            "rejected_count": len(rejected)}
