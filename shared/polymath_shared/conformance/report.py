"""The durable audit bundle: one directory per run, machine-readable + a human report."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import AUDIT_VERSION
from .classify import State

ROOT = Path(__file__).resolve().parents[3]
BUNDLE_ROOT = ROOT / "artifacts" / "audit"


def new_audit_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class Bundle:
    def __init__(self, audit_id: str | None = None, root: Path | None = None) -> None:
        self.audit_id = audit_id or new_audit_id()
        self.dir = (root or BUNDLE_ROOT) / self.audit_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.files: list[str] = []

    def write(self, name: str, payload: Any) -> Path:
        p = self.dir / name
        p.write_text(json.dumps(payload, indent=2, default=str, sort_keys=False) + "\n")
        self.files.append(name)
        return p

    def write_text(self, name: str, text: str) -> Path:
        p = self.dir / name
        p.write_text(text)
        self.files.append(name)
        return p


def manifest(*, git: dict, bundle_state: dict, config: dict, scope: dict,
             discovered: dict, live_calls: int) -> dict:
    return {
        "audit_version": AUDIT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": git,
        "runtime_bundle": bundle_state,
        "config_hashes": config,
        "scope": scope,
        "discovered": discovered,
        "live_calls_performed": live_calls,
    }


def render_report(man: dict, components: list[dict], summary: dict,
                  sections: dict[str, Any]) -> str:
    L: list[str] = []
    a = L.append
    a("# POLYMATH PRODUCTION CONFORMANCE\n")
    a(f"audit `{man['audit_version']}` · {man['generated_at']}\n")
    a("## REPO\n```")
    a(f"branch:         {man['repo']['branch']}")
    a(f"SHA:            {man['repo']['sha']}")
    a(f"worktree dirty: {man['repo']['dirty']}")
    rb = man["runtime_bundle"]
    a(f"runtime bundle: {', '.join(rb.get('live') or []) or 'none live'}"
      + ("" if rb.get("uniform") else "   ** NOT UNIFORM **"))
    a("```\n")

    d = man["discovered"]
    a("## DISCOVERY\n```")
    for k in ("functions", "providers", "models", "accounts", "lanes",
              "workers", "routes", "states"):
        if k in d:
            a(f"{k+':':12} {d[k]}")
    a("```\n")
    a(f"scope: `{man['scope']}` · live calls performed: **{man['live_calls_performed']}**\n")

    a("## CLASSIFICATION\n```")
    a(f"total {summary['total']}   green {summary['green']}   "
      f"amber {summary['amber']}   red {summary['red']}")
    for st, n in summary["by_state"].items():
        a(f"  {st:22} {n}")
    a("```\n")

    for st in State:
        rows = [c for c in components if c["state"] == st.value]
        if not rows:
            continue
        a(f"### {st.value}  ({len(rows)})\n")
        for c in sorted(rows, key=lambda x: (x["kind"], x["name"]))[:60]:
            a(f"- `{c['kind']}` **{c['name']}** — {c['notes'] or '—'}")
        if len(rows) > 60:
            a(f"- … and {len(rows)-60} more (see `function_results.json`)")
        a("")

    for title, body in sections.items():
        a(f"## {title}\n")
        if isinstance(body, str):
            a(body + "\n")
        else:
            a("```")
            a(json.dumps(body, indent=2, default=str)[:6000])
            a("```\n")

    a("## FINAL QUESTIONS\n```")
    a(f"Can a provider/model be added, replaced or removed and the SAME audit re-fired?   "
      f"{sections.get('_agnostic', 'NOT_TESTED')}")
    a(f"Can the auditor discover working systems without hardcoding them?                 "
      f"{sections.get('_discovery', 'NOT_TESTED')}")
    a(f"Can it prove unused/superseded systems before removing them?                      "
      f"{sections.get('_retirement', 'NOT_TESTED')}")
    a("```")
    return "\n".join(L)
