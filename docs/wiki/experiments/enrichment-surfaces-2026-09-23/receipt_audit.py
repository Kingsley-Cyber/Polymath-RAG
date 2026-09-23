"""ENRICHMENT-SURFACES-AUDIT (2026-09-23) — do enrichment-driven lanes reach the answer? Read-only, $0.

Reads the retrieval funnel every UI chat turn writes to `query_receipts.meta.funnel`:
  lanes   : lane -> candidate chunk ids that lane brought
  stages  : retrieved / union (both truncated to 100) / pre_rerank / post_rerank (cross-encoder order) / selected
            (the evidence rows the model saw) / cited (chunk ids behind the answer's [S#] tags)
and reports, per lane: turns it fired, chunks it brought, how many reached the rerank pool, the evidence (selected)
and the citations, and how many of those it brought ALONE (no other lane found them). Also: the share of evidence found
ONLY by enrichment lanes (not by plain dense / sparse child search), where the resolution-lift chunks sit in the
cross-encoder order, and the retrieve-phase latency per mode before / after the 5df4536 deploy.

usage: set -a; . ./.env; set +a; .venv/bin/python docs/wiki/experiments/enrichment-surfaces-2026-09-23/receipt_audit.py [out.json]
"""
import collections
import datetime
import json
import os
import statistics
import sys

import psycopg

BASELINE = {"global_dense_child", "global_sparse_child"}
DEPLOY_5DF4536 = "2026-09-23T03:00:00Z"   # merge 2026-09-23T02:49Z + one bounce (register 11.410)
NO_LANE = "(no lane: subquery / bridge rows)"


def load(conn, since, until=None):
    """UI turns received after `since` (and before `until` when given); both are timestamps."""
    with conn.cursor() as c:
        c.execute("""select mode, meta->'funnel', (meta->'phase_ms'->>'retrieve')::float from query_receipts
                     where kind='chat_stream' and status='ok' and meta ? 'funnel'
                       and received_at > %s and (%s::timestamptz is null or received_at <= %s::timestamptz)""",
                  (since, until, until))
        return c.fetchall()


def lane_table(rows):
    k = collections.defaultdict(collections.Counter)
    tot_sel = tot_cit = 0
    for _mode, f, _ms in rows:
        st = f.get("stages") or {}
        sel, cit = set(st.get("selected") or []), set(st.get("cited") or [])
        pre, post = set(st.get("pre_rerank") or []), set(st.get("post_rerank") or [])
        tot_sel += len(sel)
        tot_cit += len(cit)
        lanes = {ln: set(ids) for ln, ids in (f.get("lanes") or {}).items() if ids}
        arrivals = collections.defaultdict(set)
        for ln, ids in lanes.items():
            for x in ids:
                arrivals[x].add(ln)
        for ln, ids in lanes.items():
            s, ct = ids & sel, ids & cit
            k[ln].update(fired=1, brought=len(ids), pre_rerank=len(ids & pre), post_rerank=len(ids & post),
                         pre_rerank_alone=sum(1 for x in ids & pre if len(arrivals[x]) == 1),
                         selected=len(s), cited=len(ct), turns_selected=bool(s), turns_cited=bool(ct),
                         selected_alone=sum(1 for x in s if len(arrivals[x]) == 1),
                         cited_alone=sum(1 for x in ct if len(arrivals[x]) == 1))
        un_s, un_c = sel - set(arrivals), cit - set(arrivals)
        k[NO_LANE].update(fired=bool(un_s or un_c), selected=len(un_s), cited=len(un_c),
                          turns_selected=bool(un_s), turns_cited=bool(un_c))
    return {"turns": len(rows), "by_mode": dict(collections.Counter(m for m, _, _ in rows)),
            "selected_rows": tot_sel, "cited_rows": tot_cit,
            "lanes": {ln: dict(v) for ln, v in sorted(k.items(), key=lambda kv: -kv[1]["selected"])}}


def enrichment_only(rows):
    agg, per_mode = collections.Counter(), collections.defaultdict(collections.Counter)
    for mode, f, _ms in rows:
        st = f.get("stages") or {}
        sel, cit = set(st.get("selected") or []), set(st.get("cited") or [])
        arr = collections.defaultdict(set)
        for ln, ids in (f.get("lanes") or {}).items():
            for x in ids or []:
                arr[x].add(ln)

        def cls(x, arr=arr):
            a = arr.get(x)
            return "no_lane" if not a else ("baseline" if a & BASELINE else "enrichment_only")
        s = collections.Counter(cls(x) for x in sel)
        c = collections.Counter(cls(x) for x in cit & sel)
        for key, v in s.items():
            agg["selected_" + key] += v
            per_mode[mode]["selected_" + key] += v
        for key, v in c.items():
            agg["cited_" + key] += v
        agg["turns"] += 1
        per_mode[mode]["turns"] += 1
        agg["turns_selected_enrichment_only"] += bool(s["enrichment_only"])
        agg["turns_cited_enrichment_only"] += bool(c["enrichment_only"])
        per_mode[mode]["turns_cited_enrichment_only"] += bool(c["enrichment_only"])
    return {"all": dict(agg), "by_mode": {m: dict(v) for m, v in per_mode.items()}}


def lift_positions(rows):
    pos, sel_pos = collections.Counter(), collections.Counter()
    turns = only_lift = shared = 0
    for _mode, f, _ms in rows:
        st, lanes = f.get("stages") or {}, f.get("lanes") or {}
        post, sel = st.get("post_rerank") or [], set(st.get("selected") or [])
        lift = set(lanes.get("resolution_lift") or [])
        if not lift & set(post):
            continue
        turns += 1
        other = set().union(*[set(v) for ln, v in lanes.items() if ln != "resolution_lift" and v])
        only_lift += len((lift - other) & set(post))
        shared += len(lift & other & set(post))
        for i, x in enumerate(post):
            b = f"{5 * min(i // 5, 6) + 1}-{5 * min(i // 5, 6) + 5 if i < 30 else 'end'}"
            if x in lift:
                pos[b] += 1
            if x in sel:
                sel_pos[b] += 1
    return {"turns_with_lift_in_rerank_pool": turns, "lift_chunks_found_only_by_lift": only_lift,
            "lift_chunks_also_found_by_other_lanes": shared,
            "cross_encoder_rank_buckets_lift": dict(sorted(pos.items(), key=lambda kv: int(kv[0].split("-")[0]))),
            "cross_encoder_rank_buckets_selected": dict(sorted(sel_pos.items(), key=lambda kv: int(kv[0].split("-")[0])))}


def latency(rows):
    by = collections.defaultdict(list)
    for mode, _f, ms in rows:
        if ms is not None:
            by[mode].append(ms / 1000)
    out = {}
    for mode, v in sorted(by.items()):
        v.sort()
        out[mode] = {"n": len(v), "p50_s": round(statistics.median(v), 1), "p90_s": round(v[int(0.9 * (len(v) - 1))], 1),
                     "max_s": round(v[-1], 1)}
    return out


def main():
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"])
    week_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)
    deploy = datetime.datetime.fromisoformat(DEPLOY_5DF4536)
    week = load(conn, week_ago)
    before = load(conn, week_ago, deploy)
    after = load(conn, deploy)
    conn.close()
    out = {"generated_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
           "source": "query_receipts kind=chat_stream status=ok with meta.funnel (the owner's UI turns)",
           "lanes_7d": lane_table(week), "lanes_since_5df4536": lane_table(after),
           "enrichment_only_7d": enrichment_only(week), "resolution_lift_positions_7d": lift_positions(week),
           "retrieve_phase_latency": {"before_5df4536_7d": latency(before), "after_5df4536": latency(after)}}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
