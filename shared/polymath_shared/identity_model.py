"""STEP 1 — DEDUP IDENTITY MODEL: deterministic key derivation.

Pure functions. Source identity (document fingerprint) is separate from
processing identity (artifact hash). Entity keys are corpus-isolated by
construction. Fact keys are semantic triples, so new wording GROWS
evidence instead of duplicating.
"""
from __future__ import annotations

import hashlib


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_fingerprint(*, normalized_content: str, corpus_id: str) -> str:
    """Source identity: same knowledge source => same fingerprint,
    regardless of pipeline version."""
    return _sha256(normalized_content + "\n" + corpus_id)


def artifact_hash(*, document_fingerprint: str,
                  ingestion_contract_version: str,
                  extraction_version: str,
                  semantic_bundle_version: str) -> str:
    """Processing identity: same source + changed rules => regenerate
    derived artifacts, keep the raw document."""
    return _sha256("\n".join([document_fingerprint,
                              ingestion_contract_version,
                              extraction_version,
                              semantic_bundle_version]))


def entity_key(*, corpus_id: str, normalized_name: str,
               entity_type: str) -> str:
    """Corpus-isolated canonical entity identity."""
    return _sha256(corpus_id + "\n" + normalized_name + "\n" + entity_type)


def fact_key(*, subject_id: str, predicate: str, object_id: str) -> str:
    """Semantic-triple fact identity — wording never matters; evidence
    grows on the one canonical fact."""
    return _sha256(subject_id + "\n" + predicate + "\n" + object_id)
