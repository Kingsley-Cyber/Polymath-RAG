# Product Ideation (product_ideation) — the SET, not the top-N

Only reached with a SUPPORTED mechanism. Turn each supported mechanism into
3–6 DISTINCT product directions (schema product_concept.json), each with at
least 2 concrete variations. Distinct means a different form factor / moment
/ buyer — not the same organiser in five colours. Cover the mechanism's
physical jobs and the moments the observations named.

Each concept: id, mechanism_id (a SUPPORTED mechanism), name, form_factor
(short noun phrase — the deduplication key), target_moment (the cue moment it
lives at), buyer (the sub-population), differentiator (why the generic version
fails them — cite the friction), variations[] (≥2: {name, twist}), and
evidence_refs[] (≥1 observation id that grounds the moment or friction).

Forbidden: a concept with no observation behind it; two concepts sharing a
form factor; variations that are only colour/size/price. The portfolio law
(3–6, distinct form factors) is validated at submit — write it properly the
first time.

## Lineage (docs/25 §7)
`evidence_refs` may name observation ids AND field_record ids. Prefer records
from lived clusters OUTSIDE the seed population, and name at least one concept
whose noun came from the FIELD (`products_named` / workarounds in the records)
rather than from the corpus — set `origin: FIELD` on it. Every concept's
lineage is computed at qualify: independent voices and communities behind it,
overlap with CORPUS_EXAMPLE terms, whether it is field-originated. A concept
grounded only through a corpus example and the same-noun searches that
followed it is CORPUS_ECHO_UNGROUNDED and its leads are excluded.

