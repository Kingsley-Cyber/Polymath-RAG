"""Seeded eyes-on dump of N random parents: children text, section/S2/chunker summaries, digest, offset-verified mentions and relation quotes. Usage: .venv/bin/python scripts/quality_sample_dump.py "<source_name>" <seed> <out.md> — read-only."""
doc_name, seed, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"]); cur = conn.cursor()
cur.execute("select doc_id from documents where corpus_id='cysa-study-v1' and source_name=%s", (doc_name,)); doc = cur.fetchone()[0]
cur.execute("select chunk_id, chunk_index, heading_path, summary, region_role from chunks where doc_id=%s and tier='parent' order by chunk_index", (doc,))
parents = cur.fetchall()
rng = random.Random(seed); sample = sorted(rng.sample(parents, 10), key=lambda r: r[1])
cur.execute("select a.payload->'llm_extraction'->'digests' from artifacts a join runs r on r.run_id=a.run_id where r.corpus_id='cysa-study-v1' and a.stage='extract' and r.metadata->>'source_name'=%s", (doc_name,))
digests = {d["neighborhood_id"].split(":")[0]: d for d in (cur.fetchone()[0] or [])}
ws = lambda s: re.sub(r"\s+", " ", s or "").strip()
out = []
def P(s=""): out.append(s)
P(f"# SAMPLE — {doc_name} — {len(parents)} parents, 10 sampled (seed {seed})\n")
tot_m = ok_m = tot_r = ok_r = 0
for pid, idx, heading, psummary, role in sample:
    cur.execute("select chunk_id, chunk_index, text from chunks where parent_id=%s and tier='child' order by chunk_index", (pid,))
    kids = cur.fetchall()
    cur.execute("select summary_text, provenance from retrieval_summaries where parent_id=%s and kind='section_retrieval_summary'", (pid,))
    sec = cur.fetchone()
    cur.execute("select summary, entities, concepts from parent_summaries where parent_id=%s and superseded_at is null", (pid,))
    s2 = cur.fetchone()
    P(f"\n## PARENT {idx} `{pid[:22]}` heading={heading!r} region_role={role}")
    P(f"### CHILDREN ({len(kids)})")
    texts = {}
    for cid, ci, t in kids:
        texts[cid] = t
        P(f"- [{ci}] `{cid[:18]}` ({len(t)} ch): {ws(t)}")
    P(f"### SECTION SUMMARY (retrieval-summary-v2, {len(sec[0]) if sec else 0} ch): {ws(sec[0]) if sec else '—'}")
    P(f"### CHUNKER PARENT SUMMARY (summarizer.py, {len(psummary or '')} ch): {ws(psummary)}")
    if s2: P(f"### S2 PARENT_SUMMARIES: summary={ws(s2[0])!r} entities={s2[1]} concepts={s2[2]}")
    d = digests.get(pid)
    if d: P(f"### LLM DIGEST: claim={d.get('central_claim')!r} mechanism={d.get('main_mechanism')!r} uses={d.get('retrieval_uses')}")
    cur.execute("select chunk_id, surface, core_type, char_start, char_end, admission_class from mentions where chunk_id = any(%s) order by chunk_id, char_start", (list(texts),))
    ms = cur.fetchall(); mm = []
    for cid, surf, ct, a, b, adm in ms:
        tot_m += 1; hit = texts[cid][a:b] == surf; ok_m += hit
        mm.append(f"{surf}[{ct}{'' if hit else ' OFFSET-MISMATCH:'+repr(texts[cid][a:b][:30])}]")
    P(f"### ENTITIES/MENTIONS ({len(ms)}): " + "; ".join(mm))
    cur.execute("select chunk_id, surface, provider_label, char_start, char_end from raw_predicate_evidence where chunk_id = any(%s) order by chunk_id, char_start", (list(texts),))
    rs = cur.fetchall()
    P(f"### RELATION LEDGER ({len(rs)}):")
    for cid, surf, lab, a, b in rs:
        tot_r += 1; hit = texts[cid][a:b] == surf; ok_r += hit
        P(f"- {lab.split(':',1)[1]} ← {ws(surf)!r}{'' if hit else '  **OFFSET-MISMATCH** got '+repr(ws(texts[cid][a:b])[:40])}")
P(f"\n**OFFSET CHECK** mentions {ok_m}/{tot_m} exact; relation quotes {ok_r}/{tot_r} exact")
open(out_path, "w").write("\n".join(out)); print("\n".join(out))
