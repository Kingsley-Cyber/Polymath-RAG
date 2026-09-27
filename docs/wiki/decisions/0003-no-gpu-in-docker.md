---
owner: sidecar-gpu
last_reviewed: 2026-09-27
last_touched: 2026-09-27
status: accepted
---

# ADR-0003: No GPU in Docker

## Context

v3.3 ran the embedder and reranker inside Docker on the Mac. The GPU
is host-native. The mismatch produced a poisoned-CUDA-context failure
mode where the `/health` endpoint reported healthy for 12+ hours while
every `/embeddings` call returned 500. The fix in v3.3 was a band-aid
(`/health` does a 1-token forward pass). The band-aid does not scale
to the next sidecar someone adds.

## Decision

Every GPU service is a host-native process supervised by systemd
(Linux) or launchd (macOS). The Docker compose file contains exactly
the data stores: Postgres, Qdrant, Neo4j, Redis.

The sidecar registry (`sidecars/*.toml`) is the source of truth for
"where does service X live." Compose service names are only used for
the data stores, which are actually stable.

## Consequences

Easier:
- CUDA context poisoning is a host problem now. The orchestrator only
  sends traffic to sidecars whose `/ready` endpoint says "I can serve
  traffic." The supervisor restarts failed sidecars via systemd, not
  via a Docker autoheal band-aid.
- `/ready` is a real readiness probe (1-token forward pass). `/health`
  is a separate liveness probe (process is alive). The two are
  different and the orchestrator respects the difference.
- The contract surface is uniform across GPU and CPU sidecars. Same
  manifest, same `/ready`, same release pinning.

Harder:
- Two supervisor systems: systemd on the RTX box, launchd on the Mac.
  Each sidecar ships two unit templates.
- The Mac has both Apple MLX (for chat) and CUDA (none, but in the
  future maybe) paths. The contract is the same; the runtime is
  different.

## Triggered refactors

- `docs/wiki/refactors/0004-compose-shrink-to-stores.md`
- `docs/wiki/refactors/0005-sidecar-supervisor.md`

## Amendment — 2026-09-27 (SUPPLIER-APIS, register 11.537)

The owner added one auxiliary service. The rule this ADR protects, that GPU services are host-native, is unchanged:

- Compose may also hold a **non-GPU auxiliary service behind an opt-in profile**. The first is `searxng` (profile `search`,
  loopback `127.0.0.1:8888`, 0.5 CPU / 256 MB). It is the metasearch the supplier step uses to find Alibaba listings from
  search-engine results, so Alibaba's own pages, and their human checks, are never loaded.
- `make db-up` and a plain `docker compose up` still start exactly the four data stores. The owner starts the auxiliary service
  with `docker compose --profile search up -d searxng`.
- An auxiliary service never holds state Polymath depends on. When it is down, its caller falls back and says so (the Alibaba
  listing step falls back to the browser path, noting it in `limitations`).

