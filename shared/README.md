# Shared library

Used by orchestrator, workers, control, and sidecars. Holds the
contracts every process depends on.

## Modules

- `identity.py`: content-hash identity for documents, chunks,
  entities, facts, evidence. Use this. Do not call hashlib directly.
- `receipts.py`: durable write + receipt + status transition in a
  single transaction. Use this. Do not write receipts by hand.
- `contracts.py`: Pydantic models for every cross-process record.
- `logging.py`: structured JSON logging.
- `clients.py`: typed HTTP clients for sidecars. Use this. Do not
  hand-roll requests.
