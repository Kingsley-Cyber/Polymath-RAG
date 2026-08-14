# Sidecar Registry

Each `.toml` file in this directory registers one sidecar. The
orchestrator reads this directory at boot and refuses to start if
duplicate names or unpinned releases are found.

## Schema

```toml
[name]
display_name = "human readable"
release = "1.0.0"
manifest_url = "http://host:port/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "cuda" | "mps" | "cpu"
owner = "sidecar-gpu" | "sidecar-cpu"
```

`release` must match the version in the sidecar's manifest. A
mismatch causes the orchestrator to refuse the sidecar at boot.

## Hot reload

The orchestrator accepts SIGHUP. On SIGHUP it re-reads this
directory, re-fetches every manifest, and updates the routing table.
No restart required.
