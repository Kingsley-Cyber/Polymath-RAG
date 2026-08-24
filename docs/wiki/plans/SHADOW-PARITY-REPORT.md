# SHADOW PARITY REPORT — PREDICATE_V2 shadow → enforce gate

Date: 2026-08-24 · Branch `architecture/evidence-first-v5` · HEAD at time
of run: e306da6 + rescue-preservation fix · Fleet: kimi_v1 +
PREDICATE_V2=shadow + SYNTAX_PROVIDER=spacy · bundle v5-production-007

## Verdict: PASS — enforcement authorized

```
role binding errors      0
false positives          0
missing provenance       0
recall vs baseline       >= baseline on every document
adversarial negatives    all rejected (no over-binding)
```

## Runs measured

| Corpus | Purpose | Result |
|---|---|---|
| `s-val-doc01-cutover-v3` | CATEGORY-D live closure | trio ACCEPT (prior slice) |
| `s-validation-parity-v1` | 4-doc parity attempt | **exposed a real defect** |
| `s-validation-parity-v2` | post-fix parity | PASS (this report) |

## Defect found and fixed during parity (rescue-span deletion)

`POLYMATH_RESCUE=on` + boundary_widening REFUSAL deleted the original
provider span (`workers/workers/rescue.py`, ledger row 63 known
limitation), contradicting the module's own RESCUE-SPAN-PRESERVATION-V1
docstring. Effect: every refused speculative widening silently destroyed
an accepted GLiNER observation ("Atlas Data Platform" among them) →
doc04 lost all three baseline `contains_component` facts; doc04 mentions
17 vs 22 in the validated run.

Fix: refused widening keeps the original span untouched (zero new edges,
provider truth retained). Tests updated from pinning the limitation to
pinning the preservation contract:
`test_i4r_a_boundary.py`, `test_span_hypotheses.py`.

Isolation method: bisection over fleet env deltas against an in-process
`process_event` replay with `POLYMATH_EXTRACTION_TRACE=full`; raw L1
ledger proved GLiNER output identical across runs, placing the drop
post-discovery.

## Parity-v2 vs validated baseline (EXTRACTION-REPORT-s-validation-v1.md)

| Document | Baseline | Parity-v2 | Verdict |
|---|---|---|---|
| 01 Adaptive Neural Reasoning Systems (scientific) | 0 facts (CATEGORY-D era) | introduced_by · trained_on · evaluated_on — 3 ACCEPT, 4 UNSUPPORTED (correct type rejections) | improved recall, equal precision |
| 02 Enterprise Cloud Incident Response (procedural) | 0 facts · 1 type_violation rejected | 1 REJECT (fail-closed) | match |
| 03 hedged research notes | 1 contains_component · 6 scope rejections | 1 contains_component ACCEPT · 6 REJECT (same hedged sentences) · 1 UNSUPPORTED | exact match |
| 04 Atlas Data Platform transcript | 3 contains_component | 3 contains_component ACCEPT | restored by preservation fix |

Totals: 7 accepted facts (baseline 4 + sanctioned doc01 trio),
7 scope REJECTs (baseline 7), 0 speculative/modality facts accepted
(`may outperform` / similarity / unattributed claims: none admitted).

## Provenance completeness (all 7 facts)

fact_id present · evidence rows ≥1 · every evidence chunk resolves ·
provenance JSONB object — verified by SQL join (see session log).
Missing provenance = 0.

## Enforcement decision

Per charter stop-rule: shadow output == expected output with improved
recall and equal precision. Flip `POLYMATH_PREDICATE_V2=enforce`,
restart, re-verify persistence of the doc01 trio under enforce.
