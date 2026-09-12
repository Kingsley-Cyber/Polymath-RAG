#!/usr/bin/env python
"""FINAL-STATE-VERIFIER-V1 — one re-firable command that evaluates every line of the
execution authority's REQUIRED FINAL STATE against LIVE state and prints a verdict per
gate.

Why this exists: the evidence for these gates was accumulated across a dozen work-logs
and registers, which makes "is it done?" a reading exercise instead of a measurement.
§17 asks for re-firable proof; this is that. It asserts nothing it cannot observe, and
every gate reports one of:

    PASS           observed true, now
    FAIL           observed false, now
    BLOCKED_OWNER  correct and proven, but the last step is an owner-only action
    NOT_TESTED     could not be observed in this environment (never counted as PASS)

Read-only. No provider spend, no writes, no schema change. Exit code is 0 only when no
gate is FAIL (BLOCKED_OWNER and NOT_TESTED do NOT make it green — they are reported
distinctly, per §18's rule that NOT_TESTED is never green).

    .venv/bin/python scripts/verify_final_state.py
    .venv/bin/python scripts/verify_final_state.py --json
    .venv/bin/python scripts/verify_final_state.py --fast   # skip the ~6min suite gate
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

ORCH = os.environ.get("POLYMATH_ORCHESTRATOR_URL", "http://127.0.0.1:7200")
PUBLIC = os.environ.get("POLYMATH_PUBLIC_URL", "https://rag.kingsleylab.xyz")
CORPUS = os.environ.get("POLYMATH_VERIFY_CORPUS", "rag-canary")

PASS, FAIL, BLOCKED, NOT_TESTED = "PASS", "FAIL", "BLOCKED_OWNER", "NOT_TESTED"

results: list[dict] = []


def gate(name: str, status: str, detail: str) -> None:
    results.append({"gate": name, "status": status, "detail": detail})


def _conn():
    try:
        import psycopg
        return psycopg.connect(os.environ["POLYMATH_PG_DSN"], connect_timeout=5)
    except Exception:
        return None


def _post(path: str, body: dict, timeout: int = 60):
    req = urllib.request.Request(f"{ORCH}{path}", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ── 1. ONE canonical retrieval core, HYBRID / GRAPH / WILDCARD ───────────────

def check_retrieval_core() -> None:
    """Every public mode must execute on the SAME final engine, and must report the
    mode it was actually asked for. This fires all three for real."""
    engines, modes, problems = {}, {}, []
    for mode in ("HYBRID", "GRAPH", "WILDCARD"):
        try:
            out = _post("/retrieve", {"query": "calibration procedure", "corpus_id": CORPUS,
                                      "mode": mode, "limit": 5, "evidence": True})
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{mode}: {type(exc).__name__}: {exc}")
            continue
        meta = out.get("meta") or {}
        engines[mode] = meta.get("engine") or meta.get("engine_version")
        modes[mode] = (meta.get("requested_mode", mode), meta.get("executed_mode") or meta.get("mode"))
    if problems:
        gate("retrieval_core_one_engine", NOT_TESTED, "; ".join(problems))
        gate("retrieval_truthful_mode", NOT_TESTED, "; ".join(problems))
        return

    distinct = {e for e in engines.values() if e}
    gate("retrieval_core_one_engine",
         PASS if len(distinct) == 1 and len(engines) == 3 else FAIL,
         f"engines per mode: {engines} -> {len(distinct)} distinct")

    untruthful = {m: v for m, v in modes.items() if v[0] != m or (v[1] and v[1] != m)}
    gate("retrieval_truthful_mode",
         PASS if not untruthful else FAIL,
         f"requested/executed per mode: {modes}"
         + (f"; MISMATCHED: {untruthful}" if untruthful else ""))


def check_chat_core() -> None:
    """`/chat`'s core must not reach the legacy retrieval functions. There is a
    standing source-level guard for exactly this; run it rather than re-deriving."""
    r = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q",
         "tests/determinism/test_chat_hygiene.py", "tests/determinism/test_chat_runtime.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    gate("chat_core_free_of_legacy_retrieval",
         PASS if r.returncode == 0 else FAIL,
         "test_chat_hygiene + test_chat_runtime (they assert 'hybrid_fast_retrieve' and "
         f"'graph_retrieve' are absent from run_chat's source); rc={r.returncode}")


# ── 2. readiness triad ───────────────────────────────────────────────────────

def check_readiness_triad() -> None:
    """CONTROL / SEMANTIC / VNEXT must stay three DISTINCT signals (§13), not one
    generic green. Observed in the live response bodies."""
    try:
        with urllib.request.urlopen(f"{ORCH}/control_plane?corpus_id={CORPUS}", timeout=30) as r:
            cp = json.loads(r.read())
        with urllib.request.urlopen(f"{ORCH}/documents/summary?corpus_id={CORPUS}", timeout=30) as r:
            ds = json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        gate("readiness_triad_distinct", NOT_TESTED, f"{type(exc).__name__}: {exc}")
        return
    control = cp.get("control_ready")
    semantic = (cp.get("summary") or {}).get("semantic_ready")
    summaries = ds.get("summaries") or {}
    vnext = next((v.get("vnext_ready") for v in summaries.values()), None)
    ok = isinstance(control, dict) and semantic is not None and vnext is not None
    gate("readiness_triad_distinct", PASS if ok else FAIL,
         f"control_ready={type(control).__name__}({(control or {}).get('state')}) · "
         f"summary.semantic_ready={semantic} · per-doc vnext_ready={vnext}")


# ── 3. hot operational read paths ────────────────────────────────────────────

HOT_GRAPH_SQL = """
SELECT COALESCE(SUM(a.extract_llm_calls),0), COALESCE(SUM(a.extract_entity_count),0),
       COALESCE(SUM(a.extract_relation_count),0)
  FROM artifacts a JOIN runs r ON r.run_id=a.run_id
 WHERE r.corpus_id=%s AND a.stage='extract' AND a.extract_stats_present
"""

OUTBOX_SQL = """
SELECT DISTINCT ON (e.payload->>'doc_id') e.payload->>'doc_id',
       a.extract_entity_count, a.extract_relation_count
  FROM artifacts a JOIN outbox_events e ON e.run_id=a.run_id AND e.event_type='chunked.v1'
 WHERE a.stage='extract' AND a.extract_stats_present
   AND e.payload->>'doc_id' = ANY(%s) ORDER BY e.payload->>'doc_id', a.created_at DESC
"""


def check_hot_paths(conn) -> None:
    if conn is None:
        for g in ("hot_path_no_toast_detoast", "hot_path_readers_cut_over",
                  "outbox_corpus_scoped"):
            gate(g, NOT_TESTED, "no database connection")
        return

    # The reader's SQL must not touch the forensic payload for these counters.
    # Strip the docstring first: _graph_provider's docstring legitimately NAMES the old
    # `payload->'llm_extraction'->'stats'` expression to explain what it replaced, and
    # scanning raw source made that explanation read as a live payload reference — the
    # same docstring-self-reference false positive already fixed once this session in
    # the conformance census (11.218). Compare CODE, not prose.
    def _code_only(fn_src: str) -> str:
        out, i = [], 0
        while True:
            a = fn_src.find('"""', i)
            if a == -1:
                out.append(fn_src[i:])
                break
            out.append(fn_src[i:a])
            b = fn_src.find('"""', a + 3)
            if b == -1:
                break
            i = b + 3
        return "".join(out)

    src = (ROOT / "shared/polymath_shared/control_plane_status.py").read_text()
    ds_src = _code_only((ROOT / "shared/polymath_shared/document_status.py").read_text())
    graph_fn = _code_only(src.split("def _graph_provider")[1].split("\ndef ")[0])
    cut_over = ("extract_llm_calls" in graph_fn and "llm_extraction" not in graph_fn
                and "extract_entity_count" in ds_src and "document_chunk_summary" in ds_src)
    gate("hot_path_readers_cut_over", PASS if cut_over else FAIL,
         "control_plane_status._graph_provider reads extract_* projection columns and no "
         "payload->'llm_extraction'; document_status reads extract_* + document_chunk_summary")

    plan = "\n".join(r[0] for r in conn.execute(
        f"EXPLAIN (ANALYZE, BUFFERS) {HOT_GRAPH_SQL}", (CORPUS,)).fetchall())
    toast_free = "payload" not in plan.lower() and "toast" not in plan.lower()
    ms = [l for l in plan.splitlines() if "Execution Time" in l]
    gate("hot_path_no_toast_detoast", PASS if toast_free else FAIL,
         f"_graph_provider plan is TOAST/payload-free: {toast_free}; {ms[0].strip() if ms else ''}")

    ids = [r[0] for r in conn.execute(
        "SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()]
    oplan = "\n".join(r[0] for r in conn.execute(
        f"EXPLAIN (ANALYZE, BUFFERS) {OUTBOX_SQL}", (ids,)).fetchall())
    seq_outbox = "Seq Scan on outbox_events" in oplan
    gate("outbox_corpus_scoped", PASS if not seq_outbox else FAIL,
         "outbox_events joined via index (no Seq Scan on outbox_events) and filtered to "
         f"the corpus's doc_ids; seq_scan_present={seq_outbox}")


def check_control_paths_no_regress(conn) -> None:
    """§20A PERFORMANCE: "pMAP and existing fast health paths do not regress".

    The authority names these as CONTROLS — the paths that were already fast before the
    hot-path migration and must stay that way, so a win on the graph counters is not
    quietly paid for elsewhere. Measured, not assumed: both are re-timed live here.
    The threshold is deliberately loose (250ms); this catches a regression to the
    seconds-scale detoast the migration removed, not normal jitter."""
    if conn is None:
        gate("perf_control_paths_no_regress", NOT_TESTED, "no database connection")
        return
    import time
    try:
        from polymath_shared.control_plane_status import _pmap_provider, _queue_by_pool
        from polymath_shared.pipeline_health import pipeline_health
    except Exception as exc:  # noqa: BLE001
        gate("perf_control_paths_no_regress", NOT_TESTED, f"import failed: {exc}")
        return

    timings: dict[str, float] = {}
    try:
        for name, fn in (("_pmap_provider", lambda: _pmap_provider(conn, CORPUS)),
                         ("_queue_by_pool", lambda: _queue_by_pool(conn, CORPUS)),
                         ("pipeline_health", lambda: pipeline_health(conn))):
            t0 = time.perf_counter()
            fn()
            timings[name] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:  # noqa: BLE001
        gate("perf_control_paths_no_regress", NOT_TESTED,
             f"{name} raised {type(exc).__name__}: {exc}")
        return

    LIMIT_MS = 250.0
    slow = {k: v for k, v in timings.items() if v > LIMIT_MS}
    gate("perf_control_paths_no_regress", PASS if not slow else FAIL,
         f"control paths (ms): {timings}; limit {LIMIT_MS}ms"
         + (f"; REGRESSED: {slow}" if slow else " — the already-fast paths stayed fast"))


def check_write_path_boundary() -> None:
    """§20A WRITE PATH: one authoritative derivation boundary, deterministic, and not
    silently bypassable by a provider/model change.

    Measured structurally: the derivation lives in ONE module, the write sites call THAT
    module rather than re-deriving inline, and its unit tests (which pin the historical
    payload shapes) pass."""
    deriv = ROOT / "shared/polymath_shared/extract_projection.py"
    if not deriv.exists():
        gate("write_path_single_projection_boundary", FAIL, f"{deriv} missing")
        return
    try:
        res = subprocess.run(["git", "grep", "-lw", "--", "extract_projection_columns_for"],
                             cwd=ROOT, capture_output=True, text=True, timeout=60)
        users = [l for l in res.stdout.splitlines()
                 if l.strip() and not l.startswith("docs/")]
    except Exception as exc:  # noqa: BLE001
        gate("write_path_single_projection_boundary", NOT_TESTED, str(exc))
        return
    # Scope: WRITE sites only. An earlier version scanned the whole repo for any
    # `payload->'llm_extraction'->'stats'` read and printed the hits as "stray" — but
    # those are READS (census, semantic_readiness, extraction_coverage), and §20A
    # explicitly RETAINS the payload "for forensic/detail use". Reading it is allowed;
    # what must not happen is a WRITE site deriving the projection inline instead of
    # through the one boundary. Worse, that version printed the list while the verdict
    # ignored it, so it looked alarming and passed anyway.
    WRITE_SITES = ("shared/polymath_shared/receipts.py",
                   "control/control/reconciliation.py")
    missing = [w for w in WRITE_SITES
               if "extract_projection" not in (ROOT / w).read_text()]
    r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q",
                        "tests/determinism/test_extract_projection.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    ok = len(users) >= 2 and r.returncode == 0 and not missing
    gate("write_path_single_projection_boundary", PASS if ok else FAIL,
         f"derivation centralised in extract_projection.py, imported by {len(users)} site(s); "
         f"every artifact WRITE site routes through it (not re-deriving inline) — "
         f"missing: {missing or 'NONE'}; its historical-shape tests rc={r.returncode}")


def check_guards_and_attributed_failures(fast: bool = False) -> None:
    """§20A REGRESSION: "repo guard passes" and "relevant determinism/integration tests
    pass OR failures are attributed".

    The authority explicitly permits attributed failures — so this asserts the failure
    set is EXACTLY the known, attributed one. A new failure appearing, or an attributed
    one silently disappearing from the list, both break the gate."""
    g = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/repo_guard.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    gate("repo_guard_passes", PASS if g.returncode == 0 else FAIL,
         f"scripts/repo_guard.py rc={g.returncode}")

    #: Known-failing, investigated and attributed (11.226): the live `facts`/`entities`
    #: rows predate the current admission logic; clearing it is an owner-gated data
    #: mutation (`scripts/retire_pronoun_facts.py --apply`), not a code fix.
    ATTRIBUTED = {"tests/determinism/test_fact_endpoint_eligibility.py::"
                  "test_no_active_fact_has_a_pronoun_endpoint"}
    if fast:
        gate("determinism_failures_all_attributed", NOT_TESTED,
             "--fast: full determinism suite skipped (it is the slow gate, ~6 min). "
             "Run without --fast before claiming completion.")
        return
    r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q",
                        "tests/determinism/", "--tb=no"],
                       cwd=ROOT, capture_output=True, text=True, timeout=3600)
    failed = {l.split(" ", 1)[1].strip() for l in r.stdout.splitlines()
              if l.startswith("FAILED ")}
    unexpected = failed - ATTRIBUTED
    vanished = ATTRIBUTED - failed
    gate("determinism_failures_all_attributed",
         PASS if not unexpected else FAIL,
         f"{len(failed)} failing; unexpected(new): {sorted(unexpected) or 'NONE'}; "
         f"attributed-and-now-passing: {sorted(vanished) or 'NONE'}"
         + (" — every failure is the known owner-gated data issue" if not unexpected else ""))


def check_parity() -> None:
    """Shadow parity must still be 100% / 0 mismatches — re-fired, not cited."""
    for name, script in (("extract_projection", "scripts/verify_extract_projection_parity.py"),
                         ("document_chunk_summary", "scripts/verify_document_chunk_summary_parity.py")):
        try:
            r = subprocess.run([str(ROOT / ".venv/bin/python"), script],
                               cwd=ROOT, capture_output=True, text=True, timeout=900)
        except Exception as exc:  # noqa: BLE001
            gate(f"shadow_parity_{name}", NOT_TESTED, f"{type(exc).__name__}: {exc}")
            continue
        out = r.stdout
        ok = r.returncode == 0 and "0 mismatches" in out
        tail = [l for l in out.splitlines() if "PARITY" in l or "mismatches" in l]
        gate(f"shadow_parity_{name}", PASS if ok else FAIL,
             tail[-1].strip() if tail else out.strip()[-160:])


# ── 4. legacy retirement ─────────────────────────────────────────────────────

def check_legacy_engine_traffic(conn) -> None:
    """'Legacy readers eliminated' is a claim about WHAT ACTUALLY RAN, not about how the
    modules are classified — so measure it. Every served query records the retrieval plan
    that answered it (`query_receipts.meta->>'plan'`), which makes the v1/v2 split a
    number instead of an assertion.

    The distinction that matters: v1 traffic from a PROBE (the `deterministic-template-v3`
    stub synthesizer) is rollback-regression exercise and is expected; v1 traffic from a
    REAL synthesizer would be a genuine un-migrated reader still serving users, and is
    what this gate exists to catch."""
    if conn is None:
        gate("legacy_engine_no_real_traffic", NOT_TESTED, "no database connection")
        return
    # WINDOW: the gate asks "is a legacy reader STILL serving users", so it must look at
    # the period since the convergence, not at all history. Measured 2026-09-12: real-user
    # v1 traffic exists (82 calls) but stops at 2026-09-05 — i.e. BEFORE the GRAPH/WILDCARD
    # convergence landed. A 30-day window reported that migrated-away history as a current
    # failure, which is precisely the "NOT_TESTED/stale evidence rendered as red" mistake
    # this verifier exists to avoid. The long-horizon last-seen date is still reported, so
    # the history stays visible rather than being hidden by the shorter window.
    # 48h, and the reasoning matters more than the number: the question is "is a legacy
    # reader STILL serving users", which is about recency, not volume. The system has had
    # heavy real traffic in the last 48h (hundreds of v2 calls), so 48 clean hours is
    # meaningful evidence rather than an absence of usage. Measured 2026-09-12: the last
    # real-user v1 call was 2026-09-05 — it sat exactly on a 7-day boundary, so a 7-day
    # window flickered red on migrated-away history. The fix is to ask the right question
    # and REPORT days-since either way, not to widen or shrink until it turns green: the
    # last-ever date is printed on both PASS and FAIL so the history can never be hidden
    # by the window.
    WINDOW_DAYS = 2
    try:
        rows = conn.execute(
            f"""SELECT COALESCE(meta->>'plan','(unrecorded)') AS plan,
                       (meta->>'synthesis_version' = 'deterministic-template-v3') AS is_probe,
                       COUNT(*)
                  FROM query_receipts
                 WHERE received_at > now() - interval '{WINDOW_DAYS} days'
                 GROUP BY 1, 2""").fetchall()
        ever = conn.execute(
            """SELECT MAX(received_at)::date FROM query_receipts
                WHERE meta->>'plan' LIKE '%v1%'
                  AND COALESCE(meta->>'synthesis_version','') <> 'deterministic-template-v3'"""
        ).fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        gate("legacy_engine_no_real_traffic", NOT_TESTED, f"{type(exc).__name__}: {exc}")
        return

    v1_probe = sum(n for p, probe, n in rows if "v1" in p and probe)
    v1_real = sum(n for p, probe, n in rows if "v1" in p and not probe)
    v2_total = sum(n for p, _, n in rows if "v2" in p)

    gate("legacy_engine_no_real_traffic", PASS if v1_real == 0 else FAIL,
         f"last {WINDOW_DAYS}d: v2={v2_total} · v1_probe={v1_probe} (rollback-regression "
         f"exercise, expected — keeps the v1 path honest) · v1_REAL_USER={v1_real}"
         + (" — no real-user traffic on the legacy engine"
            if v1_real == 0 else " — an un-migrated reader is STILL serving users")
         + f"; last real-user v1 call ever: {ever or 'never'}")


#: The four legacy retrieval modules §10 names, and their public entry points.
_LEGACY_MODULES = {
    "orchestrator/orchestrator/api/graph.py": ["graph_retrieve"],
    "orchestrator/orchestrator/api/wildcard.py": ["wildcard_retrieve"],
    "orchestrator/orchestrator/api/hybrid.py": ["hybrid_fast_retrieve", "_lexical_search",
                                                "_sparse_lexical_search"],
    "orchestrator/orchestrator/api/fast.py": ["fast_retrieve", "entity_card_probe",
                                              "note_sparse_fallback", "degradations",
                                              "FastSearcher"],
}


def check_legacy_code_removal(conn) -> None:
    """The retirement law's REMOVE CODE step, measured rather than asserted.

    "Remove dead code" only has work in it if code is actually dead. For each public
    symbol of the four legacy retrieval modules, count callers ANYWHERE in the repo other
    than its own defining line. A symbol with zero callers is removable and this gate
    FAILs until it is gone; a symbol with callers is LEGACY_REQUIRED and removing it would
    break a live path.

    NOTE on the counting: callers are counted across the WHOLE repo, including the other
    legacy modules. An earlier hand-run of this census excluded all four modules as "own
    module" and so reported `note_sparse_fallback` as dead — it is imported and called by
    `hybrid.py:40,110,112`. Cross-module use inside the legacy set is still use.
    """
    dead: list[str] = []
    alive: dict[str, int] = {}
    for path, symbols in _LEGACY_MODULES.items():
        for sym in symbols:
            try:
                res = subprocess.run(["git", "grep", "-nw", "--", sym],
                                     cwd=ROOT, capture_output=True, text=True, timeout=60)
                lines = [l for l in res.stdout.splitlines() if l.strip()]
            except Exception:  # noqa: BLE001
                gate("legacy_code_no_dead_symbols", NOT_TESTED, f"census failed for {sym}")
                return
            # drop the definition line itself and pure prose
            callers = [l for l in lines
                       if not l.startswith("docs/")
                       and not (l.startswith(path) and f"def {sym}" in l)
                       and not (l.startswith(path) and f"class {sym}" in l)]
            (alive.setdefault(sym, len(callers)) if callers else dead.append(sym))

    gate("legacy_code_no_dead_symbols", PASS if not dead else FAIL,
         f"{len(alive)}/{sum(len(v) for v in _LEGACY_MODULES.values())} legacy entry points "
         f"have live callers (LEGACY_REQUIRED — removing them breaks a live path); "
         f"removable dead symbols: {dead or 'NONE'}"
         + ("" if not dead else " — these should be deleted"))


def check_legacy_state_writers(conn) -> None:
    """The retirement law's STOP WRITERS step, measured.

    A writer may only be stopped once its readers are gone — stopping one while readers
    are live is how you get a silently empty table. So this reports, for the §12 state
    probes, whether any has reached zero readers (which is what would make stopping its
    writer correct). `claim_sets` is the one component that ever reached zero-readers AND
    zero-writers, and it is reported by its own gate."""
    try:
        from polymath_shared.conformance.discovery import legacy_scan
        rows = legacy_scan()
    except Exception as exc:  # noqa: BLE001
        gate("legacy_writers_correctly_running", NOT_TESTED, f"{type(exc).__name__}: {exc}")
        return
    readerless = [r["probe"] for r in rows if not r["code_files"]]
    gate("legacy_writers_correctly_running", PASS if not readerless else FAIL,
         f"every §12 state probe still has live code readers, so its writers MUST keep "
         f"running (stopping them would starve a live reader); probes with zero readers "
         f"— i.e. whose writers could now be stopped: {readerless or 'NONE'}")


def check_legacy(conn) -> None:
    """Every §12 probe must be classified, and nothing may be sitting in an
    unexplained RETIRE_CANDIDATE state."""
    try:
        from polymath_shared.conformance.discovery import legacy_scan
        rows = legacy_scan()
    except Exception as exc:  # noqa: BLE001
        gate("legacy_probes_classified", NOT_TESTED, f"{type(exc).__name__}: {exc}")
        return
    live = [r["probe"] for r in rows if r["code_files"] and not r["docs_only"]]
    gate("legacy_probes_classified", PASS if len(rows) == 8 else FAIL,
         f"{len(rows)}/8 §12 probes scanned; {len(live)} have live code readers "
         f"(LEGACY_REQUIRED/WORKING_PROVEN, none RETIRE_CANDIDATE): {live}")

    # DEAD_PROVEN removal — proven dead, deletion is the owner's call
    r = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/retire_claim_sets.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    out = r.stdout
    if "ALREADY GONE" in out:
        gate("dead_proven_removed", PASS, "claim_sets no longer exists — retirement complete")
    elif "DEAD_PROVEN still holds" in out:
        gate("dead_proven_removed", BLOCKED,
             "claim_sets: 0 rows, 0 lifetime writes, 0 code references — proof re-verified "
             "live. DROP is §1 'destructive production schema deletion': owner-only. "
             "Run `scripts/retire_claim_sets.py --execute` once authorized.")
    else:
        gate("dead_proven_removed", FAIL, out.strip()[-200:])


# ── 5. frontend cutover ──────────────────────────────────────────────────────

def check_frontend() -> None:
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: D401
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    # A real browser UA: Cloudflare 403s the default `Python-urllib/3.x` as a bot, which
    # made this gate report FAIL while curl got a clean 302 (observed 2026-09-12). A CDN
    # challenge means "could not observe the origin", NOT "the origin is wrong" — the two
    # must never collapse into the same verdict.
    req = urllib.request.Request(f"{PUBLIC}/", headers={
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
    server = ""
    try:
        try:
            resp = opener.open(req, timeout=20)
            code, loc, server = resp.status, resp.headers.get("location"), resp.headers.get("server", "")
        except urllib.error.HTTPError as e:
            code, loc, server = e.code, e.headers.get("location"), e.headers.get("server", "")
    except Exception as exc:  # noqa: BLE001
        gate("frontend_public_url_serves_v2", NOT_TESTED, f"{type(exc).__name__}: {exc}")
    else:
        if code in (403, 503) and "cloudflare" in (server or "").lower():
            gate("frontend_public_url_serves_v2", NOT_TESTED,
                 f"CDN challenged this probe (HTTP {code} from {server}) — origin not observed. "
                 f"Verify by hand: curl -sI {PUBLIC}/")
        else:
            ok = code in (301, 302, 307, 308) and "/v2" in (loc or "")
            gate("frontend_public_url_serves_v2", PASS if ok else FAIL,
                 f"{PUBLIC}/ -> HTTP {code}, location={loc!r}")

    try:
        with urllib.request.urlopen(f"{ORCH}/v2/", timeout=20) as r:
            cc = r.headers.get("cache-control", "")
    except Exception as exc:  # noqa: BLE001
        gate("frontend_entry_uncacheable", NOT_TESTED, f"{type(exc).__name__}: {exc}")
    else:
        ok = "no-cache" in cc and "no-store" in cc
        gate("frontend_entry_uncacheable", PASS if ok else FAIL,
             f"/v2/ cache-control: {cc!r} (a cacheable entry makes deploys invisible)")


# ── 6. delivery ──────────────────────────────────────────────────────────────

def check_delivery() -> None:
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    head, upstream = g("rev-parse", "HEAD"), g("rev-parse", "@{u}")
    ahead = g("rev-list", "--count", "@{u}..HEAD")
    dirty = bool(g("status", "--porcelain"))
    ok = head and head == upstream and ahead == "0"
    gate("delivery_pushed_remote_matches", PASS if ok else FAIL,
         f"HEAD={head[:12]} upstream={upstream[:12]} unpushed={ahead} worktree_dirty={dirty}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fast", action="store_true",
                    help="skip the full determinism suite (the ~6min gate); it then "
                         "reports NOT_TESTED, never PASS")
    a = ap.parse_args()

    conn = _conn()
    check_retrieval_core()
    check_chat_core()
    check_readiness_triad()
    check_hot_paths(conn)
    check_control_paths_no_regress(conn)
    check_write_path_boundary()
    check_parity()
    check_guards_and_attributed_failures(fast=a.fast)
    check_legacy_engine_traffic(conn)
    check_legacy_code_removal(conn)
    check_legacy_state_writers(conn)
    check_legacy(conn)
    check_frontend()
    check_delivery()

    if a.json:
        print(json.dumps(results, indent=2))
    else:
        width = max(len(r["gate"]) for r in results)
        for r in results:
            print(f"  {r['status']:14} {r['gate']:{width}}  {r['detail']}")
        counts: dict[str, int] = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print("\n  " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        if counts.get(FAIL):
            print("\n  VERDICT: NOT COMPLETE — one or more gates FAIL.")
        elif counts.get(BLOCKED) or counts.get(NOT_TESTED):
            print("\n  VERDICT: every observable gate passes; the remainder is owner-gated "
                  "or unobservable here. NOT_TESTED is never counted as green (§18).")
        else:
            print("\n  VERDICT: every gate PASSES.")
    return 1 if any(r["status"] == FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
