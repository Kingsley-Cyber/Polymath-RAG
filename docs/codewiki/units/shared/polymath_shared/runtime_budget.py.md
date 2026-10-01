# unit: shared/polymath_shared/runtime_budget.py
anchor: shared/polymath_shared/runtime_budget.py:1-258

## purpose
Turns `config/runtime_budget.yaml` into constraints that actually bind at runtime: per-sidecar Metal (MPS) pool caps exported as env vars torch honours, token-aware batch bounds for the embedder, and a preflight that refuses to start a working set that cannot fit — shared/polymath_shared/runtime_budget.py:3-9 [DERIVED]. Exists because the embedder was measured holding 41.58 GiB of MPS memory on a 32 GB machine (`model.encode()` with no batch bound, Metal pool never released) — shared/polymath_shared/runtime_budget.py:11-14 [DERIVED]. Consumed by the fleet supervisor layer (see importers below).

## public surface
Module imported by: control/control/fleet_autopilot.py, control/control/process_supervisor.py (FACTS.importers).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| BudgetExceeded | class (RuntimeError) | no methods | shared/polymath_shared/runtime_budget.py:31-32 | raised by preflight:176 |
| budget | def | () -> dict[str, Any] | shared/polymath_shared/runtime_budget.py:36-37 | importers (module-level) |
| physical_gb | def | () -> float | shared/polymath_shared/runtime_budget.py:40-49 | — |
| mps_denominator_gb | def | () -> float | shared/polymath_shared/runtime_budget.py:57-83 | — |
| _sidecar_spec | def (private) | (slot: str) -> dict | shared/polymath_shared/runtime_budget.py:86-90 | internal only |
| mps_env | def | (slot: str) -> dict[str, str] | shared/polymath_shared/runtime_budget.py:93-111 | — |
| batch_bounds | def | (slot: str) -> tuple[int, int] | shared/polymath_shared/runtime_budget.py:114-118 | — |
| profile_slots | def | (name: str) -> list[str] | shared/polymath_shared/runtime_budget.py:125-130 | — |
| working_set | def | (fleet_only: str \| None = None) -> list[str] | shared/polymath_shared/runtime_budget.py:133-144 | — |
| plan | def | (fleet_only: str \| None = None) -> dict[str, Any] | shared/polymath_shared/runtime_budget.py:147-168 | — |
| preflight | def | (fleet_only: str \| None = None) -> dict[str, Any] | shared/polymath_shared/runtime_budget.py:171-182 | — |
| _listening | def (private) | (port: int) -> bool | shared/polymath_shared/runtime_budget.py:185-191 | internal only |
| footprint_gb | def | () -> dict[str, float] | shared/polymath_shared/runtime_budget.py:194-236 | — |
| export_env | def | (slot: str) -> dict[str, str] | shared/polymath_shared/runtime_budget.py:239-245 | — |

## contracts

**budget()**
- in: reads file at `parents[2]/"config"/"runtime_budget.yaml"` — shared/polymath_shared/runtime_budget.py:28,37 [DERIVED]
- out: parsed YAML dict, cached via `functools.lru_cache(maxsize=1)` — shared/polymath_shared/runtime_budget.py:35-37 [DERIVED]
- pre: CONFIG exists and parses; no handler, errors propagate — shared/polymath_shared/runtime_budget.py:36-37 [INFERRED: no try/except around read/safe_load]

**mps_denominator_gb()**
- out: GiB float from `torch.mps.recommended_max_memory()` probed via `sys.executable -c` subprocess (timeout=60) — shared/polymath_shared/runtime_budget.py:71-76 [DERIVED]
- post: cached `lru_cache(maxsize=1)` — shared/polymath_shared/runtime_budget.py:56 [DERIVED]
- fallback: `(physical_gb() or 32.0) * 0.78` — shared/polymath_shared/runtime_budget.py:83 [DERIVED]

**mps_env(slot)**
- in: spec via `_sidecar_spec`; numbered siblings (e.g. `extract2`) inherit base slot spec via `slot.rstrip("0123456789")` — shared/polymath_shared/runtime_budget.py:86-90 [DERIVED]
- out (no GPU budget, `mps_gb <= 0`): `{"PYTORCH_ENABLE_MPS_FALLBACK": "1", "POLYMATH_MPS_CAP_GB": "0"}` — shared/polymath_shared/runtime_budget.py:102-105 [DERIVED]
- out (capped): `high = max(0.02, min(0.95, cap_gb / mps_den_gb()))`; returns `PYTORCH_MPS_HIGH_WATERMARK_RATIO` = `f"{high:.4f}"`, `PYTORCH_MPS_LOW_WATERMARK_RATIO` = `f"{high*0.7:.4f}"`, `POLYMATH_MPS_CAP_GB` = `f"{cap_gb:g}"` — shared/polymath_shared/runtime_budget.py:106-110 [DERIVED]

**batch_bounds(slot)**
- out: `(int(spec.get("max_batch_texts", 8) or 8), int(spec.get("max_batch_tokens", 16384) or 16384))` — shared/polymath_shared/runtime_budget.py:117-118 [DERIVED]

**working_set(fleet_only=None)**
- pre: `POLYMATH_PROFILE` set and `fleet_only is None` → `profile_slots(prof)`; unknown profile raises `KeyError` — shared/polymath_shared/runtime_budget.py:129,134-136 [DERIVED]
- out: `POLYMATH_FLEET_ONLY` comma-split if set; else all sidecar keys + `["orchestrator", "control", "intake", "profile", "extract", "canonicalize", "project_canonical", "neo4j", "qdrant", "verify"]` — shared/polymath_shared/runtime_budget.py:137-144 [DERIVED]

**plan(fleet_only=None)**
- out: `lines` starting with `("docker_vm", b["docker"]["vm_gb"])`; sidecar cost = `resident_gb + mps_gb`; defaults `orchestrator_gb` 0.5, `control_gb` 0.15, `per_worker_gb` 0.15 — shared/polymath_shared/runtime_budget.py:152-163 [DERIVED]
- out: `ceiling_gb = total_gb - reserve_gb(0)`, `fits = committed <= ceiling` — shared/polymath_shared/runtime_budget.py:164-168 [DERIVED]
- pre: yaml must contain `docker.vm_gb` and `total_gb` (direct indexing) — shared/polymath_shared/runtime_budget.py:152,165 [INFERRED: `[]` not `.get`, missing key raises KeyError]

**preflight(fleet_only=None)**
- post: raises `BudgetExceeded` when `budget().get("enforce_preflight", True)` and `not fits`; message lists per-line GB and names `POLYMATH_FLEET_ONLY` and `config/runtime_budget.yaml` as remedies — shared/polymath_shared/runtime_budget.py:174-181 [DERIVED]
- out: plan dict when it fits — shared/polymath_shared/runtime_budget.py:182 [DERIVED]

**footprint_gb()**
- out: `host_rss_gb` (ps RSS of processes matching markers `("process_supervisor", "sidecars.", "control.main", "workers.", "orchestrator", "polymath")`), `docker_vm_gb`, `gpu_caps_gb` (sum of `mps_gb` only for sidecars whose spec `port` is listening), `total_gb`, `budget_gb`, `within_budget`, `headroom_gb` — shared/polymath_shared/runtime_budget.py:208-236 [DERIVED]
- post: `within_budget = total <= float(b["total_gb"])` (no reserve subtracted) — shared/polymath_shared/runtime_budget.py:232,235 [DERIVED]

**export_env(slot)**
- out: `mps_env(slot)` + `POLYMATH_MAX_BATCH_TEXTS` + `POLYMATH_MAX_BATCH_TOKENS` — shared/polymath_shared/runtime_budget.py:241-245 [DERIVED]

## effect surface
- file read: `config/runtime_budget.yaml` — shared/polymath_shared/runtime_budget.py:28,37 [DERIVED]
- subprocess: `sysctl -n hw.memsize` :42; `sys.executable -c` torch MPS probe :74; `lsof -nP -iTCP:{port} -sTCP:LISTEN -t` :187; `ps -eo rss,command` :208 — shared/polymath_shared/runtime_budget.py:42,74,187,208 [DERIVED]
- env read: `POLYMATH_PROFILE` = `''` :134; `POLYMATH_FLEET_ONLY` = `''` :138 — shared/polymath_shared/runtime_budget.py:134,138 [DERIVED]
- env emitted (returned, not set): `PYTORCH_MPS_HIGH_WATERMARK_RATIO` :108, `PYTORCH_MPS_LOW_WATERMARK_RATIO` :109, `POLYMATH_MPS_CAP_GB` :110, `PYTORCH_ENABLE_MPS_FALLBACK` :104, `POLYMATH_MAX_BATCH_TEXTS` :243, `POLYMATH_MAX_BATCH_TOKENS` :244 — shared/polymath_shared/runtime_budget.py:104-110,243-244 [DERIVED]
- Postgres/Qdrant: none read or written (FACTS tables_read/tables_written empty)
- stdout (CLI only): `export k=v` lines or plan JSON + `FITS`/`OVER BUDGET` — shared/polymath_shared/runtime_budget.py:248-258 [DERIVED]

## invariants
INVARIANT: `PYTORCH_MPS_LOW_WATERMARK_RATIO` == `PYTORCH_MPS_HIGH_WATERMARK_RATIO` * 0.7 — shared/polymath_shared/runtime_budget.py:106-109 [DERIVED]
  fails-if: allocator hits the wall before returning blocks; mid-batch `MPS backend out of memory` per docstring shared/polymath_shared/runtime_budget.py:97-98
INVARIANT: 0.02 <= high watermark <= 0.95 — shared/polymath_shared/runtime_budget.py:106 [DERIVED]
  fails-if: cap rounds to an unusable pool or exceeds Metal recommended max working set
INVARIANT: `plan.ceiling_gb` == `total_gb` - `reserve_gb` AND `plan.fits` == (`committed_gb` <= `ceiling_gb`) — shared/polymath_shared/runtime_budget.py:164-168 [DERIVED]
  fails-if: preflight raises `BudgetExceeded` for a fleet that fits, or starts one that does not
INVARIANT: `footprint_gb` ceiling (`total_gb`, :232) >= `plan` ceiling (`total_gb - reserve_gb`, :165) — shared/polymath_shared/runtime_budget.py:165,232 [DERIVED]
  fails-if: footprint reports `within_budget` true while preflight accounting counts the reserve as spent
INVARIANT: `gpu_caps_gb` == sum of `mps_gb` over sidecars with a listening `port` only — shared/polymath_shared/runtime_budget.py:228-230 [DERIVED]
  fails-if: over-charging never-started sidecars halts runs inside their allocation (comment :223-227)
INVARIANT: default batch bounds == (8, 16384) when spec keys absent — shared/polymath_shared/runtime_budget.py:117-118 [DERIVED]
  fails-if: unbounded `model.encode()` replay — the 41.58 GiB incident shared/polymath_shared/runtime_budget.py:11-13
INVARIANT: `budget()` returns the same dict for the process lifetime (`lru_cache(maxsize=1)`) — shared/polymath_shared/runtime_budget.py:35-37 [DERIVED]
  fails-if: yaml edits silently ignored until process restart
INVARIANT: slot name with trailing digits resolves to the base slot's spec — shared/polymath_shared/runtime_budget.py:90 [DERIVED]
  fails-if: `extract2` runs under different bounds than `extract`, breaking the identical-bounds intent of :87-88

## determinism & idempotency
determinism: NONDETERMINISTIC (host state via subprocess: sysctl shared/polymath_shared/runtime_budget.py:42, torch probe :74, lsof :187, ps :208; env: `POLYMATH_PROFILE` :134, `POLYMATH_FLEET_ONLY` :138). `budget()` and `mps_denominator_gb()` are per-process cached (:35, :56), so repeat calls within one process are stable [DERIVED].
idempotency: SAFE (no writes anywhere in SOURCE; every function returns values; env vars are returned in dicts, only the CLI prints them — shared/polymath_shared/runtime_budget.py:239-245,248-258 [DERIVED]).

## failure behaviour
- `physical_gb()`: any `Exception` swallowed → `return 0.0`; callers treat 0 as "unknown" — shared/polymath_shared/runtime_budget.py:45-49 [DERIVED]
- `mps_denominator_gb()`: probe failure swallowed (`pass`) → falls to `(physical_gb() or 32.0) * 0.78` — shared/polymath_shared/runtime_budget.py:79-83 [DERIVED]
- `_listening()`: any `Exception` swallowed → `return False`; `footprint_gb` then under-counts `gpu_caps_gb` for that sidecar — shared/polymath_shared/runtime_budget.py:190-191,228-230 [INFERRED: False fails the `if spec.get("port") and _listening(...)` filter]
- `preflight()` raises `BudgetExceeded` (a `RuntimeError`) with per-slot GB detail — shared/polymath_shared/runtime_budget.py:31,174-181 [DERIVED]
- `profile_slots()` raises `KeyError(f"unknown profile {name!r}; have {sorted(profiles)}")` — shared/polymath_shared/runtime_budget.py:129 [DERIVED]
- `plan()` raises `KeyError` on yaml missing `docker.vm_gb`/`total_gb` (direct indexing, no handler) — shared/polymath_shared/runtime_budget.py:152,165 [INFERRED]

## dumb-code flags
- Magic `0.78` Apple-Silicon fraction and `32.0` assumed RAM — shared/polymath_shared/runtime_budget.py:83 [DERIVED]
- Magic clamps `0.02`/`0.95` and low-watermark factor `0.7` — shared/polymath_shared/runtime_budget.py:106,109 [DERIVED]
- Duplicated default literal: `control_gb` 0.15 == `per_worker_gb` 0.15, written twice — shared/polymath_shared/runtime_budget.py:161,163 [DERIVED]
- Hardcoded slot list `["orchestrator", "control", "intake", "profile", "extract", "canonicalize", "project_canonical", "neo4j", "qdrant", "verify"]` duplicates deployment topology; must stay in sync with yaml `sidecars` — shared/polymath_shared/runtime_budget.py:142-144 [DERIVED]
- Marker `"polymath"` matches any command line containing the substring (over-broad RSS match); `"sidecars."`/`"workers."` rely on dotted module paths — shared/polymath_shared/runtime_budget.py:210-211 [DERIVED]
- `0.0` doubles as the "unknown RAM" sentinel — shared/polymath_shared/runtime_budget.py:49 [DERIVED]
- Two different ceilings: `plan` subtracts `reserve_gb` (:165), `footprint_gb` compares raw `total_gb` (:232) — shared/polymath_shared/runtime_budget.py:165,232 [DERIVED]
- Probe timeouts 15/30/30/60 s as bare literals — shared/polymath_shared/runtime_budget.py:187,42,208,74 [DERIVED]

## refactor notes
- Renaming any public symbol hits both importers: control/control/fleet_autopilot.py and control/control/process_supervisor.py (FACTS.importers).
- Env var names (`PYTORCH_MPS_HIGH_WATERMARK_RATIO`, `PYTORCH_MPS_LOW_WATERMARK_RATIO`, `POLYMATH_MPS_CAP_GB`, `PYTORCH_ENABLE_MPS_FALLBACK`, `POLYMATH_MAX_BATCH_TEXTS`, `POLYMATH_MAX_BATCH_TOKENS`) are a cross-process contract with the torch sidecars and the shell-facing `env` CLI — shared/polymath_shared/runtime_budget.py:104-110,243-244,252-254 [DERIVED]
- The torch probe must stay in a subprocess: the supervisor sizes the fleet before any model loads and must never import torch — shared/polymath_shared/runtime_budget.py:68-69,71-74 [DERIVED]
- `budget()`/`mps_denominator_gb()` caching (:35, :56): any caller needing fresh config or a fresh probe cannot go through these functions unchanged.
- `footprint_gb` GPU accounting is coupled to sidecar specs exposing a `port` key; dropping `port` from yaml silently zeroes `gpu_caps_gb` — shared/polymath_shared/runtime_budget.py:228-230 [DERIVED]
- `BudgetExceeded` message text embeds remediation naming `POLYMATH_FLEET_ONLY` and `config/runtime_budget.yaml`; log/tooling may match on it — shared/polymath_shared/runtime_budget.py:179-181 [DERIVED]

## VERIFY
```verify
grep -Fq 'class BudgetExceeded(RuntimeError):' shared/polymath_shared/runtime_budget.py
grep -Fq 'return (physical_gb() or 32.0) * 0.78' shared/polymath_shared/runtime_budget.py
grep -Fq 'max(0.02, min(0.95, cap_gb / mps_denominator_gb()))' shared/polymath_shared/runtime_budget.py
grep -Fq 'PYTORCH_MPS_LOW_WATERMARK_RATIO' shared/polymath_shared/runtime_budget.py
grep -Fq 'raise BudgetExceeded(' shared/polymath_shared/runtime_budget.py
test "$(grep -c -F 'subprocess.run' shared/polymath_shared/runtime_budget.py)" -ge 4
```
