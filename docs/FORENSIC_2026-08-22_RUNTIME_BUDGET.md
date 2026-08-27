# Forensic — 2026-08-22

## Six defects between a 13 GB budget and a converged corpus

Every defect below was found while trying to do one ordinary thing:
hold Polymath inside a memory allocation the workstation owner set, and
drive a corpus to `query_ready`. Five of the six were introduced or
exposed by the budget work itself. They are recorded in the order they
were found, because each one hid the next.

**Standing lesson.** Four of these defects produced a *healthy-looking*
system. Workers heartbeated, leases were sound, receipts committed, the
live build fence passed 12/12. Liveness is not progress, and a fleet
that is up is not a fleet that is working.

---

## Timeline

| time | state |
|---|---|
| 15:57 | Docker VM stops during a settings restart and never reboots |
| 17:42 | host backend still polling a guest that does not exist |
| 17:46 | fleet up; projection 500s on every `/infer` |
| 18:10 | Metal pool pinning found and fixed; projection resumes |
| 18:23 | guard stops a compliant run on the owner's own memory |
| 18:55 | core-3 ingested; intake claims nothing for 40 minutes |
| 19:35 | claim starvation found and fixed; corpus converges 24/24 |

---

## 1. Docker VM died rather than restarted

**Symptom.** `docker info` returned 500s for 100 minutes after a
settings change. Docker Desktop's UI reported the app running.

**Cause.** The VM shut down at 15:57 and a replacement never booted. No
`Virtualization.framework` process existed. The host backend spent the
whole period polling `/run/guest-services/stats.sock` and logging
`connection refused` once per second.

**Why it wasted time.** "Docker is slow to start" is a reasonable first
hypothesis and it is wrong here. The distinguishing evidence is cheap
and was not gathered early: *is there a VM process at all?* A restart
that half-completes leaves the host side alive and the guest side
absent, and only the guest side does any work.

**Fix.** Full quit and relaunch. No code change.

**Rule.** When a daemon is unreachable, check that its *worker* process
exists before concluding it is initialising.

---

## 2. MPS watermark ratio computed against the wrong denominator

**Symptom.** Every `/infer` call 500'd with
`MPS backend out of memory (max allowed: 1.56 GiB)` — while the budget
said 2.0 GB.

**Cause.** `PYTORCH_MPS_HIGH_WATERMARK_RATIO` is a fraction of Metal's
**recommended maximum working set**, not of physical memory. On this
host those differ by 22%:

```
physical RAM                        32.00 GiB
torch.mps.recommended_max_memory()  24.96 GiB
```

Dividing a 2.0 GB budget by 32 gives 0.0625, which torch applies to
24.96 → a **1.56 GiB** cap. The budget was silently 22% tighter than it
claimed.

**Fix** (`f26f93b`). Ask torch for its own denominator, in a subprocess
so the supervisor never imports torch merely to size a fleet. Falls back
to `physical × 0.78` when Metal is absent.

**Rule.** A ratio is meaningless without its denominator. If a config
expresses an absolute quantity and a runtime consumes a ratio, the
conversion is a place bugs live — test the round trip, not the ratio.

---

## 3. Sidecar memory budgets were guesses, and both were low

**Symptom.** After fixing the denominator the embedder still OOM'd, now
at the corrected 2.0 GiB cap. Later, GLiNER did the same at *its* 2.0 GB
cap and failed two of three core-3 documents.

**Cause.** Both caps were invented, never measured. Measured:

| sidecar | model | weights at rest | **peak driver** | budgeted | outcome |
|---|---|---|---|---|---|
| embedder | Qwen3-Embedding-0.6B (bf16) | 1.11 GiB | **3.17 GiB** | 2.0 GB | every request failed |
| GLiNER | gliner_medium-v2.1 (fp32) | 0.73 GiB | **3.02 GiB** | 2.0 GB | extraction failed |

Two things made the guesses badly wrong:

- **Driver allocation, not live tensors, is what the cap governs.** The
  embedder's live tensors stay at 1.11 GiB (the weights) across an
  entire run. Its *driver* allocation reaches 3.17 GiB. Watching the
  wrong number suggests enormous headroom that does not exist.
- **GLiNER is float32.** 195M parameters sounds small next to 596M until
  the dtype is checked: fp32 at 195M costs more per parameter than bf16
  at 596M.

**Fix** (`7c8239d`, `7ba40ab`). Both caps set from measurement, with the
measurement recorded in `config/runtime_budget.yaml` beside the number
so the next person does not re-guess it.

**Rejected fix.** float16 would halve both. It also changes vector
numerics, which breaks the frozen neural embedding contract
`embed_e794ec4cab197a3f` and orphans every vector already written. Not
available, and the reason is recorded so it is not re-proposed.

**Rule.** A budget figure with no measurement beside it is a guess
wearing a number's clothing.

---

## 4. The OOM retry could not retry — a live exception handler pinned the memory

This was the real one, and it hid inside the fix for the previous
defect.

**Symptom.** After adding an adaptive splitter that halves a batch on
OOM, the projection still failed — and the logs showed a *constant*
`MPS allocated: 3.42 GiB` across every attempt, failing on allocations
as small as **2.75 KiB**. Splitting all the way down to a single text
did not help.

**Cause.** The splitter released the Metal pool from inside its own
`except` handler:

```python
except Exception as exc:
    _release_mps()          # frees nothing
    return split_and_retry(...)
```

While `except ... as exc:` is executing, `exc.__traceback__` references
the frames of the call that raised, and those frames still reference the
half-built activations that caused the OOM. `empty_cache()` returns only
blocks with **no live reference**, so it freed nothing, and every retry
inherited a full pool.

**Proof.** Identical cap, identical batch, release site the only
difference:

| release site | result | pool after release |
|---|---|---|
| inside the `except` handler | **failed** at 3.48 GiB | **3.45 GiB** — never returned |
| traceback cleared, released outside | **OK, 8 vectors** | **1.14 GiB** — weights only |

**Fix** (`3973e54`). Clear `exc.__traceback__`, leave the handler, then
release. `gc.collect()` before `empty_cache()`, since a tensor held by
an unreachable cycle is still a live reference to the allocator.

**Rule.** Freeing a resource from inside the handler for the failure
that resource caused is a contradiction. Exit the handler first.

---

## 5. The same defect had to be fixed twice, in two sidecars

**Symptom.** With the embedder healthy, GLiNER 500'd on `/infer_batch`
with the identical error class.

**Cause.** The splitter and the pool release had been written *inside*
`sidecars/embedder/server.py`. GLiNER had neither, so it inherited none
of the reasoning — including the two non-obvious rules (collect before
emptying; clear the traceback before releasing) that took a measurement
to discover.

**Fix** (`7ba40ab`). The discipline moved to
`shared/polymath_shared/metal.py`; both GPU sidecars route through it. A
test asserts every GPU sidecar uses it, so a third cannot repeat this.

**Rule.** A fix that encodes hard-won, non-obvious reasoning belongs
where every caller inherits it. The second occurrence is the signal —
do not wait for the third.

---

## 6. Claim starvation — one unclaimable event blocked an entire corpus

**Symptom.** Core-3 ingested cleanly: 3 runs, 24 tickets, intake
`ready`. Then nothing, for 40 minutes. No error, no failure, no lease
fault. One `WARNING` repeating every two seconds.

**Cause.** The claim query took the oldest undelivered events:

```sql
WHERE e.delivered_at IS NULL AND ... ORDER BY e.event_id LIMIT %s
```

Event `#79621`, from a long-dead `vocab-probe-v2` corpus, pinned
`semantic-query-policy-v2` and the `semantic_v2` chunker — semantics
this fleet does not run. It is **permanently** incompatible: no worker in
this configuration will ever claim it. The worker fetched it, refused
it, `continue`d, claimed nothing, slept, and fetched the same event
again. Forever.

**48 compatible events were starved behind it**, including all three
core-3 documents.

**Why it was invisible.** Every health signal was green. Workers
heartbeated. Leases were sound. No ticket errored, no receipt failed,
the live build fence passed 12/12. The fleet was perfectly healthy and
doing nothing, and the only symptom looked like log noise.

**Fix** (`682f62b`). Workers remember what they refused on contract
grounds and exclude it from the next fetch, so the scan advances instead
of re-reading the same head. Refusals are per worker type and expire
after 15 minutes, so a deliberate semantic cutover re-admits work an
earlier configuration could not run. The warning fires once per event
rather than once per poll, so a starved queue reads as a starved queue.

**Rule.** Any queue that skips items must advance past them. "Skip and
retry from the top" is not skipping — it is a spin lock with extra
steps. And a log line that repeats on every poll trains the reader to
ignore the one time it matters.

---

## 7. The resource guard measured the wrong memory

**Symptom.** A healthy, converging projection stopped with
`CAPACITY_STOP: available memory below 34%`.

**Cause.** The guard watched the **host's** free memory. At the moment
it fired, Polymath held **6.93 GB of its 16 GB allocation** — the rest
of the machine was the owner's own applications (OPENCODE, ChatGPT,
zcode-cli, WebKit), which are entitled to it. The guard was measuring
somebody else's memory and stopping a compliant run because a browser
was open.

A second bug compounded it: `footprint_gb()` charged GPU caps for every
sidecar in the *configured* profile rather than the *running* ones,
inventing 5.5 GB of usage for models that had never started — enough to
trip the very guard it fed.

**Fix** (`d39011a`). The primary condition is now Polymath's measured
footprint against its allocation, which is the contract that actually
exists. Host starvation remains a secondary stop with the floor lowered
34% → 12%. GPU caps are charged only for sidecars that are *listening*.

**Rule.** Guard the contract you own. On a shared workstation, free
memory is not a measure of your own behaviour.

---

## Budget: three raises, and what each one bought

| ceiling | full fleet | fits? | why raised |
|---|---|---|---|
| 13 GB | — | — | owner's initial allocation |
| 16 GB | 14.95 GB (estimated) | apparently | to allow full concurrency |
| 16 GB | 17.95 GB (**measured**) | no | caps corrected (defect 3) |
| 19 GB | 19.45 GB (measured) | no | GLiNER corrected (defect 3) |

**A correction worth stating plainly.** The owner was told 16 GB would
allow the full fleet to run concurrently. That was based on the
unmeasured sidecar caps and it was wrong. Measured, the full fleet needs
~19.9 GB.

This costs nothing operationally, because no stage calls every model:

| profile | GB | purpose |
|---|---|---|
| `graph` | 5.75 | canonicalize and project the graph |
| `projection` | 9.30 | embed and upsert vectors |
| `converge` | 9.90 | drive an extracted corpus to `query_ready` |
| `retrieval` | 13.30 | serve queries |
| `extraction` | 14.40 | ingest and extract |
| `pipeline` | **15.15** | every ingestion stage, end to end |

All fit inside 19 GB with room. `pipeline` is the one that matters for
building: it runs intake → verify with GLiNER, spaCy and the embedder,
and omits only the orchestrator and reranker, which serve queries.

---

## Outcome

**core-3-v1 converged: 24/24 tickets done, 0 failed, 3/3 `query_ready`.**

Three short documents chosen by the owner for fast diagnostics —
behavioural-design narrative, procedural tutorial, technical reference —
deliberately spanning distinct registers so an extraction correct on
only one register would show.

Extraction, 134 candidates:

| document | candidates | ACCEPT | QUALIFY | REJECT |
|---|---|---|---|---|
| Eyal, *Hooked* | 75 | 15 | 6 | 54 |
| LLM fine-tuning walkthrough | 18 | 2 | 2 | 14 |
| Meyer, *Vector Database Management* | 41 | 11 | 2 | 28 |

Rejections are principled rather than noise — `scope_gate: negated`
(18), `scope_gate: question` (16), type-signature violations (22),
`binding:endpoints_outside_trigger_clause` (6). Accepted predicates are
plausible: `acquired`, `uses`, `created`, `member_of`, `similar_to`,
`founded`, `part_of`, `instance_of`.

These are **development numbers and are not release evidence.** The
sealed holdout remains the only admissible measurement.

---

## Commits

| commit | change |
|---|---|
| `f26f93b` | MPS denominator; adaptive splitter (incomplete — see `3973e54`) |
| `7c8239d` | embedder cap corrected to measured peak |
| `3973e54` | release the Metal pool outside the except handler |
| `d39011a` | guard on Polymath's allocation, not the host's free memory |
| `682f62b` | claim starvation: scan past unclaimable events |
| `7ba40ab` | shared Metal discipline; GLiNER cap; `pipeline` profile |

17 regression tests across `tests/determinism/test_mps_budget_fidelity.py`
and `tests/determinism/test_claim_starvation.py`. The Metal tests are
AST-based deliberately: a previous text patch to a sidecar silently
dedented a `return` out of its guard and caused 11 restart storms.

---

## What did not change

The semantic freeze held throughout. Semantic authority
`fd68fc57f4c18057`, embedding contract `embed_e794ec4cab197a3f`, GLiNER
provider, thresholds, labels, routing, Harbor, canonicalization and the
predicate compiler are all untouched. Every defect here was operational.

Two observations deferred rather than acted on:

- `release-books-v1` contains two documents whose source paths point
  into a session-scoped temp directory that will be cleaned up. A corpus
  whose sources can vanish is not reproducible.
- Cialdini, *Influence* yielded 54 candidates from 0.2 MB, against ~1,200
  from a 0.4 MB Bernays text. That ratio suggests a failed text
  extraction rather than a thin book.
