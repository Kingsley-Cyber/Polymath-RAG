---
owner: governance
last_reviewed: 2026-09-25
last_touched: 2026-09-25
status: accepted
---
# ADR-0021 — TrailSignal's deterministic research core runs in process (`governance/trail/`)

- **Status:** accepted 2026-09-20 under the owner's consolidation migration (`docs/migration/MIGRATION_POLICY.md` "Trail embedding: authorized in principle, subject to dependency / license /
  source verification"; verification and design in `docs/migration/ADR-TRAIL-EMBEDDING.md`; decision record `AUTO_DECISIONS.md` M-012). Default mode stays `daemon`.

## Decision
1. `governance/trail/` holds the EXACT import closure of TrailSignal's `ResearchOperationService` (16 modules, 6,944 lines) plus the registry data and config it reads and its MIT licence —
   BYTE-IDENTICAL to TrailSignal A41 @ `de64d84`, every file sha256-pinned in `PROVENANCE.json`, pinned by `tests/contracts/test_trail_core_embedding.py`. No TrailSignal line is edited.
2. One Polymath-authored file, `governance/trail/embedded.py`, does what TrailSignal's daemon composition root and MCP tool layer do: builds the service over the compiled registry snapshot,
   implements TrailSignal's store port (`commit`, `load`, `load_admitted`) on SQLite (first commit wins; durable when `POLYMATH_TRAIL_STORE` names a file), and exposes an `httpx` transport that
   answers the daemon's JSON-RPC `tools/call`.
3. `POLYMATH_TRAIL_MODE=embedded` makes the worker build the SAME `TrailMCPClient` over that transport (loaded by file path); `exec_external`, `trail_client`, the request / result envelopes and the
   refusal path are unchanged. Unset / `daemon` = today's behaviour.
4. Layer rule: dependency-map owner `trail_governance` (`governance/`) may import nothing of the runtime. TrailSignal never reads or writes Polymath state.

## What does not change
TrailSignal's logical ownership (registry, admission, freshness, independence, judgement, territory, qualification, the only score / refusal), LAW 1, LAW 2, ADR-063's split. This is a deployment
boundary change only (MIGRATION_POLICY INV-5).

## Consequences
- One checkout runs the governed loop without TrailSignal's daemon, Postgres or Temporal.
- One new third-party dependency, `packageurl` (pure Python), pulled by TrailSignal's platform contracts; it must be added to `pyproject.toml` and installed in the merge window. Until then the
  embedded-core tests run under TrailSignal's interpreter and SKIP — with the reason printed — under this repo's.
- ~57 % of the imported lines are contract models unrelated to research (`data_os`, `discovery`, `platform`); trimming them is a separate change that re-pins `PROVENANCE.json`.
- D1 and M1-01..03 live in this code. They are NOT fixed here; fixing them is a documented TrailSignal behaviour change, separate from the embedding.

## Addendum 2026-09-21 — re-pinned to HR6 @ `829a0ab` (TrailSignal ADR-069)

The embedded core is re-pinned through the SAME deterministic process (`git archive 829a0ab <the 30 pinned paths> | tar -x`; `PROVENANCE.json`
rewritten with the new sha256 of every file and `previous_pin` naming the files the pin changed). TrailSignal ADR-069 (Accepted by the owner
2026-09-21) restores the semantics of the bounded research operations: stated `knowledge_support_count`, field-aware structured mapping
with the lexical path kept as the fallback, prior / territory meaning on the wire (`label`, `section`, `match_strength`, `mapping_path`,
`territory_name`), typed refusal of a gap that names no hypothesis, and a hypothesis-relative evidence relation
(`hypothesis_relations`). Every new wire field is optional: the recorded envelopes were re-recorded at the new pin with the SAME requests
and the same clock (`tests/fixtures/trail_recorded_envelopes/*.json` carry `previous_trail_head` + `re_recorded`). Polymath's side: the closed
extended wire (`semantic_view.trail_wire`, sent only by steps that opt in with `hypotheses_from: context.semantics.trail`), the four-copy
receipt contract (`hypothesis_relations` on a receipt observation, kept only for a hypothesis the observation links). Source commit (full): `829a0abf853fdb0c3589c4162177beb8c836c515`.

## Addendum 2026-09-25 — re-pinned to HR7 @ `494905a` (TrailSignal ADR-070)

The embedded core is re-pinned through the SAME deterministic process (`git archive 494905a <the 30 pinned paths> | tar -x`;
`PROVENANCE.json` rewritten with the new sha256 of every file and `previous_pin` naming the files the pin changed; the tool is
`docs/wiki/experiments/autoresearch-r1-repin-2026-09-25/repin_trail_hr7.py`). TrailSignal ADR-070 (Accepted by the owner 2026-09-25)
adds two DATA rows to `data/source_capabilities.csv`, no code:
- `src-tiktok-comments`: class `video_platform`, pattern `tiktok.com/@` (video and comment permalinks; it sorts before
  `src-tiktok-creative`, which keeps Creative Center and short links), stages `field_evidence;product_reality`, roles
  `behavior;workaround;friction;competition;contradiction` (no `demand`), freshness `stable-behavior-365d`, independence group `tiktok`;
- `src-instagram-comments`: the same shape, patterns `instagram.com/reel;instagram.com/p/`, group `instagram`.

The registry snapshot therefore changes (`trs-da9942986e52f832` → `trs-629277494b724295`), and the three M1 recorded envelopes carry the snapshot id in
their REQUESTS. The owner authorized re-recording them (2026-09-25): only the snapshot id / content hash in the requests and what the new
rows route may change. `rerecord_envelopes_hr7.py` swaps exactly those, re-records at the same fixed clock and ASSERTS the recorded defects
unchanged (M1-02 still raises the same error with the same message; `hypotheses.judge`, findings M1-01 / M1-03, identical once the
snapshot is normalised). A response's `result_sha256` is the hash of its own result, which carries the snapshot id, so it
moves with it: the re-recorder asserts it equals that hash on both recordings and compares the result bodies exactly. Each fixture
keeps the earlier re-record in `re_recorded_history`. Source commit (full): `494905a1bfdfb2c8c7924a7baef103a91a5b3f1d`.
