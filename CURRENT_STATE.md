# CURRENT STATE — Polymath V5 (evidence-first)

Branch `architecture/evidence-first-v5` · authority `3981fcff…`
(= `v4-semantic-freeze` + qualified SUBTOKEN-SPAN-ADMISSION-V1).
`main` = `v4-semantic-freeze` (43209aa), untouched.

## Architecture (implemented and qualified)

```
L0 source (immutable, offsets)          chunks / documents / source_map
L1 raw evidence (append-only)           raw_entity_proposals · raw_predicate_evidence
                                        document_layout · sentence_slices
L2 interpretation                       span_hypotheses (rescue = hypotheses,
                                        never mutation) · mentions (admission)
L3 canonical semantics                  entities · canonical_*
L4 relation evidence                    relation_candidates (every disposition durable)
L5 canonical facts                      facts + evidence (incl. PARKED)
L6 projections                          Neo4j / Qdrant — rebuildable, proven exact
```

Governing invariant, enforced by gates: **filtering decides what becomes
knowledge; it never decides whether observed evidence survives.**

## Proven properties (each with a committed gate or live run)

- Ledger sufficiency: shadow settlement reproduces every production decision
  from L1+L2 alone (i4 82/82, smq1 69/69; UNRULED_SEMANTIC_DELTA=0).
- Full replay: ledger → settlement → compiler reproduces the exact fact-id
  set (16/16, 3/3), stable across legs.
- Reconstruction: Neo4j full wipe → exact rebuild from Postgres; Qdrant
  collection delete → re-embed → exact rebuild.
- CP2.1: SIGKILL mid-ingest → auto-restart ≤12s → re-registration →
  convergence 144s later, state hash byte-identical, zero duplicates.
  In-flight lease renewal for long stages (book-scale). Bounded restarts,
  quarantine, observable state file. Machine reboot recovered by restart of
  sidecars + supervised fleet with no data loss.
- Retrieval: FAST/HYBRID/GRAPH live; corpus isolation; typed refusals;
  GRAPH degrades to usable text at zero facts.
- V4 semantics preserved throughout: I4 P=.812 byte-identical state hash,
  55-gold 1.0, census no divergences — across every phase.

## Book-scale findings (fixed during Phase 11/12)

1. Syntax sidecar 512-sentence cap vs whole-document batch → client batching.
2. Non-durable ANTECEDENT_RESOLVED endpoints → FK violation on parked facts.
3. Embedder single-call timeout on book-sized runs → 64-batching.
4. claim_ttl (300s) vs 45-min extract → in-flight lease renewal (else healthy
   workers were revoked mid-stage and falsely quarantined).

## Known limitations (unchanged semantics, measured)

V4 freeze limitations carry forward; at book scale, provider type
instability fragments same-surface identities (row-51 homonym-guard
trade-off: `harvard` Location vs Organization). Biomedical register still
lacks a sealed document. MPS is a single shared GPU: concurrent
extract+embed contention can push sidecar calls past client timeouts.

## Operations

See `docs/RUNBOOK.md`. Sealed qualification: `eval/sealed/`. Replay and
reconstruction drivers: `eval/v5/`.

---

# HANDOFF — 2026-08-22 (release-closure forensic pass)

Authority moved `3981fcff…` → **`fd68fc57…`** (ADMISSION-IMPL-MEMO-V1,
behavior-identical, licensed by `tests/determinism/
test_concept_evidence_equivalence.py` + B8 identical-state run).
638 tests pass. HEAD = forensic-report commits on
`architecture/evidence-first-v5`.

## What "extraction is fixed" means — and what it never meant

FIXED (proven, committed):
- Extract throughput: 709 s → 315 s/book (2.25×), semantically
  byte-identical (B8), now provider-bound (77% GLiNER).
- Extract reliability: batching for syntax/embed/upsert, bulk writes,
  in-flight lease keeper for the extract stage, sub-token abstention,
  supervision with live-tested crash recovery. 25/25 books extracted;
  zero evidence lost through SIGKILL, reboot, wedge.

NEVER CLAIMED FIXED (frozen, first measured by the forensic pass):
- Relation/edge PRECISION. The semantic layer was frozen the whole
  mission; the sealed qualifications certified invariants +
  determinism, not fact-level precision. The first deterministic
  sample (FINAL_FORENSIC_REPORT.md §7) measured it: ~38% of projected
  edges WRONG under strict span attestation. That is not a regression
  of something fixed — it is the frozen layer's true baseline,
  now known.

## Read these, in order

1. `FINAL_FORENSIC_REPORT.md` — the full 19-section forensic report +
   verdict (**NOT PRODUCTION READY as a knowledge-graph product**;
   production-grade as evidence-first ingestion + text retrieval).
2. `eval/v5/forensics/*.json` — classified fact samples, fragmentation
   census, per-book accounting, global funnel.
3. `docs/KNOWN_LIMITATIONS.md`, `eval/v5/FINDINGS_phaseB.md`,
   `eval/sealed/FINDINGS_smq3-biomed.md`.

## Live state at handoff

- Corpus `release-books-v1`: 25 docs, extraction/settlement COMPLETE
  (144,396 mentions, 7,903 facts). Projections (qdrant→neo4j→verify)
  STILL DRAINING under an operator script.
- **Open incident (report §13):** project_qdrant failed 3× per ticket.
  Root causes, all still in code: (1) embedder inference wedge with a
  liveness-only health probe (restarted 00:29, healthy now);
  (2) worker batch-claims 4 tickets, lease keeper renews none of the
  project_qdrant tickets → reaper kills healthy long projections at
  claim_ttl 300 s. Mitigation running: `/tmp/serial_redrive2.py`
  (one-ticket-at-a-time promotion + external 30-min lease renewal
  every 30 s). If dead after a reboot, rerun it; procedure is also in
  docs/RUNBOOK.md (per-ticket re-drive SQL).
- The 3 permanent intake-refusal runs (2 corrupt originals + 1
  failed repair) are DELIBERATE evidence — do not clean them up.

## Next actions (ranked; from report §15/§19)

1. P1 engineering: readiness-probing health checks (probe /infer, not
   /manifest) + claim depth 1 or per-ticket lease renewal for long
   stages + regressions for both. Turns §13 into a non-event.
2. P2 cheap precision win: structure/citation-region candidacy
   suppression from layout evidence (index pages, headings, captions,
   reference lists currently mint edges).
3. First post-freeze semantic gate: relation-precision work measured
   on the L4 disposition ledger (direction-sensitive part_of frames,
   modality gate on created/acquired, pronoun durable-identity ban).
4. Finish report §11/§12 (retrieval panel — script ready at
   scratchpad `retrieval_panel.py`) + §2 store counts once the drain
   completes, then re-commit the report.

## Do not touch

Semantic freeze (GLiNER pin/labels/thresholds, Harbor, compiler,
canonicalization), frozen artifacts (`eval/i4/gold/`,
`eval/i4/verify_i4.py`, `eval/admission/artifacts/`), sealed sets,
the append-only ledger discipline.

---

# HANDOFF ADDENDUM — POLYMATH-FACT-ADMISSION-V1 (2026-08-22)

**Status: implemented, qualified, FAILED the precision bar, NOT cut over.**
Production canonical facts and the Neo4j projection are untouched.

Read `eval/v5/FINDINGS_fact_admission_v1.md` for the full qualification.

What exists now (all committed, 692 tests green):
- `shared/polymath_shared/fact_admission.py` — the F1–F8 gate chain.
- `shared/polymath_shared/fact_admission_policy.yaml` — declarative
  region licensing, orientation metadata, modal/contrastive classes,
  predicate strength ordering. No code changes needed to retune these.
- `shared/polymath_shared/source_region.py` — REGION-POLICY-V1.
- `eval/v5/fact_admission_shadow.py` — replays the whole L4 ledger in
  **10.2 s**. This is the iteration loop: no re-ingestion, ever.
- `tests/determinism/test_fact_admission.py` — 54 cases, each drawn from
  a mechanism the forensic pass actually measured.

Headline numbers (release-books-v1 graph pool, 1,521 facts):
admitted 298 · qualified 147 · rejected 1,334;
precision 44% supported / 31% questionable / **25% wrong**
(baseline 29 / 33 / 38). Bar was ≤5% wrong — not met.

Two things the next person must know:
1. **A rule-pack defect was found, not patched** (frozen): predicate
   verb lists were VerbNet-class-expanded without sense disambiguation
   (make/source/receive → acquired, work → uses, collaborate →
   similar_to). This is the predicate-misfire class from the forensic
   report. F5 compensates; the pack itself is still wrong.
2. **is_a and instance_of fall to exactly zero** (127 facts) through the
   copula-complement rule. A predicate hitting zero is a gate defect
   signature. Fix COPULA-COMPLEMENT-BINDING-V2 before anything else.

Ranked next actions supersede the earlier list:
1. COPULA-COMPLEMENT-BINDING-V2 (recover the taxonomy backbone).
2. Coordination / list-enumeration gate; multi-entity clause binding;
   agentless-passive orientation.
3. A separate ENTITY-admission gate — entity extent ("Pavlovian" →
   pavlov) and figure/document entities ("Figure 4-7") are upstream
   defects that cap achievable relation precision regardless of gates.
4. Only then re-qualify and consider cutover.

Unchanged from the earlier handoff: the semantic freeze, the projection
backlog incident (§13 of the forensic report), and the do-not-touch list.


---

# HANDOFF — COMPLETION MISSION CLOSE (2026-08-22)

**Verdict: NOT PRODUCTION READY.** See `FINAL_RELEASE_REPORT.md`.
763 tests green. Nothing cut over; all admission decisions `shadow=TRUE`.

## The one thing to do first

**Re-run convergence and the holdout on a host with memory headroom.**
Both are mechanical, need no new engineering, and are the biggest
information gain available. This host was at swap 28.6/28.6 GB, which
degraded the embedder 13x and stopped the final run.

```bash
nohup bash scripts/boot_polymath.sh &          # launchctl is a no-op here
# projections resume from checkpoint automatically (11,425 rows durable)
# then ingest the sealed holdout:
#   eval/sealed/manifest_holdout-v1.json  (hash 829c5d9b...)
```

The holdout is sealed and MUST be adjudicated once, without tuning. The
76.8% supported / 14.5% wrong figure is a DEVELOPMENT number — the gates
were iterated against those same labelled facts — so the holdout is the
number the release decision actually rests on.

## What changed this mission

Five P0 defects, all regression-covered:
1. lease starvation (claim burned a retry; keeper renewed one ticket;
   reaper quarantined healthy workers) -> `lease_faults = 0`
2. claim depth never applied (all 8 workers override the shared default)
3. **worker self-deadlock** — heartbeat inside the stage transaction held
   the worker's own registration lock for the whole stage, blocking its
   own lease keeper and control's sweep. This was the real "sidecar
   hang". -> blocked queries 3 -> 0
4. quadratic projection (every ticket re-derived the whole corpus)
5. non-resumable projection (receipts only at the end) -> now
   checkpointed every 512 rows, verified resuming after a restart

Plus: readiness vs liveness with periodic probing, stale-connection
recovery with typed errors, and failure records that carry the exception
type and cause chain (without which defects 4 and 5 were invisible).

Semantics: ENTITY-KNOWLEDGE-ADMISSION-V1 (new, 7 gates), plus role-based
binding, witnessed orientation, negation/contrastive/nominalized/
attributed clause gates, and sense agreement for class-inherited
triggers. Precision moved 29/33/38 -> 76.8/7.2/14.5 on development data.

## Traps for the next person

- `launchctl kickstart` SILENTLY NO-OPS on this machine (TCC blocks
  launchd under `~/Documents`). Verify the supervisor pid actually
  changed, or you will test stale code for hours. I did.
- A shared default is not a fix when every caller overrides it. Assert
  the ENTRY POINTS.
- Do not patch Python with text regexes. One dedented a `return` out of
  its guard and caused an 11-restart storm. The replacement tests are
  AST-based for that reason.

## Unchanged and still frozen

GLiNER pin/threshold/labels, Harbor, canonicalization, the predicate
pack (known sense-blind, reported not patched), sealed sets, authority
`fd68fc57...`, and the append-only ledger discipline.
