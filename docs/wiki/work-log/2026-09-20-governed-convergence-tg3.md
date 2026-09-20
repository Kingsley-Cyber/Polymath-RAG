---
change_id: GOVERNED-CONVERGENCE-V1-TG3
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "NO polymath-v4 code change. TG3 is a SKILL-repo slice (TRAIL_AGENT_AUTORESEARCH v2.2.0): the opportunity-research corpus lane now asks Polymath for EVIDENCE (POST /chat/evidence -> EvidencePacket) and holds no synthesis route. polymath-v4 receives the ledger only: this work-log, the acceptance receipt, a latency breakdown artifact, one contract-map comment (the EvidencePacket schema has an external sha-pinned consumer). Docs/eval only: no bundle change, no bounce. Trail untouched; the deployed Hermes copy untouched."
last_reviewed: 2026-09-20
---

## Contract
Owner word 2026-09-20: "Proceed with TG3 only. Migrate TRAIL_AGENT_AUTORESEARCH from /chat synthesis to
/chat/evidence, preserve the existing controller behavior and HTML output, validate EvidencePacket fail-closed, run the
555-check suite + doctor, then perform one real skill-level acceptance proving zero Polymath synthesis calls. Do not
start TG4 or modify Trail yet." Added acceptance shape: exactly one `/chat/evidence` exploration call, no `/chat`
call, rows preserve text / utility_role / CA4 grade / provenance / source ids, primitives + hypothesize keep working,
the HTML report still renders; instrument `polymath_chat_calls = 0`, `polymath_evidence_calls >= 1`. Carry forward:
start tracking where R1's extra ~134 s comes from; the seed's `PLAN_FALLBACK` is backlog, not a TG3 blocker.

- Authoritative tree: the skill's GIT repo `/Users/king/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH` (`main`,
  clean at `a7dbc52` v2.1.2 before the slice). Its own gate = `tests/run_all.py` + `controller.py doctor`; its own
  ledger = `WORKLOG.md`. The deployed copy `~/.hermes/standalone/opportunity-research` is byte-identical to v2.1.2
  and is NOT touched by TG3 (the mirror is a TG4 step).
- Verifier: the skill gates, then ONE live Claude-controlled run against the live fleet, proven from BOTH sides
  (the adapter's request ledger and Polymath's own `query_receipts`).
- Rollback: `--via plan` (rows only), or `git revert 438d92d` in the skill repo. Nothing in polymath-v4 to roll back.

## Changes
**Skill repo (`438d92d`, local tag `v2.2.0-tg3`, local `main` 1 ahead of origin, NOT pushed, NOT mirrored).**
- `python/corpus_polymath.py`: `ask_corpus` / `chat_question` / `answer_record` DELETED; NEW `explore_corpus()`
  (`{message, corpus_id, mode: WILDCARD, corpus_explorer: true}`), `packet_errors()` (fail closed), `rows_from_packet()`,
  `packet_record()`, `_merge_row()`; `--via evidence|plan`; node `corpus` = ONE call per corpus with the ORIGINAL
  signal, node `corpus_mechanisms` = one call per compiled question (capped, skip recorded); POST allow-list
  `{/chat/evidence, /retrieve, /retrieve/plan}` enforced before I/O; request ledger (`calls`, `timings_ms`,
  `polymath_chat_calls`, `polymath_evidence_calls`) + attributable User-Agent `opportunity-research/2.2.0 … run:<id> node:<node>`.
- NEW `schemas/evidence_packet.json` — skill-dialect rendering of `contracts/evidence/v1/evidence_packet.schema.json`,
  pinned to its sha256 (harness fails on drift when the repos sit side by side).
- `corpus_answers` → `corpus_packets` (`CORPUS_EVIDENCE_PACKET`; no answer / abstention) across graph, state defaults,
  memory, context, `lived_world`; `utilization` / `report` / `provenance` tolerate LEGACY state.
- docs/22 rewritten (+ the request ledger), docs/18 §10, docs/26 §8, SKILL.md, manifest 2.2.0, WORKLOG entry.
- Harness §17 rewritten around the boundary; §22g / §23f extended (no unscoped evidence or synthesis call).

**polymath-v4 (this commit, docs/eval only).** This work-log · `eval/governed_convergence/TG3-SKILL-ACCEPTANCE-2026-09-20.json`
· `eval/governed_convergence/R1-VS-R0-LATENCY-2026-09-20.json` · a comment on the `EVIDENCE_PACKET` contract row naming its
external sha-pinned consumer · register 11.356 · plan execution ledger · CONTINUITY to reality.

## Proof
| claim | level | evidence |
|---|---|---|
| skill gates | green | `tests/run_all.py` **580 checks** (baseline 555, both measured), `controller.py doctor` exit 0 |
| the synthesis lane is gone, not merely unused | UNIT_PROVEN + negative control | source scan (no synthesis-route literal; allow-list frozen); `_post` refuses `/chat` before I/O; on ONE stub backend the v2.1.2 adapter makes 5 × `POST /chat`, the v2.2.0 adapter 0 × and 1 × `POST /chat/evidence` |
| fail closed | UNIT_PROVEN | wrong schema version and `synthesis_performed: true` → `capability_failure{corpus_evidence_packet}`, no row lane consulted afterwards |
| live skill-level acceptance | LIVE_PATH_PROVEN | run `tg3_accept_02`, corpus `cinema`: `POST /chat/evidence` × 1, `polymath_chat_calls = 0`; Polymath's `query_receipts` for that run = one `chat / evidence_only`, 0 synthesis receipts; 15 packet rows with role / grade / provenance; primitives (16 rows cited, 8 packet rows) and hypothesize (4 CORPUS_ONLY bridges) each accepted on the FIRST submit; HTML report rendered by the existing renderer |
| latency tracking started | measured, read-only | R1 − R0 = +134 s, +133 s of it in the four knowledge steps (B_retrieve +20, B_graph +34, F_retrieve +44, F_graph +36); 6 boundary calls = 146 s of which 55.5 s is the query-compiler phase; the UNCHANGED plan lane (~100 s per run) is the largest single cost in both runs |

Guards `agent_preflight` / `repo_guard` / `wiki_worm --check` = 0 and `bundle_integrity` READY on MAIN; the fleet keeps
bundle `c0d86509ad39` (docs/eval/architecture-comment edits do not enter the bundle).

## Rejected claims
- REJECTED: "rows preserve the chunk TEXT." They preserve what the packet carries — and the packet carries
  **240-character previews** (13 of 15 live rows are exactly 240 chars; plan-lane chunks: median 736). Polymath-side
  cause: `hybrid.py:273`, `fast.py:683`, `chat_retrieval.py:598` build the chat evidence inventory with `text[:240]`
  and `ui.py` feeds that inventory to `build_evidence_packet`. NOT fixed (outside TG3; it is an orchestrator change + a
  bounce and needs the owner's word). It also means TG2's R1 packet rows were previews. Flagged for a separate slice;
  it should land before TG5.
- REJECTED: "the acceptance exercised the whole controller." It ran understand → corpus → primitives → gates →
  hypothesize → report. Field research, semantic review, challenge, mechanisms, ideation, sourcing and qualify were NOT
  run; the field lanes recorded an honest `capability_failure{field_research}` and every hypothesis is CORPUS_ONLY.
- REJECTED: "Corpus Explore enriched the signal." Requested, did not fire — `PLAN_FALLBACK` again (backlog B19), so no
  COMPLEMENTARY / DIVERGENT seat was seen live.
- REJECTED: "Hermes now runs the evidence lane." The deployed copy is still v2.1.2 and still calls the answer route
  until the TG4 mirror.
- DISCLOSED ACCIDENT: a negative-control script used the wrong env var (`OPPORTUNITY_STATE_DIR` instead of
  `OPPORTUNITY_RESEARCH_DB`) and registered a stub run `negctl` in the REAL skill loop memory
  (`~/.hermes/state/opportunity-research/opportunity.sqlite3`: 1 run row + 2 events). Ended through the controller's own
  `abandon` with that reason; nothing else in that database was touched. The acceptance itself used an isolated DB.
- Two acceptance runs exist: `tg3_accept_01` was abandoned at the corpus node when the 240-char finding surfaced (the
  adapter's merge was then improved) and `tg3_accept_02` is the acceptance of record — two live evidence calls in total.

## Open contract gaps
`contract_impact` for this commit: none (docs/eval + a YAML comment). Cross-repo contract closure:
- `EVIDENCE_PACKET` — **TESTED_UNCHANGED** here; it gained a SECOND consumer in another repo (sha-pinned). A schema
  change now needs a re-render + re-pin in the skill repo in the same slice (recorded on the contract row).
- `EVIDENCE_BOUNDARY_API` — **TESTED_UNCHANGED** (exercised live twice, both `evidence_only`). OPEN DEFECT on this
  contract: packet text is a 240-char preview (above). Its two pre-existing stale test pins also remain.
- `ADAPTER_RUNTIME`, `MCP_SURFACE` — **NOT_AFFECTED**.
Open, deliberately NOT done: TG4 (owner's word needed) · the Hermes mirror · the packet-text fix · any push.
