# POLYMATH — FINAL RELEASE REPORT

Branch `architecture/evidence-first-v5`. 763 tests passing.
Semantic authority `fd68fc57f4c18057…`, unchanged.

# VERDICT: **NOT PRODUCTION READY**

Two independent reasons, in order of how hard they are to fix:

1. **T2 knowledge does not meet the truth bar.** Required ≤5% wrong;
   measured 14.5% wrong on the development population, and that number is
   optimistic by construction (see §4). The admission gates stay in
   shadow; nothing was cut over.
2. **Unattended large-corpus convergence is unproven on this host.** Not
   for want of fixes — five real defects were found and repaired — but
   because the host is memory-saturated (§3.6) and the final convergence
   run could not complete.

What IS ready, and is a defensible product today, is narrower than the
whole system: **a deterministic, fault-tolerant, evidence-first
ingestion and text-retrieval system with a stratified, provenance-
carrying graph layer whose asserted tier is explicitly experimental.**

---

## 1. What was asked and what happened

The mission was to finish the system: fix operations first, then raise
T2 knowledge quality to ≥90% supported / ≤5% wrong, then qualify and cut
over.

Operations went deeper than expected. "Projection lease starvation"
turned out to be **five stacked defects**, four of which only became
visible after the one in front of it was fixed. All five are fixed and
regression-covered.

Semantics improved substantially — wrong edges fell from 38% to 14.5% —
but did not reach the bar, and the honest measurement that would settle
it (a fresh holdout) could not be run because the host ran out of
resources.

---

## 2. Knowledge stratification (shipped, persisted)

Migration `0021_knowledge_tiers.sql`.

```
T0 EVIDENCE      observed; append-only; never a claim
T1 INFORMATION   interpreted/plausible; provenance-carrying; not asserted
T2 KNOWLEDGE     asserted; every recorded gate decision passed
```

Live on `release-books-v1`: **T0** 174,650 raw proposals / 197,168 span
hypotheses · **T1** 7,491 facts, 34,501 relation candidates · **T2** 89
facts, every decision `shadow = TRUE`.

A fact reaches T2 only if **every** recorded decision passed — one reject
demotes. `shadow = TRUE` means the decision records what admission would
do without governing the projected graph; cutover flips a flag rather
than rewriting history. Rollback is the same flip in reverse.

Two admission boundaries, both fail-closed, both refusing promotion
without ever destroying evidence:

* **ENTITY-KNOWLEDGE-ADMISSION-V1** (E1–E7) — new. Refuses spans that cut
  a word (`Pavlovian` → Person `pavlov`) and document-structure entities
  (`Figure 4-7`, `Listing 5-1`, `Chapter 5`). 46 facts with structural
  endpoints refused. Genuine names containing structural words (`Table
  Mountain`) survive.
* **FACT-ADMISSION-V1** (F1–F8) — extended. F3 now consumes the entity
  verdict and attributes the reason to the entity layer, so forensics can
  separate "the relation gate failed" from "the endpoint was never
  admissible".

Full contract register: `docs/SEMANTIC_CONTRACTS.md`.

---

## 3. P0 — operations. Five defects, all fixed

### 3.1 Lease starvation
Claiming incremented `attempt`, so every ticket a worker merely queued
burned a retry; the keeper renewed only the executing ticket; the reaper
quarantined healthy workers. All 24 projections of `release-books-v1`
were marked failed **without a single real failure**.

Fixed: claiming is not an attempt; renewal is owner-scoped; the reaper
distinguishes a stale owner (charge + quarantine) from a live
heartbeating one (no charge, reason recorded). **Measured after:
`lease_faults = 0`.**

### 3.2 Claim depth never applied
All eight workers hardcode their own `run_forever(batch_size=4)` (intake
8), overriding the shared default. My first fix changed only the shared
default and my test asserted only that signature — so it passed while
production still claimed four. Fixed at every entry point; the
regression now asserts the **entry points**.

### 3.3 Worker self-deadlock — the actual cause of the "sidecar hang"
Workers heartbeat **inside** the stage transaction, holding a row lock on
their own `worker_registrations` row for the entire stage. Measured live:
a projection sat idle-in-transaction for 22 minutes while its own lease
keeper blocked on `Lock/transactionid` and control's staleness sweep
blocked behind it on `Lock/tuple`.

Effect: heartbeat frozen at claim time, lease expired and never renewed,
control stopped ticking, worker looked wedged — **while it was working
normally**. The 16-hour "sidecar wedge" was this, not a wedged sidecar.

Fixed: the pre-stage heartbeat runs in its own short transaction.
**Measured after: blocked queries 3 → 0; lease renewing.**

### 3.4 Quadratic projection
Routing representations are corpus-wide by design (retrieval must route
across documents), so every ticket re-derived the whole corpus: 18,823
rows per ticket, ~46 min each, ~19 h for 25 books. Now incremental — rows
whose active receipt matches the exact hash the projection would write
are skipped. The hash encodes the contract version, so a contract change
or wiped receipt still re-projects.

### 3.5 Non-resumable projection
Receipts committed only after a whole pass, inside the stage
transaction, so any failure discarded every completed batch. Three
attempts burned 1,705 embed calls without finishing one pass. Now
checkpointed in 512-row slices on an independent connection — points in
Qdrant are a non-transactional side effect that already survives
rollback, so the receipt recording that fact should too. **Verified live:
receipts advanced 3,233 → 11,425 durably and survived a worker restart.**

### 3.6 Host saturation (environmental — NOT fixed, cannot be)
Final convergence could not complete. Swap is **28.6 GB of 28.6 GB used**;
free pages 66 MB. Under that pressure the embedder degraded from 5 s to
**72.7 s for a four-text batch**, making the remaining 7,400 rows a
4.5-hour proposition that was still degrading.

The memory belongs to a 1.1 GB VM, Docker, and the user's applications.
Reclaiming it means killing the user's software, which I will not do
unasked. This is a host-capacity limit, not a pipeline defect — and
because §3.5 made the projection resumable, it will finish from
checkpoint when resources allow rather than starting over.

### 3.7 Also fixed
* **Readiness vs liveness.** All three inference sidecars ran a real
  forward pass in `/ready` but returned HTTP 200 alongside
  `{"ready": false}`, and the supervisor probed `/manifest` and checked
  only the status code. Now 503 when unusable, probed periodically (not
  only at spawn), body inspected, bounded restarts.
* **A regression I introduced and then fixed.** The 503 patch dedented a
  `return` out of its guard, so spaCy reported not-ready unconditionally;
  the new probe restarted it 11 times and killed a live projection. The
  replacement test is **AST-based** — text patching is what broke it, so
  structure is what detects it. Probe budget widened (60 s, 5 strikes) so
  a busy sidecar is not condemned.
* **Stale connections.** Connect/pool bounded at 5 s, read patient at
  300 s, pool rebuilt on transport faults, typed `SidecarUnavailable`
  terminal error.
* **Undiagnosable failures.** Records stored only `str(exc)` — literally
  `"timed out"`. Now type + full `__cause__` chain. This is what made
  §3.4 and §3.5 findable at all.
* **Boot recovery is broken on this host.** `launchctl kickstart`
  silently no-ops: macOS TCC blocks launchd from executing the boot
  script under `~/Documents` (exit 126). Every "fleet restart" for
  several hours was a no-op against stale code. Fix is to relocate the
  script; until then boot recovery must not be claimed as passing.

---

## 4. Knowledge quality — measured

Whole admitted population classified against evidence spans, not sampled.

| | baseline | final |
|---|---|---|
| SUPPORTED | 29% | **76.8%** |
| QUESTIONABLE | 33% | **7.2%** |
| WRONG | 38% | **14.5%** |
| admitted facts | 1,521 | 69 |

**This is a DEVELOPMENT number and is optimistic by construction.** The
gates were iterated against these same labelled facts all session. The
honest figure requires the fresh holdout — three books in unseen
registers, sealed before inspection (`manifest_holdout-v1.json`, hash
`829c5d9b…`) — which could not be ingested because of §3.6. My
expectation is that it reads meaningfully worse.

### Per-predicate (the actionable result)

| predicate | n | supported | wrong |
|---|---|---|---|
| part_of | 11 | 73% | 18% |
| uses | 37 | 70% | 19% |
| associated_with | 6 | 67% | 17% |
| **similar_to** | 14 | **29%** | **71%** |

`similar_to` was demoted to T1 on that evidence: its comparison triggers
(`like`, `parallel`, `related to`) mark exemplification or concurrency as
often as similarity. Even the strongest predicate sits at 19% wrong, so
**predicate filtering alone cannot reach 5%**.

### Gates added this mission
Entity admission (7 gates) · role-based argument binding (replacing
hop-reachability) · grammar-witnessed orientation incl. participial and
agentive passives · clause-local syntactic negation · contrastive
clauses · nominalized clauses (`"Writing X is hard"`) · attribution
governors (`"Yorty ignorantly told the press…"`) · sense agreement for
VerbNet class-inherited triggers · proper-name trigger rejection.

### S6 — questionable facts
Every questionable admitted fact classified. **UNEXPLAINED = 0.** Four
were supported on fuller context; one was wrong (a claim the document
explicitly discredits), which produced the attribution gate.

### Root cause found in the frozen pack (reported, not patched)
Predicate verb lists were expanded from VerbNet classes **without sense
disambiguation**: `obtain-13.5.2` inserted *make/source/receive* into
`acquired`, `use-105.1` inserted *work* into `uses`, a communication
class inserted *collaborate* into `similar_to`. This is the root of the
predicate-misfire class. F5 compensates by requiring PropBank/FrameNet
sense agreement for class-inherited triggers; correcting the pack is a
future version.

---

## 5. What is unproven

| claim | status |
|---|---|
| large-corpus unattended convergence | **UNPROVEN** — §3.6 host saturation |
| fresh-holdout precision | **UNPROVEN** — sealed, not ingested |
| GRAPH retrieval on the 25-book corpus | **UNPROVEN** — projections incomplete |
| Neo4j/Qdrant reconstruction after cutover | **N/A** — no cutover |
| boot recovery | **FAILS on this host** (§3.7) |

Everything else previously proven (evidence durability, deterministic
replay, crash recovery, corpus isolation, FAST/HYBRID retrieval,
throughput 2.25×) is unaffected by this mission's changes and remains as
recorded in `FINAL_FORENSIC_REPORT.md`.

---

## 6. Recommendation

**Ship the narrow label, not the graph.** Evidence-first ingestion plus
text retrieval is genuinely strong and measured. The asserted graph is
89 facts in shadow at 14.5% development wrong-rate; it should be labelled
experimental and excluded from any surface called "knowledge".

Ranked next work:

1. **Run the convergence and the holdout on a host with headroom.** Both
   are mechanical now; the code is resumable. This is the single biggest
   information gain available and needs no new engineering.
2. **Relocate the boot script** out of `~/Documents` so boot recovery can
   be claimed honestly.
3. **Then the semantic tail**: copula-complement binding v2 (`is_a` and
   `instance_of` currently reach zero), a corrected predicate pack with
   sense disambiguation, and coordination/list-enumeration binding.
4. **Only then** re-qualify and consider flipping `shadow`.

The bar itself should not move. 500 trustworthy facts beat 5,000
unreliable ones, and the stratification now makes that a product
decision rather than a compromise: T1 keeps everything the graph
refuses, fully provenanced and queryable.
