# Community Instantiate (community_instantiate) — real records, real people

`population_queue.batch` names the leads for THIS round (VOI order). For each
lead run its `channel_queries` exactly as compiled (`tools` per channel,
docs/24), then submit `field_records` (schema field_record.json) — one per
real person's statement:

  id, lead_id, source (recoverable URL), quote_ref (short verbatim quote),
  community (r/… or the channel key), problem, workaround, desired_outcome,
  activity, context, moment (BEFORE/ARRIVAL/DURING/TRANSITION/AFTER when the
  person says it), object_state, purchase_language (true only for buying
  intent), products_named[] (products the person NAMED — current tools,
  requests; this is where field-originated nouns come from), friction_family
  (registry family when it genuinely fits, else omit), evidence_roles[],
  freshness {class}, source_identity {source_family, platform, author_key,
  thread_key}, origin: CHANNEL.

Before the channels: `python3 python/field_evidence.py --state run.json
--leads --out prior.json` re-materializes prior field rows for these
communities (origin PRIOR_RUN, real authors, freshness recomputed). Submit
them too — they count, they are not invented.

Laws (docs/04, docs/25): a source proves only what it is qualified to prove
(an Amazon review is a PRODUCT_COMPLAINT, never life-without-the-product
friction); same (platform, author) or (platform, thread) = ONE voice, so
spread across threads; never fabricate or paraphrase a quote; a community
that yields nothing is EXHAUSTED for this round — say so, do not pad. Stop
a lead once it has clearly passed the anchor threshold (5+ records across
2+ threads by default) and move to the next lead in the batch. What people
did NOT say stays unknown — the cards will list it.
