---
owner: sidecar-gpu
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: recorded
---

# Experiment 0005 — GLiNER label-vocabulary probe (provider query-policy evidence)

Date: 2026-08-16
Gate: none (diagnostic probe recorded per TEMPORAL-DURABILITY directive §12; no
production change, no acceptance test)
Model: urchade/gliner_medium-v2.1 @ 40ec4193 (frozen), threshold 0.5 (frozen)
Method: POST /rescue on the resident GLiNER sidecar — bare noun-phrase text,
no sentence context, exact-full-span acceptance criterion.

## Purpose

During I4R-A implementation the boundary-rescue query (exact NP text +
original canonical label) refused most expansions on frozen-I4 phrases.
This probe characterizes how GLiNER's confidence depends on the
label-string vocabulary, as evidence for a future versioned query
policy (GLINER-QUERY-VOCAB-v2). It changes nothing.

## Observations (2026-08-16, host-native sidecar)

| target phrase | labels sent | raw predictions (label, score) | full-span? |
|---|---|---|---|
| Crestline Automation | [Organization] | — | no |
| Crestline Automation | [Company] | (Crestline Automation, Company, 0.821) | YES |
| Crestline Automation | [12 core labels] | — | no |
| Nimbus billing service | [Product, Technology] | — | no |
| Nimbus billing service | [12 core labels] | (Nimbus billing service, Organization, 0.527) | YES |
| CareChart EMR platform | [Product] | — | no |
| CareChart EMR platform | [12 core labels] | (CareChart, Organization, 0.571), (EMR platform, Technology, 0.523) | no (split) |
| Kubernetes | [Technology] | (Kubernetes, Technology, 0.929) | YES |
| load-testing harness | [Technology, Method, Product] | — | no |
| load-testing harness | [12 core labels] | — | no |
| Manhattan Active | [Product] | — | no |
| Manhattan Active | [12 core labels] | (Manhattan, Location, 0.954), (Active, Person, 0.565) | no (split) |
| HarborPay payments edge | [12 core labels] | (HarborPay, Organization, 0.834) | no (partial) |
| BrightPath learning portal | [12 core labels] | (BrightPath, Organization, 0.625) | no (partial) |

## Findings

1. GLiNER zero-shot confidence on bare NPs is strongly label-string
   dependent: "Crestline Automation" refuses under "Organization" (the
   canonical name) and accepts at 0.821 under "Company".
2. Bare-NP querying without sentence context accepts only a minority
   of phrases at the frozen 0.5 threshold; several phrases split into
   partial spans (precision-preserving refusals under the
   exact-full-span-only contract).
3. Provider wording is therefore a real query-policy lever — and
   exactly why it must be versioned policy data (semantic-query-policy
   aliases), never a hardcoded branch or an ontology change.

## Consequence

semantic-query-policy-v1 ships with IDENTITY aliases (canonical names
only — byte-identical with the qualified baseline). Any alias
vocabulary (e.g. Organization -> Company/Corporation/Business) must
enter through a named GLINER-QUERY-VOCAB-vN gate with probe evidence
like the table above, a policy version bump, and frozen-evaluation
promotion per the standard lifecycle. Canonical ontology terminology
is unchanged.
