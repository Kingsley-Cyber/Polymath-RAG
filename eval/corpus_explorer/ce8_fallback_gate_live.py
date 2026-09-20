#!/usr/bin/env python3
"""CORPUS-EXPLORE-FIRING-V1 Phase B — function-level LIVE proof of the fallback gate (asserting; exit != 0 on
failure). A compiler transport fallback cannot be produced on demand over HTTP, so this drives the DEPLOYED
`_add_corpus_explore_expansion` in-process against the real embedder, real Qdrant and the real bridge model.

Run from the MAIN checkout (the editable .pth resolves `orchestrator` there) with `.env` sourced:
    set -a; . ./.env; set +a; .venv/bin/python eval/corpus_explorer/ce8_fallback_gate_live.py

Cases (only case 1 makes a bridge-model call = ONE live execution):
  1. transport fallback + switch ON   -> FIRES (>=1 CORPUS_EXPLORE subquery), receipt shows plan_fallback
  2. invalid_plan fallback + switch ON -> PLAN_FALLBACK (the compiler rendered a judgment; stay closed)
  3. transport fallback + switch OFF  -> PLAN_FALLBACK (the pre-fix gate, byte-for-byte the old behavior)
  4. request flag OFF                 -> REQUEST_OFF and plan.queries untouched (flag-off invariance)
  5. no PRIMARY (compiler said no retrieval) -> OTHER no_primary:... (q0 authority, never creates retrieval)
"""
from __future__ import annotations

import json
import os
import sys

import orchestrator.api.ui as ui
from polymath_shared.chat_plan import fallback_plan
from polymath_shared.corpus_explore_firing import FALLBACK_OPEN_ENV

Q0 = "make a character's suppressed grief visible while they try hard to hide it"
CORPORA = ["cinema"]
results, failures = {}, []


def check(name: str, cond: bool, info) -> None:
    results[name] = {"ok": bool(cond), "info": info}
    if not cond:
        failures.append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {json.dumps(info, default=str)[:300]}", flush=True)


def run(reason: str, *, enabled: bool = True, strip_primary: bool = False):
    plan = fallback_plan(Q0, reason=reason)
    if strip_primary:
        plan.queries = []
        plan.retrieval_required = False
        plan.task_type = "TRANSFORM_USER_CONTENT"
    before = [(q.id, q.query) for q in plan.queries]
    ui._add_corpus_explore_expansion(plan, Q0, CORPORA, None, enabled=enabled)
    rec = plan.compiler.get("corpus_explore_firing") or {}
    ce = [q for q in plan.queries if getattr(q, "origin", "") == "CORPUS_EXPLORE"]
    return plan, rec, ce, before


def main() -> int:
    print("ui module:", ui.__file__)
    assert os.environ.get("POLYMATH_CORPUS_EXPLORER") == "1", "source the live .env first"

    os.environ[FALLBACK_OPEN_ENV] = "1"
    plan, rec, ce, before = run("transport:ReadTimeout")
    check("1_transport_fallback_fires", rec.get("fired") is True and len(ce) >= 1
          and (rec.get("stages") or {}).get("plan_fallback") == "transport:ReadTimeout"
          and plan.queries[0].type == "PRIMARY" and plan.queries[0].query == before[0][1]
          and all(getattr(q, "inspired_by_profile", None) for q in ce),
          {"receipt": rec, "ce_subqueries": [q.query for q in ce]})

    plan, rec, ce, before = run("invalid_plan:no_queries_for_retrieval")
    check("2_invalid_judgment_stays_closed", rec.get("fired") is False and rec.get("cause") == "PLAN_FALLBACK"
          and not ce and [(q.id, q.query) for q in plan.queries] == before, rec)

    os.environ[FALLBACK_OPEN_ENV] = "0"
    plan, rec, ce, before = run("transport:ReadTimeout")
    check("3_switch_off_is_pre_fix_gate", rec.get("fired") is False and rec.get("cause") == "PLAN_FALLBACK"
          and not ce and [(q.id, q.query) for q in plan.queries] == before
          and "corpus_activation" not in plan.compiler, rec)

    os.environ[FALLBACK_OPEN_ENV] = "1"
    plan, rec, ce, before = run("transport:ReadTimeout", enabled=False)
    check("4_request_off_untouched", rec.get("cause") == "REQUEST_OFF" and not ce
          and [(q.id, q.query) for q in plan.queries] == before
          and "corpus_activation" not in plan.compiler and "corpus_explore_expansion" not in plan.compiler, rec)

    plan, rec, ce, before = run("transport:ReadTimeout", strip_primary=True)
    check("5_no_primary_q0_authority", rec.get("fired") is False and rec.get("cause") == "OTHER"
          and str(rec.get("detail")).startswith("no_primary:retrieval_not_required:") and not plan.queries, rec)

    out = {"contract": "corpus-explore-ce8-fallback-gate-live-v1", "q0": Q0, "ui_module": ui.__file__,
           "results": results, "passed": not failures}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CE8-FALLBACK-GATE-LIVE-2026-09-19.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print("ARTIFACT", path)
    print("RESULT:", "PASS" if not failures else f"FAIL {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
