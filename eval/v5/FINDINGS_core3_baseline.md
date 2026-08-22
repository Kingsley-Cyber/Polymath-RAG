# core-3-v1 — retrieval baseline and entity-layer evidence

Step 1 of the enforced order (`docs/MISSION_V5_COMPLETION_AND_PATTERN_INTEGRATION.md`).
Establishes the A/B bench before any entity work begins.

Corpus: three short documents, distinct registers — behavioural-design
narrative (Eyal, *Hooked*), procedural tutorial (LLM fine-tuning),
technical reference (Meyer, *Vector Database Management*). Full pipeline
in ~6 minutes, which is the point: semantic changes are A/B'd here, not
against the 25-book corpus.

---

## Retrieval baseline

8 queries, ~3 per document, run against all three production modes.

| mode | p50 | p95 | top-1 correct document | errors |
|---|---|---|---|---|
| FAST | 1960 ms | 2008 ms | **8/8** | 0 |
| HYBRID | 1957 ms | 2009 ms | **8/8** | 0 |
| GRAPH | 1980 ms | 2035 ms | **8/8** | 0 |

Document routing is correct in every mode. `graph_fact_count` totalled
**3 facts across 8 queries** — the traversal plumbing works and is
already bounded (`graph_bounds: {max_seeds: 8, max_facts: 20}`), but it
has almost nothing trustworthy to traverse.

**Latency is provider-bound, not architectural.** ~1.95 s is dominated by
the Qwen3-Reranker cross-encoder on MPS over a 3-document corpus. It is
recorded as a baseline, not as a target.

### Response-shape inconsistency

FAST and HYBRID return documents under `selected_documents`; GRAPH
returns them under `documents`. A first scoring pass read only the former
and scored GRAPH 0/8 when it was in fact 8/8. Worth unifying, or at
minimum documenting, before anyone builds evaluation on top of it.

---

## Entity-layer evidence

This is the part that matters for the improvement track. It directly
tests the mission's central hypothesis.

### Admitted graph endpoints

Actual `ACCEPT` facts from this corpus:

```
You     -acquired->    Hooked
you     -created->     Hooked
Hooked  -is_a->        simplicity
skill   -similar_to->  users
```

Every one of these is wrong, and each fails for a *different* reason:

| fact | failure class |
|---|---|
| `You -acquired-> Hooked` | pronoun admitted as durable identity (ISSUE 1) + ambiguous trigger (ISSUE 4) |
| `you -created-> Hooked` | same endpoints, different predicate — fragmentation *and* sense drift |
| `Hooked -is_a-> simplicity` | book title vs. abstract noun; no type signature should accept this (ISSUE 3) |
| `skill -similar_to-> users` | `similar_to` firing on incidental proximity (ISSUE 4) |

### Measured on the bench

268 endpoint surfaces, 71 distinct.

**Pronouns as graph endpoints — 49/268 = 18.3%**

| surface | occurrences |
|---|---|
| `you` | 23 |
| `You` | 10 |
| `We` | 10 |
| `we` | 6 |

Nearly one endpoint in five is a pronoun. Under ruling R2 the answer is
not a pronoun blacklist — it is that a pronoun should fail **durable
identity** and `graph_eligible`. That it does not is the single largest
measurable entity defect on this corpus.

**Case-only fragmentation — 5 surface pairs**

```
You / you            HABITS / Habits        We / we
PRIVACY / privacy    VECTOR QUANTIZATION / vector quantization
```

These are the cheapest possible deterministic win and require no model
change.

**Number fragmentation** — `users` (12) and `user` (12) are separate
identities; likewise `habit` (13) against habit-form variants. This is
the lemma-normalization case, and it is *not* safe by default: `users`
and `user` merge cleanly, but plural-vs-singular is not always identity
(`Windows` ≠ `Window`). Needs an evidence-backed rule, not a stemmer.

---

## What this says about the hypothesis

The mission proposes:

> The relation layer is starved and contaminated by upstream entity
> quality plus weak relation semantics. The leverage is not another
> entity extractor — it is (1) trustworthy entities, (2) resolved
> identities, (3) only then relation redesign.

**The bench supports this.** The relation gate is not obviously
mis-calibrated: 96 of 134 candidates were rejected for principled
reasons (`scope_gate: negated` 18, `scope_gate: question` 16, type-
signature violations 22, `binding:endpoints_outside_trigger_clause` 6).
Those rejections look correct.

The problem is upstream. When 18.3% of endpoints are pronouns and
identities fragment on case, the gate is being asked to adjudicate
`You -acquired-> Hooked` — a question with no right answer. It cannot
accept it (wrong) and rejecting it teaches nothing, because the *fact*
was never the defect. The endpoint was.

**One caution against over-reading this.** Three short documents is a
small sample, and the *Hooked* text is unusually second-person
("you build a habit…"), which inflates the pronoun rate relative to a
technical corpus. The 18.3% figure should be re-measured on the 25-book
corpus before it is treated as a general rate. The *class* of defect is
real regardless; the magnitude is not yet established.

---

## Standing

- FAST / HYBRID / GRAPH: **operational**, 8/8 routing, 0 errors
- T2 knowledge: **not qualified** — GRAPH stays experimental and
  non-asserted by design
- Development numbers throughout. **Not release evidence.** The sealed
  holdout remains the only admissible measurement.

Evidence: `eval/v5/release_evidence/core3_retrieval_baseline.json`
