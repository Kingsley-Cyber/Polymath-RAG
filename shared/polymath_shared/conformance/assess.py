"""Turn discovery into CLASSIFIED components, each carrying its evidence.

Every verdict here is derived from an observation, and the observation travels with the
verdict. A component with no evidence becomes NOT_TESTED — never green, never silently
omitted.
"""
from __future__ import annotations

from typing import Any

from .classify import Level, State, severity


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
