# Use-Meaning Decomposition (PRODUCT_ANCHORED_DISCOVERY)

One physical object can occupy several COMPETING meanings — functional,
collector, hobby, ritual, identity, aesthetic, gift, performance,
convenience. Do not make them agree, and do not pick a winner.

Ask separately: What does it physically enable? What repeated interaction
occurs? What does it substitute for? Could quality/expertise change how it's
evaluated? Could collecting exist? Does maintenance/care behavior exist? Is
it bought for oneself or gifted? What co-occurs with it?

Each `product_meanings` item: `id`, `type`, `interaction`, `lived_situation`,
`job`, `possible_participants`, `origin` (which lane suggested it),
`inference_distance` (0-3 hops from evidence), `evidence_refs` where a lane
signal supports it. Meanings with zero support are allowed — mark them
clearly with higher inference_distance. State stays PROPOSED.
