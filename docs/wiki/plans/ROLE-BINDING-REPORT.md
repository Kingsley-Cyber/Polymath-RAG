# ROLE BINDING REPORT — CATEGORY-C fixes (2026-08-23)

BERT evaluated_on GLUE
  BEFORE: positional: subject='Studies'(no entity)->no candidate
  AFTER:  BERT -> evaluated_on -> GLUE
  WHY:    ARG1(theme)=BERT in active voice

BERT introduced_by Google Research
  BEFORE: v1: no anchor (trigger absent from pack)
  AFTER:  BERT -> introduced_by <- Google Research
  WHY:    nsubj:pass->ARG1; agent-by->ARG0

ToT introduced_by Princeton researchers
  BEFORE: binding distance exceeded (>4 tokens)
  AFTER:  head-chain binds: Tree of Thoughts
  WHY:    gap=filler+adjective+closing generic head

'It' evaluated_on Game of 24
  BEFORE: pronominal subject -> no candidate
  AFTER:  resolved: pronoun_resolved_unique:BERT
  WHY:    unique type-compatible prev-sentence entity

ambiguity guard: pronoun_resolved_unique:GPT (fail-closed OK)
## Provenance recorded per candidate
semantic_frame_id · lexical_resource_source · role_mapping(voice+slots) · predicate_mapping_rule · subject/object types · evidence_span — all in decision reason (see compiler._compile_frame_relation)
