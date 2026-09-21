# TG3 acceptance — the evidence-only corpus lane, live (2026-09-20, v2.2.0)

**Purpose.** Prove at SKILL level that the nested synthesis is gone: the skill asks Polymath for EVIDENCE
(`POST /chat/evidence` → `EvidencePacket`), θ reasons once, and the rest of the controller — primitives,
gates, hypothesize, the HTML report — keeps working. GOVERNED-CONVERGENCE-V1 TG3; machine-readable receipt:
`2026-09-20-tg3-evidence-lane-acceptance.json`.

**Setup.** Claude Code acted as θ; the controller decided every transition. Live Polymath (`polymath-v4`
`3d3064a`, fleet bundle `c0d86509ad39`), corpus `cinema` (the only corpus there). Loop memory isolated
(`OPPORTUNITY_RESEARCH_DB=candidates/tg3_acceptance/loop.sqlite3`); the deployed Hermes copy (v2.1.2) untouched.
**No field research, no web request, no owner session** — the field lanes recorded an honest
`capability_failure{field_research}` (real-world acquisition is reserved for TG5), so the population gate released
the run through `lived_world_empty` and every hypothesis is `CORPUS_ONLY` (it can never qualify on its own).

**Disposition.** PASS on all seven criteria. Run `tg3_accept_02` ended `ABANDONED` (terminal) at `semantic_review`
once the criteria were observed; no product claim is made from it.

| criterion | result |
|---|---|
| exactly one evidence exploration call | PASS — `POST /chat/evidence` × 1 (plus `POST /retrieve/plan` × 1, `GET /capabilities`, `GET /corpora`) |
| no Polymath synthesis call | PASS — adapter ledger `polymath_chat_calls = 0`; Polymath's OWN query-receipt ledger for `run:tg3_accept_02`: one `chat / evidence_only`, nothing else; 0 synthesis receipts from the skill |
| the need is the ORIGINAL signal | PASS — the four compiled reformulations (seed / tension / invariant / contrast) were NOT sent to the evidence boundary |
| rows preserve text, utility_role, CA4 grade, provenance, source ids | PASS — 15 packet rows: grades DIRECT 13 / RELATED 2, roles DIRECT 15, origins PROFILE 10 / USER 5, every row with provenance + doc id; 4 merged with the plan lane |
| primitives continue to work | PASS — accepted on the first submit: 34 rows classified, 16 cited (8 of them packet rows), 7 latent structures; the fail-closed lineage law held |
| hypothesize continues to work | PASS — accepted on the first submit: 4 `CORPUS_ONLY` bridges, 9 hop-cited rows; the run advanced to `semantic_review` |
| HTML report still renders | PASS — the EXISTING `report.py`, self-contained; new section "Corpus evidence packets", no corpus-written answer |

**Instrumentation.** `polymath_chat_calls = 0` · `polymath_evidence_calls = 1` (adapter ledger, `utilization.corpus`,
and the server-side receipts agree). Negative control on one stub backend: v2.1.2 adapter → 5 × `POST /chat`;
v2.2.0 adapter → 0 × `POST /chat`, 1 × `POST /chat/evidence`.

**Timing.** evidence call 18.0 s (Polymath phases: query compiler ≈ 10.0 s, then retrieval / rerank / CA4) ·
plan lane 47.1 s (unchanged, the slowest request) · whole corpus node ≈ 65 s.

## Findings (measured, nothing tuned)
1. **EvidencePacket rows carry 240-character text PREVIEWS.** 13 of 15 packet rows are exactly 240 chars; the plan
   lane's chunks have median 736. Polymath-side cause (its chat retrieval builds the evidence inventory with
   `text[:240]`); NOT fixed here. The adapter mitigates only where lawful: a chunk both lanes return keeps the FULLER
   passage (4 of 15 rows), and every packet record now states `text_chars{min,max,total}`. Run `tg3_accept_01` was
   abandoned at the corpus node when this surfaced and the acceptance restarted on the final code.
2. **Corpus Explore did not fire on the signal** — firing cause `PLAN_FALLBACK` (Polymath's compiler-reliability
   backlog). So no COMPLEMENTARY / DIVERGENT seat was observed live (unit-covered only).
3. **Accident, disclosed:** a negative-control script used the wrong env var and registered a stub run `negctl` in the
   REAL loop memory (`~/.hermes/state/opportunity-research/opportunity.sqlite3`). It was ended through the
   controller's own `abandon` with that reason; nothing else in that database was touched.
