# I2 Corpus-Scale Integrity Qualification — REPORT (FAIL)

Frozen 2026-08-15. Verifier: eval/i2/verify_i2.py.
Fixture: tests/fixtures/i2/ (SHA256SUMS + FROZEN.json).

Verdict: FAIL — queryability gate ("unsupported questions abstain").

Passing: fixture integrity, baseline ingestion (28/28 query_ready,
50s, 0 retries), durable census (eligibility-aware exact), admission
scale census, generic-hub check (no mega-hubs), identity invariants
(4/4 classes on persisted rows), corpus isolation (0 cross-corpus
leaks), replay idempotency (submitted=0, semantic hash identical).

Failing: unsupported query returns 96 cited text passages
(abstained=False). Owning layer: TEXT lane support rule in
answer_synthesis.py + unbounded bundle text items in
evidence_assembly.py. No patch applied.

Not run (stop rule): determinism, failure convergence, Qdrant/Neo4j
reconstruction, content versioning, provenance sampling.
