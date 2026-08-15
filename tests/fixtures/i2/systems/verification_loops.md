# Verification Loops

A verification loop reconciles projected state against authoritative state. It compares desired artifacts with store contents and classifies differences as missing or orphaned.

When the store lost an artifact, the verification loop clears the corresponding receipt so the scheduler can re-drive the projector. When the store holds an orphan artifact, the loop deletes it.

Receipts are the commit point for projections. A crash between a graph write and its receipt leaves an orphan that verification detects; silence is never acceptance.

The loop must distinguish intentional absence from loss. Facts whose endpoints never earned durable identity are parked in the authoritative store and are not projection failures.
