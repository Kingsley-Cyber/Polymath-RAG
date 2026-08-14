---
owner: sidecar-gpu
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# ADR-0005: Sidecar contract v1

## Context

v3.3 had 11 different discovery mechanisms for "where is service X":
compose service names, `host.docker.internal`, LAN IPs, env vars. Some
were stable, most weren't. Every "why is the RTX box unreachable" was
a 30-minute grep through compose files and env vars.

## Decision

Every sidecar (GPU or CPU) exposes the same five endpoints and ships
a manifest that pins its identity:

- `GET  /manifest`: `{identity, wire, health, signature}`. The
  manifest is published on first response and cached by the
  orchestrator. Manifest mismatch = refuse to call.
- `GET  /health`: liveness. Process is alive. Trivial.
- `GET  /ready`: readiness. The sidecar can serve traffic *right
  now*. For GPU sidecars, this does a 1-token forward pass on every
  probe to catch poisoned CUDA contexts.
- `POST /infer`: the actual work. Schema in the manifest.
- `GET  /metrics`: Prometheus. Optional in v1.

The orchestrator reads `sidecars/*.toml` at boot, fetches each
manifest, pins a release identity, and refuses to route traffic to
sidecars whose manifest doesn't match the pin.

## Consequences

Easier:
- One discovery mechanism for everything. The `sidecars/*.toml` files
  are the source of truth.
- "Why is the RTX box unreachable" becomes "read the toml file."
- Adding a new sidecar is three things: write `sidecars/<name>.toml`,
  write `sidecars/<name>/server.py`, restart the orchestrator (or
  SIGHUP it for hot reload). No compose change.

Harder:
- The contract has to be enforced. The first PR that adds a sidecar
  with `/health` doing trivial checks instead of real work is the
  beginning of the v3.3 mess again.
- TLS is out of scope for v1. LAN-only deployment is assumed. When
  that changes, the manifest gains a `tls:` section.

## Triggered refactors

- `docs/wiki/refactors/0007-sidecar-registry-loader.md`
