"""polymath-extraction-v1 — the LLM proposal packet.

Design (authoritative plan §4.3, adapted to the live checkout):

* One packet per neighborhood (a parent's child chunks, concatenated with
  ``[chunk:...]`` markers). Items stay per-neighborhood so provenance never
  mixes.
* Entities are flat (surface + verbatim quote) rather than index-encoded:
  at neighborhood scale (≤ ~1,200 words) the token cost of repeating a
  surface is bounded, and flat surfaces let the Python gate locate offsets
  without trusting model arithmetic. The model never computes offsets.
* Every entity and every relation carries a VERBATIM quote. The gate
  rejects anything not attested as an exact substring of the neighborhood.
  This is the safety guarantee: refusing unattested output, not trusting
  the model to never hallucinate.
* The routing digest rides in the same response — no second model pass.
  Latent links and prompt seeds are NOT part of the volume contract
  (decision: lean output is the speed lever; they are a quality-lane
  extension behind a later contract version).

Open vocabulary: entity ``type`` is free text proposed by the model. The
gate routes known types through the query policy and applies a documented
fallback (raw label preserved verbatim in the ledger and on every span) —
a niche domain must never fail extraction on the type list.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CONTRACT_ID = "polymath-extraction-v1"
PROFILES = ("volume", "quality")


class EntityProposal(BaseModel):
    """A source-attested entity mention."""

    surface: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=1, max_length=2000,
                       description="Verbatim source text containing the surface")

    @field_validator("surface", "quote")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RelationProposal(BaseModel):
    """A source-attested explicit triple candidate.

    ``predicate`` is the model's own verb phrase — evidence for the
    compiler, never the canonical predicate. Deterministic trigger
    localization and the predicate compiler decide what compiles.
    """

    subject: str = Field(min_length=1, max_length=200)
    predicate: str = Field(min_length=1, max_length=120)
    object: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=2000,
                       description="Verbatim source sentence(s) expressing the relation")
    # TYPED-CLAIMS-V1 (2026-09-03): what kind of lived claim the relation
    # reports, when it is one. None for ordinary facts. Read-time consumers
    # (EXPLORE rows, research skills) filter on it; retrieval ranking does not.
    claim_kind: Optional[Literal["friction", "behavior", "workaround", "purchase_language"]] = None

    @field_validator("subject", "predicate", "object", "quote")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RoutingDigest(BaseModel):
    """LLM routing digest — consumed by the corpus mapping layer, never
    answer evidence. Hard-capped: two sentences and at most three uses."""

    central_claim: str = Field(default="", max_length=500)
    main_mechanism: str = Field(default="", max_length=500)
    retrieval_uses: list[str] = Field(default_factory=list, max_length=3)


class ExtractionItem(BaseModel):
    """One neighborhood's proposals."""

    neighborhood_id: str = Field(min_length=1, max_length=200)
    entities: list[EntityProposal] = Field(default_factory=list, max_length=80)
    relations: list[RelationProposal] = Field(default_factory=list, max_length=60)
    digest: RoutingDigest = Field(default_factory=RoutingDigest)


class ExtractionPacket(BaseModel):
    """The full model response for one extraction call."""

    contract: str = Field(default=CONTRACT_ID)
    profile: str = Field(default="volume")
    items: list[ExtractionItem] = Field(min_length=1, max_length=8)

    @field_validator("contract")
    @classmethod
    def _contract_pin(cls, v: str) -> str:
        if v != CONTRACT_ID:
            raise ValueError(f"unknown contract: {v!r} (expected {CONTRACT_ID!r})")
        return v

    @field_validator("profile")
    @classmethod
    def _profile_pin(cls, v: str) -> str:
        if v not in PROFILES:
            raise ValueError(f"unknown profile: {v!r}")
        return v


class SanitizeResult(BaseModel):
    """Outcome of the SANITIZE stage — kept durable for quarantine triage."""

    ok: bool
    error_class: Optional[str] = None
    salvaged: bool = False
    raw_chars: int = 0
    detail: str = ""


# STRICT-SCHEMA-V1: the volume-profile packet as a strict JSON Schema for
# level-1 structured output (STRUCTURED-CAPABILITY-V1 "schema" endpoints;
# live-verified on Groq qwen/qwen3.8-27b). Deliberately boring: no oneOf,
# no dynamic keys, additionalProperties false everywhere, every property
# required (strict-mode rule). The LOCAL gate remains the contract —
# this only raises the floor of what the provider returns.
EXTRACTION_JSON_SCHEMA: dict = {
    "name": "polymath_extraction_v1",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["contract", "profile", "items"],
        "properties": {
            "contract": {"type": "string"},
            "profile": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["neighborhood_id", "entities",
                                 "relations", "digest"],
                    "properties": {
                        "neighborhood_id": {"type": "string"},
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["surface", "type", "quote"],
                                "properties": {
                                    "surface": {"type": "string"},
                                    "type": {"type": "string"},
                                    "quote": {"type": "string"},
                                },
                            },
                        },
                        "relations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["subject", "predicate",
                                             "object", "quote"],
                                "properties": {
                                    "subject": {"type": "string"},
                                    "predicate": {"type": "string"},
                                    "object": {"type": "string"},
                                    "quote": {"type": "string"},
                                    "claim_kind": {"type": ["string", "null"],
                                                   "enum": ["friction", "behavior", "workaround", "purchase_language", None]},
                                },
                            },
                        },
                        "digest": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["central_claim", "main_mechanism",
                                         "retrieval_uses"],
                            "properties": {
                                "central_claim": {"type": "string"},
                                "main_mechanism": {"type": "string"},
                                "retrieval_uses": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}
