"""Extract worker. The two-pass GLiNER + compiler.

Role: worker. Idempotent.

Order of operations:
  1. Call gliner-entity sidecar -> entity spans
  2. Call gliner-evidence sidecar -> evidence spans
  3. For each (entity_pair, evidence_class) candidate:
       a. Run UD parse
       b. Look up VerbNet/PropBank/FrameNet/SemLink
       c. Call the compiler (pure function)
       d. Persist CanonicalFact + EvidenceRecord
"""
from __future__ import annotations

import asyncio
import logging


logger = logging.getLogger(__name__)


async def handle_extract(job: dict) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_extract({}))
