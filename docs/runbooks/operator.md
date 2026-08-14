# Operator Runbook

Day-2 operations. The skeleton scaffolds this; the runbook fills in
over time as incidents happen.

## Restart a sidecar

```bash
# Find which unit controls the sidecar
systemctl list-units 'polymath-*'

# Restart it
sudo systemctl restart polymath-sidecar-gliner-entity

# Watch the log
journalctl -u polymath-sidecar-gliner-entity -f
```

## Restart the control plane

```bash
sudo systemctl restart polymath-control
journalctl -u polymath-control -f
```

## Check sidecar health

```bash
curl -s http://127.0.0.1:8737/manifest | jq
curl -s http://127.0.0.1:8737/ready | jq
```

A `ready: false` means the sidecar is alive but cannot serve traffic.
A `manifest: 500` means the sidecar failed to load its model.

## Diagnose stuck runs

```bash
psql -h 127.0.0.1 -U polymath -d polymath -c "
  SELECT run_id, corpus_id, status, last_stage
  FROM runs
  WHERE status NOT IN ('query_ready', 'failed')
  ORDER BY updated_at DESC
  LIMIT 20;
"
```

If a run is stuck in `reconciling` for more than the control plane's
max-tick window (default 5 minutes), file an issue.
