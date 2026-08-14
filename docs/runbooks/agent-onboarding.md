# Agent Onboarding

You are an AI agent (or a new human). Before you touch any code:

## 1. Read in order

1. `AGENTS.md`: the contract.
2. `ARCHITECTURE.md`: the topology.
3. `architecture/dependencies.json`: ownership and allowed edges.
4. `PLAN.md`: dependency-ordered work.
5. `docs/wiki/decisions/0001-use-gliner-2pass.md`: the load-bearing
   decision (the one this repo was built around).
6. The ADR, refactor, and latest work log for the selected slice.

## 2. Run preflight

```bash
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

It will fail if the skeleton is incomplete or your environment is
wrong. Fix every failure before writing code.

## 3. Find the file you need

The TREE constant in `scripts/scaffold_polymath_v4.py` is the
authoritative list of where files go. Do not invent paths. If you
need a new path, that is a refactor (see step 4).

## 4. Need to change the architecture?

Open an ADR and its triggered refactor first. Declare both paths in the
scaffold `TREE`, update `architecture/dependencies.json` if an owner or edge
changes, append `ARCHITECTURE_CHANGELOG.md`, and add a work-log entry. Do not
silently edit `ARCHITECTURE.md`.

## 5. Need to add a file?

Find the right `TREE` entry. If it does not exist, write the refactor and work
log, add the content block plus `TREE` entry, and run the scaffold. Do not
create an undeclared path by hand.

## 6. Write code

Use:
- `shared/polymath_shared/identity.py` for every content hash.
- `shared/polymath_shared/receipts.py` for every durable write.
- `shared/polymath_shared/contracts.py` for every cross-process call.

Do not call hashlib directly. Do not write receipts by hand. Do not
construct HTTP requests to sidecars without going through
`shared/polymath_shared/clients.py`.

## 7. Verify

```bash
pytest tests/determinism/
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

Both must pass. CI will reject the PR if either is red.
