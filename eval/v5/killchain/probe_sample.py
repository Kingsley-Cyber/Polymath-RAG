"""Quality probe: 4 random samples per critical phase.
Seeded, so the sample is reproducible and not cherry-picked."""
import random
import re
import sys
import textwrap

import psycopg

sys.path[:0] = ["shared", "workers", "."]
DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "quality-probe-v1"
random.seed(4)

c = psycopg.connect(DSN, connect_timeout=5)
doc = c.execute("SELECT doc_id FROM documents WHERE corpus_id=%s",
                (CORPUS,)).fetchone()[0]
src = open("/private/tmp/claude-501/-Users-king/"
           "f32f3c52-f653-4a47-91f8-494c6fb7a472/scratchpad/domain1.md").read()


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def w(s, n=200):
    return textwrap.shorten(" ".join(str(s).split()), n, placeholder=" …")


# ------------------------------------------------- PHASE 1: CHUNKING
head("PHASE 1 — CHUNKING  (4 random child chunks)")
rows = c.execute(
    "SELECT chunk_id, chunk_index, text, char_start, char_end, "
    "chunk_contract_version FROM chunks WHERE doc_id=%s AND tier='child' "
    "ORDER BY chunk_index", (doc,)).fetchall()
print(f"population: {len(rows)} child chunks")
for cid, idx, text, a, b, ver in random.sample(rows, 4):
    glued = bool(re.search(r"[^\n]\s#+ ", text))
    frag = not text.rstrip().endswith((".", "!", "?", ":", '"'))
    print(f"\n  chunk[{idx}] {ver}  span={a}:{b}  len={len(text)}")
    print(f"    newlines={text.count(chr(10))}  heading_glued={glued}  "
          f"ends_mid_sentence={frag}")
    print(f"    verbatim_in_source={text[:60] in src or text[:60].replace(chr(10),' ') in src}")
    print(f"    text: {w(text, 150)}")

# ------------------------------------------------ PHASE 2: SUMMARIES
head("PHASE 2 — SUMMARIES  (4 random parent summaries)")
rows = c.execute(
    "SELECT parent_id, summary, entities, concepts, superseded_at "
    "FROM parent_summaries WHERE corpus_id=%s AND superseded_at IS NULL",
    (CORPUS,)).fetchall()
print(f"population: {len(rows)} authoritative parent summaries "
      f"(superseded: "
      f"{c.execute('SELECT count(*) FROM parent_summaries WHERE corpus_id=%s AND superseded_at IS NOT NULL',(CORPUS,)).fetchone()[0]})")
for pid, summ, ents, cons, sup in random.sample(rows, 4):
    print(f"\n  parent {pid[:20]}  entities={len(ents or [])} concepts={len(cons or [])}")
    print(f"    summary: {w(summ, 170)}")
    print(f"    entities: {(ents or [])[:6]}")

# ------------------------------------------------- PHASE 3: ENTITIES
head("PHASE 3 — ENTITIES  (4 random durable entities)")
rows = c.execute(
    "SELECT DISTINCT m.surface, m.core_type, m.admission_class "
    "FROM mentions m WHERE m.doc_id=%s AND m.admission_class<>'MENTION_ONLY'",
    (doc,)).fetchall()
tot = c.execute("SELECT count(*) FROM mentions WHERE doc_id=%s",
                (doc,)).fetchone()[0]
print(f"population: {len(rows)} durable surfaces from {tot} mentions")
for surf, ctype, cls in random.sample(rows, 4):
    hits = src.lower().count(surf.lower())
    print(f"  {surf!r:<40} {ctype:<14} {cls:<14} occurrences_in_source={hits}")

# ---------------------------------------------------- PHASE 4: FACTS
head("PHASE 4 — FACTS  (4 random accepted facts)")
rows = c.execute(
    """SELECT f.predicate, e1.normalized_surface, e2.normalized_surface,
              ev.chunk_id
         FROM facts f
         JOIN evidence ev ON ev.fact_id=f.fact_id
         JOIN entities e1 ON e1.entity_id=f.subject_id
         JOIN entities e2 ON e2.entity_id=f.object_id
        WHERE ev.doc_id=%s AND f.decision='ACCEPT'""", (doc,)).fetchall()
print(f"population: {len(rows)} accepted fact-evidence rows "
      f"(candidates: {c.execute('SELECT count(*) FROM relation_candidates WHERE doc_id=%s',(doc,)).fetchone()[0]})")
for pred, s, o, ch in random.sample(rows, min(4, len(rows))):
    txt = c.execute("SELECT text FROM chunks WHERE chunk_id=%s",
                    (ch,)).fetchone()
    supported = bool(txt and s.split()[0].lower() in txt[0].lower()
                     and o.split()[0].lower() in txt[0].lower())
    print(f"  {s} --{pred}--> {o}")
    print(f"      both endpoints present in cited chunk: {supported}")

# ----------------------------------------------- PHASE 5: PROCEDURES
head("PHASE 5 — PROCEDURES  (4 random)")
rows = c.execute("SELECT goal, steps_json, confidence FROM procedure_artifacts "
                 "WHERE document_id=%s", (doc,)).fetchall()
print(f"population: {len(rows)} procedures (v1 would emit exactly 1)")
import json as _j
for goal, steps, conf in random.sample(rows, 4):
    st = steps if isinstance(steps, list) else _j.loads(steps or "[]")
    verbatim = all(" ".join(str(s).split()) in " ".join(src.split()) for s in st)
    print(f"\n  goal: {w(goal,110)}")
    print(f"    steps={len(st)} confidence={conf} all_steps_verbatim={verbatim}")
    for s in st[:2]:
        print(f"      - {w(s,110)}")

# ------------------------------------------------- PHASE 6: CONCEPTS
head("PHASE 6 — CONCEPTS  (4 random)")
rows = c.execute("SELECT name, description FROM concept_artifacts "
                 "WHERE document_id=%s", (doc,)).fetchall()
print(f"population: {len(rows)} concepts (v1 cap would be 10)")
for name, desc in random.sample(rows, 4):
    print(f"  {name!r}")
    print(f"      {w(desc,140)}")
