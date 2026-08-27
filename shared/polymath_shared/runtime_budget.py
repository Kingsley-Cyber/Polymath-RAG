"""RUNTIME BUDGET — enforce one memory ceiling across the whole repo.

Reads `config/runtime_budget.yaml` and turns it into things that
actually bind at runtime:

  * per-sidecar Metal (MPS) pool caps, exported as environment variables
    the torch runtimes honour;
  * token-aware batch bounds for the embedder;
  * a preflight that refuses to start a working set which cannot fit.

Written after the embedder was measured holding 41.58 GiB of MPS memory
on a 32 GB machine — `model.encode()` was called with no batch bound and
PyTorch's Metal pool was never released, so the host thrashed and the
owner's session degraded. A budget nobody enforces is a comment.
"""

from __future__ import annotations

import functools
import os
import pathlib
import subprocess
import sys
from typing import Any

import yaml

CONFIG = pathlib.Path(__file__).resolve().parents[2] / "config" / "runtime_budget.yaml"


class BudgetExceeded(RuntimeError):
    """The requested working set does not fit the allocation."""


@functools.lru_cache(maxsize=1)
def budget() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text())


def physical_gb() -> float:
    try:
        out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                             capture_output=True, text=True, timeout=30)
        return int(out.stdout.strip()) / (1024 ** 3)
    except Exception:
        # Non-Darwin, sysctl absent, or the call failed. Callers treat 0
        # as "unknown" and fall back; raising here would take the whole
        # supervisor down over a memory-size probe.
        return 0.0


# ---------------------------------------------------------------------------
# MPS caps
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def mps_denominator_gb() -> float:
    """The number PyTorch actually divides the watermark ratio by.

    NOT physical memory. `PYTORCH_MPS_HIGH_WATERMARK_RATIO` is applied
    against Metal's RECOMMENDED MAX WORKING SET, which on Apple Silicon
    is roughly 78% of RAM (24.96 GiB of 32 GiB on this host). Dividing
    the budget by physical memory instead produced a cap 22% tighter
    than the budget stated: a 2.0 GB embedder budget became a 1.56 GiB
    ceiling, and the projection failed with `MPS backend out of memory`
    at 1.54 GiB allocated while the budget appeared to have headroom.

    Asked of torch in a subprocess so the supervisor -- which sizes the
    fleet before any model loads -- never imports torch itself.
    """
    probe = ("import torch,sys;"
             "sys.stdout.write(str(torch.mps.recommended_max_memory()))")
    try:
        out = subprocess.run([sys.executable, "-c", probe],
                             capture_output=True, text=True, timeout=60)
        value = int(out.stdout.strip()) / (1024 ** 3)
        if value > 0:
            return value
    except Exception:
        pass
    # Metal unavailable or torch absent: the conventional Apple Silicon
    # fraction is a far better estimate than physical memory.
    return (physical_gb() or 32.0) * 0.78


def mps_env(slot: str) -> dict[str, str]:
    """Environment that bounds one sidecar's Metal pool.

    The low watermark sits below the high one so the allocator starts
    returning blocks before it hits the wall instead of raising `MPS
    backend out of memory` mid-batch.
    """
    spec = (budget().get("sidecars") or {}).get(slot) or {}
    cap_gb = float(spec.get("mps_gb", 0) or 0)
    if cap_gb <= 0:
        # No GPU budget: keep the runtime off Metal entirely.
        return {"PYTORCH_ENABLE_MPS_FALLBACK": "1",
                "POLYMATH_MPS_CAP_GB": "0"}
    high = max(0.02, min(0.95, cap_gb / mps_denominator_gb()))
    return {
        "PYTORCH_MPS_HIGH_WATERMARK_RATIO": f"{high:.4f}",
        "PYTORCH_MPS_LOW_WATERMARK_RATIO": f"{high * 0.7:.4f}",
        "POLYMATH_MPS_CAP_GB": f"{cap_gb:g}",
    }


def batch_bounds(slot: str) -> tuple[int, int]:
    """(max_batch_texts, max_batch_tokens) for a sidecar."""
    spec = (budget().get("sidecars") or {}).get(slot) or {}
    return (int(spec.get("max_batch_texts", 8) or 8),
            int(spec.get("max_batch_tokens", 16384) or 16384))


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------

def profile_slots(name: str) -> list[str]:
    """Slots for a named profile (POLYMATH_PROFILE)."""
    profiles = budget().get("profiles") or {}
    if name not in profiles:
        raise KeyError(f"unknown profile {name!r}; have {sorted(profiles)}")
    return list(profiles[name]["slots"])


def working_set(fleet_only: str | None = None) -> list[str]:
    prof = os.environ.get("POLYMATH_PROFILE", "").strip()
    if fleet_only is None and prof:
        return profile_slots(prof)
    only = (fleet_only if fleet_only is not None
            else os.environ.get("POLYMATH_FLEET_ONLY", "")).strip()
    if only:
        return [n.strip() for n in only.split(",") if n.strip()]
    b = budget()
    return (list((b.get("sidecars") or {}).keys())
            + ["orchestrator", "control", "intake", "profile", "extract",
               "canonicalize", "project_canonical", "neo4j", "qdrant", "verify"])


def plan(fleet_only: str | None = None) -> dict[str, Any]:
    """What the selected working set costs against the ceiling."""
    b = budget()
    slots = working_set(fleet_only)
    cp = b.get("control_plane") or {}
    lines: list[tuple[str, float]] = [("docker_vm", float(b["docker"]["vm_gb"]))]
    for slot in slots:
        spec = (b.get("sidecars") or {}).get(slot)
        if spec:
            lines.append((slot, float(spec.get("resident_gb", 0))
                          + float(spec.get("mps_gb", 0))))
        elif slot == "orchestrator":
            lines.append((slot, float(cp.get("orchestrator_gb", 0.5))))
        elif slot == "control":
            lines.append((slot, float(cp.get("control_gb", 0.15))))
        else:
            lines.append((slot, float(cp.get("per_worker_gb", 0.15))))
    committed = sum(v for _, v in lines)
    ceiling = float(b["total_gb"]) - float(b.get("reserve_gb", 0))
    return {"slots": slots, "lines": lines, "committed_gb": round(committed, 2),
            "ceiling_gb": round(ceiling, 2), "total_gb": float(b["total_gb"]),
            "fits": committed <= ceiling}


def preflight(fleet_only: str | None = None) -> dict[str, Any]:
    """Raise rather than start an over-committed fleet."""
    p = plan(fleet_only)
    if budget().get("enforce_preflight", True) and not p["fits"]:
        detail = "\n".join(f"    {n:22s} {v:5.2f} GB" for n, v in p["lines"])
        raise BudgetExceeded(
            f"working set commits {p['committed_gb']} GB against a "
            f"{p['ceiling_gb']} GB ceiling "
            f"(budget {p['total_gb']} GB minus reserve):\n{detail}\n"
            f"  Start fewer slots with POLYMATH_FLEET_ONLY, or revise "
            f"config/runtime_budget.yaml deliberately.")
    return p


def _listening(port: int) -> bool:
    try:
        out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                             capture_output=True, text=True, timeout=15)
        return bool(out.stdout.strip())
    except Exception:
        return False


def footprint_gb() -> dict[str, float]:
    """What Polymath is ACTUALLY consuming right now.

    This is the number the allocation is a contract about, and it is not
    the same as the machine's free memory. The host also runs the
    owner's own applications; those legitimately occupy the rest of the
    machine, and a run that stops because the owner opened a browser is
    measuring somebody else's memory.

    Metal allocations live in unified memory and do not appear in RSS,
    so the sidecars' GPU pools are added from their budgeted caps rather
    than observed -- the preflight already refuses a fleet whose caps do
    not fit, and the watermark ratios make the caps binding.
    """
    out = subprocess.run(["ps", "-eo", "rss,command"],
                         capture_output=True, text=True, timeout=30)
    markers = ("process_supervisor", "sidecars.", "control.main", "workers.",
               "orchestrator", "polymath")
    rss = 0.0
    for line in out.stdout.splitlines()[1:]:
        parts = line.split(None, 1)
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        if "grep" in parts[1]:
            continue
        if any(m in parts[1] for m in markers):
            rss += int(parts[0]) / (1024 ** 2)
    b = budget()
    vm = float(b["docker"]["vm_gb"])
    # Charge a GPU cap only for a sidecar that is actually LISTENING.
    # Reading the intended working set from the environment instead
    # over-charged a projection run with GLiNER and the reranker it had
    # never started, and a guard that invents 5.5 GB of usage will stop
    # a run that is comfortably inside its allocation.
    gpu = sum(float(spec.get("mps_gb", 0) or 0)
              for spec in (b.get("sidecars") or {}).values()
              if spec.get("port") and _listening(int(spec["port"])))
    total = rss + vm + gpu
    ceiling = float(b["total_gb"])
    return {"host_rss_gb": round(rss, 2), "docker_vm_gb": vm,
            "gpu_caps_gb": round(gpu, 2), "total_gb": round(total, 2),
            "budget_gb": ceiling, "within_budget": total <= ceiling,
            "headroom_gb": round(ceiling - total, 2)}


def export_env(slot: str) -> dict[str, str]:
    """Full environment for one sidecar: MPS cap plus batch bounds."""
    texts, tokens = batch_bounds(slot)
    env = dict(mps_env(slot))
    env["POLYMATH_MAX_BATCH_TEXTS"] = str(texts)
    env["POLYMATH_MAX_BATCH_TOKENS"] = str(tokens)
    return env


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "env":
        for k, v in export_env(sys.argv[2]).items():
            print(f"export {k}={v}")
    else:
        p = plan()
        print(json.dumps(p, indent=1))
        print("FITS" if p["fits"] else "OVER BUDGET")
