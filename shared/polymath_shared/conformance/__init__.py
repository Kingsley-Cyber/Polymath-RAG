"""PRODUCTION-CONFORMANCE-AUDIT-V1 — discover, prove, retire.

A re-firable audit framework. The rule that shapes every module here: **nothing about
the current provider topology is hardcoded**. Providers, models, accounts, lanes,
workers, routes and durable state are DISCOVERED from configuration, the database, the
running processes and the code graph on every run — so replacing a model or a provider
means editing config and re-firing, never editing audit logic.

Layers (see docs/wiki/plans/PRODUCTION-CONFORMANCE-AUDIT-V1.md):
    discovery  — what exists, from live sources
    execgraph  — entrypoint -> ... -> durable state, and the reverse reader graph
    classify   — one state per component, where NOT_TESTED is never green
    attempts   — provider attempt vs function outcome reconciliation
    report     — the durable audit bundle
"""

AUDIT_VERSION = "conformance-audit-v1"

__all__ = ["AUDIT_VERSION"]
