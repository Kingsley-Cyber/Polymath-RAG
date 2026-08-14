# Control Plane

Separate process. Survives orchestrator restarts. Decides "what to do
next" based on the artifact census. Writes back to Postgres.

## Layout

```
control/
├── control/
│   ├── main.py        : entrypoint, systemd hooks
│   ├── heartbeat.py   : writes to control_heartbeats every tick
│   ├── census.py      : desired-vs-observed artifact census
│   ├── scheduler.py   : enqueues stage jobs based on census gaps
│   ├── supervisor.py  : watches sidecar /ready, restarts via systemd
│   └── contracts.py   : pydantic models for control-plane state
└── systemd/
    └── polymath-control.service
```

## What it does NOT do

- Serve user requests. (That's the orchestrator.)
- Hold business logic. (That's the workers.)
- Decide predicates. (That's the compiler.)
- Touch the GPU. (That's the sidecars.)

It is a scheduler + heartbeater. That's it.
