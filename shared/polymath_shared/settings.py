"""Typed settings (ISSUES_REPORT §4.5 fix).

Every env var is a typed, documented setting. The compose file stays a
topology file; policy lives here. Secrets stay in the environment and
are never logged.
"""
from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_PG_", extra="ignore")
    dsn: str = Field(
        default="postgresql://polymath:polymath@127.0.0.1:5432/polymath",
        description="libpq DSN for the workflow authority",
    )


class SidecarSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore")
    gliner_url: str = Field(default="http://127.0.0.1:8740", description="GLiNER two-pass runtime")
    embedder_url: str = Field(default="http://127.0.0.1:8742", description="Embedder sidecar")
    reranker_url: str = Field(default="http://127.0.0.1:8743", description="Reranker sidecar")
    spacy_url: str = Field(default="http://127.0.0.1:8744", description="spaCy syntax sidecar (syntax-evidence-v1)")
    syntax_provider: str = Field(
        default="disabled",
        description="Optional syntax-evidence lane behind the extract "
                    "worker's GLiNER pass: 'disabled' (production default, "
                    "byte-identical behavior) or 'spacy'. When 'spacy', a "
                    "missing syntax sidecar fails LOUDLY — no silent "
                    "fallback (SYNTAX-BOOTSTRAP).",
    )
    g3_reranker: bool = Field(
        default=True,
        description="Cross-representation reranking over fused retrieval "
                    "candidates. PROMOTED TO DEFAULT by G3+G5 evidence "
                    "(2026-08-14); disable explicitly with POLYMATH_G3_RERANKER=0. "
                    "A missing reranker sidecar fails LOUDLY while enabled.",
    )
    sidecar_timeout_s: float = Field(default=60.0, description="Sidecar HTTP timeout")
    sidecar_pin_required: bool = Field(
        default=True,
        description="Refuse to call a sidecar whose manifest release differs from the registry pin",
    )


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_WORKER_", extra="ignore")
    poll_interval_s: float = Field(default=2.0, description="Outbox poll interval")
    batch_size: int = Field(default=8, description="Max outbox events per poll")
    claim_ttl_s: int = Field(default=300, description="Stage lease TTL")
    evidence_proposal_mode: str = Field(
        default="lexical",
        description="ADR-0008: 'lexical' (pass 2 abstains) or 'hybrid' "
                    "(GLiNER evidence proposals merge with lexical anchors)",
    )
    rule_pack_version: str = Field(
        # D2 / SCIENTIFIC-KAG-V1: docs/SEMANTIC_CONTRACTS.md declares
        # core-predicates-v1.4.0 (research predicates, 35-type backbone).
        # Earlier: v1.3.0
        # byte-frozen. Shipping 1.2.0 left I4R-D grammatical frame
        # arbitration INERT in production while the documentation said it
        # was enforced -- the drift that SEMANTIC-RUNTIME-INTEGRITY-V1
        # now makes fatal at boot. 1.3.0 adds `frames:` to has_role and
        # leads; both are NARROWING (they require specific dependency
        # patterns), so the change can only refuse, never admit more.
        default="1.4.0",
        description="Deterministic rule pack version for extraction. "
                    "1.0.1 = frozen Q1 production baseline; 1.1.0 = "
                    "candidate realistic-prose baseline (Q1-R).",
    )
    chunker: str = Field(
        default="legacy_v1",
        validation_alias=AliasChoices("chunker", "POLYMATH_CHUNKER"),
        description="Chunking provider (SEMANTIC-CHUNKING-V2): "
                    "legacy_v1 (production default) or semantic_v2 "
                    "(qualification candidate; promotion is separately "
                    "authorized).",
    )


class ControlSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_CONTROL_", extra="ignore")
    tick_interval_s: float = Field(default=10.0, description="Census tick interval")
    lease_ttl_s: int = Field(default=30, description="Controller lease TTL")
    max_attempts: int = Field(default=3, description="Stage attempts before failed")


class StoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore")
    qdrant_url: str = Field(default="http://127.0.0.1:6334", description="Qdrant projection store")
    neo4j_uri: str = Field(default="bolt://127.0.0.1:7688", description="Neo4j projection store")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="polymath-dev", description="Neo4j password (override in .env)")
    embedding_contract_id: str = Field(
        default="hash-embed-v1",
        description="Active embedding contract id (a new id = a new index version)",
    )


class RescueSettings(BaseSettings):
    """I4R rescue policy (POLYMATH_RESCUE). 'off' (production default)
    is byte-identical extraction. 'on' enables every stage; a comma list
    enables a subset: boundary, missing_argument, type_reconciliation,
    frames. Any enabled stage requires POLYMATH_SYNTAX_PROVIDER=spacy
    and fails loudly when syntax evidence is unavailable."""

    RESCUE_STAGES: ClassVar[tuple[str, ...]] = (
        "boundary", "missing_argument", "type_reconciliation", "frames",
    )

    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore")
    rescue: str = Field(default="off", description="Rescue policy stages (I4R)")

    def enabled_stages(self) -> tuple[str, ...]:
        value = self.rescue.strip()
        if value == "off":
            return ()
        if value == "on":
            return self.RESCUE_STAGES
        stages = tuple(s.strip() for s in value.split(",") if s.strip())
        unknown = [s for s in stages if s not in self.RESCUE_STAGES]
        if unknown:
            raise ValueError(f"unknown POLYMATH_RESCUE stages: {unknown}")
        return stages

    def stage_enabled(self, stage: str) -> bool:
        return stage in self.enabled_stages()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore")
    env: str = Field(default="local", description="local | prod")
    log_level: str = Field(default="INFO")
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    stores: StoreSettings = Field(default_factory=StoreSettings)
    sidecars: SidecarSettings = Field(default_factory=SidecarSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    # Field name deliberately != "rescue": POLYMATH_RESCUE belongs to the
    # nested RescueSettings field, and a colliding outer name would make
    # pydantic-settings JSON-decode the stage string as a nested model.
    rescue_policy: RescueSettings = Field(default_factory=RescueSettings)
    control: ControlSettings = Field(default_factory=ControlSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
