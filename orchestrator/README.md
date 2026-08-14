# Orchestrator

Dumb on purpose. The orchestrator is the HTTP surface. It does not
make scheduling decisions; the control plane does that. It does not
hold long-running jobs; workers do that. It validates inputs,
enqueues, and reads from the ledger.

## Layout

```
orchestrator/
└── orchestrator/
    ├── main.py       : FastAPI app
    ├── api/
    │   ├── intake.py : POST /ingest
    │   ├── chat.py   : POST /chat
    │   └── health.py : GET /health, /ready, /manifest
    ├── registry.py   : sidecar registry loader
    └── contracts.py  : Pydantic models
```

## What it does NOT do

- Schedule work. (Control plane.)
- Run long jobs. (Workers.)
- Load models. (Sidecars.)
- Hold business logic. (Workers + compiler.)
