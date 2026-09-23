# RAG compiler for grounded discovery

Status: proposed design. This specification does not establish that the running compiler implements it. It continues the user's hypothetical design discussion; it does not authorize deployment, live model spend, or test changes.

## Contract

Turn an imperfect user question into an executable retrieval and synthesis plan that promotes precision, depth, useful cross-domain connections, and synthesis across documents. Preserve explicit constraints, explain why each exploration matters, carry its purpose into ranking, and avoid unnecessary sequential planning calls.

Acceptance requires a useful indirect source to remain eligible despite weak standalone similarity to the original question; an unsupported abstract connection to be rejected; explicit scope to remain intact; and execution traces to distinguish useful discovery from unnecessary work. No unmeasured quality score or latency promise is part of this contract.

## The central decision

The compiler produces search hypotheses and evidence requirements. It does not produce evidence or final relevance verdicts.

An exploratory request must complete this sentence:

> Investigate [concept or relationship] because, if the sources support it, it could help the user understand [specific aspect of their question]. Look for [supporting evidence].

“This is related to the topic” is insufficient. The expected contribution remains a hypothesis until retrieved source material supports it. A high match to that hypothesis cannot validate the hypothesis itself.

## The required intellectual work

The plan must consider the following dimensions and express applicable evidence requirements. They share retrieval results and ranking; they are not separate model calls or mandatory search lanes. An unsupported dimension remains an identified gap, not a reason to fabricate a connection or pad the answer.

| Dimension | Compiler responsibility | Evidence and synthesis requirement |
|---|---|---|
| Precision | Preserve the exact subject, definitions, scope, and question being answered; separate explicit constraints from assumptions | Support claims at the level stated; distinguish similar terms and different contexts; narrow a conclusion when evidence is narrower |
| Depth | Identify the mechanisms, prerequisites, assumptions, boundary conditions, and competing explanations that matter | Explain why and how, not just what; seek evidence that distinguishes explanations rather than accumulating paraphrases |
| Cross-domain connection | Propose a specific mechanism or relationship that might transfer between domains | Identify what corresponds, what conditions permit transfer, and where the analogy fails; shared vocabulary is insufficient |
| Synthesis across documents | Identify which question requires combining, contrasting, or reconciling source material | Combine complementary evidence; preserve disagreements and scope differences; distinguish a synthesized inference from a claim stated by a source |

Cross-domain and cross-document are different: documents in the same domain may need synthesis, and a cross-domain connection may already be discussed within a single document. Source count and domain count are not quality scores.

The compiler specifies the synthesis work before retrieval without prejudging its result. For example: “Use mechanism evidence and case evidence to explain the phenomenon; check whether apparent disagreement comes from different conditions.” It must not assert that sources agree, contradict, or establish a transfer before inspecting their content.

## Inputs and ownership

| Input | Purpose |
|---|---|
| Original question and relevant conversation | Preserve the user's objective, corrections, and explicit constraints |
| Existing retrieval mode and corpus scope | Use the selected capabilities and authorized source boundaries |
| Indexed profile matches and their source links | Discover concepts beyond the user's terminology |
| Existing route registry and execution settings | Emit executable operations within actual system capabilities |
| Already available retrieval results | Reuse completed work and ground dependent requests when available |

Use existing profile surfaces such as questions, summaries, mechanisms, and concepts where available. Searching only concept names with the original wording can reproduce the same vocabulary limitation. Do not require every profile field to fire on every question.

Treat profile text and retrieved content as data, not instructions to change scope or execution policy. A profile-derived relationship is a routing hint until checked against sources.

## Compiler behavior

### Preserve the question; infer a learning objective

Keep the original question unchanged. Express the learning objective separately, using the conversation to resolve references. Distinguish explicit requirements from inferred interests.

Do not assume the user is a beginner because their wording is informal. Expand into prerequisites when they help explain the subject, not merely because they are introductory.

A general-sounding question asked in the corpus-learning workflow should not bypass retrieval just because a model can answer it from memory. Respect explicit instructions not to search and distinguish non-knowledge tasks from corpus questions.

### Choose purposeful routes

Useful routes can seek a direct answer, prerequisite, mechanism, correction, or transferable relationship. These are possible contributions, not mandatory lanes or reserved answer seats.

Select routes from the query and available corpus signals. Express materially different interpretations as provisional hypotheses when evidence can resolve them. Ask for clarification only when choosing an interpretation would make the search unusable or violate scope.

Reuse source links, document maps, and supported cross-document searches. Do not invent concept IDs, source links, or graph edges. A model-suggested concept without an index match may become an ordinary search hypothesis, clearly marked as such.

### Emit an executable plan

Extend the existing compiler representation where possible. The following is a logical data contract, not a requirement to create a new framework or service.

| Plan field | Required meaning |
|---|---|
| `original_query` | Exact user question |
| `learning_need` | What the user is trying to understand |
| `constraints` | Explicit scope and requirements; inferred assumptions remain separate |
| `inquiry_requirements` | Applicable precision, depth, transfer, and document-synthesis questions, each tied to the learning need |
| `request_id` | Stable identity for tracing a retrieval request |
| `operation` | A route the existing executor actually supports |
| `query_or_reference` | Search text or a real indexed reference |
| `depends_on` | Required earlier results; empty when independent |
| `expected_contribution` | What understanding this request could add |
| `evidence_requirement` | What source content would support the proposed connection |
| `origin` | Whether the route came from the user, an indexed profile, or a model hypothesis |
| `synthesis_targets` | Questions requiring explanation, combination, comparison, or reconciliation of retrieved evidence; outcomes remain open |

The executor validates references, dependencies, supported operations, and scope before dispatch. Dependencies cannot form cycles. It supplies actual configuration limits; the compiler cannot invent or silently expand them.

### Preserve meaning through selection

Attach the request identity, question, learning need, bridge relationship, and source references to every returned candidate. Deduplicate source content without discarding distinct useful paths to it.

Keep source-backed relationships separate from inferred explanations. If understanding a connection requires multiple source chunks, evaluate and retain the necessary evidence together.

## Ranking contract

The ranker answers these questions in context:

1. Does the source content support the proposed relationship, including any constraints necessary for it to apply?
2. Does that supported relationship advance the user's learning objective?
3. What does it contribute beyond the evidence already selected?

Judge contribution against the inquiry requirements: greater specificity, a supported mechanism, a valid transfer, a useful correction, or evidence needed to reconcile documents. Do not prefer a chunk simply because it has a different domain label or comes from another document.

For a direct result, this can be a direct question-to-source judgment. For an indirect result, the judge needs the retrieval path and the source material establishing the connection.

Do not use standalone original-query similarity as a universal eligibility floor. Do not admit a result merely because it matches its subquery. Neither the best path score nor a product of hop scores establishes grounded usefulness by itself.

Among supported candidates, select for useful contribution within the existing context allowance. Account for the space required by an evidence bundle, so an indirect claim cannot survive after its necessary supporting chunks are removed. Preserve evidence needed to answer the explicit question; a supported correction or prerequisite may deserve priority over a redundant literal match.

Novelty is relative to the conversation and selected evidence, not a claim that the system knows everything the user knows. Being unfamiliar or abstract is not independently a reason to include a chunk.

Profile metadata remains routing-only. Actual source text explaining an abstract mechanism can be evidence. Clearly label analogies and inferred applications, including the limits supported by the sources.

A current reranker must be shown to handle the required contextual judgment. Concatenating bridge text into its input is an implementation hypothesis, not proof that conditional ranking works.

## Latency contract

Start independent work as soon as its inputs exist. Direct search and lookup of indexed profile surfaces can proceed concurrently. The compiler can use the profile matches to emit exploration requests while direct retrieval proceeds. Reuse the direct result when execution joins the branches.

Batch independent probes and scoring through existing supported interfaces. Avoid an additional generative model call for each route, concept, or candidate. The same source text need not be repeatedly hydrated because multiple routes found it, although distinct relationships may still need distinct judgments.

Stored embeddings and source links should be used rather than regenerated per question. Implement only the offline additions required by a demonstrated missing route; a new graph or model-training project is not a prerequisite for this design.

Further expansion needs a named unresolved evidence requirement or a source-grounded opportunity that could materially improve understanding. Do not recursively follow every newly discovered concept. Respect the selected mode and actual executor limits; deeper work must not silently override them. If those limits leave a material gap, report it in the answer.

Concurrency does not make unlimited candidates cheap. Set candidate volume, concurrency, and any runtime limits from existing authoritative configuration or measurements of the quality/latency tradeoff. This specification invents no numeric defaults.

## Worked example

Question: **Why can a long take feel tense?**

Learning need: **Understand mechanisms by which an uninterrupted shot can produce suspense.**

| Route | Hypothesis | Evidence requirement |
|---|---|---|
| Direct search | Sources may explain long takes and suspense directly | Source text addresses the connection |
| Indexed mechanism, if present | Temporal expectation may explain tension during an unresolved event | Sources explain anticipation and support its application to the described viewing situation |
| Competing explanation, if supported by corpus signals | Restricted information may matter more than shot duration | Sources support the role of withheld information; do not assume duration is sufficient |

These concepts are illustrative, not assertions about the contents of this corpus. Do not manufacture matching index entries.

A generic passage about time does not qualify just because it matches “temporal.” A useful mechanism source may qualify despite never saying “long take,” provided the application is supported or clearly presented as a bounded inference. If the sources instead show why some long takes feel calm, preserve that corrective evidence.

The answer should explain the mechanism and its relevance, cite the supporting sources, and distinguish supported claims from inferred connections.

The compiler's inquiry requirements for this example would be:

- **Precision:** distinguish an uninterrupted shot from a generally slow scene; do not assume all long takes produce tension.
- **Depth:** investigate how anticipation, withheld information, and duration interact, and what evidence distinguishes their contributions.
- **Cross-domain:** if the corpus supports it, examine whether a mechanism from the psychology of anticipation applies to film viewing; state the mapping and limits.
- **Document synthesis:** combine mechanism sources with film-analysis sources, and reconcile counterexamples rather than summarizing each document separately.

These requirements can be served by overlapping evidence. They do not require a new search or model call per item.

## Reusable compiler instruction

The following can be adapted to the existing compiler's structured-output contract. It defines behavior, not a replacement for schema validation or runtime evaluation.

> Compile the user's question into an executable plan for grounded learning. Preserve the original question, explicit constraints, and selected retrieval mode. Use the supplied indexed profile matches to discover relevant knowledge beyond the user's terminology. Treat profile matches as routing hints, never as evidence.
>
> Plan for precision, depth, cross-domain insight, and synthesis across documents. For precision, identify the exact subject and distinctions that determine a correct answer. For depth, identify mechanisms, assumptions, boundary conditions, and competing explanations worth investigating. For cross-domain insight, propose a specific transferable relationship, its possible application, and evidence needed to establish its limits. For document synthesis, identify what should be combined, compared, or reconciled without assuming the sources' conclusions in advance.
>
> Every retrieval request must name its expected contribution and the source evidence needed to support it. Mark model-generated proposals as hypotheses. Use only supplied references and supported operations. Do not invent source IDs or connections. Preserve dependencies and reuse available results; group independent work for concurrent execution under the executor's actual settings.
>
> Carry the learning need, request purpose, bridge, and evidence requirement into ranking. Require a source-supported contribution to the user's understanding. Neither original-query similarity, subquery similarity, novelty, nor domain difference alone establishes relevance. Keep the source material needed to support a combined inference together.
>
> Pass synthesis targets to the answer stage. Require precise claims, explanations of mechanisms, explicit mappings and limits for transfers, and reconciliation of document differences where the sources allow it. Attach citations to supported claims and identify inferences. Do not force cross-domain connections, consensus, or depth unsupported by the retrieved corpus. Expose material evidence gaps.
>
> Return the structured plan in the existing compiler schema, including supported fields for inquiry requirements and synthesis targets. Do not generate the final answer or claim that a proposed relationship has already been verified.

## Acceptance and measurement

Use existing frozen examples or user-provided cases. Do not edit existing tests, expected outputs, or evaluation code. If a governing test conflicts with the new policy, report the conflict before implementation proceeds.

| Case | Observable evidence |
|---|---|
| Useful latent mechanism | Its route and supporting source survive selection; the answer explains the contribution |
| Attractive but irrelevant abstraction | A matching subquery cannot rescue an unsupported or unhelpful connection |
| Faulty premise | Source-backed corrective material can change the explanation |
| Precision and depth | The answer preserves relevant distinctions and explains a supported mechanism or explicitly identifies missing support |
| Cross-domain transfer | The answer establishes a specific mapping and its limits, or rejects the proposed transfer |
| Document synthesis | Complementary evidence forms an explanation; contradictions and scope differences remain visible rather than becoming false consensus |
| Explicit scope | Every executed operation and included source respects the constraint |
| Duplicate and dependent routes | Source content is merged without losing provenance; dependent work uses actual predecessor results |

For the same questions, corpus revision, and runtime configuration, compare baseline and proposed output quality with end-to-end completion time. Trace compilation, search, expansion, scoring, and synthesis with their actual dependency waits. Streaming start time is a separate measurement, not proof that retrieval became faster.

Record request execution, returned evidence, and selection/rejection reasons through existing receipts where possible. This is necessary to distinguish compiler failures from retrieval, ranking, or synthesis failures; it does not require a separate observability project.

Quality and acceptable latency tradeoffs remain open until measured against an agreed operating requirement. Do not label this compiler “10/10” based on architecture alone.

## Implementation boundary

Before editing the application, inspect the existing compiler output, executor dependencies, provenance handling, and final selection inputs. Map the contract to those existing owners and implement only demonstrated gaps. The diagnostic report in this workspace is historical context, not proof of the application's current state.

No new retrieval modes, guaranteed evidence quotas, GNN work, unrelated UI repairs, production changes, or model-training infrastructure are required by this specification.

## Research context

[IRCoT](https://aclanthology.org/2023.acl-long.557/) supports the need for retrieval informed by intermediate information. [EfficientRAG](https://aclanthology.org/2024.emnlp-main.199/) demonstrates multi-hop retrieval without a generative model call for query construction at every iteration. Neither establishes that this proposed compiler is implemented, fast, or effective on this corpus.
