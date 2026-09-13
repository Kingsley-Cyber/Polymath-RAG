---
change_id: CLOUDFLARE-WORKERS-AI-V1
date: 2026-09-13
last_reviewed: 2026-09-13
status: evidence (frozen)
architecture_impact: none (live-canary evidence for the Cloudflare Workers AI qualification; account id scrubbed; no credentials)
---

# Cloudflare Workers AI qualification evidence — 2026-09-13

Live canaries for `@cf/qwen/qwen3-30b-a3b-fp8` on the one supplied account (id scrubbed to
`acct2`). Full analysis + promotion decisions: `docs/wiki/plans/CLOUDFLARE-WORKERS-AI-QUALIFICATION.md`.

- `extraction-canary.json` — production `_extract_prompt` path, 3 real neighborhoods × {thinking-on, /no_think}.
  100% schema+sanitize valid; thinking-on 22 ent / 23 rel vs /no_think 79 / 8 → PROMOTE thinking-on.
- `profile-canary-text-mode.json` — production profile fingerprint + compiler, TEXT mode, 3 docs ×
  {thinking-on, /no_think}. 100% `ok=True`; /no_think faster + richer → PROMOTE /no_think.

Model finding: reasoning-burn; only Qwen's `/no_think` soft switch disables thinking on Cloudflare
(reasoning_effort / enable_thinking / chat_template_kwargs ignored). URL, quota (3036 park / 3040
backoff), and the /infer_batch 400→fallback are covered by `test_cloudflare_provider.py`.
