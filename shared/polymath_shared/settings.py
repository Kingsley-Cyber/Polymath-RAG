"""Typed settings (ISSUES_REPORT §4.5 fix).

Every env var is a typed, documented setting. The compose file stays a
topology file; policy lives here. Secrets stay in the environment and
are never logged.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore")
    env: str = Field(default="local", description="local | prod")
    log_level: str = Field(default="INFO")
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    stores: StoreSettings = Field(default_factory=StoreSettings)
    sidecars: SidecarSettings = Field(default_factory=SidecarSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    control: ControlSettings = Field(default_factory=ControlSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
