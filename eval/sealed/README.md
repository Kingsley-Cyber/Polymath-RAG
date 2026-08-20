# SEALED-MULTIDOMAIN-QUALIFICATION-V1

Release qualification for `v4-semantic-freeze`. This directory measures.
It has no opinion about semantics and must never acquire one.

## The shift this enforces

```
DEVELOPMENT                         QUALIFICATION
document exposes defect             document exposes defect
  -> understand it                    -> measure it
  -> authorize a fix                  -> classify it
  -> rerun                            -> DO NOT MODIFY V4
```

A defect found here is a **finding**, not a work item. The only outcomes are
`QUALIFIED`, `QUALIFIED WITH KNOWN LIMITATIONS`, or `REJECTED FOR RELEASE`.

## Why a harness rather than a promise

The development probes cannot prove generalization: the system has already
been shaped by them. That makes the *provenance of the evaluation set* part
of the evidence, so it is mechanised rather than remembered.

`seal.py` refuses to proceed when:

| refusal | why |
|---|---|
| document changed after sealing | the set must not move once results are visible |
| manifest edited after sealing | self-hash mismatch; tampering is detectable, not silent |
| set re-sealed | re-sealing is how an evaluation set quietly changes |
| document already in the corpus store | a document the system has seen cannot prove generalization — checked by CONTENT hash, so renaming does not launder it |
| working tree dirty | "which code produced this result" must have exactly one answer |
| code commit moved | same |
| semantic authorities changed | the frozen semantics are what is under test |

It cannot make tuning impossible. It makes an altered set or an altered
semantic surface **blocking and named** instead of a matter of recollection.

## Protocol

```
seal    --set NAME --sealed-at ISO --doc REGISTER=PATH ...   # BEFORE any ingestion
verify  --set NAME                                            # before, and again after
run     (ingest through the normal pipeline; no flags, no overrides)
stamp   --set NAME --corpus ID                                # record output hashes
replay  --set NAME                                            # re-derive, compare
```

`--sealed-at` is supplied by the caller rather than read from the clock, so
the manifest stays reproducible.

Escape hatches exist (`--allow-dirty`, `--allow-seen`, `--force`) because a
harness that cannot be overridden gets worked around instead. Each one is
recorded in the manifest, and `--allow-seen` explicitly forfeits the
generalization claim.

## The sealed set

Five registers, chosen to stress different failure modes rather than to
sample "five random books".

| register | stresses | why it is here |
|---|---|---|
| `technical_cyber` | acronyms, tools, versions, named products | identity precision — `OAuth 2.0`, `MITRE ATT&CK`, `PostgreSQL` |
| `biomedical_scientific` | concept definitions, hedged language | concept admission and predicate restraint |
| `business_operations` | organizations, roles, workflows | local references and external-party handling |
| `academic_social_science` | hedged definitions, competing concepts | concept != identity, mentioned != defined, correlated != causal |
| `structurally_different` | headings, dialogue, pronouns, partial references | where the known limitations actually live |

Coverage gaps are recorded in the manifest, so a verdict cannot silently
claim breadth the set does not have.

## Measured, separately

Provider/span coverage · admission and eligibility · canonical identity ·
relation truth · unsupported facts · abstentions · surface metrics ·
deterministic replay · retrieval quality.

The attribution waterfalls (`eval/i4/endpoint_coverage_attribution.py`,
`canonical_fp_attribution.py`) already require `UNEXPLAINED = 0` and are
reused unchanged.

## Known limitations carried into this run

Recorded in the plan under **V4 SEMANTIC FREEZE**, and expected to appear:
failed boundary widening suppressing valid spans (63); conservative discourse
(69, 70); identity extent (73); heading-only alias recovery (61);
corpus-scoped concept homonyms; and consequently some valid relationships
never entering the graph.

Observing these is confirmation, not failure. Rejection requires something
severe enough to fail the release on its own terms.
