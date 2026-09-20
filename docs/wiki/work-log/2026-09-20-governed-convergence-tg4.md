---
change_id: GOVERNED-CONVERGENCE-V1-TG4
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "TG4 is a SKILL-repo slice (TRAIL_AGENT_AUTORESEARCH v2.3.0): the existing opportunity-research skill becomes the harness executor for the governed adapter (HarnessActionV1 -> the skill's own controller / acquisition tools -> HarnessResearchReceiptV1 -> adapter_submit) and its existing renderer gains a governed dossier model. polymath-v4 receives TEXT + LEDGER only: a DEPRECATED lead sentence on MCP Server A's four legacy query tools (pinned by a test; committed, NOT running until the next bounce), a corrected mcp_server/CONNECTORS.md, this work-log, one proof artifact. No retrieval, ranking, adapter-runtime, contract or Trail change. No bounce."
last_reviewed: 2026-09-20
---

## Contract
Owner word 2026-09-20: "Proceed with TG4. Do not start TG5 yet." TG4 = `HarnessActionV1 → existing controller / host
acquisition tools → HarnessResearchReceiptV1 → adapter_submit`. "Reuse the existing opportunity-research controller and
source tooling. Do not build a second harness." The tracked source stays
`/Users/king/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH`; "Mirror into the Hermes standalone deployment only
after its gates pass." Trail is untouched; no real-world run; no push. RB5 (the packet-text excerpt the same message
ordered "before TG5") is its own slice: work-log `2026-09-20-evidence-packet-text-excerpt.md`, register 11.357.

- Authoritative tree: the skill's git repo (`main`). Its own gate = `tests/run_all.py` + `python/controller.py doctor`
  under `~/.hermes/hermes-agent/venv/bin/python`; its own ledger = `WORKLOG.md`.
- Verifier: the skill gates in the repo, the same gates IN PLACE in the deployed copy after the mirror, the skill
  suite's cross-repo checks against THIS checkout (byte-copy of the receipt contract, the EvidencePacket sha pin, and
  Polymath's own `transitions.validate_receipt` run under this repo's `.venv`), and `tests/mirror_check.py` parity.
- Rollback: skill `git revert 076922d` + re-mirror; polymath-v4 `git revert` of this commit (text + ledger only).

## Changes
**Skill repo (`076922d`, local tag `v2.3.0-tg4`; `main` = `a7baa66`, 3 ahead of origin, NOT pushed).**
- NEW `python/adapter_receipt.py` — builds a `HarnessResearchReceiptV1` from the skill's OWN `observation` /
  `field_record` / `supplier_candidate` shapes. One static role table (18 skill roles → Trail's roles; vocabulary-only
  roles map to nothing and the item is omitted); source class = registered domain, else the item's own platform /
  family, else unknown (never guessed). Provenance is harvest-time or absent: no URL, no `retrieved_at`, an unrecorded
  `published_at_if_known` key, a corpus row, a prior-run record, an unknown source class → OMITTED with the reason
  written into the receipt's own `limitations`. Clamps to the ACTION's budget in input order; hypothesis ids ⊆ the
  action's; tool-trace rows bind to the action's search intents; a blown query budget is recorded as run. Built from
  a whitelist: no `score|rank|weight` key can ride along, and one fails validation. Deterministic. Fetches nothing.
- NEW `schemas/harness_receipt.schema.json` — BYTE COPY of `contracts/adapter/v1/harness_receipt.schema.json`
  (sha256 pinned as a constant in `adapter_receipt.py`; drift fails the suite when the repos sit side by side).
- NEW `python/governed_run.py` — `governed-run-journal-v1`: what `adapter_next` issued, what was submitted (rejections
  kept), the final result. A record, not a runtime: the agent drives the adapter through MCP, the journal only remembers.
- `python/report.py` — `build_model_from_governed(journal)`: the EXISTING renderer produces the dossier. Verdicts
  `GOVERNED — TRAIL SCORED` / `… TRAIL REFUSED TO SCORE` / `GOVERNED GAP — <code>` / `GOVERNED RUN <STATUS>`; lead cards
  carry Trail's record and NO `evidence_score`; standalone reports unchanged.
- Schemas `observation` / `field_record` / `supplier_candidate` gain OPTIONAL `retrieved_at`, `published_at_if_known`,
  `hypothesis_ids` (+ `metric`); prompts `evidence_judgment.md` / `community_instantiate.md` teach harvest provenance;
  `SKILL.md` "Governed entrypoint"; `docs/27_governed_entrypoint.md`; manifest 2.3.0; `tests/mirror_check.py`
  repointed (reference = the git repo, deployed = the Hermes dir); suite §17 rewritten, §24 added (609 checks).
- RB5 follow-through in the corpus lane: rows carry `text_truncated` / `text_chars`; the EvidencePacket dialect is
  re-pinned to the post-RB5 authoritative sha.

**Mirror (after the gates): `~/.hermes/standalone/opportunity-research` = v2.3.0**, 190 files compared, 0 missing / 0
drift / 0 unexpected, parity true (`MIRROR_RECEIPT.json`, skill commit `a7baa66`). `state/` (76 entries) and
`registry/research_evidence.csv` preserved. A pre-mirror tarball of the deployed dir sits in the session scratchpad.

**Hermes skill TEXT (tracked files in HERMES-KING, edited as text, UNCOMMITTED — 3 files, +47/−17):**
`skills/productivity/ecommerce-niche-discovery/SKILL.md` (Phase 1 = ONE `polymath_explore` with the ORIGINAL need, a
reading framework for the packet, checklist), its `references/polymath-multi-query-pattern.md` (RETIRED banner),
`skills/mlops/polymath/SKILL.md` (the v4 canonical surface ahead of the v3.3 tool list). `config.yaml` / `models.json`
untouched.

**polymath-v4 (this commit — text + ledger):**
- `orchestrator/orchestrator/mcp_server.py`: `ask` / `retrieve` / `compile_plan` / `retrieve_evidence` docstrings LEAD
  with `DEPRECATED — use …` naming the canonical replacement; `ask` loses "Prefer this over retrieve() when you want an
  answer" (it steered agents into a nested synthesis). Behaviour, parameters and routes unchanged.
- `mcp_server/CONNECTORS.md`: Hermes uses Server A (`:8930`, supervised `mcp` slot); Claude Code / Codex use Server B
  over stdio; both serve the seven `adapter_*` tools; the custom-agent example calls `polymath_explore` with the real
  parameter names (`query`, `corpus_id`); a changed Server A description needs a bounce AND a Hermes MCP reload.
- `tests/contracts/test_mcp_adapter_parity.py`: +1 pin (7 tests) — every legacy query tool on either server leads with
  DEPRECATED and names its canonical replacement; the canonical trio never does; the old steer is gone.
- NEW `eval/governed_convergence/TG4-SKILL-HARNESS-RECEIPT-2026-09-20.json` (written with hard assertions).
- NEW `docs/wiki/reports/2026-09-20/ECOM-CORPUS-INGESTIBILITY.md` — the READ-ONLY determination the owner asked for
  with the TG4 word; the plan's TG5 section records the owner's corpus amendment and points at it. Nothing ingested.

## Proof
| Slice | Level | Evidence |
|---|---|---|
| Skill receipt builder + journal + governed report model | UNIT_PROVEN (skill suite; executed path = the skill repo) | `tests/run_all.py` exit 0, **609 checks**; `controller.py doctor` exit 0 (re-run fresh at close) |
| Receipt is lawful for Polymath | UNIT_PROVEN cross-repo | the suite runs `shared/polymath_shared/adapter/transitions.py::validate_receipt` from THIS checkout under this `.venv`: accepts the skill-built receipt, refuses it under another action id; receipt schema is a byte copy (sha `f6189a45…` in all three locations); structurally equal to `tests/fixtures/harness_receipts/AGENT_RESEARCH.json` |
| Governed dossier | UNIT_PROVEN on REAL data | journal rebuilt read-only from finished fixture run R1 `adr_12ddda16f9b589fbdf7dfab9f31efedf` → existing renderer → verdict `GOVERNED — TRAIL SCORED`, 0 `evidence_score` mentions, sections incl. "TrailSignal's Record" and "Field Observations — admitted 33 · rejected 0" |
| Mirror | DEPLOYED (skill) | parity true, 190 files; the deployed copy's own gates IN PLACE: **606 checks** exit 0 + doctor exit 0 (six cross-repo checks collapse into three explicit "not on this machine" passes — polymath-v4 is not beside the deployed dir) |
| Server A deprecation leads | UNIT_PROVEN, MERGED, **NOT RUNNING** | new pin RED without the docstring edit (exit 1), GREEN with it (exit 0); both servers loaded BY FILE PATH from this checkout; `tests/determinism/test_mcp_server_v2.py` green. `bundle_integrity` READY, fence set untouched (orchestrator + docs only) |
| TG4 chain end to end (`adapter_next` → research → receipt → `adapter_submit`) | **NOT PROVEN LIVE** | that is TG5 = R2, which needs the owner's word |

Guards at close: `agent_preflight` 0 · `repo_guard` 0 · `wiki_worm --check` 0 · `bundle_integrity` READY.

## Rejected claims
- "TG4 is live-proven." No. No live governed run has driven `adapter_receipt.py` / `governed_run.py`. `adapter_start`
  and `adapter_submit` over Server B are still not live-exercised. The dossier was rendered from a REBUILT journal.
- "The Server A deprecation text is live." No — committed, inert until the next bounce, and Hermes sees it only after
  one MCP reload. No bounce was spent on docstrings ("Bounce only if required").
- "The Hermes skill edits are recorded." They are UNCOMMITTED in HERMES-KING (owner's repo, owner's commit).
- "606 < 609 means the deployed copy is missing checks." No — same suite; the cross-repo checks say so explicitly when
  polymath-v4 is not a sibling directory.
- "A `cinema`-backed governed run would say something about product discovery." No (owner rule): cinema is lawful only
  for a mechanical real-agent smoke run.

## Open contract gaps
Dispositions (`scripts/contract_impact.py --staged`): **MCP_SURFACE — UPDATED** (description text of four legacy tools;
names, parameters, routes unchanged; pinned). **ADAPTER_RUNTIME, EVIDENCE_PACKET, EVIDENCE_BOUNDARY_API —
TESTED_UNCHANGED** (the skill consumes them; the cross-repo checks pass against this checkout). Everything else
NOT_AFFECTED.

- TG5 / R2 is NOT authorized. Corpus reality: Polymath v4 holds ONE corpus, `cinema` (67 docs). A meaningful
  product-discovery R2 needs an ecommerce corpus; a second corpus is BLOCKED on finish-line Item 2 sub-item D
  (`search_atoms` takes no corpus argument; five unscoped callers), which the owner has sequenced first.
  Determination: the old `ecom-meta-v1` material is INGESTIBLE WITH PREP — source bytes intact in the v4 spool (11
  blobs) and in the v3.3 `ecommerce_meta` library (117 `.md`, 71 MB); its old indexes are gone, so there is nothing to
  copy. Open owner decisions: 10 docs vs 117, the commerce ontology profile, a staged 3–5 book cost probe.
- Harvest provenance is now REQUIRED for a receipt observation. Records harvested before v2.3.0 carry no
  `retrieved_at` and are omitted by design — the first real run will show how much of a normal harvest survives.
- Role table and source-class tables are static and conservative: an unknown domain with no declared platform/family
  is omitted, not guessed. Trail's registry decides the rest; nothing here is tuned to Trail's gates.
- Pre-existing red determinism tests (`test_query_receipts::test_all_three_query_handlers…`,
  `test_chat_runtime::test_compiler_on_drives…`) remain red and untouched (owner decision pending).
