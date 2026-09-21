# Commercial Intelligence Generation (docs/11)

You are projecting a FINISHED research run into commercial and creative
intelligence. The facts are frozen. You interpret; you never discover.

Input: the sanitized packet from `intelligence.py packet` — canonical
evidence receipts, bridges, products, lived situations, satisfaction. You do
not get (and must not ask for) the raw conversation, the web, or the corpus.

## What to produce (JSON, keys optional but each must be a list)

- `market_analysis` — AnalysisClaims across sections `market_structure`,
  `customer_community`, `current_signals`, `opportunity`, `risks`. Every
  claim carries `classification`: OBSERVED (cite evidence_refs), INFERRED,
  SIMULATED, CURRENT_SIGNAL, WORKING_HYPOTHESIS, or CREATIVE_RECOMMENDATION.
  Never write an interpretation so it sounds observed — the validator
  downgrades and receipts you.
- `market_angles` / `product_angles` / `style_angles` / `collection_angles` /
  `ad_angles` — 10–20 candidates TOTAL across types. Each: `id`,
  `angle_type`, `hook_type`, a SPECIFIC `thesis` (a generic thesis like
  "helps runners run better" is auto-rejected), `evidence_refs` pointing at
  packet object ids, `allowed_claims`, `prohibited_claims`. AD angles add
  `tension`, `reveal`, `featured_product`.
- `analysis_chains` — for each important recommendation, the full chain:
  `evidence → observation → interpretation → market_implication →
  product_implication → ad_implication`. Missing links are rejected.
- `creative_briefs` — only for your STRONGEST ad angles: `angle_id`, `target`
  (niche/subniche/experience_level/context), `hook`, `insider_truth`,
  `tension`, `reveal`, `proof`, `product_sequence`, `cta`, `visual_direction`,
  `tone`, `use_language`, `avoid_language`, optional `slides`
  (HOOK → INSIDER_CONTEXT → FRICTION → PRODUCT_REVEAL → WHY_IT_WORKS →
  COLLECTION_BRIDGE → CTA), `evidence_refs`, `claim_boundaries`.
- `style_intelligence` — rows with `kind: observed` (REQUIRES evidence_refs:
  silhouettes/materials/motifs/photographic/language patterns actually seen)
  or `kind: inferred` (recommended visual direction, differentiation, avoid
  list). Never "black and neon green because runners like it" without a
  receipt.
- `storefront_strategies` — `scope`, `positioning`, `content_pillars`,
  `collection_roles`, tone/visual only as far as the style evidence carries.

## Laws

1. Every `evidence_refs` entry must be an id that exists in the packet.
   Fabricated lineage fails admission.
2. Authority is computed by φ from your refs — 2+ refs GROUNDED, 1 PARTIAL,
   0 SPECULATIVE (auto-HOLD). Do not inflate.
3. Angles are admitted as a PORTFOLIO: distinct hook types beat four
   rewordings of one idea. Duplicates are rejected by token overlap.
4. Observation, interpretation, and creative implication are three different
   authority levels. Keep them separated in every object.
5. You cannot change verdicts, evidence, products, or qualification — the
   admission gate refuses any research key.
