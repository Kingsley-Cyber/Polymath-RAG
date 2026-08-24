"""SUMMARY-WORKER-FLEET-V1: the durable worker for the four background
intelligence stages (PARENT_SUMMARY / DOCUMENT_SUMMARY / CORPUS_MAPPING
/ VOCABULARY_MAPPING).

Until now these stages existed as library functions driven only by
tests and replay scripts; the control plane emitted their events but no
process consumed them. This worker closes that gap: it claims all four
stage event types and delegates to DB-driven assembly + the existing
run_*_ticket contracts (see summary_worker_impl).
"""
from __future__ import annotations

from polymath_shared.worker_runtime import run_worker

from workers.summary_worker_impl import process_event


def main() -> None:
    run_worker(
        "summaries",
        ["parent_summary.v1", "document_summary.v1",
         "corpus_summary.v1", "vocabulary.v1"],
        process_event,
    )


if __name__ == "__main__":
    main()
