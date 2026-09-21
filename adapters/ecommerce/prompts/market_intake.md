# Market Intake (MARKET_DISCOVERY)

Resolve the user's broad market seed into one canonical `market_seed` object:

- `market`: canonical name (e.g. "running", "pet ownership")
- `canonical_identity`: one sentence on what this market IS as lived activity
- `aliases`: terminology variants people actually use
- `known_dimensions`: axes worth latticing later (activity, experience,
  social, life-intersection, context) — candidates only, not conclusions
- `exclusions`: what the user ruled out

If a `handoff_packet` is present, its promoted scope IS the seed — honor its
prior rejections; do not resurrect them. Do NOT propose niches, products, or
hypotheses here. The discovery lanes that follow must start unanchored.
