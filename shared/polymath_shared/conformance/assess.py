"""Turn discovery into CLASSIFIED components, each carrying its evidence.

Every verdict here is derived from an observation, and the observation travels with the
verdict. A component with no evidence becomes NOT_TESTED — never green, never silently
omitted.
"""
from __future__ import annotations

from typing import Any

from .classify import Level, State, Status, severity

#: A lane's `function` -> the `stage_tickets.stage` value that function's pipeline runs
#: under. CHAT is deliberately absent: chat is a synchronous request path with no ticket
#: stage of its own (confirmed live: `chat_compiler` never appears in `stage_tickets`),
#: so its pipeline/E2E evidence comes from `query_receipts` instead (see `qualify_lane`).
FUNCTION_STAGE = {"GRAPH_EXTRACTION": "extract", "DOCUMENT_PROFILE": "doc_profile",
                  "PMAP": "doc_parent_map"}


def _c(kind: str, name: str, state: State, levels: list[Level],
       evidence: dict, notes: str = "") -> dict:
    return {"kind": kind, "name": name, "state": state.value,
            "severity": severity(state),
            "levels": [l.value for l in levels], "evidence": evidence, "notes": notes}


# ── provider lanes ───────────────────────────────────────────────────────────

def assess_lanes(lanes: list[dict], controller: dict[str, dict],
                 attempts: dict[str, dict] | None = None) -> list[dict]:
    """A lane is only WORKING_PROVEN when something actually dispatched on it.

    `controller` is the durable llm_controller_state keyed by lane name; `attempts` is
    the per-lane attempt ledger when one is available. Config alone never promotes a
    lane past CONFIGURED_IDLE — a configured lane with no caller is not "working".
    """
    out = []
    for l in lanes:
        name = l["name"]
        st = controller.get(name, {})
        at = (attempts or {}).get(name, {})
        day = int(st.get("day_count") or 0)
        seen = int(at.get("attempts") or 0)
        ok = int(at.get("ok") or 0)
        levels = [Level.IMPLEMENTED]
        ev: dict[str, Any] = {
            "enabled": l["enabled"], "reachability": l["reachability"],
            "function": l["function"], "model": l["model"],
            "account_env": l["account_env"], "stage_pin": l["stage_pin"],
            "fallback_tier": l["fallback_tier"], "capacity": l["capacity"],
            "durable_day_count": day, "durable_state_present": bool(st),
            "attempts_ledger": at or None,
        }
        if not l["enabled"]:
            out.append(_c("lane", name, State.RETIRE_CANDIDATE, levels, ev,
                          "disabled in config; superseded unless a rollback needs it"))
            continue
        if l["reachability"] != "active":
            out.append(_c("lane", name, State.BROKEN_REACHABLE, levels, ev,
                          f"enabled but reachability={l['reachability']}"))
            continue
        levels += [Level.WIRED, Level.LIVE]
        if l["function"] == "dedicated_unpinned":
            out.append(_c("lane", name, State.BROKEN_REACHABLE, levels, ev,
                          "enabled + reachable but pinned to NO function — serves nothing"))
            continue
        if day > 0 or seen > 0:
            levels.append(Level.OBSERVED)
            if ok > 0 or day > 0:
                levels.append(Level.CONTRACT_QUALIFIED)
                state = State.WORKING_PROVEN if ok or day else State.WORKING_UNQUALIFIED
            else:
                state = State.BROKEN_REACHABLE
            out.append(_c("lane", name, state, levels, ev,
                          f"{day} durable dispatches today" + (f", {seen} ledger attempts" if seen else "")))
            continue
        out.append(_c("lane", name, State.CONFIGURED_IDLE, levels, ev,
                      "reachable, pinned, but no dispatch observed"))
    return out


def _chat_pipeline_status(agg: dict) -> Status:
    """L3 for CHAT: did the retrieval pipeline actually run and return, regardless of
    whether it found grounded evidence (an honest `insufficient_evidence` abstention is a
    working pipeline, not a failure)."""
    if agg.get("ok", 0) > 0:
        return Status.PASS
    return Status.FAIL if agg.get("error", 0) > 0 else Status.NOT_TESTED


def _chat_e2e_status(agg: dict) -> Status:
    """L5 for CHAT: did the full upload->process->ready->query->evidence->answer chain
    actually produce grounded, cited evidence -- the fuller bar above mere pipeline PASS."""
    if agg.get("ok", 0) == 0:
        return Status.FAIL if agg.get("error", 0) > 0 else Status.NOT_TESTED
    return Status.PASS if (agg.get("grounded", 0) or agg.get("cited", 0)) else Status.DEGRADED


def qualify_lane(lane: dict, attempts_per_lane: dict[str, dict], controller: dict[str, dict],
                 stage_act: dict[str, dict], chat_receipts: dict) -> dict:
    """CONTRACT/PIPELINE/E2E qualification (L2/L3/L5) for ONE lane, derived ONLY from
    evidence that already exists: the provider-attempt ledger and durable limiter state
    (real round-trips already made) and `stage_tickets`/`query_receipts` (real
    pipeline/product completions already recorded). This function dispatches nothing and
    infers nothing from absence -- a lane with zero recent evidence stays honestly
    NOT_TESTED, matching `classify.py`'s own rule that NOT_TESTED must never be
    manufactured into a PASS.

    `contract_qualified` is genuinely per-LANE (did THIS lane's own dispatches succeed).
    Two evidence tiers, preferring the richer one: the attempt ledger (per-call
    success/failure, `llm_provider_attempts`) when THIS lane has rows in it; falling back
    to the durable limiter's `day_count` (`llm_controller_state`) when it does not --
    **as of 2026-09-12 the ledger is populated only for the CHAT-compiler lanes**
    (confirmed live: `compiler_alt`/`compiler_ollama_gemma`/`compiler_alibaba_qwen` are
    the only rows in `llm_provider_attempts` even over a 7-day window, despite
    `doc_parent_map_stage_worker.py` wrapping its calls in `attempt_context(function=
    "PMAP", ...)` -- a separate, pre-existing ledger-population gap, not something this
    slice fixes), so for GRAPH_EXTRACTION/DOCUMENT_PROFILE/PMAP lanes today this
    correctly and necessarily falls back to `day_count`. This exactly matches the
    precedent `assess_lanes` (above) already established in production -- `day > 0`
    already promotes a lane to `Level.CONTRACT_QUALIFIED` there; this function must not
    invent a stricter, inconsistent bar. The day_count fallback has no per-call
    failure visibility, so PASS is its honest ceiling (never DEGRADED/FAIL from count
    alone); the ledger tier, where populated, gives the finer PASS/DEGRADED/FAIL.

    `pipeline_qualified` is per-FUNCTION (did the ticket stage complete recently at all,
    regardless of which lane within the function served it -- matching the execution
    authority's own point that batch SUCCESS and per-attempt failure are different facts).
    `e2e_qualified` is NOT_APPLICABLE for the three ticket-pipeline functions (L5 "product
    E2E" is a CHAT/retrieval-surface concept; GRAPH_EXTRACTION/DOCUMENT_PROFILE/PMAP's own
    completion IS their L3, they have no separate query/answer step) and is CHAT-specific.
    """
    fn = lane["function"]
    at = attempts_per_lane.get(lane["name"], {})
    attempts, succeeded = int(at.get("attempts") or 0), int(at.get("succeeded") or 0)
    day = int((controller.get(lane["name"]) or {}).get("day_count") or 0)

    if attempts > 0:
        if succeeded == 0:
            contract = Status.FAIL
        elif succeeded < attempts:
            contract = Status.DEGRADED
        else:
            contract = Status.PASS
    elif day > 0:
        contract = Status.PASS
    else:
        contract = Status.NOT_TESTED

    if fn == "CHAT":
        pipeline, e2e = _chat_pipeline_status(chat_receipts), _chat_e2e_status(chat_receipts)
        pipeline_evidence = {"query_receipts_overall": chat_receipts}
    else:
        stage = FUNCTION_STAGE.get(fn)
        recent = int((stage_act.get(stage) or {}).get("recent") or 0) if stage else 0
        pipeline = Status.PASS if recent else Status.NOT_TESTED
        e2e = Status.NOT_APPLICABLE
        pipeline_evidence = {"stage": stage, "stage_activity": stage_act.get(stage) if stage else None}

    return {
        "contract_qualified": contract.value,
        "pipeline_qualified": pipeline.value,
        "e2e_qualified": e2e.value,
        "qualification_evidence": {
            "attempt_ledger": at or None,
            "attempts": attempts, "succeeded": succeeded,
            "durable_day_count": day, "contract_evidence_tier": (
                "attempt_ledger" if attempts > 0 else ("day_count" if day > 0 else "none")),
            **pipeline_evidence,
        },
    }


# ── workers ──────────────────────────────────────────────────────────────────

def assess_workers(on_disk: list[dict], supervisor: dict, live: dict,
                   stage_activity: dict[str, dict]) -> list[dict]:
    """A worker file with no supervisor slot and no live registration is not 'working'."""
    slots = {s["name"]: s for s in (supervisor.get("slots") or [])}
    live_types = {r["worker_type"]: r for r in (live.get("by_type") or [])}
    out = []
    for w in on_disk:
        mod = w["module"]
        stem = mod.split(".")[-1]
        slot_names = [n for n, s in slots.items() if stem in str(s.get("name", "")) or n.startswith(stem.replace("_worker", ""))]
        matched_live = [t for t in live_types if t.replace("_", "") in stem.replace("_", "") or stem.replace("_worker", "").replace("_", "") in t.replace("_", "")]
        act = {}
        for t in matched_live:
            act = stage_activity.get(t, act)
        levels = [Level.IMPLEMENTED]
        ev = {"path": w["path"], "supervisor_slots": slot_names,
              "live_worker_types": matched_live, "stage_activity": act or None}
        if not slot_names and not matched_live:
            out.append(_c("worker", mod, State.NOT_TESTED, levels, ev,
                          "no supervisor slot and no live registration found — verify before assuming dead"))
            continue
        levels.append(Level.WIRED)
        if matched_live:
            levels += [Level.LIVE]
            if act.get("recent"):
                levels += [Level.OBSERVED, Level.PIPELINE_QUALIFIED]
                st = State.WORKING_PROVEN
                note = f"{act.get('recent')} tickets in the activity window"
            else:
                st = State.CONFIGURED_IDLE
                note = "registered and healthy, no recent tickets"
        else:
            st = State.CONFIGURED_IDLE
            note = "has a supervisor slot but is not currently registered (autopilot parking is normal)"
        out.append(_c("worker", mod, st, levels, ev, note))
    return out


# ── API routes ───────────────────────────────────────────────────────────────

def assess_routes(routes: list[dict], probe_results: dict[str, dict] | None = None) -> list[dict]:
    out = []
    for r in routes:
        path = r["path"]
        pr = (probe_results or {}).get(path)
        levels = [Level.IMPLEMENTED, Level.WIRED]
        ev = {"methods": r.get("methods"), "source": r.get("source"), "probe": pr}
        if r.get("source") == "live":
            levels.append(Level.LIVE)
        if pr is None:
            out.append(_c("route", path, State.NOT_TESTED, levels, ev, "not probed in this scope"))
            continue
        levels.append(Level.OBSERVED)
        if pr.get("ok"):
            levels.append(Level.CONTRACT_QUALIFIED)
            out.append(_c("route", path, State.WORKING_PROVEN, levels, ev,
                          f"HTTP {pr.get('status')}"))
        else:
            out.append(_c("route", path, State.BROKEN_REACHABLE, levels, ev,
                          f"HTTP {pr.get('status')}: {str(pr.get('error'))[:120]}"))
    return out


# ── durable state ────────────────────────────────────────────────────────────

def assess_state(tables: list[dict], readers: dict[str, dict]) -> list[dict]:
    """Classify a table by its READERS, never by whether it looks old.

    `readers` maps table -> {"readers": [...], "writers": [...], "runtime": bool}.
    Retirement requires zero readers AND zero writers; this function never promotes a
    table to DEAD_PROVEN on row count or age alone.
    """
    out = []
    for t in tables:
        name = t["table"]
        r = readers.get(name, {})
        rd, wr = r.get("readers", []), r.get("writers", [])
        levels = [Level.IMPLEMENTED]
        ev = {"rows": t["rows"], "last_activity": t["last_activity"],
              "static_readers": rd, "static_writers": wr,
              "reader_count": len(rd), "writer_count": len(wr)}
        if rd or wr:
            levels += [Level.WIRED]
            if t["rows"]:
                levels.append(Level.LIVE)
            st = State.WORKING_PROVEN if (rd and t["rows"]) else State.LEGACY_REQUIRED
            note = f"{len(rd)} reader(s), {len(wr)} writer(s)"
            if rd and not wr:
                st, note = State.LEGACY_REQUIRED, f"read by {len(rd)} site(s) but nothing writes it"
            out.append(_c("state", name, st, levels, ev, note))
            continue
        if not r:
            out.append(_c("state", name, State.NOT_TESTED, levels, ev,
                          "reader/writer census not run for this table"))
            continue
        out.append(_c("state", name, State.RETIRE_CANDIDATE, levels, ev,
                      "no static reader or writer found — needs runtime proof before removal"))
    return out


def summarize(components: list[dict]) -> dict:
    by_state: dict[str, int] = {}
    for c in components:
        by_state[c["state"]] = by_state.get(c["state"], 0) + 1
    return {
        "total": len(components),
        "by_state": dict(sorted(by_state.items())),
        "green": sum(1 for c in components if c["severity"] == "green"),
        "amber": sum(1 for c in components if c["severity"] == "amber"),
        "red": sum(1 for c in components if c["severity"] == "red"),
    }
