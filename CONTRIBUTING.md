# Contributing

Read `AGENTS.md` first. It is the contract.

For humans:

1. Fork or branch.
2. Run `python3 scripts/agent_preflight.py` (yes, even humans).
3. Make the change.
4. Run the determinism test suite: `pytest tests/determinism/`.
5. Open a PR. The PR template will ask which ADR (if any) you are
   implementing.

For AI agents:

1. Read `AGENTS.md` §4 (reading order) before anything else.
2. Run `scripts/agent_preflight.py`.
3. Use the TREE constant in `scripts/scaffold_polymath_v4.py` as the
   authoritative list of where files go. Do not invent paths.
4. Use `shared/polymath_shared/identity.py` for every content hash.
   Do not call hashlib directly.
5. Use `shared/polymath_shared/receipts.py` for every durable write.
   Do not write receipts by hand.
