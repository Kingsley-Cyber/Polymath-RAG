"""Typed settings (ISSUES_REPORT §4.5 fix).

Every env var is a typed, documented setting. The compose file stays a
topology file; policy lives here. Secrets stay in the environment and
are never logged.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: RUNTIME-CONFIG-CONTRACT-V1 (P21, 2026-08-28).
#:
#: There is ONE place a process gets its configuration: the environment,
#: seeded from the repo `.env`. It is resolved ABSOLUTELY, from this
#: file's location, because pydantic-settings resolves a relative
#: env_file against the working directory — and the orchestrator is
#: launched from `orchestrator/`, where no `.env` exists. That single
#: detail is why every settings class silently fell back to its
#: built-in defaults.
#:
#: MEASURED consequence: PostgresSettings.dsn defaulted to password
#: "polymath" while the deployment uses "polymath-dev", so a normally
#: launched orchestrator authenticated with the wrong credential and
#: every /retrieve returned HTTP 500 — 30s of pool timeouts per
#: request, with the real cause ("password authentication failed")
#: visible only in the server log.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_PG_", extra="ignore", env_file=_ENV_FILE, env_file_encoding="utf-8")
    dsn: str = Field(
        default="postgresql://polymath:polymath@127.0.0.1:5432/polymath",
        description="libpq DSN for the workflow authority",
    )


_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


class SidecarSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore", env_file=_ENV_FILE, env_file_encoding="utf-8")
    gliner_url: str = Field(default="http://127.0.0.1:8740", description="GLiNER two-pass runtime")
    embedder_url: str = Field(default="http://127.0.0.1:8742", description="Embedder sidecar")
    reranker_url: str = Field(default="http://127.0.0.1:8743", description="Reranker sidecar")
    spacy_url: str = Field(default="http://127.0.0.1:8744", description="spaCy syntax sidecar (syntax-evidence-v1)")
    local_llm_provider: str = Field(
        default="disabled",
        description="Future LOCAL-LLM-EXTRACTION-V1 connection provider: "
                    "'disabled' or 'ollama_local'. This setting does not "
                    "activate extraction.",
    )
    local_llm_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Loopback Ollama server used by the local-LLM connection probe",
    )
    local_llm_model: str = Field(
        default="",
        description="Exact locally installed Ollama model tag; required when enabled",
    )
    llm_local_extract_url: str = Field(
        default="http://127.0.0.1:8755",
        description="LOCAL-LLM-EXTRACTION-V1: OpenAI-compatible endpoint of the "
                    "local MLX extraction sidecar (loopback only)",
    )
    llm_local_extract_model: str = Field(
        default="mlx-community/Qwen3.5-4B-MLX-4bit",
        description="Pinned local extraction model served by the MLX sidecar",
    )
    llm_cloud_url: str = Field(
        default="http://127.0.0.1:11434",
        description="LOCAL-LLM-EXTRACTION-V1 cloud lane: OpenAI-compatible "
                    "endpoint (the local Ollama daemon proxies cloud models "
                    "under the signed-in account). Loopback enforced.",
    )
    llm_cloud_model: str = Field(
        default="qwen3.5:397b-cloud",
        description="Pinned cloud quality-lane model tag (verify with a "
                    "one-token probe; no document content in probes)",
    )
    llm_cloud_extra_endpoints: str = Field(
        default="",
        description="EXTRACTION-POOL-V1: additional cloud providers as a "
                    'JSON list [{"name","url","model"}]. Each joins the '
                    "deterministic doc->endpoint router with its own AIMD "
                    "limiter lane. The 300 KB owner boundary applies to "
                    "every endpoint here — extras widen throughput, never "
                    "eligibility.",
    )
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

    @model_validator(mode="after")
    def validate_llm_extraction_endpoints(self) -> "SidecarSettings":
        """LOCAL-LLM-EXTRACTION-V1 boundary: BOTH extraction endpoints are
        loopback, unconditionally. The 'local' lane carries every document
        at or below the 300 KB rule — a LAN host here would move those
        documents off the machine under a 'local' label; the 'cloud' lane
        is the local Ollama daemon (the daemon relays), never a remote
        URL configured from this process."""
        for name, url in (("POLYMATH_LLM_LOCAL_EXTRACT_URL", self.llm_local_extract_url),
                          ("POLYMATH_LLM_CLOUD_URL", self.llm_cloud_url)):
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or parsed.hostname not in _LOOPBACK_HOSTS:
                raise ValueError(
                    f"{name} must be a loopback URL (got {url!r}); the 300 KB "
                    "rule forbids extraction endpoints off this machine")
        return self

    @model_validator(mode="after")
    def validate_local_llm_connection(self) -> "SidecarSettings":
        provider = self.local_llm_provider.strip()
        if provider not in ("disabled", "ollama_local"):
            raise ValueError(f"unknown local LLM provider: {provider}")
        if provider == "disabled":
            return self
        if not self.local_llm_model.strip():
            raise ValueError(
                "POLYMATH_LOCAL_LLM_MODEL is required when the local LLM provider is enabled"
            )
        parsed = urlparse(self.local_llm_url)
        if parsed.scheme not in ("http", "https") or parsed.hostname not in (
            "127.0.0.1", "localhost", "::1",
        ):
            raise ValueError(
                "POLYMATH_LOCAL_LLM_URL must be loopback for ollama_local"
            )
        return self


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_WORKER_", extra="ignore", env_file=_ENV_FILE, env_file_encoding="utf-8")
    poll_interval_s: float = Field(default=2.0, description="Outbox poll interval")
    batch_size: int = Field(default=8, description="Max outbox events per poll")
    claim_ttl_s: int = Field(default=300, description="Stage lease TTL")
    evidence_proposal_mode: str = Field(
        default="lexical",
        description="ADR-0008: 'lexical' (pass 2 abstains) or 'hybrid' "
                    "(GLiNER evidence proposals merge with lexical anchors)",
    )
    extraction_provider: str = Field(
        default="gliner",
        description="LOCAL-LLM-EXTRACTION-V1: 'gliner' (frozen default, "
                    "byte-identical behavior), 'llm_shadow' (LLM proposals "
                    "recorded, nothing admitted), or 'llm_live' (LLM "
                    "proposals enter the unchanged admission pipeline).",
    )
    enrichment_auto: bool = Field(
        default=True,
        description="AUTO-ENRICH-ON-INGEST: mint parent_enrichment on "
                    "run promotion to query_ready (census tick = the "
                    "control timer). Buttons remain the gap-filler.")
    enrichment_provider: str = Field(
        default="llm",
        description="parent_enrichment stage: 'llm' (the pinned cloud "
                    "group) or 'disabled' (stage returns DISABLED)")
    enrichment_profile: str = Field(
        default="qualification",
        description="EnrichmentBounds profile: qualification (700 tok) "
                    "or production (900 tok)")
    enrichment_input_token_ceiling: int = Field(
        default=6000,
        description="Reject (durable INVALID) any parent whose rendered "
                    "enrichment input exceeds this — never truncate")
    latent_retrieval_enabled: bool = Field(
        default=True,
        description="Query-time latent rescue default for HYBRID/GRAPH "
                    "(per-request `latent` flag overrides). OWNER GO "
                    "2026-08-31 on P6: survival 78%, +3.0 evidence/case, "
                    "~20 ms delta. FAST stays the frozen baseline.")
    cloud_min_bytes: int = Field(
        default=300_000,
        ge=300_000,
        description="Owner rule 2026-08-29: documents at or below this size "
                    "can never select or dispatch a cloud provider "
                    "(enforced at selection AND dispatch, fail closed). "
                    "300,000 is a FLOOR: the value may be raised, never "
                    "lowered (policy.effective_threshold clamps again).",
    )
    llm_concurrency_local: int = Field(
        default=2, description="Parallel in-flight extraction calls, local lane")
    llm_concurrency_cloud: int = Field(
        default=6, description="Parallel in-flight extraction calls, cloud lane")
    llm_max_neighborhood_chars: int = Field(
        default=60_000,
        description="Target evidence-neighborhood size (~15K tokens, "
                    "owner directive 2026-08-29: large inputs on BOTH lanes "
                    "for speed). Builder balances to near-uniform buckets "
                    "under this cap; local 15K-token inputs measured clean.",
    )
    rule_pack_version: str = Field(
        # SPOKEN-RELATION-ADAPTER-V1: docs/SEMANTIC_CONTRACTS.md declares
        # core-predicates-v1.5.0 (`created` object signature gains
        # Technology — the creation class already accepted the typed
        # pair via `developed`; shadow-qualified 18/18 by
        # eval/v5/spoken_adapter_shadow.py with zero negative accepts).
        # Earlier: v1.4.0 (SCIENTIFIC-KAG-V1), v1.3.0
        # byte-frozen. Shipping 1.2.0 left I4R-D grammatical frame
        # arbitration INERT in production while the documentation said it
        # was enforced -- the drift that SEMANTIC-RUNTIME-INTEGRITY-V1
        # now makes fatal at boot. 1.3.0 adds `frames:` to has_role and
        # leads; both are NARROWING (they require specific dependency
        # patterns), so the change can only refuse, never admit more.
        default="1.5.0",
        description="Deterministic rule pack version for extraction. "
                    "1.0.1 = frozen Q1 production baseline; 1.1.0 = "
                    "candidate realistic-prose baseline (Q1-R).",
    )
    chunker: str = Field(
        default="tier_v3",
        validation_alias=AliasChoices("chunker", "POLYMATH_CHUNKER"),
        description="Chunking provider. tier_v3 (TIER-CHUNKER-V3, the "
                    "production default — owner GO 2026-08-31, latent "
                    "plan D15 Phase 0: heading-bounded parents with "
                    "real section text and heading_path, byte-exact "
                    "offsets); legacy_v1 (pre-Phase-0 baseline); "
                    "semantic_v2 (retired qualification candidate).",
    )


class ControlSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_CONTROL_", extra="ignore", env_file=_ENV_FILE, env_file_encoding="utf-8")
    tick_interval_s: float = Field(default=10.0, description="Census tick interval")
    lease_ttl_s: int = Field(default=30, description="Controller lease TTL")
    max_attempts: int = Field(default=3, description="Stage attempts before failed")
    extraction_coverage_floor: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="EXTRACTION-COVERAGE-V1 soft floor on parents_with_extraction/"
                    "parents_total. 0 = report only. Never blocks promotion "
                    "(zero yield is completion); breaches surface as warnings "
                    "in /semantic_readiness. Owner sets it from measured runs.",
    )


class StoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore", env_file=_ENV_FILE, env_file_encoding="utf-8")
    qdrant_url: str = Field(default="http://127.0.0.1:6334", description="Qdrant projection store")
    neo4j_uri: str = Field(default="bolt://127.0.0.1:7688", description="Neo4j projection store")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="polymath-dev", description="Neo4j password (override in .env)")
    embedding_contract_id: str = Field(
        default="neural-embed-v1",
        description=(
            "Production default embedding contract for NEW corpora "
            "(G1 owner decision 2026-08-25). Per-corpus authority lives "
            "in corpora.embedding_contract_id; this default applies only "
            "where a corpus has not been created yet. hash-embed-v1 "
            "remains available as deterministic test/fallback provider."
        ),
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

    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore", env_file=_ENV_FILE, env_file_encoding="utf-8")
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
    model_config = SettingsConfigDict(env_prefix="POLYMATH_", extra="ignore", env_file=_ENV_FILE, env_file_encoding="utf-8")
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
