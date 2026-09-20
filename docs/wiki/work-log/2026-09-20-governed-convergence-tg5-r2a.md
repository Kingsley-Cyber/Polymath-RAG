---
change_id: GOVERNED-CONVERGENCE-V1-TG5-R2A
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — NO code change. R2a = the ONE real governed run (cinema MECHANICAL smoke): a real agent (Claude Code session) drove trail.product_discovery through MCP Server B with the skill as the harness and Trail as-is. polymath-v4 receives the record only: this work-log, the TG6 artifact, ledger rows. Trail untouched. Nothing pushed."
last_reviewed: 2026-09-20
---

## Contract
Owner word 2026-09-20: "Proceed with a single cinema R2 mechanical smoke to live-prove TG4. Do not interpret its product
output as meaningful. Then execute Item 2 corpus-scoping before creating any second corpus. … ANY REFERENCE OF ECOM SHOULD
BE IGNORED." Mid-run guidance (same day): fewer, evidence-bound hypotheses; the persisted step ledger — not the client
poll — proves which steps ran; the receipt must come from `adapter_receipt.py`, never by hand; the directive chooses the
sources; 12 queries per action is a MAXIMUM; classify the outcome as `CHAIN_PASS` / `CHAIN_PASS_WITH_TYPED_REFUSAL` /
`PARTIAL` / `FAIL`; do not judge product quality, the corpus, Trail's scoring, GRAPH latency or source coverage.

- §11 mini-plan: hypothesis = the TG4 chain runs live end to end · N = 1 · seed + corpus identical to R0 / R1 (the only
  changed variable is a real agent + a real harness) · stop on a > 3 min stall, 3 rejections on one step, or any
  credential prompt · prediction: completes; Trail rejects most Reddit as stale; a score may be refused.
- Verifier: the persisted `adapter_steps` ledger, `adapter_harness_actions` / `adapter_admitted_evidence`,
  `query_receipts`, `scripts/adapter_evidence_boundary_proof.py`, the skill's run journal, the rendered dossier.
- Rollback: nothing to roll back (no code, no config). The run's rows stay as the record.

## Changes
- NEW `eval/governed_convergence/GC1-FIRST-REAL-RUN-2026-09-20.json` — the TG6 record, written with hard assertions.
- Ledger: this work-log, register 11.360, plan execution ledger + TG5 note, CONTINUITY CURRENT, scaffold `TREE`.
- Run files (skill repo, gitignored `candidates/r2a_cinema_smoke/`): journal, 3 actions, 3 receipts + builder reports,
  every `adapter_next` payload, every submission + response, the harvest ledger with fetch-time stamps, the dossier, and
  four small transport / display helpers (`mcpb.py` one MCP call over stdio, `poll_next.py`, `harvest.py`,
  `show_step.py`). The helpers reason about nothing; they are NOT a second harness and are not tracked.

## Proof
Run `adr_d96032aef165a999774bd4bbabb37b1d` · 18:11:21Z → 18:34:29Z · bundle `9cb421b4eeed` · Trail A41 `de64d84`.

| Check | Result |
|---|---|
| `adapter_start` over Server B (stdio, official `mcp` client) | LIVE — first time |
| AGENT_REASON answered from the readable evidence (60 rows, roles, CA4 grades, RB5 truncation fields) | 7 accepted, 0 rejected (4 hypotheses, DIRECT evidence only, contradictions kept) |
| HARNESS_ACTION → skill acquisition tools → `adapter_receipt.py` → `HarnessResearchReceiptV1` → `adapter_submit` | 3 / 3 receipts built, validated and ACCEPTED — **TG4 segment LIVE_PATH_PROVEN** |
| Queries | 8 + 4 + 3 = 15 (cap 12 per action); tools: `opencli reddit`, `opencli youtube`, Exa via `mcporter`; 3 failed tool calls, none counted |
| Trail admission | 3 runs: 6 / 5, 2 / 0, 0 / 2 → **8 admitted, 7 rejected, all `STALE_BEYOND_POLICY`**; 1 press item omitted by the builder (no source class), reason recorded |
| Trail judge | ran twice: `WEAKEN SINGLE_INDEPENDENCE_GROUP` (everything admitted is Reddit); third verdict refused by the ADAPTER |
| Qualification / score / compiled result | NOT REACHED — terminal gap `PHI_VERDICT_INVALID` at `L_judge` seq 30 |
| Persisted ledger | 30 steps; `B_graph` executed at seq 4 although the client poll never saw it |
| Synthesis | 8 × `chat/evidence_only` + 2 × `retrieve`; **0 synthesis receipts** in the run window; boundary proof exit 0 |
| Dossier | rendered by the existing renderer: `GOVERNED GAP — PHI_VERDICT_INVALID`, 0 `evidence_score` mentions, but 0 field observations shown |

**Classification (owner rubric): FAIL** — a runtime / lineage defect, met AFTER the harness path had run live three times.

Root cause, confirmed by a live probe (hypothesis promoted): `shared/polymath_shared/adapter/store.py::admission_ids`
selects `DISTINCT admission_id FROM adapter_admitted_evidence`. An admission that admits ZERO observations writes no such
row, so its id is missing from `service._allowed_causes`; Trail's judge lawfully cites the latest admission
(`hadm_5b24774f31c8`, admitted 0 / rejected 2) and `hypotheses.apply` refuses it. Fixtures always admit something, which
is why R0 / R1 never met it.

## Rejected claims
- "R2a passed." No. The chain did not complete: no qualification, no score or refusal, an empty result output.
- "Trail broke the run." No. Trail admitted, rejected and judged lawfully, with reasons. The refusal is Polymath's.
- "The harness or the receipt was the problem." No. 3 / 3 receipts accepted; the builder's one omission was correct.
- "Evidence was insufficient, so this is a typed refusal." No. `PHI_VERDICT_INVALID` is a validation defect, not a verdict
  about evidence.
- "The run says something about product ideas." No (owner rule): cinema corpus, mechanical smoke.
- "The sources were chosen freely." Partly: the directive preferred community / video / first-party / statistics; video
  was unavailable on the first pass and thin on the third, forums returned only years-old posts, so everything admitted
  is Reddit. That is a measured limitation of what worked today, not a design choice.

## Open contract gaps
Dispositions: no contract changed. `ADAPTER_RUNTIME` — **BLOCKED** for real runs by D1 until fixed; `EVIDENCE_BOUNDARY_API`
— DEFERRED defect D2; everything else NOT_AFFECTED.

- **D1 (blocking):** the all-rejected-admission cause (above). One query change + a pin; `shared/` → one bounce; needs the
  owner's word. Until then ANY real run dies at the first research pass that admits nothing.
- **D2 (high):** `/chat/evidence` classified my declarative hypothesis statements as `GENERAL_CONVERSATION` →
  `retrieval_required: false` → `F_retrieve` returned 0 rows on 3 / 3 needs. An evidence-only request must never skip
  retrieval.
- **D3:** the readable view showed 0 new knowledge rows at `G_mechanisms` / `K_revise` (60-row cap filled by the first
  phase; 43 readable chunk refs never shown).
- **D4:** all 4 hypotheses `WEAKEN NO_KNOWLEDGE_SUPPORT` straight after generation despite 4–5 DIRECT citations each
  (the plan's `knowledge_support_count = 0` item — a TG7 wire-contract change, Trail side, NOT started).
- **D5:** on a terminal gap the result output is empty, so the journal summary and the dossier show admitted 0 /
  rejected 0; rejected observations and their reason codes never reach the agent.
- **D6 / D7:** generic physical-product search-intent templates and an empty first `evidence_gaps`; `max_calls = 3`
  drops the 4th hypothesis need.
- Any re-run needs the owner's word (live-run budget rule). TG7 stays untouched until the owner scopes it from this record.
