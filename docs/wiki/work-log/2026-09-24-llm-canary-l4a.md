---
change_id: LLM-BACKEND-L4A-CANARY
owner: "@king"
date: 2026-09-24
status: complete
status_note: "L4a (the canary) is done. L4b (one small document through the fleet: the profile + pMAP slots on their own keys, L-19) waits on the owner's choice of document, because both corpora are fully mapped and a new corpus needs the owner's word. Cloudflare account 1's id is still missing (L-11)."
architecture_impact: "No code change. Live .env: CLOUDFLARE_ACCOUNT_ID_3..6 filled (account ids, not secrets). 23 real model calls (one per lane) through the production client, each recorded in llm_provider_attempts with stage l4_canary."
last_reviewed: 2026-09-24
---

# LLM-BACKEND L4a: the canary and the Cloudflare account ids

## Contract
- The owner, 2026-09-24: pasted five Cloudflare account ids (unlabelled) and "go l4". Roadmap
  `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §3 row 5: ≤ 20 Groq + ≤ 6 Cloudflare calls (each pair reachable, OTPM per org,
  the TPM reservation), then one profile ticket and one small pMAP document on their owning slots. Gap rows L-03, L-11
  (and L-19 for the document).

## Changes
- Cloudflare ids, matched to tokens without a model call. Each token was tried against each pasted id on the read-only
  model catalog (`GET /client/v4/accounts/<id>/ai/models/search`); a 200 = the token belongs to that account.
  - Token 3 matched …6960, token 4 …ef43, token 5 …8f74, token 6 …3a98.
  - The fifth pasted id (…1efb) is account 2's, already set, and token 1 matched none of the five. Token 1 itself is
    valid (`/user/tokens/verify`: active).
  - The live `.env` had empty placeholders `CLOUDFLARE_ACCOUNT_ID_1..6=`; ids 3-6 were written into them (no inline
    comments). `CLOUDFLARE_ACCOUNT_ID_1` stays empty.
- No bounce is needed. The workers were spawned with the empty values in their environment, and `pool._resolve_key`
  falls through an empty env value to the `.env` file. Checked: with the four variables set empty in a process, the
  extraction ring has 19 lanes including cloudflare3..6; a running extract worker carries the empty values.
- The canary: `docs/wiki/experiments/llm-backend-l4-canary-2026-09-24/canary.py` → `canary.json`.
  - One call per active lane through `LLMExtractionClient.complete_one`: the L2 reservation, the call, settle-to-usage,
    and an attempt row tagged `stage=l4_canary`, `function=CANARY`.
  - The same prompt everywhere ("Reply with the word OK."); max_tokens 256 (Groq) / 512 (Cloudflare); `max_attempts=1`;
    sequential.

## Proof
- 23 / 23 active lanes answered HTTP 200 with the text "OK" (EXECUTED 2026-09-25 02:44:22–02:44:45 UTC):
  - profile_groq1..6 (gpt-oss-120b), map_groq1..6 (gpt-oss-20b) and map_groq1q..6q (qwen3.8-27b): all 18 Groq pairs;
  - cloudflare_map2 and cloudflare3..6;
  - cloudflare_map1 was parked (no account-1 id), so 23 calls against a cap of 26.
  - The Cloudflare extraction lanes answered in JSON (`{ "response": "OK" }`, json_mode on), the pMAP lane in text.
- Groq's own headers on every pair: `x-ratelimit-limit-requests: 1000` (per day), `x-ratelimit-limit-tokens: 8000`
  (per minute), `remaining-requests: 999`.
  - All three models on one key started from 999 separately, so the per-(key, model) independence the owner stated on
    2026-09-23 is now EXECUTED, not only stated.
  - `remaining-tokens` 7651 after a 93-token prompt with max_tokens 256 (8000 − 349): Groq counts prompt + REQUESTED
    output against TPM at request time. That is exactly what L2 reserves (`admit(prompt + max_tokens,
    reserved_output=max_tokens)`). The qwen pairs showed the same (8000 − 36 − 256 = 7708).
- The ledger (`llm_provider_attempts`, stage `l4_canary`):
  - 23 rows, 23 admitted, 23 dispatched, 23 success, 23 distinct lanes, 11 distinct accounts (6 Groq + 5 Cloudflare);
  - the real token counts: 1,492 in, 1,069 out;
  - every row carries its stage, function, lane, model and key variable name (never a value).
- Account 1 re-checked after the owner confirmed sending five ids. Token 1 got 403 (code 10000) on the model catalog for
  all five ids, while token 2 got 200 on …1efb. One real call with token 1 on …1efb (the 6th and last Cloudflare call of the
  L4 cap, ledger stage `l4_canary`) returned HTTP 401. So …1efb is account 2 only, and token 1 belongs to a sixth login
  whose id was not in the list.
- `scripts/llm_accounts.py validate`: 0 errors, 6 warnings (the 5 shared-tier pairs, L5; ACCOUNT_ID_UNSET for
  cloudflare_1).
- No existing document has pMAP work left: `document_status` shows 0 unresolved eligible parents in cinema (67 docs)
  and commerce-v1 (10). Every document has a profile artifact.

## Rejected claims
- "Run the document half on an existing document": there is no pMAP work left to do, and re-running a mapped document
  is not the upload path L-19 is about.
- "Upload a test document into cinema or commerce-v1": it would put a test document into the owner's real corpora.
- "Create a canary corpus now": the bootstrap's standing rule forbids admitting a new corpus without the owner's word
  and the corpus-filter checks; the owner's own plan said the owner picks the document.

## Open contract gaps
- L-03 CLOSED 11.468 (every Groq pair live).
- L-11 stays OPEN for account 1 only (ids 3-6 wired and live; account 2 was already set).
- L-19 OPEN until L4b: the first new document through the fleet shows its profile on the claiming slot's own key and its
  pMAP batches on that slot's two pairs, with fleet stage tags (`doc_profile` / `PROFILE`, `doc_parent_map` / `PMAP`).
- No architecture contract is touched (no code change).
