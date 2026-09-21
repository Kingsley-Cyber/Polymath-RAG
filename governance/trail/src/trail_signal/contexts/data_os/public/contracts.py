from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, Self
from pydantic import (
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)
from trail_signal.kernel.contracts import (
    BoundaryModel,
    Identifier,
    NonEmptyText,
    ReasonCode,
    Sha256,
    WireSchemaName,
    WorkEnvelopeV1,
)
PositiveInt = Annotated[int, Field(strict=True, ge=1)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
CurrencyCode = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{3}$"),
]
CanonicalText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=8192),
]
OpaqueResultCursor = Annotated[
    str,
    StringConstraints(pattern=r"^cursor:[A-Za-z0-9_-]{32,128}$"),
]
class SourceGapReason(StrEnum):
    POLICY_DENIED = "POLICY_DENIED"; DNS_DENIED = "DNS_DENIED"; REDIRECT_DENIED = "REDIRECT_DENIED"
    ROBOTS_DENIED = "ROBOTS_DENIED"; SOURCE_DENIED = "SOURCE_DENIED"; AUTH_REQUIRED = "AUTH_REQUIRED"
    TIMEOUT = "TIMEOUT"; RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"; RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
class GapValidationStage(StrEnum):
    PRE_CONNECT = "PRE_CONNECT"; REDIRECT = "REDIRECT"; RECONNECT = "RECONNECT"; SOURCE_POLICY = "SOURCE_POLICY"
class CapacityLeaseState(StrEnum):
    ACTIVE = "ACTIVE"; RELEASED = "RELEASED"; EXPIRED = "EXPIRED"
class ClassificationLevel(StrEnum):
    PUBLIC = "PUBLIC"; BUSINESS_INTERNAL = "BUSINESS_INTERNAL"; PERSONAL = "PERSONAL"
    SENSITIVE_PERSONAL = "SENSITIVE_PERSONAL"; AUTHENTICATED_CONFIDENTIAL = "AUTHENTICATED_CONFIDENTIAL"
    CREDENTIAL = "CREDENTIAL"
class RetentionDisposition(StrEnum):
    RETAIN = "RETAIN"; CRYPTO_ERASE = "CRYPTO_ERASE"; DELETE = "DELETE"
class DecisionType(StrEnum):
    ACQUISITION_ROUTE = "ACQUISITION_ROUTE"; CAPACITY_ADMISSION = "CAPACITY_ADMISSION"
    NETWORK_POLICY = "NETWORK_POLICY"; RETRY = "RETRY"; TERMINAL_REDUCTION = "TERMINAL_REDUCTION"
class CanonicalRecordKind(StrEnum):
    TITLE = "TITLE"; HEADING = "HEADING"; PARAGRAPH = "PARA" + "GRAP" + "H"
    LIST_ITEM = "LIST_ITEM"; BLOCK_QUOTE = "BLOCK_QUOTE"
    PREFORMATTED = "PREFORMATTED"; TABLE_CELL = "TABLE_CELL"
class CostUnit(StrEnum):
    REQUESTS = "REQUESTS"; BYTES = "BYTES"; RECORDS = "RECORDS"
    BROWSER_MILLISECONDS = "BROWSER_MILLISECONDS"; CPU_MILLISECONDS = "CPU_MILLISECONDS"
    MODEL_INPUT_TOKENS = "MODEL_INPUT_TOKENS"; MODEL_OUTPUT_TOKENS = "MODEL_OUTPUT_TOKENS"
    MEDIA_SECONDS = "MEDIA_SECONDS"; MONETARY_MICROS = "MONETARY_MICROS"
class CostEstimationStatus(StrEnum):
    MEASURED = "MEASURED"; ESTIMATED = "ESTIMATED"; NOT_APPLICABLE = "NOT_APPLICABLE"
class RawArtifactRefV1(BoundaryModel):
    artifact_id: Identifier
    artifact_state: Literal["COMPLETE"] = "COMPLETE"
    content_hash: Sha256
    byte_count: NonNegativeInt
    media_type: NonEmptyText
    blob_locator_ref: Identifier
    source_url_hash: Sha256
    attempt_receipt_id: Identifier
    policy_validation_id: Identifier
    classification_ref: Identifier
    retention_policy_ref: Identifier
    retrieved_at: datetime
    system_recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]
    source_event_at: datetime | None = None
    source_event_absence_reason: ReasonCode | None = None
    observed_at: datetime | None = None
    @model_validator(mode="after")
    def validate_artifact(self) -> Self:
        if self.retrieved_at > self.system_recorded_at:
            raise ValueError("retrieval cannot follow system recording")
        if not self.lineage_parent_ids:
            raise ValueError("raw artifact requires lineage parents")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("lineage_parent_ids must be unique")
        temporal_metadata_present = any(
            value is not None
            for value in (
                self.source_event_at,
                self.source_event_absence_reason,
                self.observed_at,
            )
        )
        if temporal_metadata_present:
            if self.observed_at is None or (
                (self.source_event_at is None)
                == (self.source_event_absence_reason is None)
            ):
                raise ValueError("complete source-time metadata is required")
            if self.source_event_at is not None and self.source_event_at > self.observed_at:
                raise ValueError("source event cannot follow observation")
            if self.observed_at > self.retrieved_at:
                raise ValueError("observation cannot follow retrieval")
        return self
class SourceGapV1(BoundaryModel):
    source_gap_id: Identifier
    operation_id: Identifier
    reason: SourceGapReason
    detail_code: ReasonCode
    validation_stage: GapValidationStage | None
    hop_ref: Identifier | None
    last_failure_class: ReasonCode | None
    attempt_receipt_ids: tuple[Identifier, ...]
    incomplete_content_hash: Sha256 | None
    incomplete_attempt_receipt_id: Identifier | None
    incomplete_policy_validation_id: Identifier | None
    incomplete_byte_count: NonNegativeInt | None
    incomplete_stop_reason: ReasonCode | None
    occurred_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]
    @model_validator(mode="after")
    def validate_gap(self) -> Self:
        network_policy_gap = self.reason in {
            SourceGapReason.POLICY_DENIED,
            SourceGapReason.DNS_DENIED,
        }
        if network_policy_gap and (
            self.validation_stage is None or self.hop_ref is None
        ):
            raise ValueError(
                "policy and DNS gaps require validation_stage and hop_ref"
            )
        if not network_policy_gap and (
            self.validation_stage is not None or self.hop_ref is not None
        ):
            raise ValueError("only policy and DNS gaps carry validation details")
        exhausted = self.reason == SourceGapReason.RETRY_EXHAUSTED
        if exhausted and (
            self.last_failure_class is None or not self.attempt_receipt_ids
        ):
            raise ValueError(
                "retry exhaustion requires last failure and attempt receipts"
            )
        if not exhausted and (
            self.last_failure_class is not None or self.attempt_receipt_ids
        ):
            raise ValueError("only retry exhaustion carries retry details")
        incomplete_values = (
            self.incomplete_content_hash,
            self.incomplete_attempt_receipt_id,
            self.incomplete_policy_validation_id,
            self.incomplete_byte_count,
            self.incomplete_stop_reason,
        )
        retained_incomplete = any(value is not None for value in incomplete_values)
        if retained_incomplete and not all(
            value is not None for value in incomplete_values
        ):
            raise ValueError("retained incomplete artifact metadata is atomic")
        if retained_incomplete and self.reason not in {
            SourceGapReason.INCOMPLETE_RESPONSE,
            SourceGapReason.RESPONSE_TOO_LARGE,
        }:
            raise ValueError(
                "only incomplete or oversized responses retain partial artifact metadata"
            )
        if len(self.attempt_receipt_ids) != len(set(self.attempt_receipt_ids)):
            raise ValueError("attempt_receipt_ids must be unique")
        if not self.lineage_parent_ids:
            raise ValueError("source gap requires lineage parents")
        return self
class AtomicCapacityClaimV1(BoundaryModel):
    claim_id: Identifier
    resource_key: Sha256
    capacity_units: PositiveInt
    owner_attempt_id: Identifier
    requested_at: datetime
    expires_at: datetime
    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if self.expires_at <= self.requested_at:
            raise ValueError("claim expiry must follow request time")
        return self
class AtomicCapacityLeaseRecordV1(BoundaryModel):
    lease_record_id: Identifier
    claim_id: Identifier
    resource_key: Sha256
    capacity_units: PositiveInt
    fence: PositiveInt
    owner_attempt_id: Identifier
    state: CapacityLeaseState
    issued_at: datetime
    expires_at: datetime
    released_at: datetime | None
    @model_validator(mode="after")
    def validate_lease_record(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("lease expiry must follow issue time")
        if self.state is CapacityLeaseState.RELEASED:
            if self.released_at is None or self.released_at < self.issued_at:
                raise ValueError("released lease requires a valid release time")
        elif self.released_at is not None:
            raise ValueError("only a released lease may have released_at")
        return self
class DataClassificationV1(BoundaryModel):
    classification_id: Identifier
    level: ClassificationLevel
    source_policy_ref: Identifier
    purpose_ref: Identifier
    reason_codes: tuple[ReasonCode, ...]
    classified_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]
    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        if not self.reason_codes:
            raise ValueError("classification requires a reason code")
        if not self.lineage_parent_ids:
            raise ValueError("classification requires lineage parents")
        return self
class RetentionPolicyV1(BoundaryModel):
    retention_policy_id: Identifier
    policy_version: Identifier
    classification_ref: Identifier
    source_policy_ref: Identifier
    purpose_ref: Identifier
    disposition: RetentionDisposition
    retain_until: datetime | None
    legal_hold: bool
    decided_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]
    @model_validator(mode="after")
    def validate_retention(self) -> Self:
        if self.disposition is RetentionDisposition.RETAIN:
            if self.retain_until is None and not self.legal_hold:
                raise ValueError("retention requires an expiry or legal hold")
        elif self.retain_until is not None or self.legal_hold:
            raise ValueError("erasure dispositions cannot retain or hold bytes")
        if self.retain_until is not None and self.retain_until <= self.decided_at:
            raise ValueError("retention expiry must follow decision time")
        if not self.lineage_parent_ids:
            raise ValueError("retention policy requires lineage parents")
        return self
class DecisionEventV1(BoundaryModel):
    decision_id: Identifier
    operation_id: Identifier
    workflow_id: Identifier
    task_id: Identifier | None
    correlation_id: Identifier
    causation_id: Identifier
    decision_type: DecisionType
    reason_codes: tuple[ReasonCode, ...]
    considered_options: tuple[Identifier, ...]
    selected_option: Identifier
    policy_version: Identifier
    configuration_version: Identifier
    code_version: Identifier
    numeric_input_names: tuple[Identifier, ...]
    numeric_input_values: tuple[Annotated[int, Field(strict=True)], ...]
    expected_effect: NonEmptyText
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]
    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if not self.reason_codes or not self.considered_options:
            raise ValueError("decision requires reasons and considered options")
        if self.selected_option not in self.considered_options:
            raise ValueError("selected option must be considered")
        if len(self.numeric_input_names) != len(self.numeric_input_values):
            raise ValueError("numeric input names and values must align")
        if (self.source_event_at is None) == (
            self.source_event_absence_reason is None
        ):
            raise ValueError(
                "source_event_at and source_event_absence_reason are mutually exclusive"
            )
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError("source event cannot follow observation")
        if not (
            self.observed_at <= self.retrieved_at <= self.system_recorded_at
        ):
            raise ValueError("decision times are out of order")
        if not self.lineage_parent_ids:
            raise ValueError("decision requires lineage parents")
        return self
class CostObservationV1(BoundaryModel):
    cost_observation_id: Identifier
    operation_id: Identifier
    task_id: Identifier | None
    source_ref: Identifier | None
    lane: Identifier | None
    provider_ref: Identifier | None
    unit: CostUnit
    quantity: NonNegativeInt
    currency: CurrencyCode | None
    monetary_micros: NonNegativeInt | None
    estimation_status: CostEstimationStatus
    pricing_table_version: Identifier | None
    started_at: datetime
    ended_at: datetime
    causation_id: Identifier
    lineage_parent_ids: tuple[Identifier, ...]
    @model_validator(mode="after")
    def validate_cost(self) -> Self:
        if self.ended_at < self.started_at:
            raise ValueError("cost interval end cannot precede start")
        if (self.currency is None) != (self.monetary_micros is None):
            raise ValueError("currency and monetary_micros must appear together")
        if (
            self.monetary_micros is not None
            and self.pricing_table_version is None
        ):
            raise ValueError("monetary cost requires a pricing table version")
        if self.unit is CostUnit.MONETARY_MICROS:
            if self.monetary_micros is None or self.quantity != self.monetary_micros:
                raise ValueError("monetary unit quantity must equal monetary_micros")
        if not self.lineage_parent_ids:
            raise ValueError("cost observation requires lineage parents")
        return self
SourceGapWorkEnvelopeV1 = WorkEnvelopeV1[SourceGapV1]
DecisionEventWorkEnvelopeV1 = WorkEnvelopeV1[DecisionEventV1]
CostObservationWorkEnvelopeV1 = WorkEnvelopeV1[CostObservationV1]


class SourceGapReasonV2(StrEnum):
    POLICY_DENIED = "POLICY_DENIED"
    DNS_DENIED = "DNS_DENIED"
    REDIRECT_DENIED = "REDIRECT_DENIED"
    ROBOTS_DENIED = "ROBOTS_DENIED"
    SOURCE_DENIED = "SOURCE_DENIED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TIMEOUT = "TIMEOUT"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    INVALID_TEXT_ENCODING = "INVALID_TEXT_ENCODING"
    EMPTY_CONTENT = "EMPTY_CONTENT"
    MALFORMED_DOCUMENT = "MALFORMED_DOCUMENT"
    NO_USABLE_CONTENT = "NO_USABLE_CONTENT"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"


class ParserGapStage(StrEnum):
    MEDIA_VALIDATION = "MEDIA_VALIDATION"
    TEXT_DECODING = "TEXT_DECODING"
    DOCUMENT_PARSE = "DOCUMENT_PARSE"
    CONTENT_NORMALIZATION = "CONTENT_NORMALIZATION"
    OUTPUT_VALIDATION = "OUTPUT_VALIDATION"


class DecisionTypeV2(StrEnum):
    ACQUISITION_ROUTE = "ACQUISITION_ROUTE"
    CAPACITY_ADMISSION = "CAPACITY_ADMISSION"
    NETWORK_POLICY = "NETWORK_POLICY"
    RETRY = "RETRY"
    TERMINAL_REDUCTION = "TERMINAL_REDUCTION"
    PARSER_SELECTION = "PARSER_SELECTION"
    RESULT_PAGE_AUTHORIZATION = "RESULT_PAGE_AUTHORIZATION"
    BATCH_ADMISSION = "BATCH_ADMISSION"
    BATCH_BACKPRESSURE = "BATCH_BACKPRESSURE"
    DATASET_COMMIT = "DATASET_COMMIT"


class OperationPrincipalSnapshotV1(BoundaryModel):
    snapshot_id: Identifier
    operation_id: Identifier
    principal_id: Identifier
    audit_identity: Identifier
    capabilities: tuple[Identifier, ...]
    policy_ref: Identifier
    budget_ref: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if (
            not self.capabilities
            or len(self.capabilities) != len(set(self.capabilities))
        ):
            raise ValueError(
                "operation principal capabilities must be nonempty and unique"
            )
        if self.expires_at <= self.authenticated_at:
            raise ValueError(
                "operation principal expiry must follow authentication"
            )
        required = {self.operation_id, self.principal_id}
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError(
                "operation principal lineage requires operation and principal"
            )
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("operation principal lineage must be unique")
        return self


class RawArtifactReadRequestV1(BoundaryModel):
    read_request_id: Identifier
    principal_id: Identifier
    artifact_id: Identifier
    extraction_request_id: Identifier
    parser_profile_ref: Identifier
    result_policy_ref: Identifier
    maximum_bytes: Annotated[int, Field(strict=True, ge=1, le=8388608)]
    purpose_ref: Identifier
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_read(self) -> Self:
        if not self.lineage_parent_ids:
            raise ValueError("verified raw read requires lineage parents")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("lineage_parent_ids must be unique")
        return self


class CanonicalDerivedRecordV1(BoundaryModel):
    record_id: Identifier
    result_id: Identifier
    artifact_id: Identifier
    ordinal: NonNegativeInt
    record_kind: CanonicalRecordKind
    text: CanonicalText
    content_hash: Sha256
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if len(self.text.encode("utf-8")) > 8192:
            raise ValueError("record text exceeds the UTF-8 byte ceiling")
        if not self.lineage_parent_ids:
            raise ValueError("derived record requires lineage parents")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("lineage_parent_ids must be unique")
        return self


class ResultPageRequestV1(BoundaryModel):
    request_id: Identifier
    principal_id: Identifier
    result_id: Identifier
    cursor: OpaqueResultCursor | None
    page_size: Annotated[int, Field(strict=True, ge=1, le=64)]


class ResultPageRequestV2(BoundaryModel):
    request_id: Identifier
    result_id: Identifier
    cursor: OpaqueResultCursor | None
    page_size: Annotated[int, Field(strict=True, ge=1, le=64)]


class ResultPageAuthorizationV1(BoundaryModel):
    authorization_id: Identifier
    principal_id: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_authorization(self) -> Self:
        if self.expires_at <= self.authenticated_at:
            raise ValueError(
                "result-page authorization expiry must follow authentication"
            )
        return self


class ResultPageTargetV1(BoundaryModel):
    target_id: Identifier
    authorization_id: Identifier
    principal_id: Identifier
    result_id: Identifier
    operation_id: Identifier
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        required = {
            self.authorization_id,
            self.result_id,
            self.operation_id,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError(
                "result-page target requires authorization, result, and operation lineage"
            )
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("result-page target lineage must be unique")
        return self


def upcast_result_page_request_v1(
    value: ResultPageRequestV1,
) -> ResultPageRequestV2:
    return ResultPageRequestV2.model_validate(
        value.model_dump(exclude={"principal_id"})
    )


class ResultPageV1(BoundaryModel):
    result_id: Identifier
    operation_id: Identifier
    artifact_id: Identifier
    artifact_content_hash: Sha256
    result_content_hash: Sha256
    parser_name: NonEmptyText
    parser_version: NonEmptyText
    parser_profile_ref: Identifier
    parser_profile_hash: Sha256
    result_policy_ref: Identifier
    result_policy_hash: Sha256
    code_version: Identifier
    result_contract_version: Literal["1.0"] = "1.0"
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    causation_id: Identifier
    lineage_parent_ids: tuple[Identifier, ...]
    ordering: Literal["DOCUMENT_ORDER_V1"] = "DOCUMENT_ORDER_V1"
    returned_count: NonNegativeInt
    has_more: bool
    next_cursor: OpaqueResultCursor | None

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        if (self.source_event_at is None) == (
            self.source_event_absence_reason is None
        ):
            raise ValueError(
                "source_event_at and source_event_absence_reason are mutually exclusive"
            )
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError("source event cannot follow observation")
        if not (
            self.observed_at <= self.retrieved_at <= self.system_recorded_at
        ):
            raise ValueError("page times are out of order")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("next_cursor is required exactly when more records exist")
        if not self.lineage_parent_ids:
            raise ValueError("result page requires lineage parents")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("lineage_parent_ids must be unique")
        return self


class DocumentResultPageV1(BoundaryModel):
    page: ResultPageV1
    records: tuple[CanonicalDerivedRecordV1, ...]
    page_content_hash: Sha256
    response_byte_count: Annotated[int, Field(strict=True, ge=1, le=131072)]

    @model_validator(mode="after")
    def validate_document_page(self) -> Self:
        if len(self.records) != self.page.returned_count:
            raise ValueError("returned_count must match records")
        if not self.records:
            raise ValueError("document result page cannot be empty")
        if any(record.result_id != self.page.result_id for record in self.records):
            raise ValueError("every page record must belong to the result")
        ordinals = tuple(record.ordinal for record in self.records)
        if tuple(sorted(set(ordinals))) != ordinals:
            raise ValueError("page records must be unique and in document order")
        return self


class SourceGapV2(BoundaryModel):
    source_gap_id: Identifier
    operation_id: Identifier
    reason: SourceGapReasonV2
    detail_code: ReasonCode
    validation_stage: GapValidationStage | None
    hop_ref: Identifier | None
    last_failure_class: ReasonCode | None
    attempt_receipt_ids: tuple[Identifier, ...]
    incomplete_content_hash: Sha256 | None
    incomplete_attempt_receipt_id: Identifier | None
    incomplete_policy_validation_id: Identifier | None
    incomplete_byte_count: NonNegativeInt | None
    incomplete_stop_reason: ReasonCode | None
    artifact_id: Identifier | None
    parser_profile_ref: Identifier | None
    parser_stage: ParserGapStage | None
    occurred_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_gap(self) -> Self:
        network_policy_gap = self.reason in {
            SourceGapReasonV2.POLICY_DENIED,
            SourceGapReasonV2.DNS_DENIED,
        }
        if network_policy_gap and (
            self.validation_stage is None or self.hop_ref is None
        ):
            raise ValueError(
                "policy and DNS gaps require validation_stage and hop_ref"
            )
        if not network_policy_gap and (
            self.validation_stage is not None or self.hop_ref is not None
        ):
            raise ValueError("only policy and DNS gaps carry validation details")
        exhausted = self.reason is SourceGapReasonV2.RETRY_EXHAUSTED
        if exhausted and (
            self.last_failure_class is None or not self.attempt_receipt_ids
        ):
            raise ValueError(
                "retry exhaustion requires last failure and attempt receipts"
            )
        if not exhausted and (
            self.last_failure_class is not None or self.attempt_receipt_ids
        ):
            raise ValueError("only retry exhaustion carries retry details")
        incomplete_values = (
            self.incomplete_content_hash,
            self.incomplete_attempt_receipt_id,
            self.incomplete_policy_validation_id,
            self.incomplete_byte_count,
            self.incomplete_stop_reason,
        )
        retained_incomplete = any(value is not None for value in incomplete_values)
        if retained_incomplete and not all(
            value is not None for value in incomplete_values
        ):
            raise ValueError("retained incomplete artifact metadata is atomic")
        if retained_incomplete and self.reason not in {
            SourceGapReasonV2.INCOMPLETE_RESPONSE,
            SourceGapReasonV2.RESPONSE_TOO_LARGE,
        }:
            raise ValueError(
                "only incomplete or oversized responses retain partial artifact metadata"
            )
        parser_reasons = {
            SourceGapReasonV2.UNSUPPORTED_MEDIA_TYPE,
            SourceGapReasonV2.INVALID_TEXT_ENCODING,
            SourceGapReasonV2.EMPTY_CONTENT,
            SourceGapReasonV2.MALFORMED_DOCUMENT,
            SourceGapReasonV2.NO_USABLE_CONTENT,
            SourceGapReasonV2.OUTPUT_LIMIT_EXCEEDED,
        }
        parser_values = (
            self.artifact_id,
            self.parser_profile_ref,
            self.parser_stage,
        )
        if self.reason in parser_reasons and not all(
            value is not None for value in parser_values
        ):
            raise ValueError("parser gaps require artifact, profile, and stage")
        if self.reason not in parser_reasons and any(
            value is not None for value in parser_values
        ):
            raise ValueError("retained acquisition gaps cannot carry parser fields")
        if len(self.attempt_receipt_ids) != len(set(self.attempt_receipt_ids)):
            raise ValueError("attempt_receipt_ids must be unique")
        if not self.lineage_parent_ids:
            raise ValueError("source gap requires lineage parents")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("lineage_parent_ids must be unique")
        return self


class DecisionEventV2(BoundaryModel):
    decision_id: Identifier
    operation_id: Identifier
    workflow_id: Identifier
    task_id: Identifier | None
    correlation_id: Identifier
    causation_id: Identifier
    decision_type: DecisionTypeV2
    reason_codes: tuple[ReasonCode, ...]
    considered_options: tuple[Identifier, ...]
    selected_option: Identifier
    policy_version: Identifier
    configuration_version: Identifier
    code_version: Identifier
    numeric_input_names: tuple[Identifier, ...]
    numeric_input_values: tuple[Annotated[int, Field(strict=True)], ...]
    expected_effect: NonEmptyText
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if not self.reason_codes or not self.considered_options:
            raise ValueError("decision requires reasons and considered options")
        if self.selected_option not in self.considered_options:
            raise ValueError("selected option must be considered")
        if len(self.numeric_input_names) != len(self.numeric_input_values):
            raise ValueError("numeric input names and values must align")
        if (self.source_event_at is None) == (
            self.source_event_absence_reason is None
        ):
            raise ValueError(
                "source_event_at and source_event_absence_reason are mutually exclusive"
            )
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError("source event cannot follow observation")
        if not (
            self.observed_at <= self.retrieved_at <= self.system_recorded_at
        ):
            raise ValueError("decision times are out of order")
        if not self.lineage_parent_ids:
            raise ValueError("decision requires lineage parents")
        return self


def upcast_source_gap_v1(value: SourceGapV1) -> SourceGapV2:
    return SourceGapV2.model_validate(
        {
            **value.model_dump(),
            "reason": SourceGapReasonV2(value.reason.value),
            "artifact_id": None,
            "parser_profile_ref": None,
            "parser_stage": None,
        }
    )


def upcast_decision_event_v1(value: DecisionEventV1) -> DecisionEventV2:
    return DecisionEventV2.model_validate(
        {
            **value.model_dump(),
            "decision_type": DecisionTypeV2(value.decision_type.value),
        }
    )


RawArtifactReadRequestWorkEnvelopeV1 = WorkEnvelopeV1[RawArtifactReadRequestV1]
ResultPageRequestWorkEnvelopeV1 = WorkEnvelopeV1[ResultPageRequestV1]
ResultPageRequestV2WorkEnvelopeV1 = WorkEnvelopeV1[ResultPageRequestV2]
DocumentResultPageWorkEnvelopeV1 = WorkEnvelopeV1[DocumentResultPageV1]
SourceGapV2WorkEnvelopeV1 = WorkEnvelopeV1[SourceGapV2]
DecisionEventV2WorkEnvelopeV1 = WorkEnvelopeV1[DecisionEventV2]


class BatchItemRecordKind(StrEnum):
    OUTCOME = "OUTCOME"
    FAILURE = "FAILURE"
class BatchItemFailureKind(StrEnum):
    SOURCE_GAP = "SOURCE_GAP"
    CHILD_FAILURE = "CHILD_FAILURE"
class ResultPageTargetKind(StrEnum):
    DOCUMENT_RESULT = "DOCUMENT_RESULT"
    DATASET = "DATASET"
class ResultPageResponseKind(StrEnum):
    DOCUMENT_RESULT = "DOCUMENT_RESULT"
    DATASET = "DATASET"
def _wire_result_page_target_kind(value: object) -> object:
    """Normalize an exact JSON enum string without enabling scalar coercion."""
    if type(value) is str:
        return ResultPageTargetKind(value)
    return value
class BatchItemOutcomeV1(BoundaryModel):
    record_kind: Literal[BatchItemRecordKind.OUTCOME] = BatchItemRecordKind.OUTCOME
    outcome_id: Identifier
    dataset_id: Identifier
    item_id: Identifier
    ordinal: Annotated[int, Field(strict=True, ge=0, le=63)]
    parent_operation_id: Identifier
    crawl_child_workflow_id: Identifier
    crawl_child_operation_id: Identifier
    extraction_child_workflow_id: Identifier
    extraction_child_operation_id: Identifier
    raw_artifact_id: Identifier
    raw_artifact_content_hash: Sha256
    document_result_id: Identifier
    document_result_content_hash: Sha256
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    causation_id: Identifier
    decision_id: Identifier
    cost_observation_id: Identifier
    batch_policy_ref: Identifier
    configuration_ref: Identifier
    code_version: Identifier
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if (self.source_event_at is None) == (
            self.source_event_absence_reason is None
        ):
            raise ValueError(
                "source_event_at and source_event_absence_reason are mutually exclusive"
            )
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError("source event cannot follow observation")
        if not (
            self.observed_at <= self.retrieved_at <= self.system_recorded_at
        ):
            raise ValueError("batch outcome times are out of order")
        required = {
            self.item_id,
            self.parent_operation_id,
            self.crawl_child_operation_id,
            self.extraction_child_operation_id,
            self.raw_artifact_id,
            self.document_result_id,
            self.decision_id,
            self.cost_observation_id,
            self.batch_policy_ref,
            self.configuration_ref,
            self.code_version,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("batch outcome lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("batch outcome lineage must be unique")
        return self
class BatchItemFailureV1(BoundaryModel):
    record_kind: Literal[BatchItemRecordKind.FAILURE] = BatchItemRecordKind.FAILURE
    failure_id: Identifier
    dataset_id: Identifier
    item_id: Identifier
    ordinal: Annotated[int, Field(strict=True, ge=0, le=63)]
    parent_operation_id: Identifier
    crawl_child_workflow_id: Identifier
    crawl_child_operation_id: Identifier
    extraction_child_workflow_id: Identifier | None
    extraction_child_operation_id: Identifier | None
    failure_kind: BatchItemFailureKind
    source_gap_id: Identifier | None
    child_failure_ref: Identifier | None
    child_failure_code: ReasonCode | None
    raw_artifact_id: Identifier | None
    raw_artifact_content_hash: Sha256 | None
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    causation_id: Identifier
    decision_id: Identifier
    cost_observation_id: Identifier
    batch_policy_ref: Identifier
    configuration_ref: Identifier
    code_version: Identifier
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        extraction_refs = (
            self.extraction_child_workflow_id,
            self.extraction_child_operation_id,
        )
        if any(value is not None for value in extraction_refs) and not all(
            value is not None for value in extraction_refs
        ):
            raise ValueError("extraction child references are atomic")
        child_failure_values = (
            self.child_failure_ref,
            self.child_failure_code,
        )
        if self.failure_kind is BatchItemFailureKind.SOURCE_GAP:
            if self.source_gap_id is None or any(
                value is not None for value in child_failure_values
            ):
                raise ValueError(
                    "source-gap failure requires only a source-gap reference"
                )
        elif self.source_gap_id is not None or not all(
            value is not None for value in child_failure_values
        ):
            raise ValueError(
                "child failure requires only its typed reference and code"
            )
        if (self.raw_artifact_id is None) != (
            self.raw_artifact_content_hash is None
        ):
            raise ValueError("raw artifact identity and hash are atomic")
        if (self.source_event_at is None) == (
            self.source_event_absence_reason is None
        ):
            raise ValueError(
                "source_event_at and source_event_absence_reason are mutually exclusive"
            )
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError("source event cannot follow observation")
        if not (
            self.observed_at <= self.retrieved_at <= self.system_recorded_at
        ):
            raise ValueError("batch failure times are out of order")
        failure_ref = self.source_gap_id or self.child_failure_ref
        required = {
            self.item_id,
            self.parent_operation_id,
            self.crawl_child_operation_id,
            self.decision_id,
            self.cost_observation_id,
            self.batch_policy_ref,
            self.configuration_ref,
            self.code_version,
        }
        if failure_ref is not None:
            required.add(failure_ref)
        if self.extraction_child_operation_id is not None:
            required.add(self.extraction_child_operation_id)
        if self.raw_artifact_id is not None:
            required.add(self.raw_artifact_id)
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("batch failure lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("batch failure lineage must be unique")
        return self

BatchDatasetRecordV1 = Annotated[
    BatchItemOutcomeV1 | BatchItemFailureV1,
    Field(discriminator="record_kind"),
]
class DatasetRefV1(BoundaryModel):
    dataset_id: Identifier
    principal_id: Identifier
    parent_operation_id: Identifier
    generation: PositiveInt
    ordered_item_count: Annotated[int, Field(strict=True, ge=1, le=64)]
    success_count: Annotated[int, Field(strict=True, ge=0, le=64)]
    failure_count: Annotated[int, Field(strict=True, ge=0, le=64)]
    content_hash: Sha256
    committed_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        if self.success_count + self.failure_count != self.ordered_item_count:
            raise ValueError("dataset item counts must sum exactly")
        if self.parent_operation_id not in self.lineage_parent_ids:
            raise ValueError("dataset lineage requires its parent operation")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("dataset lineage must be unique")
        return self


DatasetGenerationItemIds = Annotated[
    tuple[Identifier, ...],
    Field(min_length=1, max_length=64),
]
DatasetGenerationItemUrls = Annotated[
    tuple[str, ...],
    Field(min_length=1, max_length=64),
]
DatasetGenerationRecords = Annotated[
    tuple[BatchDatasetRecordV1, ...],
    Field(min_length=1, max_length=64),
]
DatasetGenerationDocumentRecords = Annotated[
    tuple[CanonicalDerivedRecordV1, ...],
    Field(max_length=4096),
]


class DatasetGenerationBindingV1(BoundaryModel):
    """Verified immutable inputs for one principal-owned P3 generation."""

    dataset: DatasetRefV1
    request_id: Identifier
    request_envelope_hash: Sha256
    item_ids: DatasetGenerationItemIds
    item_urls: DatasetGenerationItemUrls
    batch_records: DatasetGenerationRecords
    document_records: DatasetGenerationDocumentRecords
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        expected_count = self.dataset.ordered_item_count
        if not (
            len(self.item_ids)
            == len(self.item_urls)
            == len(self.batch_records)
            == expected_count
        ):
            raise ValueError("generation binding counts must match the dataset")
        if len(self.item_ids) != len(set(self.item_ids)):
            raise ValueError("generation item identities must be unique")
        if tuple(record.ordinal for record in self.batch_records) != tuple(
            range(expected_count)
        ):
            raise ValueError(
                "generation records must be in contiguous ordinal order"
            )
        if tuple(record.item_id for record in self.batch_records) != self.item_ids:
            raise ValueError("generation request items and records are misbound")
        if any(
            record.dataset_id != self.dataset.dataset_id
            or record.parent_operation_id != self.dataset.parent_operation_id
            for record in self.batch_records
        ):
            raise ValueError("generation records do not belong to the dataset")

        outcomes = tuple(
            record
            for record in self.batch_records
            if isinstance(record, BatchItemOutcomeV1)
        )
        if (
            len(outcomes) != self.dataset.success_count
            or expected_count - len(outcomes) != self.dataset.failure_count
        ):
            raise ValueError(
                "generation outcome counts do not match the dataset"
            )
        outcome_result_ids = tuple(
            outcome.document_result_id for outcome in outcomes
        )
        if len(outcome_result_ids) != len(set(outcome_result_ids)):
            raise ValueError(
                "generation document result identities must be unique"
            )

        records_hash = "sha256:" + hashlib.sha256(
            json.dumps(
                tuple(
                    record.model_dump(mode="json")
                    for record in self.batch_records
                ),
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if records_hash != self.dataset.content_hash:
            raise ValueError("generation records do not match the dataset hash")

        grouped: dict[str, list[CanonicalDerivedRecordV1]] = {}
        for record in self.document_records:
            grouped.setdefault(record.result_id, []).append(record)
        if set(grouped).difference(outcome_result_ids):
            raise ValueError("generation contains an unknown document result")
        outcomes_by_result = {
            outcome.document_result_id: outcome for outcome in outcomes
        }
        for result_id, outcome in outcomes_by_result.items():
            records = tuple(
                sorted(
                    grouped.get(result_id, ()),
                    key=lambda record: record.ordinal,
                )
            )
            if tuple(record.ordinal for record in records) != tuple(
                range(len(records))
            ):
                raise ValueError(
                    "document records must be in contiguous ordinal order"
                )
            if any(
                record.artifact_id != outcome.raw_artifact_id
                for record in records
            ):
                raise ValueError(
                    "document records do not match the raw artifact"
                )
            for record in records:
                text_hash = "sha256:" + hashlib.sha256(
                    record.text.encode("utf-8")
                ).hexdigest()
                if record.content_hash != text_hash:
                    raise ValueError("document record text hash is invalid")
            result_hash = "sha256:" + hashlib.sha256(
                json.dumps(
                    [
                        record.model_dump(mode="json")
                        for record in records
                    ],
                    allow_nan=False,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            if result_hash != outcome.document_result_content_hash:
                raise ValueError("document result hash is invalid")

        batch_record_ids = tuple(
            record.outcome_id
            if isinstance(record, BatchItemOutcomeV1)
            else record.failure_id
            for record in self.batch_records
        )
        required_lineage = {
            self.dataset.dataset_id,
            self.dataset.parent_operation_id,
            self.request_id,
            self.request_envelope_hash,
            *batch_record_ids,
            *(record.record_id for record in self.document_records),
        }
        if not required_lineage.issubset(self.lineage_parent_ids):
            raise ValueError("generation binding lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("generation binding lineage must be unique")
        return self


DatasetPageRecords = Annotated[
    tuple[BatchDatasetRecordV1, ...],
    Field(min_length=1, max_length=64),
]
class DatasetResultPageV1(BoundaryModel):
    request_id: Identifier
    dataset: DatasetRefV1
    start_ordinal: Annotated[int, Field(strict=True, ge=0, le=63)]
    records: DatasetPageRecords
    returned_count: Annotated[int, Field(strict=True, ge=1, le=64)]
    has_more: bool
    next_cursor: OpaqueResultCursor | None
    page_content_hash: Sha256
    response_byte_count: Annotated[int, Field(strict=True, ge=1, le=131072)]
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_dataset_page(self) -> Self:
        if self.returned_count != len(self.records):
            raise ValueError("returned_count must match dataset page records")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("next_cursor is required exactly when more records exist")
        if any(
            record.dataset_id != self.dataset.dataset_id
            for record in self.records
        ):
            raise ValueError("every page record must belong to the dataset")
        ordinals = tuple(record.ordinal for record in self.records)
        expected = tuple(
            range(self.start_ordinal, self.start_ordinal + len(self.records))
        )
        if ordinals != expected:
            raise ValueError(
                "dataset records must be contiguous in request-ordinal order"
            )
        if ordinals[-1] >= self.dataset.ordered_item_count:
            raise ValueError("dataset page exceeds the immutable generation")
        required = {
            self.dataset.dataset_id,
            *(record.outcome_id if isinstance(record, BatchItemOutcomeV1)
              else record.failure_id for record in self.records),
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("dataset page lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("dataset page lineage must be unique")
        return self
class ResultPageRequestV3(BoundaryModel):
    request_id: Identifier
    target_kind: Annotated[ResultPageTargetKind, BeforeValidator(_wire_result_page_target_kind)]
    target_id: Identifier
    cursor: OpaqueResultCursor | None
    page_size: Annotated[int, Field(strict=True, ge=1, le=64)]
class ResultPageTargetV2(BoundaryModel):
    target_id: Identifier
    authorization_id: Identifier
    principal_id: Identifier
    operation_id: Identifier
    target_kind: ResultPageTargetKind
    requested_target_id: Identifier
    target_generation: PositiveInt | None
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if self.target_kind is ResultPageTargetKind.DATASET:
            if self.target_generation is None:
                raise ValueError("dataset target requires a resolved generation")
        elif self.target_generation is not None:
            raise ValueError("document target cannot carry a dataset generation")
        required = {
            self.authorization_id,
            self.requested_target_id,
            self.operation_id,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("result-page target lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("result-page target lineage must be unique")
        return self
def upcast_result_page_target_v1(value: ResultPageTargetV1) -> ResultPageTargetV2:
    return ResultPageTargetV2(
        target_kind=ResultPageTargetKind.DOCUMENT_RESULT,
        requested_target_id=value.result_id, target_generation=None,
        **value.model_dump(exclude={"result_id"}))
class ResultPageResponseV1(BoundaryModel):
    response_kind: ResultPageResponseKind
    document_page: DocumentResultPageV1 | None
    dataset_page: DatasetResultPageV1 | None

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if self.response_kind is ResultPageResponseKind.DOCUMENT_RESULT:
            if self.document_page is None or self.dataset_page is not None:
                raise ValueError(
                    "document response requires only a document page"
                )
        elif self.dataset_page is None or self.document_page is not None:
            raise ValueError("dataset response requires only a dataset page")
        return self
def upcast_result_page_request_v2(
    value: ResultPageRequestV2,
) -> ResultPageRequestV3:
    return ResultPageRequestV3(
        request_id=value.request_id,
        target_kind=ResultPageTargetKind.DOCUMENT_RESULT,
        target_id=value.result_id,
        cursor=value.cursor,
        page_size=value.page_size,
    )


BatchItemOutcomeWorkEnvelopeV1 = WorkEnvelopeV1[BatchItemOutcomeV1]
BatchItemFailureWorkEnvelopeV1 = WorkEnvelopeV1[BatchItemFailureV1]
DatasetRefWorkEnvelopeV1 = WorkEnvelopeV1[DatasetRefV1]
ResultPageRequestV3WorkEnvelopeV1 = WorkEnvelopeV1[ResultPageRequestV3]
DatasetResultPageWorkEnvelopeV1 = WorkEnvelopeV1[DatasetResultPageV1]
ResultPageResponseWorkEnvelopeV1 = WorkEnvelopeV1[ResultPageResponseV1]

# P4 query/export contracts (inventory-owned)

# P4 inlined from p4_types.py
MaterializedOrdinal = Annotated[int, Field(strict=True, ge=0, le=4095)]
PositiveInt = Annotated[int, Field(strict=True, ge=1)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
ItemOrdinal = Annotated[int, Field(strict=True, ge=0, le=63)]
PageSize = Annotated[int, Field(strict=True, ge=1, le=64)]
ScanOrdinal = Annotated[int, Field(strict=True, ge=0, le=4096)]
SnapshotRecordCount = Annotated[int, Field(strict=True, ge=0, le=4096)]
SerializedByteCount = Annotated[int, Field(strict=True, ge=0, le=41943040)]
ExportByteCount = Annotated[int, Field(strict=True, ge=0, le=67108864)]
ReadBodyByteCount = Annotated[int, Field(strict=True, ge=0, le=1048576)]
RangeBound = Annotated[int, Field(strict=True, ge=0, le=67108863)]
HttpStatus = Annotated[int, Field(strict=True, ge=100, le=599)]
ActivityAttempt = Annotated[int, Field(strict=True, ge=1, le=3)]
FenceOrdinal = Annotated[int, Field(strict=True, ge=1)]
StrongEtag = Annotated[str, StringConstraints(min_length=66, max_length=66)]
ImfFixdate29 = Annotated[str, StringConstraints(min_length=29, max_length=29)]
ContentRangeText = Annotated[str, StringConstraints(min_length=1, max_length=128)]
MediaTypeText = Annotated[str, StringConstraints(min_length=1, max_length=128)]
CacheControlText = Annotated[str, StringConstraints(min_length=1, max_length=256)]
RangeHeaderText = Annotated[str, StringConstraints(min_length=1, max_length=256)]
ConditionHeaderText = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
DateHeaderText = Annotated[str, StringConstraints(min_length=1, max_length=64)]
IfRangeHeaderText = Annotated[str, StringConstraints(min_length=1, max_length=128)]
HexCommit40 = Annotated[str, StringConstraints(min_length=40, max_length=40, pattern='^[0-9a-f]{40}$')]
NormalizedUrl = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
CanonicalText = Annotated[str, StringConstraints(min_length=1, max_length=8192)]

# P4 inlined from data_os_p4_support.py
# P4 inlined from materialized_record_v1.py
# Reuses CanonicalRecordKind / BatchItemRecordKind / BatchItemFailureKind above.
CanonicalText = Annotated[str, StringConstraints(min_length=1, max_length=8192)]

class DatasetMaterializedRecordV1(BoundaryModel):
    materialized_record_id: Identifier
    materialized_ordinal: MaterializedOrdinal
    dataset_id: Identifier
    generation: PositiveInt
    dataset_content_hash: Sha256
    parent_operation_id: Identifier
    item_id: Identifier
    item_ordinal: ItemOrdinal
    url: NormalizedUrl
    record_kind: BatchItemRecordKind
    outcome_id: Identifier | None
    failure_id: Identifier | None
    failure_kind: BatchItemFailureKind | None
    source_gap_id: Identifier | None
    child_failure_ref: Identifier | None
    child_failure_code: ReasonCode | None
    raw_artifact_id: Identifier | None
    raw_artifact_content_hash: Sha256 | None
    document_result_id: Identifier | None
    document_result_content_hash: Sha256 | None
    document_record_id: Identifier | None
    document_record_ordinal: NonNegativeInt | None
    document_record_kind: CanonicalRecordKind | None
    canonical_text: CanonicalText | None
    document_record_content_hash: Sha256 | None
    decision_id: Identifier
    cost_observation_id: Identifier
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    causation_id: Identifier
    policy_ref: Identifier
    configuration_ref: Identifier
    code_version: Identifier
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_record(self) -> Self:
        if self.record_kind is BatchItemRecordKind.OUTCOME:
            if self.outcome_id is None or self.failure_id is not None:
                raise ValueError('outcome row requires outcome_id and no failure fields')
            if any((value is None for value in (self.document_result_id, self.document_result_content_hash))):
                raise ValueError('outcome row requires document result identity')
        elif self.outcome_id is not None or self.failure_id is None:
            raise ValueError('failure row requires failure_id and no outcome_id')
        if (self.raw_artifact_id is None) != (self.raw_artifact_content_hash is None):
            raise ValueError('raw artifact identity and hash are atomic')
        if (self.source_event_at is None) == (self.source_event_absence_reason is None):
            raise ValueError('source_event_at and source_event_absence_reason are mutually exclusive')
        if not self.observed_at <= self.retrieved_at <= self.system_recorded_at:
            raise ValueError('materialized record times are out of order')
        if not self.lineage_parent_ids:
            raise ValueError('materialized record requires lineage parents')
        return self
DatasetMaterializedRecordWorkEnvelopeV1 = WorkEnvelopeV1[DatasetMaterializedRecordV1]

# P4 inlined from export_manifest_v1.py
ALL_RECORDS_V1_HASH = 'sha256:cb09cc8be42e51d8cbb2603c5369b8c4e87a6b7b47c0e446c7f215134d23999b'
ExportMediaType = Literal['application/x-ndjson', 'application/vnd.apache.' + 'par' + 'quet']

class DatasetExportFormatV1(StrEnum):
    JSONL = 'JSONL'
    PARQUET = 'PAR' + 'QUET'


def _coerce_dataset_export_format(value: object) -> DatasetExportFormatV1:
    if isinstance(value, DatasetExportFormatV1):
        return value
    if isinstance(value, str):
        return DatasetExportFormatV1(value)
    raise TypeError('dataset export format must be a DatasetExportFormatV1 value')


DatasetExportFormatWireV1 = Annotated[
    DatasetExportFormatV1,
    BeforeValidator(_coerce_dataset_export_format),
]


class ExportManifestV1(BoundaryModel):
    manifest_id: Identifier
    export_id: Identifier
    principal_id: Identifier
    principal_snapshot_id: Identifier
    operation_id: Identifier
    dataset_id: Identifier
    dataset_generation: PositiveInt
    dataset_content_hash: Sha256
    dataset_snapshot_id: Identifier
    dataset_snapshot_content_hash: Sha256
    canonical_filter_hash: Sha256
    format: DatasetExportFormatWireV1
    media_type: ExportMediaType
    export_schema_ref: Identifier
    export_schema_hash: Sha256
    writer_configuration_ref: Identifier
    writer_configuration_hash: Sha256
    ordered_record_ids_hash: Sha256
    record_count: SnapshotRecordCount
    byte_count: ExportByteCount
    content_hash: Sha256
    exact_object_version_ref: Identifier
    lock_receipt_id: Identifier
    analytics_package_ref: Identifier
    analytics_configuration_ref: Identifier
    analytics_code_version: Identifier
    classification_ref: Identifier
    retention_policy_id: Identifier
    retention_policy_hash: Sha256
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    committed_at: datetime
    decision_id: Identifier
    cost_observation_id: Identifier
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_manifest(self) -> Self:
        if self.format is DatasetExportFormatV1.JSONL:
            if self.media_type != 'application/x-ndjson':
                raise ValueError('JSONL format requires application/x-ndjson')
        elif self.media_type != 'application/vnd.apache.' + 'par' + 'quet':
            raise ValueError('columnar format requires matching media type')
        if self.canonical_filter_hash != ALL_RECORDS_V1_HASH:
            raise ValueError('manifest must bind the frozen ALL_RECORDS_V1 hash')
        if (self.source_event_at is None) == (self.source_event_absence_reason is None):
            raise ValueError('source_event_at and source_event_absence_reason are mutually exclusive')
        if not self.observed_at <= self.retrieved_at <= self.system_recorded_at <= self.committed_at:
            raise ValueError('manifest operational times are out of order')
        return self
ExportManifestWorkEnvelopeV1 = WorkEnvelopeV1[ExportManifestV1]

# P4 inlined from export_publish_v1.py
class ExportPublicationFenceStatusV1(StrEnum):
    ACTIVE = 'ACTIVE'
    SUPERSEDED = 'SUPERSEDED'
    COMMITTED = 'COMMITTED'
    CANCELLED = 'CANCELLED'
    FAILED = 'FAILED'
    EXPIRED = 'EXPIRED'

class ObjectLockCanaryDecisionV1(StrEnum):
    PASSED = 'PASSED'
    FAILED = 'FAILED'

class DatasetExportRequestV1(BoundaryModel):
    request_id: Identifier
    dataset_id: Identifier
    format: DatasetExportFormatWireV1
    idempotency_key: Identifier

class ExportPublicationFenceV1(BoundaryModel):
    publication_fence_id: Identifier
    export_id: Identifier
    operation_id: Identifier
    workflow_id: Identifier
    run_id: Identifier
    activity_id: Identifier
    activity_attempt: ActivityAttempt
    fence_ordinal: FenceOrdinal
    supersedes_fence_id: Identifier | None
    status: ExportPublicationFenceStatusV1
    issued_at: datetime
    expires_at: datetime
    terminal_at: datetime | None
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_fence(self) -> Self:
        if self.status is ExportPublicationFenceStatusV1.ACTIVE:
            if self.terminal_at is not None:
                raise ValueError('active fence cannot have terminal_at')
        elif self.terminal_at is None:
            raise ValueError('terminal fence requires terminal_at')
        if self.expires_at <= self.issued_at:
            raise ValueError('fence expiry must follow issue time')
        return self

class ExportObjectRetentionPolicyV1(BoundaryModel):
    retention_policy_id: Identifier
    mode: Literal['COMPLIANCE']
    retain_until: datetime
    implementation_profile_ref: Literal['minio-community-source-build']
    deployment_profile_ref: Literal['local_single_host_guarded_single_node']
    minio_source_commit: HexCommit40
    minio_source_archive_sha256: Sha256
    builder_image_digest: Sha256
    builder_platform_digest: Sha256
    runtime_image_digest: Sha256
    threat_boundary_version: Identifier
    decided_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_policy(self) -> Self:
        if self.retain_until <= self.decided_at:
            raise ValueError('retain_until must follow decided_at')
        return self

class ExportObjectLockReceiptV1(BoundaryModel):
    lock_receipt_id: Identifier
    export_id: Identifier
    retention_policy_id: Identifier
    exact_object_version_ref: Identifier
    object_content_hash: Sha256
    object_byte_count: ExportByteCount
    versioning_enabled: Literal[True]
    object_lock_enabled: Literal[True]
    retention_mode: Literal['COMPLIANCE']
    retain_until: datetime
    root_canary_decision: ObjectLockCanaryDecisionV1
    application_canary_decision: ObjectLockCanaryDecisionV1
    verified_at: datetime
    recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_receipt(self) -> Self:
        if self.recorded_at < self.verified_at:
            raise ValueError('lock receipt recording cannot precede verification')
        if self.root_canary_decision is not ObjectLockCanaryDecisionV1.PASSED or self.application_canary_decision is not ObjectLockCanaryDecisionV1.PASSED:
            raise ValueError('object lock canaries must pass')
        return self

class ExportPublishRequestV1(BoundaryModel):
    publish_request_id: Identifier
    export_id: Identifier
    operation_id: Identifier
    principal_snapshot_id: Identifier
    dataset_id: Identifier
    dataset_generation: PositiveInt
    dataset_snapshot_id: Identifier
    dataset_snapshot_content_hash: Sha256
    format: DatasetExportFormatWireV1
    canonical_filter_hash: Sha256
    record_count: SnapshotRecordCount
    ordered_record_ids_hash: Sha256
    serializer_request_id: Identifier
    serializer_receipt_id: Identifier
    serializer_receipt_hash: Sha256
    serializer_output_byte_count: ExportByteCount
    serializer_output_content_hash: Sha256
    serializer_runtime_tuple_hash: Sha256
    export_schema_ref: Identifier
    export_schema_hash: Sha256
    writer_configuration_ref: Identifier
    writer_configuration_hash: Sha256
    serializer_code_version: Identifier
    publication_fence_id: Identifier
    publication_fence_ordinal: FenceOrdinal
    workflow_id: Identifier
    run_id: Identifier
    activity_id: Identifier
    activity_attempt: ActivityAttempt
    retention_policy_id: Identifier
    retention_policy_hash: Sha256
    classification_ref: Identifier
    requested_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

class ExportRefV1(BoundaryModel):
    export_id: Identifier
    manifest_id: Identifier
    format: DatasetExportFormatWireV1
    media_type: ExportMediaType
    byte_count: ExportByteCount
    content_hash: Sha256
    committed_at: datetime
DatasetExportRequestWorkEnvelopeV1 = WorkEnvelopeV1[DatasetExportRequestV1]
ExportPublishRequestWorkEnvelopeV1 = WorkEnvelopeV1[ExportPublishRequestV1]

ExportPublicationFenceWorkEnvelopeV1 = WorkEnvelopeV1[ExportPublicationFenceV1]
ExportObjectRetentionPolicyWorkEnvelopeV1 = WorkEnvelopeV1[ExportObjectRetentionPolicyV1]
ExportObjectLockReceiptWorkEnvelopeV1 = WorkEnvelopeV1[ExportObjectLockReceiptV1]
ExportRefWorkEnvelopeV1 = WorkEnvelopeV1[ExportRefV1]

# P4 inlined from query_export_wires.py
DatasetQueryCursorWire = Annotated[str, StringConstraints(pattern='^cursor:[A-Za-z0-9_-]{43}$')]

class DecisionTypeV3(StrEnum):
    ACQUISITION_ROUTE = 'ACQUISITION_ROUTE'
    CAPACITY_ADMISSION = 'CAPACITY_ADMISSION'
    NETWORK_POLICY = 'NETWORK_POLICY'
    RETRY = 'RETRY'
    TERMINAL_REDUCTION = 'TERMINAL_REDUCTION'
    PARSER_SELECTION = 'PARSER_SELECTION'
    RESULT_PAGE_AUTHORIZATION = 'RESULT_PAGE_AUTHORIZATION'
    BATCH_ADMISSION = 'BATCH_ADMISSION'
    BATCH_BACKPRESSURE = 'BATCH_BACKPRESSURE'
    DATASET_COMMIT = 'DATASET_COMMIT'
    DATASET_QUERY_AUTHORIZATION = 'DATASET_QUERY_AUTHORIZATION'
    DATASET_FILTER_COMPILATION = 'DATASET_FILTER_COMPILATION'
    DATASET_SNAPSHOT_SELECTION = 'DATASET_SNAPSHOT_SELECTION'
    DATASET_EXPORT_FORMAT_SELECTION = 'DATASET_EXPORT_FORMAT_SELECTION'
    DATASET_EXPORT_PUBLICATION = 'DATASET_EXPORT_PUBLICATION'
    DATASET_EXPORT_RETRIEVAL = 'DATASET_EXPORT_RETRIEVAL'
    DATASET_EXPORT_TERMINAL_REDUCTION = 'DATASET_EXPORT_TERMINAL_REDUCTION'

class DatasetQueryCursorStateV1(StrEnum):
    ISSUED = 'ISSUED'
    CONSUMED = 'CONSUMED'
    REVOKED = 'REVOKED'

class ExportReadOutcomeV1(StrEnum):
    HEAD_METADATA = 'HEAD_METADATA'
    WHOLE = 'WHOLE'
    PARTIAL = 'PARTIAL'
    NOT_MODIFIED = 'NOT_MODIFIED'
    PRECONDITION_FAILED = 'PRECONDITION_FAILED'
    FAILURE = 'FAILURE'

class ExportReadFailureV1(StrEnum):
    FORBIDDEN = 'FORBIDDEN'
    EXPORT_NOT_FOUND = 'EXPORT_NOT_FOUND'
    EXPORT_NOT_READY = 'EXPORT_NOT_READY'
    STALE_EXPORT = 'STALE_EXPORT'
    PRECONDITION_LIMIT_EXCEEDED = 'PRECONDITION_LIMIT_EXCEEDED'
    MALFORMED_CONDITION = 'MALFORMED_CONDITION'
    MALFORMED_RANGE = 'MALFORMED_RANGE'
    MULTIPLE_RANGES_UNSUPPORTED = 'MULTIPLE_RANGES_UNSUPPORTED'
    UNSATISFIABLE_RANGE = 'UNSATISFIABLE_RANGE'
    RANGE_REQUIRED = 'RANGE_REQUIRED'
    RANGE_TOO_LARGE = 'RANGE_TOO_LARGE'
    INTEGRITY_MISMATCH = 'INTEGRITY_MISMATCH'
    STORAGE_UNAVAILABLE = 'STORAGE_UNAVAILABLE'

class ExportReadAttemptStatusV1(StrEnum):
    DISPATCH_STARTED = 'DISPATCH_STARTED'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'

class DecisionEventV3(BoundaryModel):
    decision_id: Identifier
    operation_id: Identifier
    workflow_id: Identifier
    task_id: Identifier | None
    correlation_id: Identifier
    causation_id: Identifier
    decision_type: DecisionTypeV3
    reason_codes: tuple[ReasonCode, ...]
    considered_options: tuple[Identifier, ...]
    selected_option: Identifier
    policy_version: Identifier
    configuration_version: Identifier
    code_version: Identifier
    numeric_input_names: tuple[Identifier, ...]
    numeric_input_values: tuple[Annotated[int, Field(strict=True)], ...]
    expected_effect: NonEmptyText
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_decision(self) -> Self:
        if not self.reason_codes or not self.considered_options:
            raise ValueError('decision requires reasons and considered options')
        if self.selected_option not in self.considered_options:
            raise ValueError('selected option must be considered')
        if len(self.numeric_input_names) != len(self.numeric_input_values):
            raise ValueError('numeric input names and values must align')
        if (self.source_event_at is None) == (self.source_event_absence_reason is None):
            raise ValueError('source_event_at and source_event_absence_reason are mutually exclusive')
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError('source event cannot follow observation')
        if not self.observed_at <= self.retrieved_at <= self.system_recorded_at:
            raise ValueError('decision times are out of order')
        if not self.lineage_parent_ids:
            raise ValueError('decision requires lineage parents')
        return self

class DatasetReadAuthorizationV1(BoundaryModel):
    authorization_id: Identifier
    operation_id: Identifier
    principal_id: Identifier
    principal_snapshot_id: Identifier
    dataset_id: Identifier
    required_capability: Literal['dataset.query', 'dataset.export']
    policy_ref: Identifier
    authorized_at: datetime
    expires_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_authorization(self) -> Self:
        if self.expires_at <= self.authorized_at:
            raise ValueError('authorization expiry must follow authorization time')
        required = {self.operation_id, self.principal_snapshot_id, self.principal_id, self.dataset_id}
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError('dataset read authorization lineage is incomplete')
        return self

class DatasetReadTargetV1(BoundaryModel):
    target_id: Identifier
    authorization_id: Identifier
    operation_id: Identifier
    principal_id: Identifier
    dataset_id: Identifier
    generation: PositiveInt
    dataset_content_hash: Sha256
    snapshot_id: Identifier
    snapshot_content_hash: Sha256
    resolved_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_target(self) -> Self:
        required = {self.authorization_id, self.operation_id, self.dataset_id, self.snapshot_id}
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError('dataset read target lineage is incomplete')
        return self

class DatasetSnapshotV1(BoundaryModel):
    snapshot_id: Identifier
    principal_id: Identifier
    dataset_id: Identifier
    generation: PositiveInt
    dataset_content_hash: Sha256
    snapshot_content_hash: Sha256
    materialization_contract_ref: Identifier
    materialization_contract_hash: Sha256
    record_count: SnapshotRecordCount
    record_ids: tuple[Identifier, ...]
    ordered_record_ids_hash: Sha256
    serialized_byte_count: SerializedByteCount
    committed_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_snapshot(self) -> Self:
        if len(self.record_ids) != self.record_count:
            raise ValueError('record_ids length must equal record_count')
        if len(self.record_ids) != len(set(self.record_ids)):
            raise ValueError('record_ids must be unique')
        return self

class DatasetSnapshotRefV1(BoundaryModel):
    snapshot_id: Identifier
    principal_id: Identifier
    dataset_id: Identifier
    generation: PositiveInt
    dataset_content_hash: Sha256
    snapshot_content_hash: Sha256
    materialization_contract_ref: Identifier
    materialization_contract_hash: Sha256
    record_count: SnapshotRecordCount
    ordered_record_ids_hash: Sha256
    serialized_byte_count: SerializedByteCount
    committed_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

class DatasetQueryCursorV1(BoundaryModel):
    cursor_event_id: Identifier
    cursor_sha256: Sha256
    state: DatasetQueryCursorStateV1
    principal_id: Identifier
    query_result_id: Identifier
    snapshot_id: Identifier
    snapshot_content_hash: Sha256
    dataset_id: Identifier
    dataset_generation: PositiveInt
    canonical_filter_hash: Sha256
    page_size: PageSize
    next_scan_ordinal: ScanOrdinal
    issued_at: datetime
    expires_at: datetime
    terminal_at: datetime | None
    successor_cursor_sha256: Sha256 | None
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_cursor(self) -> Self:
        expected_expiry = self.issued_at + timedelta(seconds=3600)
        if self.expires_at != expected_expiry:
            raise ValueError('cursor expiry must equal issue plus 3600 seconds')
        if self.state is DatasetQueryCursorStateV1.ISSUED:
            if self.terminal_at is not None or self.successor_cursor_sha256 is not None:
                raise ValueError('issued cursor cannot have terminal metadata')
        elif self.state is DatasetQueryCursorStateV1.CONSUMED:
            if self.terminal_at is None or self.successor_cursor_sha256 is not None:
                raise ValueError('consumed cursor requires terminal_at and no successor')
        elif self.terminal_at is None or self.successor_cursor_sha256 is None:
            raise ValueError('revoked cursor requires terminal_at and successor hash')
        return self
MaterializedRecordRows = Annotated[tuple[DatasetMaterializedRecordV1, ...], Field(max_length=64)]

class DatasetQueryResultV1(BoundaryModel):
    result_id: Identifier
    operation_id: Identifier
    principal_id: Identifier
    principal_snapshot_id: Identifier
    query_request_id: Identifier
    query_message_id: Identifier
    dataset_id: Identifier
    generation: PositiveInt
    snapshot_id: Identifier
    snapshot_content_hash: Sha256
    snapshot_record_count: SnapshotRecordCount
    canonical_filter_hash: Sha256
    page_size: PageSize
    scan_start_ordinal: ScanOrdinal
    scan_end_ordinal_exclusive: ScanOrdinal
    rows: MaterializedRecordRows
    returned_count: NonNegativeInt
    has_more: bool
    next_scan_ordinal: ScanOrdinal | None
    result_content_hash: Sha256
    decision_id: Identifier
    cost_observation_id: Identifier
    committed_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_result(self) -> Self:
        if self.returned_count != len(self.rows):
            raise ValueError('returned_count must match rows')
        if self.has_more != (self.next_scan_ordinal is not None):
            raise ValueError('next_scan_ordinal is required exactly when has_more')
        if self.has_more and self.next_scan_ordinal != self.scan_end_ordinal_exclusive:
            raise ValueError('next_scan_ordinal must equal scan_end_ordinal_exclusive')
        if not self.has_more and self.scan_end_ordinal_exclusive != self.snapshot_record_count:
            raise ValueError('terminal scan must end at snapshot record count')
        return self

class DatasetQueryDeliveryV1(BoundaryModel):
    delivery_id: Identifier
    result: DatasetQueryResultV1
    next_cursor: DatasetQueryCursorWire | None
    cursor_issued_at: datetime | None
    cursor_expires_at: datetime | None
    delivered_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_delivery(self) -> Self:
        cursor_fields = (self.next_cursor, self.cursor_issued_at, self.cursor_expires_at)
        if any((value is not None for value in cursor_fields)) and (not all((value is not None for value in cursor_fields))):
            raise ValueError('cursor triple must be all present or all absent')
        if self.cursor_issued_at is not None and self.cursor_expires_at is not None:
            if self.cursor_expires_at != self.cursor_issued_at + timedelta(seconds=3600):
                raise ValueError('cursor expiry must equal issue plus 3600 seconds')
        if not self.lineage_parent_ids:
            raise ValueError('delivery requires lineage parents')
        return self

class ExportReadRequestV1(BoundaryModel):
    read_request_id: Identifier
    export_id: Identifier
    method: Literal['GET', 'HEAD']
    range_header: RangeHeaderText | None = None
    if_match: ConditionHeaderText | None = None
    if_none_match: ConditionHeaderText | None = None
    if_modified_since: DateHeaderText | None = None
    if_unmodified_since: DateHeaderText | None = None
    if_range: IfRangeHeaderText | None = None

class ExportReadAuthorizationV1(BoundaryModel):
    authorization_id: Identifier
    read_request_id: Identifier
    principal_id: Identifier
    principal_snapshot_id: Identifier
    export_id: Identifier
    method: Literal['GET', 'HEAD']
    required_capability: Literal['export.read']
    policy_ref: Identifier
    authorized_at: datetime
    expires_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_authorization(self) -> Self:
        if self.expires_at <= self.authorized_at:
            raise ValueError('export read authorization expiry must follow authorization')
        return self

class ExportReadTargetV1(BoundaryModel):
    target_id: Identifier
    authorization_id: Identifier
    principal_id: Identifier
    export_id: Identifier
    manifest_id: Identifier
    exact_object_version_ref: Identifier
    opaque_target_ref: Identifier
    content_hash: Sha256
    byte_count: ExportByteCount
    media_type: ExportMediaType
    committed_at: datetime
    retention_policy_id: Identifier
    resolved_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

class ExportReadDecisionV1(BoundaryModel):
    decision_id: Identifier
    read_attempt_id: Identifier | None
    read_request_id: Identifier
    authorization_id: Identifier
    target_id: Identifier | None
    export_id: Identifier
    method: Literal['GET', 'HEAD']
    outcome: ExportReadOutcomeV1
    status_code: HttpStatus
    failure: ExportReadFailureV1 | None
    representation_byte_count: ExportByteCount
    selected_byte_count: ReadBodyByteCount
    response_body_byte_count: ReadBodyByteCount
    range_start: RangeBound | None
    range_end: RangeBound | None
    content_range: ContentRangeText | None
    media_type: MediaTypeText | None
    strong_etag: StrongEtag | None
    last_modified: ImfFixdate29 | None
    cache_control: CacheControlText | None
    content_length: ReadBodyByteCount | None
    exact_object_version_ref: Identifier | None
    opaque_target_ref: Identifier | None
    committed_at: datetime | None
    decided_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

class ExportReadAttemptOutcomeV1(BoundaryModel):
    read_attempt_event_id: Identifier
    read_attempt_id: Identifier
    dispatch_event_id: Identifier | None
    event_ordinal: Literal[1, 2]
    read_decision_id: Identifier
    read_request_id: Identifier
    authorization_id: Identifier
    target_id: Identifier
    principal_id: Identifier
    export_id: Identifier
    method: Literal['GET']
    attempt_status: ExportReadAttemptStatusV1
    failure: ExportReadFailureV1 | None
    exact_object_version_ref: Identifier
    opaque_target_ref: Identifier
    expected_response_body_byte_count: ReadBodyByteCount
    actual_response_body_byte_count: ReadBodyByteCount
    response_body_sha256: Sha256 | None
    started_at: datetime
    completed_at: datetime | None
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode='after')
    def validate_attempt(self) -> Self:
        if self.event_ordinal == 1:
            if self.dispatch_event_id is not None or self.completed_at is not None:
                raise ValueError('dispatch event cannot carry terminal metadata')
            if self.attempt_status is not ExportReadAttemptStatusV1.DISPATCH_STARTED:
                raise ValueError('ordinal 1 must be DISPATCH_STARTED')
            if self.actual_response_body_byte_count != 0:
                raise ValueError('dispatch event must have zero actual body bytes')
        elif self.dispatch_event_id is None:
            raise ValueError('terminal event requires dispatch_event_id')
        if self.attempt_status is ExportReadAttemptStatusV1.FAILED:
            if self.failure not in {ExportReadFailureV1.STORAGE_UNAVAILABLE, ExportReadFailureV1.INTEGRITY_MISMATCH}:
                raise ValueError('failed attempt requires typed storage failure')
            if self.response_body_sha256 is not None:
                raise ValueError('failed attempt cannot carry body hash')
        return self
DatasetReadAuthorizationWorkEnvelopeV1 = WorkEnvelopeV1[DatasetReadAuthorizationV1]
DatasetReadTargetWorkEnvelopeV1 = WorkEnvelopeV1[DatasetReadTargetV1]
DatasetSnapshotWorkEnvelopeV1 = WorkEnvelopeV1[DatasetSnapshotV1]
DatasetSnapshotRefWorkEnvelopeV1 = WorkEnvelopeV1[DatasetSnapshotRefV1]
DatasetQueryResultWorkEnvelopeV1 = WorkEnvelopeV1[DatasetQueryResultV1]
DatasetQueryDeliveryWorkEnvelopeV1 = WorkEnvelopeV1[DatasetQueryDeliveryV1]
ExportReadRequestWorkEnvelopeV1 = WorkEnvelopeV1[ExportReadRequestV1]
ExportReadAuthorizationWorkEnvelopeV1 = WorkEnvelopeV1[ExportReadAuthorizationV1]
ExportReadTargetWorkEnvelopeV1 = WorkEnvelopeV1[ExportReadTargetV1]
ExportReadDecisionWorkEnvelopeV1 = WorkEnvelopeV1[ExportReadDecisionV1]
DecisionEventV3WorkEnvelopeV1 = WorkEnvelopeV1[DecisionEventV3]
ExportReadAttemptOutcomeWorkEnvelopeV1 = WorkEnvelopeV1[ExportReadAttemptOutcomeV1]


def upcast_decision_event_v2(value: DecisionEventV2) -> DecisionEventV3:
    return DecisionEventV3.model_validate({
        **value.model_dump(),
        "decision_type": DecisionTypeV3(value.decision_type.value),
    })


# P5 discovery contracts

CanonicalPayloadJson = Annotated[
    str,
    StringConstraints(min_length=2, max_length=131_072),
]
TypedResultRecordCount = Annotated[
    int,
    Field(strict=True, ge=0, le=64),
]
TypedResultOrdinal = Annotated[
    int,
    Field(strict=True, ge=0, le=63),
]
TypedResultRecords = Annotated[
    tuple["TypedResultRecordV1", ...],
    Field(max_length=64),
]
ResultPageTargetKindV4 = Literal[
    "DOCUMENT_RESULT",
    "DATASET",
    "URL_CANDIDATE_RESULT",
]


def _canonical_json_text(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_lineage(
    lineage: tuple[str, ...], required: set[str], label: str
) -> None:
    if not required.issubset(lineage):
        raise ValueError(f"{label} lineage is incomplete")
    if len(lineage) != len(set(lineage)):
        raise ValueError(f"{label} lineage must be unique")


class RawResponsePublicationV1(BoundaryModel):
    publication_id: Identifier
    principal_id: Identifier
    request_id: Identifier
    operation_id: Identifier
    artifact_id: Identifier
    attempt_id: Identifier
    engine_identity_id: Identifier
    engine_execution_receipt_id: Identifier
    policy_validation_id: Identifier
    source_url_hash: Sha256
    classification_ref: Identifier
    retention_policy_ref: Identifier
    media_type: Literal["application/json"] = "application/json"
    maximum_bytes: Literal[2_097_152] = 2_097_152
    retrieved_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_publication(self) -> Self:
        _require_lineage(
            self.lineage_parent_ids,
            {
                self.operation_id,
                self.request_id,
                self.attempt_id,
                self.engine_identity_id,
                self.classification_ref,
                self.retention_policy_ref,
            },
            "raw response publication",
        )
        if {
            self.engine_execution_receipt_id,
            self.policy_validation_id,
        }.intersection(self.lineage_parent_ids):
            raise ValueError(
                "raw response publication lineage cannot depend on future receipt or decision records"
            )
        return self


class SourceGapReasonV3(StrEnum):
    POLICY_DENIED = "POLICY_DENIED"
    UPSTREAM_AUTH_DENIED = "UPSTREAM_AUTH_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    MALFORMED_UPSTREAM_RESPONSE = "MALFORMED_UPSTREAM_RESPONSE"
    UNSUPPORTED_UPSTREAM_RESPONSE = "UNSUPPORTED_UPSTREAM_RESPONSE"


class SourceGapV3(BoundaryModel):
    source_gap_id: Identifier
    operation_id: Identifier
    request_id: Identifier
    reason: SourceGapReasonV3
    detail_code: ReasonCode
    attempt_receipt_ids: tuple[Identifier, ...]
    last_failure_class: ReasonCode
    http_status: Annotated[int, Field(strict=True, ge=400, le=599)] | None
    retry_after_ms: NonNegativeInt | None
    occurred_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_gap(self) -> Self:
        if not self.attempt_receipt_ids:
            raise ValueError(
                "source gaps require all attempt receipts"
            )
        if (
            self.reason is not SourceGapReasonV3.RATE_LIMITED
            and self.retry_after_ms is not None
        ):
            raise ValueError("only rate limits may carry retry_after_ms")
        if self.http_status is not None and self.reason not in {
            SourceGapReasonV3.UPSTREAM_AUTH_DENIED,
            SourceGapReasonV3.RATE_LIMITED,
        }:
            raise ValueError(
                "only upstream auth and rate-limit gaps may carry HTTP status"
            )
        if len(self.attempt_receipt_ids) != len(
            set(self.attempt_receipt_ids)
        ):
            raise ValueError("attempt receipt identifiers must be unique")
        required = {self.operation_id, self.request_id, *self.attempt_receipt_ids}
        _require_lineage(self.lineage_parent_ids, required, "source gap")
        return self


class TypedResultRecordV1(BoundaryModel):
    record_id: Identifier
    result_id: Identifier
    generation: PositiveInt
    ordinal: TypedResultOrdinal
    payload_schema_name: WireSchemaName
    payload_schema_version: Literal["1.0"] = "1.0"
    payload_schema_hash: Sha256
    canonical_payload_json: CanonicalPayloadJson
    payload_byte_count: Annotated[
        int,
        Field(strict=True, ge=2, le=131_072),
    ]
    payload_content_hash: Sha256
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        payload_octets = self.canonical_payload_json.encode("utf-8")
        if len(payload_octets) != self.payload_byte_count:
            raise ValueError("typed payload byte count differs from its bytes")
        if _sha256_text(self.canonical_payload_json) != self.payload_content_hash:
            raise ValueError("typed payload hash differs from its bytes")
        try:
            decoded = json.loads(self.canonical_payload_json)
        except json.JSONDecodeError as error:
            raise ValueError("typed payload must be a UTF-8 JSON object") from error
        if not isinstance(decoded, dict):
            raise ValueError("typed payload must be a canonical JSON object")
        if _canonical_json_text(decoded) != self.canonical_payload_json:
            raise ValueError("typed payload bytes are not canonical JSON")
        if len(payload_octets) > 131_072:
            raise ValueError("typed payload exceeds the UTF-8 byte ceiling")
        if not self.lineage_parent_ids:
            raise ValueError("typed result record requires upstream lineage")
        _require_lineage(self.lineage_parent_ids, set(), "typed result record")
        if self.record_id in self.lineage_parent_ids or self.result_id in self.lineage_parent_ids:
            raise ValueError("typed result record lineage cannot contain record or result self-edges")
        return self

    @classmethod
    def from_payload(
        cls,
        *,
        record_id: Identifier,
        result_id: Identifier,
        generation: int,
        ordinal: int,
        payload_schema_name: WireSchemaName,
        payload_schema_hash: Sha256,
        payload: BoundaryModel,
        lineage_parent_ids: tuple[Identifier, ...],
    ) -> "TypedResultRecordV1":
        canonical = _canonical_json_text(payload.model_dump(mode="json"))
        return cls(
            record_id=record_id,
            result_id=result_id,
            generation=generation,
            ordinal=ordinal,
            payload_schema_name=payload_schema_name,
            payload_schema_version="1.0",
            payload_schema_hash=payload_schema_hash,
            canonical_payload_json=canonical,
            payload_byte_count=len(canonical.encode("utf-8")),
            payload_content_hash=_sha256_text(canonical),
            lineage_parent_ids=lineage_parent_ids,
        )


def canonical_typed_result_content_hash(
    records: tuple[TypedResultRecordV1, ...],
) -> str:
    content = tuple(
        {
            "ordinal": record.ordinal,
            "record_id": record.record_id,
            "payload_schema_hash": record.payload_schema_hash,
            "payload_content_hash": record.payload_content_hash,
        }
        for record in records
    )
    return _sha256_text(_canonical_json_text(content))


def canonical_typed_result_page_hash(
    *,
    result_id: Identifier,
    generation: int,
    start_ordinal: int,
    records: tuple[TypedResultRecordV1, ...],
) -> str:
    return _sha256_text(
        _canonical_json_text(
            {
                "generation": generation,
                "record_ids": tuple(record.record_id for record in records),
                "record_payload_hashes": tuple(
                    record.payload_content_hash for record in records
                ),
                "record_schema_hashes": tuple(
                    record.payload_schema_hash for record in records
                ),
                "result_id": result_id,
                "start_ordinal": start_ordinal,
            }
        )
    )


class TypedResultPageV1(BoundaryModel):
    request_id: Identifier
    principal_id: Identifier
    operation_id: Identifier
    result_id: Identifier
    generation: PositiveInt
    record_schema_name: WireSchemaName
    record_schema_version: Literal["1.0"] = "1.0"
    payload_schema_hash: Sha256
    result_content_hash: Sha256
    total_record_count: TypedResultRecordCount
    start_ordinal: Annotated[int, Field(strict=True, ge=0, le=64)]
    records: TypedResultRecords
    returned_count: TypedResultRecordCount
    has_more: bool
    next_cursor: OpaqueResultCursor | None
    page_content_hash: Sha256
    response_byte_count: Annotated[
        int,
        Field(strict=True, ge=1, le=131_072),
    ]
    committed_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        if self.returned_count != len(self.records):
            raise ValueError("returned count differs from typed page records")
        if self.start_ordinal + self.returned_count > self.total_record_count:
            raise ValueError("typed page extends beyond its immutable result")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("next cursor is required exactly when more records exist")
        if self.has_more != (
            self.start_ordinal + self.returned_count
            < self.total_record_count
        ):
            raise ValueError("typed page continuation state is inconsistent")
        expected_ordinals = tuple(
            range(
                self.start_ordinal,
                self.start_ordinal + self.returned_count,
            )
        )
        if tuple(record.ordinal for record in self.records) != expected_ordinals:
            raise ValueError("typed page records must be contiguous and ordered")
        if any(
            record.result_id != self.result_id
            or record.generation != self.generation
            or record.payload_schema_name != self.record_schema_name
            or record.payload_schema_version != self.record_schema_version
            or record.payload_schema_hash != self.payload_schema_hash
            for record in self.records
        ):
            raise ValueError("typed page record identity is inconsistent")
        expected_page_hash = canonical_typed_result_page_hash(
            result_id=self.result_id,
            generation=self.generation,
            start_ordinal=self.start_ordinal,
            records=self.records,
        )
        if self.page_content_hash != expected_page_hash:
            raise ValueError("typed page content hash is inconsistent")
        if self.total_record_count == self.returned_count and (
            self.start_ordinal == 0
        ):
            if (
                canonical_typed_result_content_hash(self.records)
                != self.result_content_hash
            ):
                raise ValueError("complete typed result content hash is inconsistent")
        required = {self.request_id, self.operation_id, *(record.record_id for record in self.records)}
        _require_lineage(self.lineage_parent_ids, required, "typed result page")
        if self.result_id in self.lineage_parent_ids:
            raise ValueError("typed result page lineage cannot contain its result self-edge")
        return self


class ResultPageRequestV4(BoundaryModel):
    request_id: Identifier
    target_kind: ResultPageTargetKindV4
    target_id: Identifier
    cursor: OpaqueResultCursor | None
    page_size: Annotated[int, Field(strict=True, ge=1, le=64)]


class ResultPageTargetV3(BoundaryModel):
    target_id: Identifier
    authorization_id: Identifier
    principal_id: Identifier
    operation_id: Identifier
    target_kind: ResultPageTargetKindV4
    requested_target_id: Identifier
    target_generation: PositiveInt | None
    record_schema_name: WireSchemaName | None
    record_schema_version: Literal["1.0"] | None
    payload_schema_hash: Sha256 | None
    result_content_hash: Sha256 | None
    total_record_count: TypedResultRecordCount | None
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        typed_values = (
            self.record_schema_name,
            self.record_schema_version,
            self.payload_schema_hash,
            self.result_content_hash,
            self.total_record_count,
        )
        if self.target_kind == "URL_CANDIDATE_RESULT":
            if self.target_generation is None or not all(
                value is not None for value in typed_values
            ):
                raise ValueError(
                    "URL candidate target requires immutable typed-result identity"
                )
        elif any(value is not None for value in typed_values):
            raise ValueError(
                "document and dataset targets cannot carry typed-result identity"
            )
        if self.target_kind == "DATASET":
            if self.target_generation is None:
                raise ValueError("dataset target requires a generation")
        elif self.target_kind == "DOCUMENT_RESULT":
            if self.target_generation is not None:
                raise ValueError("document target cannot carry a generation")
        required = {
            self.authorization_id,
            self.requested_target_id,
            self.operation_id,
        }
        _require_lineage(self.lineage_parent_ids, required, "result-page target")
        return self


def upcast_result_page_request_v3(
    value: ResultPageRequestV3,
) -> ResultPageRequestV4:
    return ResultPageRequestV4(
        request_id=value.request_id,
        target_kind=value.target_kind.value,
        target_id=value.target_id,
        cursor=value.cursor,
        page_size=value.page_size,
    )


RawResponsePublicationWorkEnvelopeV1 = WorkEnvelopeV1[
    RawResponsePublicationV1
]
ResultPageRequestV4WorkEnvelopeV1 = WorkEnvelopeV1[ResultPageRequestV4]
TypedResultPageWorkEnvelopeV1 = WorkEnvelopeV1[TypedResultPageV1]
SourceGapV3WorkEnvelopeV1 = WorkEnvelopeV1[SourceGapV3]
