"""LOCAL-LLM-EXTRACTION-V1 — versioned LLM proposal source.

Owner-authorized (2026-08-29, see docs/wiki/plans/
LEXICAL-ROLE-REALIGNMENT-PLAN.md) as a shadow extraction lane that may be
promoted per the canary gate. The model proposes source-attested evidence;
deterministic code retains authority over canonical identity, admission,
persistence, predicate selection, fact identity, and graph projection.

Modules:
  contract — the polymath-extraction-v1 packet (Pydantic)
  policy   — the cloud boundary (300 KB) and provider selection
  gate     — sanitize → validate → normalize (the only write boundary)
  client   — direct OpenAI-compatible transport (local MLX + cloud proxy)
"""
