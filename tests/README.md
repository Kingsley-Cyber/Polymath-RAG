# Tests

Three buckets, by what they protect.

- `contracts/`: every JSON schema validates. Examples and
  hand-written negative cases.
- `determinism/`: given the same input, the same output. Canonical
  hashing, idempotent retries, receipt-stable writes.
- `integration/`: end-to-end flows. Slower. Gated to nightly.
