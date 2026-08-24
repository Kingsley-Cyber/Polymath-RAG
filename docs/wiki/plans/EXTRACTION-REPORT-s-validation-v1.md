# EXTRACTION REPORT — s-validation-v1 (4-document validation set)
Source: /Users/king/Downloads/untitled folder/S/
Pipeline: kimi_v1 + Predicate Compiler v2 shadow · persisted corpus

## Per-document results

### 01_psychology_working_memory → actually "Adaptive Neural Reasoning Systems" (scientific)
- 26 entities · **0 candidates · 0 facts**
- CLASSIFICATION: under-extraction on scientific prose — triggers like
  "was evaluated on" present but frame anchors absent. B-class gap
  candidate; requires single-doc debugging (noted for next slice).

### 02_technical_event_pipeline → Enterprise Cloud Incident Response (PROCEDURAL)
- 19 entities · **PROCEDURE ARTIFACT: 4 steps** ✓
  1. review alert metadata (resources/timestamps/identities/network)
  2. isolate affected systems when unauthorized access suspected
  3. document findings in incident management platform
  4. perform recovery validation after remediation
- 1 legacy-lane type_violation rejected (fail-closed) ✓

### 03_research_notes_sleep_and_attention (hedged research notes)
- 24 entities · 1 fact accepted (contains_component) · **6 scope-gate
  rejections** ("attributed, negated, speculative") — the hedging
  defense performed exactly as designed on real cautious language ✓

### 04_transcript_local_rag_build (build transcript)
- 24 entities · **3 facts**: Atlas Data Platform contains_component
  Distributed Storage Systems / Event Processing Services / Workflow
  Orchestration Components ✓ plausible component taxonomy

## Cross-set totals
facts 5 · procedures 1 (4 steps) · concepts 0 · scope rejections 7

## Classification ledger (new items)
- 01 zero-candidate: B-class suspect (frame anchors absent on
  scientific prose) — needs isolated debugging before any fix.
- Word-numeral step markers ("Step one:") — SUPPORT ADDED to procedure
  compiler this slice (measured failure → fixture-backed).
- Passive definitional patterns ("is often described as") — SUPPORT
  ADDED to concept compiler (same driver).

## Isolation & guards
All four documents share one corpus: vocabulary correctly admitted 0
families (single-document support everywhere). No cross-contamination.
