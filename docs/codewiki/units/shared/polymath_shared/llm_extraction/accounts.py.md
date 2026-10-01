# unit: shared/polymath_shared/llm_extraction/accounts.py
anchor: shared/polymath_shared/llm_extraction/accounts.py:1-408

## purpose
L1 + L3 of the LLM backend: `config/llm_accounts.yaml` is the single registry of accounts (one API key = one account), models/quotas, and lanes (account × model × stage use); this module compiles it into the two runtime files `config/cloud_providers.json` and `config/extraction_models/limiter.yaml`, writes them, and checks drift — shared/polymath_shared/llm_extraction/accounts.py:1-15 [DERIVED]. Also validates slot ownership (`slots.<stage>.owners`), lane pinning, and quota budgets, and emits one ownership row per (account, model) with credential set-ness only, never secret values — shared/polymath_shared/llm_extraction/accounts.py:9-14, 295-366, 376-408 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Lane | class | (name, account, model, fields, limiter) -> frozen dataclass; props `enabled`, `dedicated` | shared/polymath_shared/llm_extraction/accounts.py:43-56 | — |
| Account | class | (name, provider, key_env, account_id_env, quota, notes="", lanes=()) -> frozen dataclass | shared/polymath_shared/llm_extraction/accounts.py:60-67 | — |
| Registry | class | (version, docs, stage_pins, slots, local_limiters, accounts, lanes={}) -> frozen dataclass | shared/polymath_shared/llm_extraction/accounts.py:71-78 | — |
| Finding | class | (level, code, message) -> frozen dataclass; level is `"error"` or `"warning"` | shared/polymath_shared/llm_extraction/accounts.py:219-222 | — |
| load_registry | def | (path=REGISTRY_FILE) -> Registry | shared/polymath_shared/llm_extraction/accounts.py:81-99 | — |
| slot_index | def | (stage, slot_name) -> int \| None | shared/polymath_shared/llm_extraction/accounts.py:106-112 | — |
| stage_owner_groups | def | (reg, stage) -> list[list[str]] | shared/polymath_shared/llm_extraction/accounts.py:115-123 | — |
| owned_lanes | def | (reg) -> dict[stage, dict[lane, slot_name]] | shared/polymath_shared/llm_extraction/accounts.py:126-133 | — |
| compile_runtime | def | (reg) -> (providers_dict, limiter_dict) | shared/polymath_shared/llm_extraction/accounts.py:136-153 | — |
| render_runtime | def | (reg) -> (json_text, limiter_text) | shared/polymath_shared/llm_extraction/accounts.py:156-164 | — |
| write_runtime | def | (reg, providers_path=PROVIDERS_FILE, limiter_path=LIMITER_FILE) -> list[str] | shared/polymath_shared/llm_extraction/accounts.py:167-175 | `scripts/llm_accounts.py write` (named in LIMITER_HEADER literal) — shared/polymath_shared/llm_extraction/accounts.py:35-38 |
| runtime_not_generated | def | (reg, providers_path, limiter_path) -> list[str] | shared/polymath_shared/llm_extraction/accounts.py:178-185 | — |
| runtime_drift | def | (reg, providers_path, limiter_path) -> list[str] | shared/polymath_shared/llm_extraction/accounts.py:188-215 | — |
| lane_uses | def | (reg) -> dict[lane, list[stage]] | shared/polymath_shared/llm_extraction/accounts.py:233-239 | — |
| lane_slots | def | (reg) -> dict[lane, int] | shared/polymath_shared/llm_extraction/accounts.py:242-249 | — |
| validate | def | (reg, env=None) -> list[Finding] | shared/polymath_shared/llm_extraction/accounts.py:295-366 | — |
| ownership_rows | def | (reg, env=None) -> list[dict] | shared/polymath_shared/llm_extraction/accounts.py:376-408 | — |

## contracts

**load_registry** — shared/polymath_shared/llm_extraction/accounts.py:81-99
- in: YAML with `accounts.<name>` carrying `provider`, `key_env`, optional `account_id_env`, `quota`, `notes`, `lanes` — shared/polymath_shared/llm_extraction/accounts.py:85-97.
- pre: `provider` and `key_env` accessed as `str(a["provider"])` / `str(a["key_env"])`; missing key raises KeyError — shared/polymath_shared/llm_extraction/accounts.py:96 [INFERRED: direct dict indexing].
- post: lane's `limiter` key popped out of lane fields into `Lane.limiter` — shared/polymath_shared/llm_extraction/accounts.py:91.
- post: lane name under two accounts raises `ValueError(f"lane {lname!r} is declared under two accounts")` — shared/polymath_shared/llm_extraction/accounts.py:88-89.
- post: `version` defaults to 1 (`int(raw.get("version", 1))`) — shared/polymath_shared/llm_extraction/accounts.py:98.

**slot_index** — shared/polymath_shared/llm_extraction/accounts.py:106-112
- `slot_name == stage` -> 1; `<stage>` + digit suffix ≥ 2 -> that digit; anything else (including `<stage>1`) -> None — shared/polymath_shared/llm_extraction/accounts.py:109-112.

**stage_owner_groups** — shared/polymath_shared/llm_extraction/accounts.py:115-123
- out: list of length `count` (default 1); index k-1 = slot k's lanes; `[]` for a stage with no `owners` — shared/polymath_shared/llm_extraction/accounts.py:116-123.

**compile_runtime** — shared/polymath_shared/llm_extraction/accounts.py:136-153
- provider entry = `{"name": lane.name, **lane.fields, "api_key_env": acct.key_env}`, plus `account_id_env` only when set — shared/polymath_shared/llm_extraction/accounts.py:142-144.
- limiter: lane limiters, then `limiter.update({k: dict(v) for k, v in reg.local_limiters.items()})` — a local limiter with a lane's name overwrites the lane's — shared/polymath_shared/llm_extraction/accounts.py:146-148.
- providers dict keys: `_doc`, `stage_pins`, `stage_owners`, `providers`; `stage_owners` only for stages with owners; limiter wrapper `{"providers": limiter}` — shared/polymath_shared/llm_extraction/accounts.py:149-153.

**render_runtime** — shared/polymath_shared/llm_extraction/accounts.py:156-164
- json text = `json.dumps(providers, indent=2) + "\n"` — shared/polymath_shared/llm_extraction/accounts.py:163.
- limiter text = `LIMITER_HEADER + yaml.safe_dump({"providers": ordered}, **_DUMP)` with `_DUMP = {"sort_keys": False, "allow_unicode": True, "width": 120}`; local seeds ordered first — shared/polymath_shared/llm_extraction/accounts.py:39, 161-164.

**write_runtime** — shared/polymath_shared/llm_extraction/accounts.py:167-175
- post: writes a file only when missing or bytes differ; returns changed path strings — shared/polymath_shared/llm_extraction/accounts.py:170-174.

**runtime_not_generated** — shared/polymath_shared/llm_extraction/accounts.py:178-185
- out: `[]` iff both files byte-equal `render_runtime(reg)`; a missing file counts as not-generated — shared/polymath_shared/llm_extraction/accounts.py:182-184.

**runtime_drift** — shared/polymath_shared/llm_extraction/accounts.py:188-215
- out: difference strings, empty = no drift; provider order ignored, per-name diffs list the differing field keys; limiter compared per name — shared/polymath_shared/llm_extraction/accounts.py:190, 201-214.
- pre: both runtime files must exist and parse — `json.loads(Path(providers_path).read_text())` with no existence guard — shared/polymath_shared/llm_extraction/accounts.py:192-193 [INFERRED].

**lane_uses** — shared/polymath_shared/llm_extraction/accounts.py:233-239: pin stages per lane, plus `"extract"` appended for every enabled non-dedicated lane — shared/polymath_shared/llm_extraction/accounts.py:235-238.

**lane_slots** — shared/polymath_shared/llm_extraction/accounts.py:242-249: per lane, 1 for each stage that owns it, else the stage's `count` (default 1) — shared/polymath_shared/llm_extraction/accounts.py:248.

**validate** — shared/polymath_shared/llm_extraction/accounts.py:295-366
- env defaults to `os.environ` — shared/polymath_shared/llm_extraction/accounts.py:296.
- errors: `PIN_UNKNOWN_LANE` (301), `OWNER_WITHOUT_OFFSET` (261), `OWNER_BAD_SLOT` (269), `OWNER_UNKNOWN_LANE` (277), `OWNER_NOT_PINNED` (279), `OWNED_TWICE` (282).
- warnings: `OWNER_SPANS_ACCOUNTS` (286), `SLOT_WITHOUT_OWN_LANE` (290), `FAMILY_SPANS_ACCOUNTS` (311), `PAIR_SHARED_BY_SLOTS` (328), `IDLE_PAIR` (335), `BUDGET_EXCEEDS_QUOTA` for metrics `("rpd", "tpd", "tpm", "otpm")` (340, 350), `KEY_UNSET` (359), `ACCOUNT_ID_UNSET` (361), `LANE_UNUSED` (365).
- W4 skips accounts with no enabled lane (parked/retired, e.g. Cloudflare account 1) — shared/polymath_shared/llm_extraction/accounts.py:352-357.

**ownership_rows** — shared/polymath_shared/llm_extraction/accounts.py:376-408
- one row per (account, model) over the union of `quota` keys and lane models — shared/polymath_shared/llm_extraction/accounts.py:384-386.
- row keys: `account, provider, model, lanes, stages, slots, owners, quota, key_set, account_id_set, state` — shared/polymath_shared/llm_extraction/accounts.py:397-407.
- `state` = `"parked"` when active lanes exist but key/account-id unset (mirrors runtime `pool._configured_providers`), else `"active"`, else `"idle"` — shared/polymath_shared/llm_extraction/accounts.py:394-396.
- secret values never read; only `bool((env.get(...) or "").strip())` — shared/polymath_shared/llm_extraction/accounts.py:392-393.

## effect surface
- Files read: `config/llm_accounts.yaml` — shared/polymath_shared/llm_extraction/accounts.py:27, 82; `config/cloud_providers.json` — shared/polymath_shared/llm_extraction/accounts.py:28, 172, 183, 192; `config/extraction_models/limiter.yaml` — shared/polymath_shared/llm_extraction/accounts.py:29, 172, 183, 193. All resolved from `REPO_ROOT = Path(__file__).resolve().parents[3]` — shared/polymath_shared/llm_extraction/accounts.py:26.
- Files written: both runtime paths via `path.write_text(text)` — shared/polymath_shared/llm_extraction/accounts.py:173.
- Env read: `validate(env=None)` and `ownership_rows(env=None)` default to `os.environ`; variable names come from registry data (`acct.key_env`, `acct.account_id_env`), none hardcoded — shared/polymath_shared/llm_extraction/accounts.py:296, 358-361, 379, 392-393.
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty) — shared/polymath_shared/llm_extraction/accounts.py:241-242 [DERIVED]. Qdrant, network, subprocess: none in SOURCE [DERIVED].

## invariants
- INVARIANT: occurrences of a lane name across accounts ≤ 1 — shared/polymath_shared/llm_extraction/accounts.py:88-89 [DERIVED]
  fails-if: `load_registry` raises ValueError; registry will not load at all.
- INVARIANT: `len(stage_owner_groups(reg, stage))` == `slots.<stage>.count` (default 1) — shared/polymath_shared/llm_extraction/accounts.py:123 [DERIVED]
  fails-if: `stage_owners` index k-1 no longer maps to slot k in `cloud_providers.json`; workers grab the wrong lanes.
- INVARIANT: rendered limiter bytes == `LIMITER_HEADER + yaml.safe_dump(..., sort_keys=False, allow_unicode=True, width=120)` — shared/polymath_shared/llm_extraction/accounts.py:35-39, 164 [DERIVED]
  fails-if: `runtime_not_generated` flags the checked-in file; writer must rerun.
- INVARIANT: `runtime_not_generated(reg) == []` ⟺ second `write_runtime(reg)` run changes nothing — shared/polymath_shared/llm_extraction/accounts.py:171-184 [DERIVED]
  fails-if: a hand-edited runtime file silently diverges from the registry.
- INVARIANT: owning slots per owned lane == 1 (OWNED_TWICE guards) — shared/polymath_shared/llm_extraction/accounts.py:281-283 [DERIVED]
  fails-if: two worker processes share one (account, model) budget; W2 slot math undercounts.
- INVARIANT: Σ `lane.limiter[metric]` × `lane_slots(lane)` ≤ `quota[metric]` for `"rpd", "tpd", "tpm", "otpm"` — shared/polymath_shared/llm_extraction/accounts.py:340-351 [DERIVED]
  fails-if: `BUDGET_EXCEEDS_QUOTA` warning only — run can still blow the provider quota.
- INVARIANT: valid slot names == `stage` or `stage` + digit ≥ 2 — shared/polymath_shared/llm_extraction/accounts.py:109-112 [DERIVED]
  fails-if: `doc_profile1` yields slot_index None → `OWNER_BAD_SLOT` error.
- INVARIANT: `ownership_rows` state ∈ {"parked", "active", "idle"} — shared/polymath_shared/llm_extraction/accounts.py:395-396 [DERIVED]
  fails-if: consumers keying on state strings break.

## determinism & idempotency
determinism: DETERMINISTIC for `load_registry` / `compile_runtime` / `render_runtime` / `runtime_drift` / `lane_uses` / `lane_slots` (pure functions of registry bytes + runtime files) — shared/polymath_shared/llm_extraction/accounts.py:82, 136-164, 188-215 [DERIVED]; NONDETERMINISTIC for `validate` / `ownership_rows` (env: `os.environ` at shared/polymath_shared/llm_extraction/accounts.py:296, 379) [DERIVED].
idempotency: SAFE — `write_runtime` writes only on byte diff (shared/polymath_shared/llm_extraction/accounts.py:171-174); all other functions are read-only.

## failure behaviour
- No try/except anywhere in this file; nothing is swallowed — shared/polymath_shared/llm_extraction/accounts.py:1-408 [DERIVED].
- `load_registry`: ValueError on duplicate lane name — shared/polymath_shared/llm_extraction/accounts.py:89; KeyError on account missing `provider`/`key_env` — shared/polymath_shared/llm_extraction/accounts.py:96 [INFERRED].
- `runtime_drift`: missing/unparsable runtime file raises (unguarded `read_text()` / `json.loads`) — shared/polymath_shared/llm_extraction/accounts.py:192-193 [INFERRED]; `runtime_not_generated` instead reports a missing file as a finding string — shared/polymath_shared/llm_extraction/accounts.py:183-184.
- Missing credentials never raise: `KEY_UNSET` / `ACCOUNT_ID_UNSET` warnings only — shared/polymath_shared/llm_extraction/accounts.py:358-361.

## dumb-code flags
- `ACCOUNT_FIELDS = ("api_key_env", "account_id_env")` documented as "re-attached to every lane when compiling" but never referenced after its definition; `compile_runtime` re-attaches the two keys by literal name instead — shared/polymath_shared/llm_extraction/accounts.py:32, 142-144 [DERIVED].
- Default slot `count` of 1 duplicated 4×: `spec.get("count", 1)` / `get("count", 1)` — shared/polymath_shared/llm_extraction/accounts.py:123, 248, 259, 325 [DERIVED].
- Register numbers disagree across comments: docstring "registers 11.465, 11.467" (line 1), LIMITER_HEADER "register 11.467" (line 36), W4 comment "register 11.469" (line 354) — shared/polymath_shared/llm_extraction/accounts.py:1, 36, 354 [DERIVED].
- `slot_index` silently rejects `<stage>1` (`int(suffix) >= 2`), undocumented beyond the docstring examples — shared/polymath_shared/llm_extraction/accounts.py:107-112 [DERIVED].
- `Finding.level` contract `"error" | "warning"` is a comment only, unenforced — shared/polymath_shared/llm_extraction/accounts.py:220 [DERIVED].

## refactor notes
- Byte format is API: any change to `LIMITER_HEADER` (35-38), `indent=2` (163), `_DUMP` (39), or ordering (local seeds first, 161-162) makes every checked-in runtime file fail `runtime_not_generated` until `scripts/llm_accounts.py write` reruns (command named in the header literal, 36) — shared/polymath_shared/llm_extraction/accounts.py:35-39, 161-164, 178-185.
- Runtime JSON top-level keys `_doc`, `stage_pins`, `stage_owners`, `providers` and limiter key `providers` are read by the extraction runtime and compared field-by-field in `runtime_drift`; renaming breaks both — shared/polymath_shared/llm_extraction/accounts.py:4-5, 151-153, 195-214.
- Finding codes and `ownership_rows` `state` strings are the machine-readable outputs of `validate`/`ownership_rows` — shared/polymath_shared/llm_extraction/accounts.py:261-365, 395-396.
- Registry schema keys `stage_pins`, `slots.<stage>.owners/count/lane_offset_env`, `local_limiters` are read in load/compile/validate; a rename ripples across shared/polymath_shared/llm_extraction/accounts.py:98, 118-123, 148, 259-261, 325.
- `lane_offset_env` absence makes owners unusable at runtime (`OWNER_WITHOUT_OFFSET`) — shared/polymath_shared/llm_extraction/accounts.py:260-262.

## VERIFY
```verify
grep -Fq 'ACCOUNT_FIELDS = ("api_key_env", "account_id_env")' shared/polymath_shared/llm_extraction/accounts.py
grep -Fq 'raise ValueError(f"lane {lname!r} is declared under two accounts")' shared/polymath_shared/llm_extraction/accounts.py
grep -Fq 'return int(suffix) if suffix.isdigit() and int(suffix) >= 2 else None' shared/polymath_shared/llm_extraction/accounts.py
grep -Fq 'uses.setdefault(n, []).append("extract")' shared/polymath_shared/llm_extraction/accounts.py
grep -Fq '_DUMP = {"sort_keys": False, "allow_unicode": True, "width": 120}' shared/polymath_shared/llm_extraction/accounts.py
test "$(grep -c -F 'Finding(' shared/polymath_shared/llm_extraction/accounts.py)" -ge 14
```
