# Market Reframe (PRODUCT_ANCHORED_DISCOVERY)

Audit the user's initial frame against what field evidence actually showed.
This mode exists to find the strongest defensible interpretation of the
product — not to validate the user's idea.

Output `market_reframes` (at least one): `id`, `initial_user_frame`,
`user_frame_state` (CONFIRMED | WEAKENED | CONTRADICTED | UNTESTED — decided
by the evidence in front of you, cited), `evidence_supported_frame` (the
strongest actual frame), `why`, `proposed_repositioning`, plus
`adjacent_products` / `adjacent_markets` discovered along the way (care
kits, storage, display, gifting sets — the original SKU may not be the best
opportunity; that is a feature, not a failure). Cite `evidence_refs`.

When the evidence-supported frame reroutes EXISTING demand (Liquid Death
pattern: demand didn't need inventing, the route changed), also submit
`demand_reroutes` (optional key) with reroute_dimension + target_scope +
why_existing_demand_transfers + evidence_refs.
