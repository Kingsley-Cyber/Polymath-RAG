"""Eyes-on read of one run's extract artifact (dispositions, finish reasons, per-parent pattern vs a baseline, sampled parents). Usage: .venv/bin/python scripts/read_extract_artifact.py "<source_name LIKE>" [baseline.json]"""
import os, sys, json, collections, random, psycopg
sys.path.insert(0, "shared"); sys.path.insert(0, "workers")
like = sys.argv[1]
base = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {"documents": {}}
conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"]); c = conn.cursor()
c.execute("select r.run_id, r.metadata->>'source_name', a.payload from artifacts a join runs r on r.run_id=a.run_id where r.corpus_id='cysa-study-v1' and a.stage='extract' and r.metadata->>'source_name' like %s order by a.created_at desc limit 1", (like,))
row = c.fetchone()
if not row: print("no extract artifact yet"); sys.exit()
rid, name, p = row; llm = p["llm_extraction"]; st = llm["stats"]
print(f"== {name} run {rid[:16]} lane {llm['lane_decision']['lane']}")
print("stats:", {k: st.get(k) for k in ("calls","calls_reissue","calls_truncated","calls_salvaged","calls_quarantined","neighborhoods_sent","neighborhoods_returned","neighborhoods_returned_empty","neighborhoods_reissued","neighborhoods_recovered","neighborhoods_incomplete_kept","neighborhoods_dropped","neighborhoods_unaccounted","parents_total","parents_with_extraction","entities","relations","entities_rejected","relations_rejected","predicate_fallbacks")})
print("rejections_by_class:", st.get("rejections_by_class"))
calls = llm["calls"]
print("finish_reason:", collections.Counter(c_.get("finish_reason") for c_ in calls), "| reissue calls:", sum(1 for c_ in calls if c_.get("reissue")), "| ids/call:", collections.Counter(len(c_.get("neighborhood_ids") or []) for c_ in calls))
touts = sorted(c_.get("tokens_out") or 0 for c_ in calls); print("tokens_out min/med/max:", touts[0], touts[len(touts)//2], touts[-1], "| tokens_in med:", sorted(c_.get("tokens_in") or 0 for c_ in calls)[len(calls)//2])
disp = collections.Counter(d["disposition"] for d in llm.get("neighborhood_dispositions", [])); print("dispositions:", dict(disp))
direct = p.get("llm_direct") or {}; print("llm_direct:", {k: direct.get(k) for k in ("seen","written","unknown_predicates")}, "predicates:", direct.get("predicates"))
# per-parent pattern vs baseline
c.execute("select doc_id from documents where source_name=%s", (name,)); doc = c.fetchone()[0]
c.execute("""select p.chunk_id, p.chunk_index, count(m.mention_id), count(distinct e.evidence_id) from chunks p join chunks ch on ch.parent_id=p.chunk_id and ch.tier='child'
             left join mentions m on m.chunk_id=ch.chunk_id left join evidence e on e.chunk_id=ch.chunk_id where p.doc_id=%s and p.tier='parent' group by 1,2 order by 2""", (doc,))
rows = c.fetchall()
pat_new = "".join("X" if r[2] > 0 else "." for r in rows)
bdoc = base["documents"].get(doc, {}).get("parents", {})
pat_old = "".join("X" if bdoc.get(r[0], {}).get("mentions", 0) > 0 else "." for r in rows) if bdoc else "(no baseline)"
print(f"parents with entities: new {pat_new.count('X')}/{len(rows)}  baseline {pat_old.count('X') if bdoc else '-'}/{len(rows)}")
print("new :", pat_new); print("old :", pat_old)
print("evidence rows (facts w/ offsets) on parents:", sum(1 for r in rows if r[3] > 0))
# eyes on: 4 random parents — entities + relations + quotes
random.seed(20260830); sample = random.sample(rows, min(4, len(rows)))
for pid, idx, nm, ne in sorted(sample, key=lambda r: r[1]):
    c.execute("select surface, core_type from mentions where chunk_id in (select chunk_id from chunks where parent_id=%s) order by char_start limit 12", (pid,))
    ents = c.fetchall()
    c.execute("""select f.predicate, e.span_offsets->>'subject_surface', e.span_offsets->>'object_surface', e.span_offsets->>'evidence_surface' from evidence e join facts f on f.fact_id=e.fact_id
                 where e.chunk_id in (select chunk_id from chunks where parent_id=%s) limit 6""", (pid,))
    rels = c.fetchall()
    print(f"\n-- PARENT {idx} {pid[:18]} mentions={nm} evidence={ne} (baseline mentions {bdoc.get(pid, {}).get('mentions', '-')})")
    print("   entities:", "; ".join(f"{s}[{t}]" for s, t in ents))
    for pr, s, o, q in rels: print(f"   {s} --{pr}--> {o}   ⟵ {q[:120]!r}")
