#!/usr/bin/env python
"""extraction-observability-v1 trace reports (repo-native CLI).

Usage:
  python scripts/trace_report.py run <run_id>
  python scripts/trace_report.py surface <run_id> "bounded leases"
  python scripts/trace_report.py sentence <sentence_id>
  python scripts/trace_report.py waterfall <run_id>

Add --all to any command to union every configuration ever recorded for
the target instead of the newest one.

SCOPING: run_ids are deterministic (same canonical input -> same run_id),
so a run_id identifies a DOCUMENT, not one execution. Re-ingesting the
same corpus under a different pipeline / rule pack / chunker appends to
the SAME run_id. These reports therefore scope to the most recent
extraction contract by default and print the scope they used; without
that a waterfall silently unions every experiment ever run.

Reads extraction_trace_events + semantic tables; analysis only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))


def _conn():
    import psycopg

    from polymath_shared.settings import get_settings

    return psycopg.connect(get_settings().postgres.dsn)



# --- contract scoping -----------------------------------------------------
SHOW_ALL = False


def _scope(c, run_id: str):
    """Newest (relation_pipeline, rule_pack_version, chunk_contract_hash)
    recorded for this run_id, or None when unioning."""
    if SHOW_ALL:
        return None
    row = c.execute(
        """SELECT envelope->>'relation_pipeline', envelope->>'rule_pack_version',
                  envelope->>'chunk_contract_hash'
             FROM extraction_trace_events WHERE run_id=%s
            GROUP BY 1,2,3 ORDER BY MAX(created_at) DESC LIMIT 1""",
        (run_id,)).fetchone()
    return row


def _scope_sql(scope, alias: str = ""):
    """(sql_fragment, params) restricting to one extraction contract."""
    if scope is None:
        return "", ()
    p = f"{alias}." if alias else ""
    return (f" AND {p}envelope->>'relation_pipeline' IS NOT DISTINCT FROM %s"
            f" AND {p}envelope->>'rule_pack_version' IS NOT DISTINCT FROM %s"
            f" AND {p}envelope->>'chunk_contract_hash' IS NOT DISTINCT FROM %s"), tuple(scope)


def _print_scope(c, run_id: str, scope) -> None:
    if scope is None:
        n = c.execute("SELECT COUNT(DISTINCT (envelope->>'relation_pipeline', "
                      "envelope->>'rule_pack_version', envelope->>'chunk_contract_hash')) "
                      "FROM extraction_trace_events WHERE run_id=%s", (run_id,)).fetchone()[0]
        print(f"SCOPE: ALL configurations ({n} distinct) — counts are a union, not one run")
        return
    print(f"SCOPE: pipeline={scope[0] or 'unrecorded'} pack={scope[1]} chunker={scope[2]}")
    others = c.execute(
        """SELECT COUNT(*) FROM (SELECT 1 FROM extraction_trace_events WHERE run_id=%s
             GROUP BY envelope->>'relation_pipeline', envelope->>'rule_pack_version',
                      envelope->>'chunk_contract_hash') t""", (run_id,)).fetchone()[0]
    if others > 1:
        print(f"       ({others - 1} older configuration(s) hidden; --all to include)")


def cmd_surface(run_id: str, surface: str) -> None:
    c = _conn()
    print(f"SURFACE: {surface}")
    scope = _scope(c, run_id)
    _print_scope(c, run_id, scope)
    sql, sp = _scope_sql(scope)
    like = f"%{surface.lower()}%"
    rows = c.execute(
        "SELECT event_type, decision, reason_code, sentence_id, detail FROM extraction_trace_events "
        "WHERE run_id=%s AND lower(surface) LIKE %s" + sql + " ORDER BY created_at",
        (run_id, like, *sp)).fetchall()
    if not rows:
        rows = c.execute(
            "SELECT event_type, decision, reason_code, sentence_id, detail FROM extraction_trace_events "
            "WHERE run_id=%s AND lower(envelope::text) LIKE %s" + sql + " ORDER BY created_at LIMIT 20",
            (run_id, like, *sp)).fetchall()
    mention = c.execute(
        "SELECT normalized_surface, core_type, admission_class, gliner_score FROM mentions "
        "WHERE corpus_id=(SELECT corpus_id FROM runs WHERE run_id=%s) AND normalized_surface LIKE %s "
        "ORDER BY gliner_score DESC LIMIT 3", (run_id, like)).fetchall()
    print(f"FOUND IN SOURCE       {'YES' if rows or mention else 'CHECK CHUNKS'}")
    if mention:
        m = mention[0]
        print(f"GLINER                 YES ({round(m[3],3)}, core={m[1]}, raw label in detail)")
        print(f"MENTION PERSISTED      YES ({m[0]})")
        print(f"ADMISSION              {m[2]}")
    else:
        print("GLINER                 NO (no durable mention)")
    np_hit = c.execute(
        "SELECT COUNT(*) FROM extraction_trace_events WHERE run_id=%s AND event_type='syntax' "
        "AND lower(envelope::text) LIKE %s", (run_id, like)).fetchone()[0]
    print(f"SPACY NP EVIDENCE      {'YES' if np_hit else 'see syntax events (full mode)'}")
    cand = [r for r in rows if r[0] in ("candidate", "first_loss")]
    compiler = [r for r in rows if r[0] == "compiler"]
    fact = [r for r in rows if r[0] == "fact"]
    if cand:
        print("CANDIDATE PARTICIPATION:")
        for r in cand[:6]:
            d = r[4] if isinstance(r[4], dict) else {}
            print(f"   [{r[0]}] {r[2]:32} trigger={d.get('trigger')!r} subj={d.get('subject')!r} obj={d.get('object')!r}")
    else:
        print("CANDIDATE PARTICIPATION NONE")
    for r in compiler[:4]:
        print(f"   compiler: {r[1]} {r[2]}")
    for r in fact[:2]:
        print(f"   fact: {r[1]}")
    losses = [r for r in rows if r[0] == "first_loss"]
    if losses:
        d = losses[0][4] if isinstance(losses[0][4], dict) else {}
        print("WHY?")
        print(f"   {losses[0][2]} — {json.dumps(d)[:220]}")
        print(f"FIRST LOSS: {d.get('first_loss_stage')}")
    c.close()


def cmd_sentence(sentence_id: str) -> None:
    c = _conn()
    rows = c.execute(
        "SELECT event_type, decision, reason_code, surface, detail FROM extraction_trace_events "
        "WHERE sentence_id=%s ORDER BY created_at", (sentence_id,)).fetchall()
    print(f"SENTENCE {sentence_id} — {len(rows)} trace events")
    for r in rows:
        d = r[4] if isinstance(r[4], dict) else {}
        print(f"  [{r[0]:10}] {r[2]:34} {str(r[3])[:44]:44} {json.dumps(d)[:140]}")
    c.close()


def cmd_run(run_id: str) -> None:
    c = _conn()
    rows = c.execute(
        "SELECT payload FROM artifacts WHERE run_id=%s AND stage='extract' "
        "AND payload ? 'trace' ORDER BY artifact_id DESC LIMIT 1", (run_id,)).fetchall()
    if rows:
        funnel = rows[0][0]["trace"]
        print(json.dumps(funnel, indent=1, default=str)[:3000])
    else:
        n = c.execute("SELECT COUNT(*) FROM extraction_trace_events WHERE run_id=%s", (run_id,)).fetchone()[0]
        print(f"trace events: {n} (no funnel artifact — summary/full mode?)")
    c.close()


def cmd_waterfall(run_id: str) -> None:
    c = _conn()
    scope = _scope(c, run_id)
    _print_scope(c, run_id, scope)
    sql, sp = _scope_sql(scope)
    rows = c.execute(
        "SELECT reason_code, COUNT(*) FROM extraction_trace_events WHERE run_id=%s"
        + sql + " GROUP BY 1 ORDER BY 2 DESC", (run_id, *sp)).fetchall()
    total = sum(n for _, n in rows) or 1
    print("REJECTION/DECISION WATERFALL")
    for code, n in rows:
        print(f"  {100*n//total:3}% {code:36} {n}")
    c.close()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    global SHOW_ALL
    argv = [a for a in sys.argv if a != "--all"]
    SHOW_ALL = len(argv) != len(sys.argv)
    if len(argv) < 3:
        print(__doc__)
        return 1
    sys.argv = argv
    cmd, arg = argv[1], argv[2]
    if cmd == "surface":
        cmd_surface(arg, sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "sentence":
        cmd_sentence(arg)
    elif cmd == "run":
        cmd_run(arg)
    elif cmd == "waterfall":
        cmd_waterfall(arg)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
