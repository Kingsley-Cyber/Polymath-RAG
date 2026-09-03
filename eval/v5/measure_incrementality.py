#!/usr/bin/env python3
"""INCREMENTALITY evidence producer (release_gates.gate_incrementality).

Measures, against the LIVE pipeline, the two claims the gate reads:
  rows_projected <= max(3 * rows_changed, 50)   "a delta costs delta-sized work"
  resume_no_recompute                            "a restart resumes, never recomputes"

Method (one disposable probe corpus, three documents):
  A  upload prose P            -> wait query_ready; N_A children, R_A projection receipts
  A' re-upload identical bytes -> intake answers already_exists; 0 new runs, 0 new receipts
  B  upload P + one paragraph  -> new doc (chunk ids are doc-scoped: every row is a
                                  changed row) -> rows_changed = N_B, rows_projected = R_B
  C  upload P x REPEAT          -> when project_qdrant is LEASED and >= 1 batch receipt
                                  exists, SIGTERM the projection worker; the supervisor
                                  respawns it, the lease is released, the retry resumes.
                                  Evidence = the LAST attempt's projection_telemetry:
                                  representations_already_current >= receipts_at_kill and
                                  total embed_texts over all attempts <= N_C + one batch.
Writes eval/v5/release_evidence/incrementality.json with every measurement.

    .venv/bin/python eval/v5/measure_incrementality.py [--repeat 6] [--timeout-min 25]

Costs real extraction/enrichment calls on ~(2 + REPEAT) x |P| of text. The
probe corpus is left in place (CORPUS-DELETE cascade gap, work-log
2026-09-02-stall-tracer) and named so it is obvious.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

import psycopg

ROOT = pathlib.Path(__file__).resolve().parents[2]
DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200").rstrip("/")
OUT = pathlib.Path(__file__).resolve().parent / "release_evidence" / "incrementality.json"

PARAS = [
    "The lighthouse keeper at Pelican Point logged every vessel that passed between dusk and dawn, "
    "noting the flag, the heading and the weather in a ledger that his predecessors had kept since 1871.",
    "Salt corrodes brass hinges faster than iron ones, so the keeper replaced the lamp-room fittings "
    "every third spring, ordering them from a foundry in Bristol that still cast them by hand.",
    "During the storm of October 1904 the fog signal ran for forty-one hours without pause, consuming "
    "two tons of coal and forcing the assistant keeper to sleep beside the boiler in shifts.",
    "Migrating terns use the beam as a waypoint; ornithologists counted eleven thousand birds in one "
    "September night, which is why the station switched to a red filter during the autumn passage.",
    "The Fresnel lens, ground in Paris and shipped in fourteen crates, magnifies a single flame into a "
    "beam visible for nineteen nautical miles when the air is clear and the mercury bath is level.",
    "A supply tender called once a month with flour, lamp oil, newspapers and letters; in winter the "
    "landing was often impossible and the keepers relied on the smokehouse and the root cellar.",
    "Automation arrived in 1962: a photocell switch, a bank of batteries and a telephone line to the "
    "harbour master replaced three families, and the cottages were let to a marine research unit.",
    "Researchers now measure water temperature, salinity and plankton density from the old boathouse, "
    "publishing a quarterly bulletin that fishermen read for the position of the warm current.",
]


def prose(seed: int, copies: int) -> str:
    out = []
    for c in range(copies):
        for i, p in enumerate(PARAS):
            out.append(f"Section {c + 1}.{i + 1} (probe {seed}). {p}")
    return "\n\n".join(out) + "\n"


def http(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(ORCH + path, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "measure-incrementality/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def upload(corpus: str, name: str, text: str) -> dict:
    code, out = http("POST", "/intake", {
        "corpus_id": corpus, "source_name": name, "media_type": "text/markdown",
        "content_b64": base64.b64encode(text.encode()).decode(), "config": {}})
    if code != 200:
        raise SystemExit(f"intake {name}: HTTP {code} {out}")
    return out


def status(corpus: str, run_id: str) -> dict:
    code, out = http("GET", f"/status?corpus_id={corpus}&run_id={run_id}")
    return out if code == 200 else {"status": f"http_{code}", "tickets": []}


def wait_ready(corpus: str, run_id: str, timeout_s: float, on_poll=None, poll_s: float = 8.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = status(corpus, run_id)
        if on_poll:
            on_poll(st)
        if st.get("status") in ("query_ready", "failed", "degraded"):
            return st
        time.sleep(poll_s)
    return {"status": "timeout", "tickets": []}


def projection_leased(conn, run_id: str) -> bool:
    row = conn.execute("SELECT status FROM stage_tickets WHERE run_id=%s AND stage='project_qdrant'",
                       (run_id,)).fetchone()
    return bool(row) and row[0] == "leased"


def doc_rows(conn, corpus: str, name: str) -> tuple[str | None, list[str], int]:
    row = conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s AND source_name=%s "
                       "ORDER BY created_at DESC LIMIT 1", (corpus, name)).fetchone()
    if not row:
        return None, [], 0
    ids = [r[0] for r in conn.execute("SELECT chunk_id FROM chunks WHERE doc_id=%s", (row[0],)).fetchall()]
    children = conn.execute("SELECT count(*) FROM chunks WHERE doc_id=%s AND tier='child'", (row[0],)).fetchone()[0]
    return row[0], ids, children


def receipts_for(conn, ids: list[str]) -> int:
    if not ids:
        return 0
    return conn.execute("SELECT count(*) FROM projection_receipts WHERE entity_id = ANY(%s)", (ids,)).fetchone()[0]


def telemetry(conn, run_id: str) -> list[dict]:
    rows = conn.execute("""SELECT payload FROM artifacts WHERE run_id=%s AND stage='project_qdrant'
                            ORDER BY created_at""", (run_id,)).fetchall()
    out = []
    for (payload,) in rows:
        p = payload if isinstance(payload, dict) else json.loads(payload)
        t = p.get("projection_telemetry") if isinstance(p, dict) else None
        if isinstance(t, dict):
            out.append(t)
    return out


def projection_pids(conn) -> list[int]:
    """The live projection worker(s) by the fleet's own registry, each
    verified against its command line (macOS reuses low pids — the first
    run's worker was pid 193 — so a bare pattern match is not proof)."""
    rows = conn.execute("""SELECT pid FROM worker_registrations
                            WHERE worker_type ILIKE '%%qdrant%%'
                              AND heartbeat_at > now() - interval '120 s'""").fetchall()
    out = []
    for (pid,) in rows:
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
        if "project_qdrant_worker" in cmd:
            out.append(int(pid))
    return out


def rejudge(baseline: int | None) -> int:
    """Re-apply the resume judgement to recorded step-C numbers. The first
    judgement compared the resumed run's embed_texts with the CHILD count;
    the routing lane is corpus-wide, so the right yardstick is an
    uninterrupted run of the same document (run 1 of 2026-09-03: 1,067
    embed texts for 480 children = 480 chunk + 587 routing)."""
    ev = json.loads(OUT.read_text())
    c = ev["steps"]["C"]
    kill = c.get("kill") or {}
    last = c.get("last_attempt") or {}
    embed_total = int(c.get("embed_texts_total") or 0)
    budget = (baseline - int(kill.get("receipts_at_kill") or 0) + 32) if baseline else (int(c["children"]) + 32)
    resumed = bool(kill.get("done") and c.get("status") == "query_ready"
                   and int(last.get("representations_already_current") or 0) >= int(kill.get("receipts_at_kill") or 0)
                   and embed_total <= budget)
    c["resume_budget"] = {"baseline_embed_texts": baseline, "embed_budget": budget, "embed_texts_total": embed_total,
                          "rejudged_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    ev["resume_no_recompute"] = resumed
    ev["recorded_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(ev, indent=1, default=str))
    print(f"rejudged: embed_texts_total={embed_total} budget={budget} already_current={last.get('representations_already_current')} "
          f"receipts_at_kill={kill.get('receipts_at_kill')} -> resume_no_recompute={resumed}")
    return 0 if resumed else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-copies", type=int, default=5, help="copies of the prose in documents A and B")
    ap.add_argument("--repeat", type=int, default=60,
                    help="copies of the prose in document C (>= ~6 embed batches so a mid-projection kill has work left)")
    ap.add_argument("--timeout-min", type=float, default=25.0)
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--baseline-embed-texts", type=int, default=None,
                    help="embed_texts of an UNINTERRUPTED projection of the same document size "
                         "(the routing lane is corpus-wide, so the resumed total is judged against a full run, "
                         "not against the child count)")
    ap.add_argument("--rejudge", action="store_true",
                    help="no ingest: re-evaluate the existing evidence file's step C against --baseline-embed-texts")
    ap.add_argument("--only-resume", action="store_true",
                    help="skip A/A'/B (reuse their numbers from the existing evidence file); run the kill/resume probe only")
    a = ap.parse_args()
    if a.rejudge:
        return rejudge(a.baseline_embed_texts)
    seed = int(time.time())
    corpus = a.corpus or f"probe-incr-{dt.date.today().isoformat()}-{seed % 10000}"
    timeout = a.timeout_min * 60
    ev: dict = {"corpus": corpus, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "producer": "eval/v5/measure_incrementality.py", "steps": {}}
    conn = psycopg.connect(DSN, autocommit=True)
    if not conn.execute("SELECT 1 FROM corpora WHERE corpus_id=%s", (corpus,)).fetchone():
        conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose) VALUES (%s,%s,'probe','probe')",
                     (corpus, corpus))
    print(f"probe corpus {corpus}")
    if a.only_resume:
        prev = json.loads(OUT.read_text()) if OUT.exists() else {}
        ev["steps"] = {k: v for k, v in prev.get("steps", {}).items() if k in ("A", "A_identical", "B")}
        ev["reused_from"] = prev.get("recorded_at")
        pa = prose(seed, a.base_copies)   # only used to size C below
        if not ev["steps"].get("B"):
            raise SystemExit("--only-resume needs a prior evidence file with steps A/A_identical/B")
    else:
        pa = None

    # ---- A
    if pa is None:
        pa = prose(seed, a.base_copies)
    if a.only_resume:
        ra = None
    else:
      ra = upload(corpus, "probe_A.md", pa)
      t0 = time.time()
      st = wait_ready(corpus, ra["run_id"], timeout)
      _, ids_a, n_a = doc_rows(conn, corpus, "probe_A.md")
      r_a = receipts_for(conn, ids_a)
      ev["steps"]["A"] = {"run_id": ra["run_id"], "status": st.get("status"), "wall_s": round(time.time() - t0),
                          "children": n_a, "chunks": len(ids_a), "projection_receipts": r_a}
      print("A:", ev["steps"]["A"])
      if st.get("status") != "query_ready":
          ev["error"] = "A did not reach query_ready"; OUT.write_text(json.dumps(ev, indent=1)); return 2

      # ---- A' identical bytes
      runs_before = conn.execute("SELECT count(*) FROM runs WHERE corpus_id=%s", (corpus,)).fetchone()[0]
      rec_before = receipts_for(conn, ids_a)
      ra2 = upload(corpus, "probe_A.md", pa)
      time.sleep(20)
      runs_after = conn.execute("SELECT count(*) FROM runs WHERE corpus_id=%s", (corpus,)).fetchone()[0]
      ev["steps"]["A_identical"] = {"already_exists": bool(ra2.get("already_exists")), "same_run": ra2["run_id"] == ra["run_id"],
                                    "new_runs": runs_after - runs_before, "new_receipts": receipts_for(conn, ids_a) - rec_before}
      print("A':", ev["steps"]["A_identical"])

      # ---- B one paragraph added
      pb = pa + "\n\nSection 9.1 (probe %d). In 2019 the trust reopened the tower to visitors on summer weekends, " \
                "and the ledger, now digitised, can be searched by ship name.\n" % seed
      rb = upload(corpus, "probe_B.md", pb)
      t0 = time.time()
      st = wait_ready(corpus, rb["run_id"], timeout)
      _, ids_b, n_b = doc_rows(conn, corpus, "probe_B.md")
      r_b = receipts_for(conn, ids_b)
      ev["steps"]["B"] = {"run_id": rb["run_id"], "status": st.get("status"), "wall_s": round(time.time() - t0),
                          "children": n_b, "chunks": len(ids_b), "projection_receipts": r_b,
                          "rows_changed": len(ids_b), "rows_projected": r_b}
      print("B:", ev["steps"]["B"])

    # ---- C resume under a mid-projection kill
    pc = prose(seed + 1, a.repeat)
    c_name = f"probe_C_{seed % 100000}.md"
    rc = upload(corpus, c_name, pc)
    killed = {"done": False, "pids": [], "receipts_at_kill": 0, "at_s": None}
    t0 = time.time()

    def on_poll(stx: dict) -> None:
        if killed["done"]:
            return
        if not projection_leased(conn, rc["run_id"]):      # ticket state from the DB, not the HTTP shape
            return
        _, ids_c, _ = doc_rows(conn, corpus, c_name)
        n = receipts_for(conn, ids_c)
        if n >= 1:
            pids = projection_pids(conn)
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            killed.update(done=True, pids=pids, receipts_at_kill=n, at_s=round(time.time() - t0))
            print(f"C: SIGTERM projection worker(s) {pids} with {n} receipts written at +{killed['at_s']}s")

    st = wait_ready(corpus, rc["run_id"], timeout, on_poll=on_poll, poll_s=2.0)
    _, ids_c, n_c = doc_rows(conn, corpus, c_name)
    tel = telemetry(conn, rc["run_id"])
    attempts = conn.execute("SELECT attempt FROM stage_tickets WHERE run_id=%s AND stage='project_qdrant'",
                            (rc["run_id"],)).fetchone()
    embed_total = sum(int(t.get("embed_texts", 0) or 0) for t in tel)
    last = tel[-1] if tel else {}
    ev["steps"]["C"] = {"run_id": rc["run_id"], "source_name": c_name, "status": st.get("status"), "wall_s": round(time.time() - t0),
                        "children": n_c, "chunks": len(ids_c), "projection_receipts": receipts_for(conn, ids_c),
                        "kill": killed, "project_qdrant_attempt": attempts[0] if attempts else None,
                        "telemetry_attempts": len(tel), "embed_texts_total": embed_total,
                        "last_attempt": {k: last.get(k) for k in ("embed_texts", "representations_total",
                                                                  "representations_already_current", "qdrant_batches")}}
    print("C:", json.dumps(ev["steps"]["C"], default=str))
    # resume_no_recompute: the resumed run skipped at least the work that was
    # receipted before the kill. Judged against an uninterrupted run of the
    # same document (baseline), with one embed batch (32) of slack; without a
    # baseline the child count + one batch is the (routing-blind) fallback.
    baseline = a.baseline_embed_texts
    if baseline is None and not a.only_resume:
        baseline = None
    budget = (baseline - killed["receipts_at_kill"] + 32) if baseline else (n_c + 32)
    resumed = bool(killed["done"] and st.get("status") == "query_ready"
                   and int(last.get("representations_already_current", 0) or 0) >= killed["receipts_at_kill"]
                   and embed_total <= budget)
    ev["steps"]["C"]["resume_budget"] = {"baseline_embed_texts": baseline, "embed_budget": budget,
                                         "embed_texts_total": embed_total}
    ev["rows_changed"] = ev["steps"]["B"]["rows_changed"]
    ev["rows_projected"] = ev["steps"]["B"]["rows_projected"]
    ev["zero_delta_new_receipts"] = ev["steps"]["A_identical"]["new_receipts"]
    ev["resume_no_recompute"] = resumed
    ev["recorded_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ev, indent=1, default=str))
    print(f"evidence written: {OUT}\nrows_changed={ev['rows_changed']} rows_projected={ev['rows_projected']} "
          f"zero_delta_new_receipts={ev['zero_delta_new_receipts']} resume_no_recompute={resumed}")
    return 0 if resumed else 1


if __name__ == "__main__":
    raise SystemExit(main())
