---
change_id: GOVERNED-CONVERGENCE-V1-ADMISSION
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "DOCS ONLY. Admits an owner-approved multi-repo plan of record and the read-only discovery dossier it rests on. No code, no config, no fleet impact, no Trail change. Re-points CONTINUITY's Active Mission / Next Action at TG0."
last_reviewed: 2026-09-20
---

## Contract
Owner request 2026-09-20: (1) discover what Trail Signal OS actually does today before proposing any
architecture; (2) plan the convergence of the two product-research paths the discovery found; (3) hand the
approved plan to a FRESH session, because this session's context is exhausted. A fresh session bootstraps
from REPOSITORY truth, and the approved plan existed only in `~/.claude/plans/` — so it is admitted here.
Owner decisions locked: keep ADR-063 (zero Trail changes before the first real governed run) · Trail
correctness fixes AFTER the first real E2E, evidenced by it, ADR accepted by the owner · the skill's git repo
is authoritative, the Hermes copy is deployment · Claude Code + Codex reach the adapter through seven thin
proxies on MCP Server B · Claude Code is the first real harness, Hermes repeats second · no field evidence is
ingested into Polymath in v1 · corpus isolation (finish-line Item 2) gates only a SECOND corpus.

## Changes
- NEW `docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md` — the plan of record: TG0 baseline → TG1 Server B adapter
  proxies + parity → TG2 readable evidence in `adapter_next` + opt-in evidence-boundary surface → TG3 skill
  evidence-only corpus lane → TG4 receipt builder + governed run journal + report bridge + mirror → TG5 first
  real governed run (Claude Code) → TG6 record what it cost → TG7 Trail correctness slice (owner word + owner
  ADR only) → TG8 Hermes repeat. Carries a "where things live" header (repos, authoritative trees, runtime).
- NEW `docs/wiki/reports/2026-09-20/TRAIL-GROUND-TRUTH-DOSSIER.md` — deliverables A–H + runtime map + the
  three-part answer, with every contradiction between recon passes shown and resolved by direct check.
- `CONTINUITY-REPORT.md` — new CURRENT section (Active Mission = GOVERNED-CONVERGENCE-V1, Next Action = TG0);
  the CORPUS-EXPLORE-FIRING-V1 section becomes PRIOR. Item 2 is recorded as DEFERRED-BY-OWNER-SEQUENCING,
  still the prerequisite for any second corpus.
- `PLAN-AUTHORITY-REGISTER.md` row 11.351; scaffold `TREE` entries for the three new files.

## Proof
- Docs only: `agent_preflight` / `repo_guard` / `wiki_worm --check` = 0 each (captured on their own lines);
  `bundle_integrity` READY (no production-dir file touched).
- The dossier's claims are READ-ONLY observations with `path:line` evidence; the authoritative Trail tree was
  verified (`A41` HEAD == `origin/main` == `de64d84`, clean) before any Trail file was read.
- Nothing was booted or changed during discovery or planning: the fleet has been DOWN since the 06:20 reboot
  (Docker stores up; orchestrator :7200, MCP :8930, adapter worker, sidecars and the Trail daemon :8767 down).

## Rejected claims
- REJECTED: "HARNESS-RESEARCH-MIGRATION-V1 proved the governed path live." It proved the RUNTIME. Every
  recorded run used fixture receipts (`*.example` URLs, `harness_id mcp-acceptance-harness`) and hard-coded
  Python answers (`model: scripted-acceptance`). No LLM has answered an AGENT_REASON step and no harness has
  executed a HARNESS_ACTION with real tools.
- REJECTED (the first draft of this plan): "Trail becomes a client of `polymath_search/explore/answer`." Trail
  has no reasoning agent, and ADR-063 + `policy_v2.yaml:3154` forbid it retrieval, hypothesis generation,
  harness hosting and scraping; LAW 1 forbids the score reading any Polymath field.
- REJECTED: building a new research system or a new HTML dossier. Both already exist in the
  opportunity-research controller (`report.render`, a real rendered example on disk).
- REJECTED: tuning Trail's registry (Reddit = one independence group, 14-day freshness) before the first real
  run, or omitting known publish dates to read as fresh. The first run measures the rejections honestly.

## Open contract gaps
No contract changed in this slice (docs only) → `contract_impact`: none. Contracts the PLAN will touch, each
to receive a disposition in its own slice: the adapter wire schema (`contracts/adapter/v1/adapter_step`, four
optional ref properties — additive), the EvidencePacket (first external consumer; gains a JSON Schema under
`contracts/evidence/v1/`), both MCP surfaces, and four NEW rows in `architecture/contract-dependencies.yaml`
(`EVIDENCE_PACKET`, `EVIDENCE_BOUNDARY_API`, `ADAPTER_RUNTIME`, `MCP_SURFACE`) — today `contract_impact.py` is
blind to all of them. DEFERRED by owner sequencing: finish-line Item 2 (coverage + corpus isolation), B19
compiler provider reliability, B20 toggle-vs-routing. Not started: TG0.
