from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from trail_signal.kernel.contracts import (
    BoundaryModel,
    Identifier,
    ReasonCode,
    Sha256,
    WorkEnvelopeV1,
)

PositiveInt = Annotated[int, Field(strict=True, ge=1)]
CandidateLimit = Annotated[int, Field(strict=True, ge=1, le=64)]
PageNumber = Annotated[int, Field(strict=True, ge=1, le=10)]
ResponseByteCount = Annotated[int, Field(strict=True, ge=2, le=131_072)]
RawResponseByteCount = Annotated[int, Field(strict=True, ge=2, le=2_097_152)]
DiscoveryQuery = Annotated[str, StringConstraints(min_length=1, max_length=512)]
DiscoveryCategory = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=48,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    ),
]
DiscoveryLanguage = Annotated[
    str,
    StringConstraints(
        min_length=2,
        max_length=16,
        pattern=r"^(?:all|[a-z]{2}(?:-[A-Z]{2})?)$",
    ),
]
CandidateUrl = Annotated[str, StringConstraints(min_length=8, max_length=4096)]
CandidateCursor = Annotated[
    str,
    StringConstraints(pattern=r"^cursor:[A-Za-z0-9_-]{32,128}$"),
]

class DiscoveryTimeRange(StrEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


class DiscoverySourceFailureKind(StrEnum):
    POLICY_DENIED = "POLICY_DENIED"
    UPSTREAM_AUTH_DENIED = "UPSTREAM_AUTH_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"
    MALFORMED_UPSTREAM_RESPONSE = "MALFORMED_UPSTREAM_RESPONSE"
    UNSUPPORTED_UPSTREAM_RESPONSE = "UNSUPPORTED_UPSTREAM_RESPONSE"


class DiscoverySourceFailure(Exception):
    def __init__(
        self,
        kind: DiscoverySourceFailureKind,
        detail_code: str,
        *,
        http_status: int | None = None,
        retry_after_ms: int | None = None,
        raw_artifact_id: str | None = None,
        raw_artifact_content_hash: str | None = None,
        byte_count: int | None = None,
    ) -> None:
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", detail_code) is None:
            raise ValueError("discovery failure detail_code is invalid")
        if http_status is not None and not 400 <= http_status <= 599:
            raise ValueError("discovery failure HTTP status is invalid")
        if retry_after_ms is not None and not 0 <= retry_after_ms <= 86_400_000:
            raise ValueError("discovery failure retry delay is invalid")
        artifact_values = (
            raw_artifact_id,
            raw_artifact_content_hash,
            byte_count,
        )
        if any(value is not None for value in artifact_values) != all(
            value is not None for value in artifact_values
        ):
            raise ValueError("discovery failure raw artifact metadata is atomic")
        if byte_count is not None and not 0 <= byte_count <= 2_097_152:
            raise ValueError("discovery failure raw byte count is invalid")
        super().__init__(detail_code)
        self.kind = kind
        self.detail_code = detail_code
        self.http_status = http_status
        self.retry_after_ms = retry_after_ms
        self.raw_artifact_id = raw_artifact_id
        self.raw_artifact_content_hash = raw_artifact_content_hash
        self.byte_count = byte_count


def _identifier(prefix: str, material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}"


def derive_discovery_attempt_identifiers(
    attempt_message_id: Identifier,
) -> tuple[Identifier, Identifier, Identifier, Identifier]:
    """Derive physical-attempt ledger IDs from one workflow-owned message ID."""

    if re.fullmatch(r"^.+:attempt:([1-9][0-9]*)$", attempt_message_id) is None:
        raise ValueError(
            "discovery attempt message_id must end with :attempt:<positive-int>"
        )
    physical_attempt_id = _identifier(
        "discovery-attempt",
        f"physical-attempt|{attempt_message_id}",
    )
    receipt_id = _identifier(
        "engine-execution-receipt",
        f"engine-receipt|{attempt_message_id}",
    )
    decision_id = _identifier(
        "decision",
        f"discovery-policy|{attempt_message_id}",
    )
    cost_id = _identifier(
        "cost-observation",
        f"discovery-cost|{attempt_message_id}",
    )
    return physical_attempt_id, receipt_id, decision_id, cost_id


class DiscoveryRequestV1(BoundaryModel):
    request_id: Identifier
    query: DiscoveryQuery
    categories: tuple[DiscoveryCategory, ...]
    language: DiscoveryLanguage
    time_range: DiscoveryTimeRange | None
    safe_search: Literal[0, 1, 2]
    page_number: PageNumber
    maximum_candidates: CandidateLimit
    purpose_ref: Identifier
    idempotency_key: Identifier

    @field_validator("categories", mode="before")
    @classmethod
    def normalize_json_categories(cls, value: object) -> object:
        if type(value) is list:
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.query != " ".join(self.query.split()):
            raise ValueError("query must use canonical whitespace")
        if len(self.query.encode("utf-8")) > 512:
            raise ValueError("query exceeds the UTF-8 byte ceiling")
        if not self.categories:
            raise ValueError("at least one category is required")
        if (
            len(self.categories) != len(set(self.categories))
            or self.categories != tuple(sorted(self.categories))
        ):
            raise ValueError("categories must be unique and sorted")
        return self


class DiscoveryPolicyV1(BoundaryModel):
    policy_id: Identifier
    policy_version: Identifier
    source_policy_ref: Identifier
    endpoint_ref: Identifier
    engine_identity_ref: Identifier
    allowed_categories: tuple[DiscoveryCategory, ...]
    allowed_languages: tuple[DiscoveryLanguage, ...]
    maximum_query_bytes: Annotated[int, Field(strict=True, ge=1, le=512)]
    maximum_candidates: CandidateLimit
    maximum_page_number: PageNumber
    maximum_response_bytes: Literal[2_097_152] = 2_097_152
    timeout_milliseconds: Annotated[
        int,
        Field(strict=True, ge=100, le=120_000),
    ]
    classification_ref: Identifier
    retention_policy_ref: Identifier
    reason_codes: tuple[ReasonCode, ...]
    verified_at: datetime
    expires_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if (
            not self.allowed_categories
            or len(self.allowed_categories) != len(set(self.allowed_categories))
            or self.allowed_categories != tuple(sorted(self.allowed_categories))
        ):
            raise ValueError("allowed categories must be nonempty, unique, and sorted")
        if (
            not self.allowed_languages
            or len(self.allowed_languages) != len(set(self.allowed_languages))
            or self.allowed_languages != tuple(sorted(self.allowed_languages))
        ):
            raise ValueError("allowed languages must be nonempty, unique, and sorted")
        if not self.reason_codes:
            raise ValueError("discovery policy requires reason codes")
        if self.expires_at <= self.verified_at:
            raise ValueError("policy expiry must follow verification")
        if not self.lineage_parent_ids:
            raise ValueError("discovery policy requires lineage parents")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("policy lineage must be unique")
        return self


class UrlCandidateV1(BoundaryModel):
    candidate_id: Identifier
    result_id: Identifier
    operation_id: Identifier
    request_id: Identifier
    query: DiscoveryQuery
    rank: PositiveInt
    upstream_rank: PositiveInt
    url: CandidateUrl
    url_hash: Sha256
    title: str
    snippet: str
    source_engine: str | None
    source_category: str | None
    retrieved_at: datetime
    truncated: bool
    truncation_reason_codes: tuple[ReasonCode, ...]
    policy_decision_id: Identifier
    raw_artifact_id: Identifier
    raw_artifact_content_hash: Sha256
    engine_execution_receipt_id: Identifier
    cost_observation_id: Identifier
    record_class: Literal["OPERATIONAL_LEAD"] = "OPERATIONAL_LEAD"
    evidence_eligible: Literal[False] = False
    lineage_parent_ids: tuple[Identifier, ...]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 1024:
            raise ValueError("candidate title exceeds the UTF-8 byte ceiling")
        return value

    @field_validator("snippet")
    @classmethod
    def validate_snippet(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 4096:
            raise ValueError("candidate snippet exceeds the UTF-8 byte ceiling")
        return value

    @field_validator("source_engine", "source_category")
    @classmethod
    def validate_optional_source(cls, value: str | None) -> str | None:
        if value is not None and (
            not value or len(value.encode("utf-8")) > 128
        ):
            raise ValueError("candidate source value is outside its byte bound")
        return value

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if self.truncated != bool(self.truncation_reason_codes):
            raise ValueError(
                "truncation reasons are required exactly when candidate is truncated"
            )
        if len(self.truncation_reason_codes) != len(
            set(self.truncation_reason_codes)
        ):
            raise ValueError("truncation reasons must be unique")
        required = {
            self.request_id,
            self.policy_decision_id,
            self.raw_artifact_id,
            self.engine_execution_receipt_id,
            self.cost_observation_id,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("candidate lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("candidate lineage must be unique")
        if self.candidate_id in self.lineage_parent_ids or self.result_id in self.lineage_parent_ids:
            raise ValueError("candidate lineage cannot contain candidate or result self-edges")
        return self


def url_candidate_schema_hash() -> Sha256:
    canonical = json.dumps(
        UrlCandidateV1.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


class DiscoveryResultRefV1(BoundaryModel):
    result_id: Identifier
    operation_id: Identifier
    request_id: Identifier
    candidate_schema_hash: Sha256
    result_content_hash: Sha256
    raw_artifact_id: Identifier
    raw_artifact_content_hash: Sha256
    raw_response_byte_count: RawResponseByteCount
    candidate_count: Annotated[int, Field(strict=True, ge=0, le=64)]
    truncated: bool
    ordering: Literal["DISCOVERY_RANK_V1"] = "DISCOVERY_RANK_V1"
    engine_execution_receipt_id: Identifier
    policy_decision_id: Identifier
    cost_observation_id: Identifier
    retrieved_at: datetime
    system_recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_result_ref(self) -> Self:
        if self.retrieved_at > self.system_recorded_at:
            raise ValueError("retrieval cannot follow system recording")
        required = {
            self.request_id,
            self.raw_artifact_id,
            self.engine_execution_receipt_id,
            self.policy_decision_id,
            self.cost_observation_id,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("discovery result lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("discovery result lineage must be unique")
        if self.result_id in self.lineage_parent_ids:
            raise ValueError("discovery result lineage cannot contain its result self-edge")
        return self


class UrlCandidatePageV1(BoundaryModel):
    result: DiscoveryResultRefV1
    items: tuple[UrlCandidateV1, ...]
    returned_count: Annotated[int, Field(strict=True, ge=0, le=64)]
    has_more: bool
    next_cursor: CandidateCursor | None
    page_content_hash: Sha256
    response_byte_count: ResponseByteCount

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        if self.returned_count != len(self.items):
            raise ValueError("returned_count must match page items")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("next cursor is required exactly when more items exist")
        if self.returned_count > self.result.candidate_count:
            raise ValueError("page cannot return more than the durable result")
        result_identity = (
            self.result.result_id,
            self.result.operation_id,
            self.result.request_id,
            self.result.raw_artifact_id,
            self.result.raw_artifact_content_hash,
            self.result.engine_execution_receipt_id,
            self.result.policy_decision_id,
            self.result.cost_observation_id,
        )
        if any(
            (
                item.result_id,
                item.operation_id,
                item.request_id,
                item.raw_artifact_id,
                item.raw_artifact_content_hash,
                item.engine_execution_receipt_id,
                item.policy_decision_id,
                item.cost_observation_id,
            )
            != result_identity
            for item in self.items
        ):
            raise ValueError("every candidate must match the page result identity")
        ranks = tuple(item.rank for item in self.items)
        if ranks and ranks != tuple(range(ranks[0], ranks[0] + len(ranks))):
            raise ValueError("candidate ranks must be contiguous")
        return self


DiscoveryRequestWorkEnvelopeV1 = WorkEnvelopeV1[DiscoveryRequestV1]
DiscoveryResultRefWorkEnvelopeV1 = WorkEnvelopeV1[DiscoveryResultRefV1]
UrlCandidatePageWorkEnvelopeV1 = WorkEnvelopeV1[UrlCandidatePageV1]
