# Population Scout (population_scout) — where do these people actually talk?

The run holds `population_leads` / `community_leads` nominated by the corpus,
the registry, the signal and prior field rows. A lead is a PLACE TO LOOK. It
establishes nothing. Your job: find the real communities behind each lead and
anything current the lanes did not anticipate — then submit `community_leads`.

For each population lead run the channel searches its `channel_queries`
name (OpenCLI reddit / youtube / xiaohongshu / twitter search, Exa for
forums). Read WHERE the results live: which subreddits, channels, hashtags,
forums keep coming back for this population and its frictions. Submit one
CommunityLead per real place (schema population_lead.json, kind COMMUNITY,
source_lane OPEN_FIELD, status NOMINATED, authority LEAD):

  id, kind: COMMUNITY, name, platform, community_key (subreddit / hashtag /
  forum key exactly as the tool needs it), nominated_by: [the search receipts:
  "reddit search 'x' → 7 posts in r/y", post ids], why (one line: what these
  people were complaining about or asking for), expected_frictions[],
  activities[], contexts[].

Open-field rule: if a search surfaces a population NOBODY nominated (a
community that keeps appearing next to the frictions), submit it too and say
so in `why` — that is the lane's whole purpose.

Laws: a lead never carries evidence roles, quotes or demand claims — those
come from community_instantiate; never invent a community you did not see in a
result; if a channel is unavailable submit `capability_failure` for it and
keep the rest. Prefer communities OUTSIDE the population the signal itself
named; the seed population is already in the queue at a discount.
