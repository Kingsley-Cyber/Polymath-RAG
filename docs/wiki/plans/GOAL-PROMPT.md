# GOAL PROMPT — Polymath LLM ingestion: finish, verify, report

Paste this into a fresh session to continue the work. Context files to read
first, in order:
1. `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — the completion contract
   (every plan detail tagged DONE/DEVIATED/SUPERSEDED/PARTIAL/MISSING).
2. `docs/wiki/plans/LOCAL-MIGRATION-FEASIBILITY-SCORECARD.md` — scores,
   proof, and the honest unknowns.
3. `docs/wiki/work-log/2026-08-29-llm-ingestion-migration.md` — running log.
4. `/Users/king/Downloads/polymath-v4-local-migration-plan.md` — the
   authoritative detailed reference (owner-editable).

## Owner decisions already made (do not re-litigate)

- **Single-lane extraction** (two-tier superseded): >300 KB → cloud
  (`qwen3.5:397b-cloud` via Ollama daemon), ≤300 KB → local 4B
  (`mlx-community/Qwen3.5-4B-MLX-4bit`, locked gen config).
- **Scope**: the wave covers ONLY the original 12 cyber books in
  `cysa-study-v1` (3 LLM-done + 9 in flight). The 14 non-cyber backfilled
  books are parked in archived `cysa-backlog-v1` (restore = delete the
  registry row in `archived_corpora`).
- **Three-layer graph / latent miner / query modes: IGNORED.**
- Relation ontology: the 17 predicates + RELATED_TO — enforced at prompt and
  gate. Adaptive limiter: per-(provider,key), AIMD, buckets, breaker — built.
- GLiNER retired from the LLM path (rollback only). Control plane is the
  single authority; no second control-plane tables.

## Environment

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
export POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
# stores are docker (postgres/neo4j/redis/qdrant); fleet:
env POLYMATH_PG_DSN="$POLYMATH_PG_DSN" POLYMATH_PROFILE=pipeline \
  POLYMATH_RELATION_PIPELINE=kimi_v1 POLYMATH_PREDICATE_V2=enforce \
  POLYMATH_SYNTAX_PROVIDER=spacy nohup bash scripts/boot_polymath.sh \
  > /tmp/polymath_fleet/bootX.log 2>&1 & disown
# local 4B sidecar (batched): sidecars/local_extractor/batched_server.py 8755
# provider env in .env: POLYMATH_WORKER_EXTRACTION_PROVIDER=llm_live
```

Rules: fence after every commit (bundle embeds git HEAD — restart workers or
claims are refused). launchctl no-ops under ~/Documents. pkill leaves PG
backends — sweep before DDL. max_connections=250 is set in compose.yaml.

## Goal (work until ALL are true, then write the final report)

1. **Book wave completes**: all extract tickets for `cysa-study-v1` reach
   `done`, all 12 runs reach `query_ready`. Record per-book wall times and
   the lane each used. Poller pattern: /tmp/wave_poll.log.
2. **Kill→resume drill**: kill the extract worker mid-book once; verify the
   lease reaper re-arms, the book re-extracts idempotently, and no duplicate
   facts/receipts appear (count facts before/after).
3. **True canary timing**: the 813,984 B `Intelligence-Driven Incident
   Response.md` gets one clean generation bump with an unpolluted clock
   (t0=bump, t1=run query_ready). Target ≤8 min; report the number either way.
4. **Quality sampling**: `scripts/llm_quality_sample.py --corpus
   cysa-study-v1 --sample 60` → attestation rate; plus a 10-fact
   human-judgeable sample written to `/tmp/llm_fact_sample.md` (fact +
   verbatim evidence quote + source) for the owner to judge.
5. **Register items 3–6**, in order, each with tests + commit:
   - `scripts/ingest_cli.py` (add/run/status/resume/cancel/report,
     --tier volume|quality|both, --max-docs, --keep-model)
   - extractor_version stamping for LLM-era facts + parent-level resume
   - corpus_entities + entity_links migration (merge ladder: exact → alias →
     cluster → keep-separate; provenance arrays; deletion-safe)
   - digest → parent routing cards (compiled parent summaries into the
     retrieval routing index; the corpus mapping layer payoff)
6. **Keep the register and work log updated before/after each task.** Never
   delete register lines. Never hardcode evaluation fixtures into gates.
   Never claim held-out/qualified — everything is development evidence.

## Non-goals (owner-ignored)

Three-layer graph modes, latent miner, P6 UI, 4,500-doc corpus, two-tier
volume/quality, Ollama-as-local-engine.

## Final report (write to docs/wiki/work-log/ same day)

Per-book timings + lanes · canary SLO number · drill result · sampler
verdict · register delta (statuses moved) · remaining MISSING lines · spend
(tokens per book from artifacts; no price cap exists).
