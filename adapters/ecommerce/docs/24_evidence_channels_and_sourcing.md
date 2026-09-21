# 24 — Evidence channels and sourcing channels

Owner (2026-09-03): "for comments i want it to use amazon comments, reddits,
tiktok, and with agent reach more social places … streamline in there as well
as cjdropshipping in addition to alibaba."

## §1 Evidence channels are compiled, with the tool chain

`gap_compiler` emits one query per gap per channel in
`policies.evidence_channels` (order = priority). Every query carries the SHORT
keyword form, the source family (docs/04 decides what it may establish), the
exact tool chain to run, how to key independence, and the freshness source:

| channel | family | tool chain (OpenCLI / agent-reach, verified 2026-09-03) | may establish |
|---|---|---|---|
| reddit | community | `opencli reddit search … --subreddit <hint>` → `opencli reddit read <id>` | friction, workaround, comparison, purchase intent |
| amazon_reviews | review | `opencli amazon search` → `opencli amazon discussion <asin>` | PRODUCT_COMPLAINT, workaround, comparison, request, current product reference — never FRICTION_EVIDENCE about life without the product |
| youtube | community | `opencli youtube search` → `opencli youtube comments <url>` | friction, behavior, workaround |
| tiktok | community | `opencli tiktok search` (captions / on-screen text; comment threads need the browser lane) | behavior, workaround, friction |
| xiaohongshu | community | `opencli xiaohongshu search` → `… comments <note-id>` (translate, keep the original) | behavior, workaround, friction, comparison |
| twitter | community | `opencli twitter search` → `… thread <id>` | friction, comparison, purchase intent |
| forum | community | Exa `"<kw> forum"` → Jina reader | behavior, workaround, friction |

Not compiled, honestly: Instagram (OpenCLI searches users, not posts or
comments) and Facebook groups (membership). `source_identity` per channel is
in each query (`identity`); independence stays one law: same (platform,
author) or (platform, thread) = one voice. Freshness comes from the post,
review, video or note date. Observations record `query_id` / `query_used`
so query patterns only become registry candidates when they yielded
admitted evidence.

## §2 Sourcing channels: Alibaba and CJdropshipping

`sourcing_plan_compiler` emits one job per concept PER channel in
`policies.sourcing.channels` (default `[alibaba, cjdropshipping]`), each with
its tool chain. `python/sourcing_exa.py --state run.json --out cands.json`
runs the plan through Exa scoped to each channel's site, keeps price and MOQ
text verbatim (`not shown in listing snippet` when absent), and stamps
`concept_id`, `mechanism_id`, `channel`. Normalize applies
`supplier.moq_default_by_channel` (CJ = 1, noted on the row); leads carry
`channel`; the report and the receipt show leads by channel.

A dropship listing is a supplier fact (docs/04 `supplier` family): price and
availability, never demand.
