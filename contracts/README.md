# Contracts

The single source of truth for every cross-process boundary. Every
schema here is versioned, and the version is the contract. Code that
drifts from the schema is wrong.

## Layout

```
contracts/
├── sidecar/
│   └── v1/                : the sidecar contract (ADR-0005)
├── ingestion/
│   └── v1/                : intake events, run lifecycle
└── extraction/
    └── v1/                : relation candidates, fact/evidence
```

A contract at version N is frozen the day N is released. Breaking
changes require N+1. Additive changes are allowed within N with
backwards-compatible JSON Schema rules (additionalProperties, etc.).

## How to add a contract

1. Find the right domain folder.
2. Bump the version if the existing one is frozen.
3. Write `<thing>.schema.json` with `$id`, `title`, `description`.
4. Write `<thing>.example.json` with a valid instance.
5. Add a test in `tests/contracts/` that validates the example against
   the schema and checks invariants the schema can't express.
