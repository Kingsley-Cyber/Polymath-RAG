# I4 Compiler Capability Matrix (derived from executable config)

- rule pack: core-predicates-v1.2.0 (active default)
- compiled_lexical_sha256: `d96560393884381d33754c1c…`
- resource_contract_id: `03a513ece6da32b243289fa9…`

## Global semantics

- **trigger_matching**: typed trigger contract: the compiler tests ONLY the lexical arm (verbs/nouns/multiword) of the predicate that localized the trigger; verb surfaces match BOUNDED inflection forms (base/+s/+es/+d/+ed/+ing with e-drop, y->ies/ied, consonant doubling) — arbitrary prefix strings never match; noun surfaces match exact word boundaries; multiword triggers match by substring
- **argument_frames**: SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)
- **association_frame**: ARG1_AFTER_TRIGGER_ARG2_AFTER_PREP when a preposition follows the trigger (referential-argument gate: MENTION_ONLY args abstain); otherwise the default frame
- **coordination**: predicate-region boundaries: a coordinator (and/but/or/while, optionally comma-prefixed, or ';') opens a NEW region only when the word after it is a trigger surface; entity lists (max 3 members) expand only on ONE side; double lists fail closed
- **surface_weak**: YES — without a syntactic parse every pairing is a surface frame; at most one unambiguous binding per trigger, else no fact
- **local_reference**: bounded definite descriptions ('the X', 1-3 content words) resolve the SUBJECT slot only: head-match against one unique history entity, or closed-class org descriptions against the unique Organization entity; 0 or >1 candidates -> abstain; alias-only identity
- **passive**: UNSUPPORTED without a parse record — no syntactic parse means surface order only; 'by'-passives typically fail subject signatures and abstain
- **negation_modality**: per-predicate constraints (reject/qualify); negated/conditional/question -> REJECT; speculative/hypothetical/attributed -> QUALIFY
- **graph_eligibility**: fact eligible iff BOTH endpoints have admission_class != MENTION_ONLY (shared neo4j_eligibility predicate used by projector, census, verifier)
- **referentiaL_gate_evidence_classes**: ['association']

## Predicates

### is_a
- definition: Subject is a subtype or kind of object.
- subject core types: ['Concept', 'Method', 'Process', 'Product', 'Technology']
- object core types: ['Concept']
- verbs: ['be', 'constitute', 'represent']
- nouns: []
- multiword: ['categorized as', 'is a', 'is a kind of', 'is a type of', 'kind of', 'known as', 'type of']
- direction: sub_to_super (inverse has_subclass)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### instance_of
- definition: Subject is an instance of a class or category.
- subject core types: ['Document', 'Event', 'Location', 'Method', 'Organization', 'Person', 'Product', 'Technology']
- object core types: ['Concept', 'Organization']
- verbs: ['be']
- nouns: []
- multiword: ['a member of the class', 'an example of', 'an instance of']
- direction: instance_to_class (inverse has_instance)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### part_of
- definition: Subject is a component, part, or member of object.
- subject core types: ['Concept', 'Organization', 'Process', 'Product', 'Technology']
- object core types: ['Concept', 'Organization', 'Product', 'Technology']
- verbs: ['compose', 'comprise', 'consist', 'constitute', 'contain', 'include']
- nouns: ['component', 'element', 'member', 'part', 'section']
- multiword: ['component of', 'comprised of', 'consists of', 'made up of', 'member of', 'part of']
- direction: part_to_whole (inverse contains)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### located_in
- definition: Subject is physically located in object.
- subject core types: ['Document', 'Event', 'Location', 'Organization', 'Product']
- object core types: ['Location']
- verbs: ['base', 'coexist', 'dwell', 'exist', 'extend', 'flourish', 'hold', 'languish', 'linger', 'live', 'locate', 'loom'] …
- nouns: []
- multiword: ['based in', 'has offices in', 'headquartered in', 'located in', 'operates in', 'situated in']
- direction: entity_to_place (inverse location_of)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### alias_of
- definition: Subject and object denote the same entity under different names.
- subject core types: ['Concept', 'Method', 'Organization', 'Person', 'Product', 'Technology']
- object core types: ['Concept', 'Method', 'Organization', 'Person', 'Product', 'Technology']
- verbs: []
- nouns: []
- multiword: ['aka', 'also known as', 'formerly known as', 'goes by', 'renamed']
- direction: surface_to_canonical (inverse alias_of)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: low

### occurred_at
- definition: Event happened at a time.
- subject core types: ['Event']
- object core types: ['TimeReference']
- verbs: ['happen', 'hold', 'occur']
- nouns: []
- multiword: ['happened in', 'occurred in', 'took place in', 'was held in']
- direction: event_to_time (inverse None)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### stated_in
- definition: A claim is stated in a document.
- subject core types: ['Concept', 'Document', 'Method', 'Product', 'Technology']
- object core types: ['Document']
- verbs: ['cite', 'describe', 'document', 'report', 'state']
- nouns: []
- multiword: ['according to', 'cited in', 'described in', 'documented in', 'per', 'stated in']
- direction: content_to_document (inverse states)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: low

### measured_by
- definition: Subject's magnitude is expressed by a measurement.
- subject core types: ['Concept', 'Process', 'Product', 'Technology']
- object core types: ['Measurement']
- verbs: ['measure', 'quantify', 'rate', 'record', 'score']
- nouns: []
- multiword: ['accuracy of', 'measured at', 'measured by', 'rated at', 'scored']
- direction: entity_to_measurement (inverse measures)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### created
- definition: Agent brings a product, artifact, or concept into existence.
- subject core types: ['Organization', 'Person']
- object core types: ['Concept', 'Method', 'Product']
- verbs: ['arrange', 'assemble', 'author', 'bake', 'bead', 'blow', 'build', 'cast', 'chisel', 'churn', 'coin', 'compile'] …
- nouns: ['author', 'creation']
- multiword: []
- direction: agent_to_patient (inverse created_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### founded
- definition: Agent establishes an organization or institution.
- subject core types: ['Organization', 'Person']
- object core types: ['Organization']
- verbs: ['arrange', 'assemble', 'author', 'bake', 'bead', 'blow', 'cast', 'charter', 'chisel', 'churn', 'coin', 'compile'] …
- nouns: ['establishment', 'formation', 'founding']
- multiword: ['set up']
- direction: agent_to_patient (inverse founded_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### developed
- definition: Agent develops a technology, method, or product.
- subject core types: ['Organization', 'Person']
- object core types: ['Method', 'Product', 'Technology']
- verbs: ['arrange', 'assemble', 'bake', 'bead', 'blow', 'cast', 'chisel', 'churn', 'code', 'compile', 'cook', 'crochet'] …
- nouns: ['development', 'implementation']
- multiword: []
- direction: agent_to_patient (inverse developed_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### employs
- definition: Organization employs a person.
- subject core types: ['Organization']
- object core types: ['Person']
- verbs: ['employ', 'hire', 'recruit', 'retain']
- nouns: ['employer']
- multiword: []
- direction: org_to_person (inverse works_for)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### has_role
- definition: Person holds a role in an organization.
- subject core types: ['Person']
- object core types: ['Organization']
- verbs: ['chair', 'direct', 'head', 'lead', 'manage', 'serve']
- nouns: ['ceo', 'cto', 'director', 'engineer', 'founder', 'head', 'lead', 'manager'] …
- multiword: ['CEO of', 'CTO of', 'is the head of', 'runs the', 'serves as', 'works for']
- direction: person_to_org (inverse role_held_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### leads
- definition: Person leads an organization, event, or process.
- subject core types: ['Person']
- object core types: ['Event', 'Organization', 'Process']
- verbs: ['chair', 'direct', 'head', 'lead', 'manage', 'run', 'spearhead']
- nouns: []
- multiword: []
- direction: person_to_led (inverse led_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### member_of
- definition: Person or organization is a member of an organization.
- subject core types: ['Organization', 'Person']
- object core types: ['Organization']
- verbs: ['belong', 'join']
- nouns: ['member']
- multiword: ['joined', 'member of']
- direction: member_to_group (inverse has_member)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### owns
- definition: Owner possesses an organization or product.
- subject core types: ['Organization', 'Person']
- object core types: ['Organization', 'Product']
- verbs: ['control', 'hold', 'own', 'possess']
- nouns: ['owner', 'proprietor']
- multiword: []
- direction: owner_to_owned (inverse owned_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### acquired
- definition: Buyer acquires an organization or product.
- subject core types: ['Organization', 'Person']
- object core types: ['Organization', 'Product']
- verbs: ['absorb', 'accept', 'accrue', 'accumulate', 'acquire', 'appropriate', 'arrogate', 'borrow', 'buy', 'cadge', 'collect', 'commandeer'] …
- nouns: ['acquisition', 'takeover']
- multiword: []
- direction: buyer_to_acquired (inverse acquired_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### subsidiary_of
- definition: Organization is a subsidiary of another organization.
- subject core types: ['Organization']
- object core types: ['Organization']
- verbs: []
- nouns: ['branch', 'division', 'subsidiary']
- multiword: ['a division of', 'subsidiary of']
- direction: child_to_parent (inverse parent_of)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### uses
- definition: Agent or process applies a technology, method, or resource instrumentally.
- subject core types: ['Method', 'Organization', 'Person', 'Process', 'Product']
- object core types: ['Method', 'Product', 'Technology']
- verbs: ['adopt', 'apply', 'employ', 'exert', 'exploit', 'leverage', 'play', 'reuse', 'run', 'use', 'utilize', 'work']
- nouns: []
- multiword: ['adoption of', 'application of', 'based on', 'built on', 'built with', 'powered by', 'run on', 'usage of', 'use of']
- direction: agent_to_instrument (inverse used_by)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### implemented_with
- definition: A product or method is implemented with a technology.
- subject core types: ['Method', 'Product']
- object core types: ['Technology']
- verbs: ['implement', 'realize']
- nouns: []
- multiword: ['implemented in', 'implemented with', 'powered by', 'written in']
- direction: product_to_tech (inverse implements)
- constraints: {'negated': 'reject', 'hypothetical': 'reject', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### causes
- definition: Subject causes or produces an effect.
- subject core types: ['Concept', 'Event', 'Process']
- object core types: ['Concept', 'Event', 'Process', 'Product']
- verbs: ['cause', 'induce', 'produce', 'trigger']
- nouns: []
- multiword: ['because of', 'due to', 'lead to', 'leads to', 'led to', 'result in', 'resulted in', 'results in']
- direction: cause_to_effect (inverse caused_by)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'qualify', 'attributed': 'qualify_wrap_stated_in', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### enables
- definition: A method or technology enables a process.
- subject core types: ['Method', 'Technology']
- object core types: ['Process']
- verbs: ['allow', 'enable', 'facilitate', 'permit']
- nouns: []
- multiword: ['allows for', 'makes it possible']
- direction: enabler_to_process (inverse enabled_by)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'qualify', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### influences
- definition: Subject influences, affects, or modulates an object.
- subject core types: ['Concept', 'Method', 'Organization', 'Person', 'Process']
- object core types: ['Concept', 'Process']
- verbs: ['affect', 'bias', 'influence', 'modulate', 'shape', 'sway']
- nouns: []
- multiword: []
- direction: influencer_to_influenced (inverse influenced_by)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'qualify', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### depends_on
- definition: A system, method, or process requires another to function.
- subject core types: ['Method', 'Process', 'Product', 'Technology']
- object core types: ['Method', 'Technology']
- verbs: ['depend', 'need', 'require']
- nouns: []
- multiword: ['depends on', 'is a prerequisite for', 'relies on', 'requires']
- direction: dependent_to_requirement (inverse dependent_of)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'qualify', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: high

### transforms_into
- definition: Subject converts into an object.
- subject core types: ['Concept', 'Process', 'Product']
- object core types: ['Concept', 'Process', 'Product']
- verbs: ['alter', 'compile', 'convert', 'deform', 'metamorphose', 'morph', 'mutate', 'transform', 'translate', 'transmute']
- nouns: []
- multiword: ['compiles into', 'converts to', 'maps to', 'turned into', 'turns into']
- direction: source_to_result (inverse transformed_from)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'qualify', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### derived_from
- definition: An artifact derives from a source artifact.
- subject core types: ['Concept', 'Document', 'Product']
- object core types: ['Concept', 'Document']
- verbs: ['adapt', 'derive', 'fork', 'port']
- nouns: []
- multiword: ['a fork of', 'adapted from', 'based on', 'derived from']
- direction: artifact_to_source (inverse derives)
- constraints: {'negated': 'reject', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: medium

### similar_to
- definition: Two entities resemble each other.
- subject core types: ['Concept', 'Method', 'Organization', 'Person', 'Product', 'Technology']
- object core types: ['Concept', 'Method', 'Organization', 'Person', 'Product', 'Technology']
- verbs: ['banter', 'bargain', 'collaborate', 'collide', 'commiserate', 'communicate', 'compromise', 'concur', 'confer', 'cooperate', 'correspond', 'deliberate'] …
- nouns: []
- multiword: ['analogous to', 'comparable to', 'like', 'similar to']
- direction: canonical_order (inverse similar_to)
- constraints: {'negated': 'qualify', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'reject', 'question': 'reject'}
- frames: ['SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)']
- graph weight: low

### associated_with
- definition: Fallback association. Emitted only when no specific predicate applies.
- subject core types: ['Concept', 'Document', 'Event', 'Location', 'Method', 'Organization', 'Person', 'Process', 'Product', 'Technology']
- object core types: ['Concept', 'Document', 'Event', 'Location', 'Method', 'Organization', 'Person', 'Process', 'Product', 'Technology']
- verbs: ['associate', 'connect', 'link', 'relate']
- nouns: []
- multiword: ['associated with', 'connected to', 'linked to', 'related to']
- direction: canonical_order (inverse associated_with)
- constraints: {'negated': 'qualify', 'hypothetical': 'qualify', 'speculative': 'qualify', 'conditional': 'qualify', 'question': 'reject'}
- frames: ['ARG1_AFTER_TRIGGER_ARG2_AFTER_PREP when a preposition follows the trigger (referential-argument gate: MENTION_ONLY args abstain); otherwise the default frame']
- graph weight: low
