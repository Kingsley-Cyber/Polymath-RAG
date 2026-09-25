"""K1b live check ($0 — no model call; register 11.487). Run with the main .env loaded and the checkout's PYTHONPATH
(`$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control`). It loads THIS checkout's adapter worker file — Trail's one
outbound function, `_orch_post` — and calls the live orchestrator exactly as Trail's legacy and plan lanes do:
  1. /retrieve GRAPH without a scope → 200 and no `knowledge_scope` key (a request without a scope is unchanged);
  2. /retrieve GRAPH with Trail's scope → the reply confirms `{"roles": ["reference"]}`;
  3. /retrieve/plan with Trail's scope → confirmed (no model call: the plan compiler is deterministic);
  4. Trail's `_orch_post` with the legacy-lane body and the plan-lane body → accepted (no ScopeNotConfirmed);
  5. no Traceback written to orchestrator.log while the calls ran.
Not called: /chat/evidence — a live evidence-route probe needs the owner's word; its confirmation is unit-proven through
`run_chat`, the one reply builder behind /chat and /chat/evidence.
`--control`: the same calls against an orchestrator that does not confirm (the K1 fleet before the K1b bounce). Checks 2–4
must fail there: Trail's consumer refuses an orchestrator that does not confirm its scope — what a rollback to pre-K1b
code looks like from Trail's side. Writes live_check.json (live_check_control.json with --control), ids and counts only;
exit 0 only when every check holds."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import time

import httpx

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
LOG = pathlib.Path(os.environ.get("POLYMATH_ORCH_LOG", "/private/tmp/polymath_fleet/orchestrator.log"))
QUESTION = "How do editors and directors build suspense without dialogue?"
UA = "k1b-live-check"


def _worker():
    spec = importlib.util.spec_from_file_location("adapter_step_worker_live_check", ROOT / "workers" / "workers" / "adapter_step_worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _post(path: str, body: dict) -> tuple[int, dict]:
    r = httpx.post(f"{ORCH}{path}", json=body, timeout=180, headers={"User-Agent": UA})
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})


def main() -> int:
    control = "--control" in sys.argv[1:]
    W = _worker()
    scope = dict(W.EB.TRAIL_SCOPE)
    log_from = LOG.stat().st_size if LOG.exists() else 0
    runs: dict[str, dict] = {}
    code, out = _post("/retrieve", {"query": QUESTION, "corpus_id": "cinema", "mode": "GRAPH", "limit": 10})
    runs["retrieve_no_scope"] = {"http": code, "evidence": len(out.get("evidence") or []), "confirmation": out.get("knowledge_scope", "<absent>")}
    code, out = _post("/retrieve", {"query": QUESTION, "corpus_id": "cinema", "mode": "GRAPH", "limit": 10, "scope": scope})
    runs["retrieve_reference"] = {"http": code, "evidence": len(out.get("evidence") or []), "confirmation": out.get("knowledge_scope", "<absent>")}
    code, out = _post("/retrieve/plan", {"signal": QUESTION, "corpus_ids": ["cinema"], "limit": 24, "explore": True, "scope": scope})
    runs["plan_reference"] = {"http": code, "rows": len(out.get("evidence_rows") or []), "confirmation": out.get("knowledge_scope", "<absent>")}
    trail_bodies = {"trail_legacy_lane": ("/retrieve", {"query": QUESTION, "corpus_ids": ["cinema"], "limit": 16, "scope": scope, "explore": True}),
                    "trail_plan_lane": ("/retrieve/plan", {"signal": QUESTION, "corpus_ids": ["cinema"], "limit": 24, "explore": True, "scope": scope})}
    for name, (path, body) in trail_bodies.items():
        t0 = time.perf_counter()
        try:
            got = W._orch_post(path, body, user_agent=UA)
            runs[name] = {"accepted": True, "rows": len(got.get("evidence_rows") or []), "wall_ms": round((time.perf_counter() - t0) * 1000)}
        except W.ScopeNotConfirmed as exc:
            runs[name] = {"accepted": False, "refused": type(exc).__name__, "why": str(exc)[:240]}
    new_log = LOG.read_bytes()[log_from:].decode("utf-8", "replace") if LOG.exists() else ""
    checks = {
        "no_scope_unchanged": runs["retrieve_no_scope"]["http"] == 200 and runs["retrieve_no_scope"]["confirmation"] == "<absent>",
        "retrieve_confirms": runs["retrieve_reference"]["http"] == 200 and runs["retrieve_reference"]["confirmation"] == scope,
        "plan_confirms": runs["plan_reference"]["http"] == 200 and runs["plan_reference"]["confirmation"] == scope,
        "trail_accepts_both_lanes": all(runs[n]["accepted"] for n in trail_bodies),
        "no_new_traceback": "Traceback" not in new_log,
    }
    report = {"control": control, "worker_file": str(ROOT / "workers" / "workers" / "adapter_step_worker.py"), "runs": runs, "checks": checks}
    (HERE / ("live_check_control.json" if control else "live_check.json")).write_text(json.dumps(report, indent=1, default=str))
    for name, r in runs.items():
        print(name, r, flush=True)
    print(checks)
    ok = all(checks.values())
    print("ALL CHECKS PASS" if ok else "A CHECK FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
