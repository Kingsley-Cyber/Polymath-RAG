---
owner: governance
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: recorded
---

# Experiment 0004: G5 verification — reranked evidence through the existing R3a/R3b answer path

Date: 2026-08-14
Status: FROZEN — verification recorded; G3 promotion remains a product decision

## Question

Does the EXISTING EvidenceBundle → grounded-answer path (R3a/R3b)
consume the G3 reranked fused ordering correctly — preserving
provenance/citations, failing safely, and never inventing candidates?

## Changes audited

- R3a assembler gained an optional `evidence_order` hint (G5/G3):
  claims stay identity-ordered; evidence-only items follow the
  rerank hint when provided; the candidate SET never changes.
  `meta.ordering` records the policy ("identity" | "rerank").
  Schema updated accordingly (additive field).
- /evidence and /chat pass the reranked child order when the G3
  candidate flag is on.

## Verification (live stores, real reranker, integration tests)

| Requirement | Result |
|---|---|
| reranked ordering reflected in evidence | PASS — `meta.ordering == "rerank"`; evidence items follow the hint |
| no candidate invented outside the fused set | PASS — claim set and citation set identical rerank-off vs on |
| every answer claim maps back to evidence/provenance | PASS — all supported claims carry support ids; citations carry locators |
| citations survive representation mixing | PASS — bundle item ids + locators intact both ways |
| unsupported claims rejected/abstained | PASS — existing R3b tests green (unchanged path) |
| reranker unavailable → loud failure if enabled | PASS — 502 `rerank_unavailable` |
| reranker disabled → baseline unchanged | PASS — dead reranker URL + flag off still answers (sidecar never contacted) |
| deterministic bundle/answer | PASS — reranked /chat byte-identical across two runs |
| no extraction changes | PASS — extraction files untouched |

Suites: 165 unit + 23 integration green; G1 golden trace untouched.

## Verdict

**G5 PASS**: the existing answer path consumes the reranked ordering
safely — grounding, citations, provenance, and abstention all hold
under reranking, and disabled behavior is byte-identical. This does
NOT promote G3 to a default: promotion remains a product decision
(after G4 scale evidence), per the established candidate discipline.
