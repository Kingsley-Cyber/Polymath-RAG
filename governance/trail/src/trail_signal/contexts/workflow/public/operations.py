from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator
from trail_signal.contexts.data_os.public.contracts import (
    ResultPageResponseKind,
    ResultPageResponseV1,
)
from trail_signal.contexts.discovery.public.contracts import UrlCandidatePageV1
from trail_signal.contexts.evidence.public.contracts import EvidenceAdmissionV1, HarnessResearchReceiptV1, QualificationV1
from trail_signal.contexts.planning.public.contracts import ResearchDirectiveV1
from trail_signal.contexts.scoring.public.contracts import OpportunityScoreRefusalV1, OpportunityScoreV1
from trail_signal.kernel.contracts import (
    BoundaryModel,
    Identifier,
    NonEmptyText,
    ReasonCode,
    Sha256,
    WorkEnvelopeV1,
)
PositiveInt = Annotated[int, Field(strict=True, ge=1)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
BATCH_CHECKPOINT_MAXIMUM_JSON_BYTES = 57344
BATCH_CHECKPOINT_MAXIMUM_APPLIED_COMMAND_IDENTITIES = 64
class OperationPhase(StrEnum):
    PENDING = "PENDING"; RUNNING = "RUNNING"; PAUSED = "PAUSED"; WAITING = "WAITING"; TERMINAL = "TERMINAL"
class OperationTerminalOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"; SUCCEEDED_WITH_GAPS = "SUCCEEDED_WITH_GAPS"; CANCELLED = "CANCELLED"; FAILED = "FAILED"
class OperationWaitReason(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"; CAPACITY = "CAPACITY"; POLICY_REVIEW = "POLICY_REVIEW"; SOURCE_COOLDOWN = "SOURCE_COOLDOWN"
class OperationCommandKind(StrEnum):
    CANCEL = "CANCEL"; PAUSE = "PAUSE"; RESUME = "RESUME"
class OperationRefV1(BoundaryModel):
    operation_id: Identifier
    operation_kind: Identifier
    temporal_workflow_id: Identifier
    temporal_run_id: Identifier | None
    submitted_at: datetime = Field(strict=False)
    status_revision: NonNegativeInt = 0
class OperationStatusV1(BoundaryModel):
    operation_id: Identifier
    phase: OperationPhase
    terminal_outcome: OperationTerminalOutcome | None
    waiting_reason: OperationWaitReason | None
    gap_ids: tuple[Identifier, ...]
    artifact_ids: tuple[Identifier, ...]
    result_ids: tuple[Identifier, ...] = ()
    revision: NonNegativeInt
    updated_at: datetime
    terminal_at: datetime | None
    failure_code: ReasonCode | None
    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        terminal = self.phase is OperationPhase.TERMINAL
        if terminal != (self.terminal_outcome is not None):
            raise ValueError("terminal outcome is required only for TERMINAL phase")
        if terminal != (self.terminal_at is not None):
            raise ValueError("terminal_at is required only for TERMINAL phase")
        waiting = self.phase is OperationPhase.WAITING
        if waiting != (self.waiting_reason is not None):
            raise ValueError("waiting_reason is required only for WAITING phase")
        failed = self.terminal_outcome is OperationTerminalOutcome.FAILED
        if failed != (self.failure_code is not None):
            raise ValueError("failure_code is required only for FAILED outcome")
        if self.terminal_at is not None and self.terminal_at < self.updated_at:
            raise ValueError("terminal_at cannot precede updated_at")
        if len(self.gap_ids) != len(set(self.gap_ids)):
            raise ValueError("gap_ids must be unique")
        if len(self.artifact_ids) != len(set(self.artifact_ids)):
            raise ValueError("artifact_ids must be unique")
        if len(self.result_ids) != len(set(self.result_ids)):
            raise ValueError("result_ids must be unique")
        if (
            self.terminal_outcome is OperationTerminalOutcome.SUCCEEDED
            and self.gap_ids
        ):
            raise ValueError("SUCCEEDED cannot carry source gaps")
        if (
            self.terminal_outcome is OperationTerminalOutcome.SUCCEEDED_WITH_GAPS
            and not self.gap_ids
        ):
            raise ValueError("SUCCEEDED_WITH_GAPS requires at least one gap")
        if (
            self.terminal_outcome is OperationTerminalOutcome.SUCCEEDED
            and bool(self.artifact_ids) == bool(self.result_ids)
        ):
            raise ValueError("successful outcome requires exactly one output kind")
        if self.terminal_outcome in {
            OperationTerminalOutcome.CANCELLED,
            OperationTerminalOutcome.FAILED,
        } and (self.artifact_ids or self.result_ids):
            raise ValueError("cancelled or failed outcome cannot expose outputs")
        if self.terminal_outcome is OperationTerminalOutcome.FAILED and self.gap_ids:
            raise ValueError("internal failure cannot be represented as a source gap")
        return self
class OperationCommandV1(BoundaryModel):
    command_id: Identifier
    operation_id: Identifier
    command: OperationCommandKind = Field(strict=False)
    expected_revision: NonNegativeInt
    idempotency_key: Identifier
    requested_at: datetime = Field(strict=False)
    reason_code: ReasonCode | None
class OperationBudgetV1(BoundaryModel):
    budget_id: Identifier
    max_physical_attempts: PositiveInt
    max_duration_seconds: PositiveInt
    max_response_bytes: PositiveInt
    max_redirects: NonNegativeInt
    deadline_at: datetime
    policy_ref: Identifier
    exhaustion_reason_code: Literal["BUDGET_EXHAUSTED"] = "BUDGET_EXHAUSTED"
OperationCommandWorkEnvelopeV1 = WorkEnvelopeV1[OperationCommandV1]


class OperationTerminalOutcomeV2(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
class OperationOutputKind(StrEnum):
    RAW_ARTIFACT = "RAW_ARTIFACT"
    DOCUMENT_RESULT = "DOCUMENT_RESULT"
    DATASET = "DATASET"
class OperationIssueKind(StrEnum):
    SOURCE_GAP = "SOURCE_GAP"
    CHILD_FAILURE = "CHILD_FAILURE"
class BatchChildPhase(StrEnum):
    CRAWL_PENDING = "CRAWL_PENDING"
    CRAWLING = "CRAWLING"
    EXTRACTION_PENDING = "EXTRACTION_PENDING"
    EXTRACTING = "EXTRACTING"
    TERMINAL = "TERMINAL"
class OperationOutputRefV1(BoundaryModel):
    output_kind: OperationOutputKind
    output_id: Identifier
    generation: PositiveInt | None

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        if self.output_kind is OperationOutputKind.DATASET:
            if self.generation is None:
                raise ValueError("dataset output requires a generation")
        elif self.generation is not None:
            raise ValueError("only dataset output carries a generation")
        return self
class OperationIssueRefV1(BoundaryModel):
    issue_kind: OperationIssueKind
    issue_id: Identifier
    item_id: Identifier | None
    ordinal: Annotated[int, Field(strict=True, ge=0, le=63)] | None

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        if (self.item_id is None) != (self.ordinal is None):
            raise ValueError("item identity and ordinal must appear together")
        if (
            self.issue_kind is OperationIssueKind.CHILD_FAILURE
            and self.item_id is None
        ):
            raise ValueError("child failure requires an item identity")
        return self
class BatchExecutionRefV1(BoundaryModel):
    operation_id: Identifier
    workflow_id: Identifier
    run_id: Identifier | None
    dataset_id: Identifier
    generation: PositiveInt
    checkpoint_id: Identifier | None
    configuration_ref: Identifier
    code_version: Identifier
    submitted_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        required = {
            self.operation_id,
            self.dataset_id,
            self.configuration_ref,
            self.code_version,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError(
                "batch execution lineage requires operation and dataset identities"
            )
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("batch execution lineage must be unique")
        return self
class BatchChildOperationRefV1(BoundaryModel):
    item_id: Identifier
    ordinal: Annotated[int, Field(strict=True, ge=0, le=63)]
    crawl_operation_id: Identifier
    crawl_workflow_id: Identifier
    extraction_operation_id: Identifier | None
    extraction_workflow_id: Identifier | None
    phase: BatchChildPhase
    terminal_item_record_id: Identifier | None

    @model_validator(mode="after")
    def validate_child(self) -> Self:
        extraction_refs = (
            self.extraction_operation_id,
            self.extraction_workflow_id,
        )
        if any(value is not None for value in extraction_refs) and not all(
            value is not None for value in extraction_refs
        ):
            raise ValueError("extraction operation and workflow references are atomic")
        if self.phase in {
            BatchChildPhase.EXTRACTION_PENDING,
            BatchChildPhase.EXTRACTING,
        } and self.extraction_operation_id is None:
            raise ValueError("extraction phases require extraction child references")
        if self.phase is BatchChildPhase.TERMINAL:
            if self.terminal_item_record_id is None:
                raise ValueError("terminal child requires an item record reference")
        elif self.terminal_item_record_id is not None:
            raise ValueError("only a terminal child carries an item record reference")
        return self
class BatchCheckpointV1(BoundaryModel):
    checkpoint_id: Identifier
    operation_id: Identifier
    dataset_id: Identifier
    generation: PositiveInt
    status_revision: PositiveInt
    next_unadmitted_ordinal: Annotated[int, Field(strict=True, ge=0, le=64)]
    outcome_ids: tuple[Identifier, ...]
    failure_ids: tuple[Identifier, ...]
    child_refs: tuple[BatchChildOperationRefV1, ...]
    issue_refs: tuple[OperationIssueRefV1, ...]
    applied_command_message_ids: Annotated[
        tuple[Identifier, ...],
        Field(max_length=BATCH_CHECKPOINT_MAXIMUM_APPLIED_COMMAND_IDENTITIES),
    ] = ()
    requested_count: Annotated[int, Field(strict=True, ge=1, le=64)]
    admitted_count: Annotated[int, Field(strict=True, ge=0, le=64)]
    succeeded_count: Annotated[int, Field(strict=True, ge=0, le=64)]
    failed_count: Annotated[int, Field(strict=True, ge=0, le=64)]
    paused: bool
    backpressure_generation: NonNegativeInt
    continue_as_new_after_events: Annotated[int, Field(strict=True, ge=1, le=1000000)]
    batch_policy_ref: Identifier
    configuration_ref: Identifier
    code_version: Identifier
    recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_checkpoint(self) -> Self:
        if len(self.outcome_ids) != len(set(self.outcome_ids)):
            raise ValueError("checkpoint outcome references must be unique")
        if len(self.failure_ids) != len(set(self.failure_ids)):
            raise ValueError("checkpoint failure references must be unique")
        if set(self.outcome_ids) & set(self.failure_ids):
            raise ValueError("outcome and failure references must be disjoint")
        if len(self.child_refs) != self.admitted_count:
            raise ValueError(
                "drained checkpoint requires one child reference per admitted item"
            )
        if any(
            child.phase is not BatchChildPhase.TERMINAL
            for child in self.child_refs
        ):
            raise ValueError("drained checkpoint child references must be terminal")
        child_ordinals = tuple(child.ordinal for child in self.child_refs)
        if child_ordinals != tuple(range(self.admitted_count)):
            raise ValueError(
                "checkpoint child references must be in contiguous admitted order"
            )
        child_item_ids = tuple(child.item_id for child in self.child_refs)
        if len(child_item_ids) != len(set(child_item_ids)):
            raise ValueError("checkpoint child item identities must be unique")
        terminal_record_ids = tuple(
            child.terminal_item_record_id for child in self.child_refs
        )
        expected_record_ids = set(self.outcome_ids) | set(self.failure_ids)
        if (
            len(terminal_record_ids) != len(set(terminal_record_ids))
            or set(terminal_record_ids) != expected_record_ids
        ):
            raise ValueError(
                "each terminal child must map to exactly one outcome or failure"
            )
        issue_keys = tuple(
            (issue.issue_kind, issue.issue_id, issue.item_id, issue.ordinal)
            for issue in self.issue_refs
        )
        if len(issue_keys) != len(set(issue_keys)):
            raise ValueError("checkpoint issue references must be unique")
        if len(self.applied_command_message_ids) != len(
            set(self.applied_command_message_ids)
        ):
            raise ValueError(
                "checkpoint command message identities must be unique"
            )
        issue_ordinals = tuple(issue.ordinal for issue in self.issue_refs)
        failed_ordinals = tuple(
            child.ordinal
            for child in self.child_refs
            if child.terminal_item_record_id in set(self.failure_ids)
        )
        if issue_ordinals != failed_ordinals:
            raise ValueError(
                "checkpoint requires one ordered issue per failed item"
            )
        if self.succeeded_count != len(self.outcome_ids):
            raise ValueError("succeeded_count must match outcome references")
        if self.failed_count != len(self.failure_ids):
            raise ValueError("failed_count must match failure references")
        if self.admitted_count != self.succeeded_count + self.failed_count:
            raise ValueError("a drained checkpoint requires every admitted item reduced")
        if self.admitted_count > self.requested_count:
            raise ValueError("admitted count cannot exceed requested count")
        if self.next_unadmitted_ordinal < self.admitted_count:
            raise ValueError("next ordinal cannot precede admitted count")
        if self.next_unadmitted_ordinal > self.requested_count:
            raise ValueError("next ordinal cannot exceed requested count")
        required = {
            self.operation_id,
            self.dataset_id,
            self.configuration_ref,
            self.code_version,
            *self.outcome_ids,
            *self.failure_ids,
            *(issue.issue_id for issue in self.issue_refs),
            *self.applied_command_message_ids,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("checkpoint lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("checkpoint lineage must be unique")
        if (
            len(self.model_dump_json().encode("utf-8"))
            > BATCH_CHECKPOINT_MAXIMUM_JSON_BYTES
        ):
            raise ValueError(
                "batch checkpoint exceeds the canonical JSON byte ceiling"
            )
        return self
class BatchWorkflowConfigurationV1(BoundaryModel):
    configuration_ref: Identifier
    code_version: Identifier
    static_task_queue: Identifier
    extraction_task_queue: Identifier
    maximum_applied_commands: Annotated[int, Field(
        strict=True, ge=1, le=BATCH_CHECKPOINT_MAXIMUM_APPLIED_COMMAND_IDENTITIES,
    )] = BATCH_CHECKPOINT_MAXIMUM_APPLIED_COMMAND_IDENTITIES
    maximum_active_item_pipelines: Annotated[int, Field(strict=True, ge=1, le=16)]
    extraction_backlog_high_watermark: Annotated[int, Field(strict=True, ge=2, le=64)]
    extraction_backlog_low_watermark: Annotated[int, Field(strict=True, ge=1, le=63)]
    maximum_extraction_records: Annotated[int, Field(strict=True, ge=1, le=64)]
    maximum_extraction_output_bytes: Annotated[int, Field(strict=True, ge=1, le=524288)]
    continue_as_new_after_events: Annotated[int, Field(strict=True, ge=1, le=1000000)]

    @model_validator(mode="after")
    def validate_watermarks(self) -> Self:
        if (
            self.extraction_backlog_low_watermark
            >= self.extraction_backlog_high_watermark
        ):
            raise ValueError(
                "extraction backlog low watermark must be below high watermark"
            )
        return self

BatchWorkflowConfigurationWorkEnvelopeV1 = WorkEnvelopeV1[BatchWorkflowConfigurationV1]
class BatchStartIntentV1(BoundaryModel):
    operation_id: Identifier
    workflow_id: Identifier
    request_message_id: Identifier
    principal_snapshot_id: Identifier
    batch_task_queue: Identifier
    configuration: BatchWorkflowConfigurationWorkEnvelopeV1
    recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_start_intent(self) -> Self:
        configuration = self.configuration
        if (
            configuration.operation_id != self.operation_id
            or configuration.operation_kind != "scrape.submit"
            or configuration.causation_id != self.request_message_id
            or configuration.observed_at != self.recorded_at
            or configuration.retrieved_at != self.recorded_at
            or configuration.system_recorded_at != self.recorded_at
        ):
            raise ValueError("batch start configuration is misbound")
        required = {
            self.operation_id,
            self.workflow_id,
            self.request_message_id,
            self.principal_snapshot_id,
            configuration.message_id,
            configuration.payload.configuration_ref,
            configuration.payload.code_version,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("batch start intent lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("batch start intent lineage must be unique")
        return self

BatchStartIntentWorkEnvelopeV1 = WorkEnvelopeV1[BatchStartIntentV1]
class OperationStatusV2(BoundaryModel):
    operation_id: Identifier
    phase: OperationPhase
    terminal_outcome: OperationTerminalOutcomeV2 | None
    waiting_reason: OperationWaitReason | None
    output_refs: tuple[OperationOutputRefV1, ...]
    issue_refs: tuple[OperationIssueRefV1, ...]
    revision: NonNegativeInt
    updated_at: datetime
    terminal_at: datetime | None
    failure_code: ReasonCode | None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        terminal = self.phase is OperationPhase.TERMINAL
        if terminal != (self.terminal_outcome is not None):
            raise ValueError("terminal outcome is required only for TERMINAL phase")
        if terminal != (self.terminal_at is not None):
            raise ValueError("terminal_at is required only for TERMINAL phase")
        waiting = self.phase is OperationPhase.WAITING
        if waiting != (self.waiting_reason is not None):
            raise ValueError("waiting_reason is required only for WAITING phase")
        failed = self.terminal_outcome is OperationTerminalOutcomeV2.FAILED
        if failed != (self.failure_code is not None):
            raise ValueError("failure_code is required only for FAILED outcome")
        if self.terminal_at is not None and self.terminal_at < self.updated_at:
            raise ValueError("terminal_at cannot precede updated_at")
        output_keys = tuple(
            (value.output_kind, value.output_id, value.generation)
            for value in self.output_refs
        )
        if len(output_keys) != len(set(output_keys)):
            raise ValueError("operation output references must be unique")
        issue_keys = tuple(
            (value.issue_kind, value.issue_id) for value in self.issue_refs
        )
        if len(issue_keys) != len(set(issue_keys)):
            raise ValueError("operation issue references must be unique")
        if self.terminal_outcome is OperationTerminalOutcomeV2.SUCCEEDED:
            if not self.output_refs or self.issue_refs:
                raise ValueError("SUCCEEDED requires output and forbids issues")
        if self.terminal_outcome is OperationTerminalOutcomeV2.PARTIAL:
            if not self.issue_refs:
                raise ValueError("PARTIAL requires at least one typed issue")
        if self.terminal_outcome is OperationTerminalOutcomeV2.CANCELLED:
            if any(
                value.output_kind is not OperationOutputKind.DATASET
                for value in self.output_refs
            ):
                raise ValueError("CANCELLED may expose only a dataset output")
        if self.terminal_outcome is OperationTerminalOutcomeV2.FAILED:
            if self.output_refs or self.issue_refs:
                raise ValueError("FAILED cannot expose outputs or item issues")
        return self


def upcast_operation_status_v1(value: OperationStatusV1) -> OperationStatusV2:
    outputs = tuple(
        OperationOutputRefV1(
            output_kind=OperationOutputKind.RAW_ARTIFACT,
            output_id=artifact_id,
            generation=None,
        )
        for artifact_id in value.artifact_ids
    ) + tuple(
        OperationOutputRefV1(
            output_kind=OperationOutputKind.DOCUMENT_RESULT,
            output_id=result_id,
            generation=None,
        )
        for result_id in value.result_ids
    )
    issues = tuple(
        OperationIssueRefV1(
            issue_kind=OperationIssueKind.SOURCE_GAP,
            issue_id=gap_id,
            item_id=None,
            ordinal=None,
        )
        for gap_id in value.gap_ids
    )
    outcome = (
        None
        if value.terminal_outcome is None
        else OperationTerminalOutcomeV2.PARTIAL
        if value.terminal_outcome
        is OperationTerminalOutcome.SUCCEEDED_WITH_GAPS
        else OperationTerminalOutcomeV2(value.terminal_outcome.value)
    )
    return OperationStatusV2(
        operation_id=value.operation_id,
        phase=value.phase,
        terminal_outcome=outcome,
        waiting_reason=value.waiting_reason,
        output_refs=outputs,
        issue_refs=issues,
        revision=value.revision,
        updated_at=value.updated_at,
        terminal_at=value.terminal_at,
        failure_code=value.failure_code,
    )


BatchExecutionRefWorkEnvelopeV1 = WorkEnvelopeV1[BatchExecutionRefV1]
BatchCheckpointWorkEnvelopeV1 = WorkEnvelopeV1[BatchCheckpointV1]


class OperationOutputKindV2(StrEnum):
    RAW_ARTIFACT = "RAW_ARTIFACT"
    DOCUMENT_RESULT = "DOCUMENT_RESULT"
    DATASET = "DATASET"
    DATASET_QUERY = "DATASET_QUERY"
    EXPORT = "EXPORT"


class OperationExecutionAuthorityV1(StrEnum):
    TEMPORAL = "TEMPORAL"
    SYNCHRONOUS = "SYNCHRONOUS"


class OperationOutputRefV2(BoundaryModel):
    output_kind: OperationOutputKindV2
    output_id: Identifier
    generation: PositiveInt | None

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        if self.output_kind.value == OperationOutputKindV2.DATASET.value:
            if self.generation is None:
                raise ValueError("dataset output requires a generation")
        elif self.generation is not None:
            raise ValueError("only dataset output carries a generation")
        return self


class OperationStatusV3(BoundaryModel):
    operation_id: Identifier
    execution_authority: OperationExecutionAuthorityV1
    phase: OperationPhase
    terminal_outcome: OperationTerminalOutcomeV2 | None
    waiting_reason: OperationWaitReason | None
    output_refs: tuple[OperationOutputRefV2, ...]
    issue_refs: tuple[OperationIssueRefV1, ...]
    revision: NonNegativeInt
    updated_at: datetime
    terminal_at: datetime | None
    failure_code: ReasonCode | None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        terminal = self.phase is OperationPhase.TERMINAL
        if terminal != (self.terminal_outcome is not None):
            raise ValueError("terminal outcome is required only for TERMINAL phase")
        if terminal != (self.terminal_at is not None):
            raise ValueError("terminal_at is required only for TERMINAL phase")
        waiting = self.phase is OperationPhase.WAITING
        if waiting != (self.waiting_reason is not None):
            raise ValueError("waiting_reason is required only for WAITING phase")
        failed = self.terminal_outcome is OperationTerminalOutcomeV2.FAILED
        if failed != (self.failure_code is not None):
            raise ValueError("failure_code is required only for FAILED outcome")
        if self.terminal_at is not None and self.terminal_at < self.updated_at:
            raise ValueError("terminal_at cannot precede updated_at")
        output_keys = tuple(
            (value.output_kind, value.output_id, value.generation)
            for value in self.output_refs
        )
        if len(output_keys) != len(set(output_keys)):
            raise ValueError("operation output references must be unique")
        issue_keys = tuple(
            (value.issue_kind, value.issue_id) for value in self.issue_refs
        )
        if len(issue_keys) != len(set(issue_keys)):
            raise ValueError("operation issue references must be unique")
        if self.terminal_outcome is OperationTerminalOutcomeV2.SUCCEEDED:
            if not self.output_refs or self.issue_refs:
                raise ValueError("SUCCEEDED requires output and forbids issues")
        if self.terminal_outcome is OperationTerminalOutcomeV2.PARTIAL:
            if not self.issue_refs:
                raise ValueError("PARTIAL requires at least one typed issue")
        if self.terminal_outcome is OperationTerminalOutcomeV2.CANCELLED:
            if any(
                value.output_kind.value != OperationOutputKindV2.DATASET.value
                for value in self.output_refs
            ):
                raise ValueError("CANCELLED may expose only a dataset output")
        if self.terminal_outcome is OperationTerminalOutcomeV2.FAILED:
            if self.output_refs or self.issue_refs:
                raise ValueError("FAILED cannot expose outputs or item issues")
        if self.execution_authority is OperationExecutionAuthorityV1.SYNCHRONOUS:
            if self.phase is not OperationPhase.TERMINAL:
                raise ValueError("synchronous status requires TERMINAL phase")
            if self.waiting_reason is not None:
                raise ValueError("synchronous status forbids waiting_reason")
            if self.terminal_outcome in {
                OperationTerminalOutcomeV2.PARTIAL,
                OperationTerminalOutcomeV2.CANCELLED,
            }:
                raise ValueError("synchronous status forbids PARTIAL and CANCELLED")
            if self.terminal_outcome is OperationTerminalOutcomeV2.SUCCEEDED:
                if len(self.output_refs) != 1 or (
                    self.output_refs[0].output_kind.value
                    != OperationOutputKindV2.DATASET_QUERY.value
                ):
                    raise ValueError(
                        "synchronous success requires exactly one DATASET_QUERY output"
                    )
            if any(
                value.output_kind.value == OperationOutputKindV2.EXPORT.value
                for value in self.output_refs
            ):
                raise ValueError("synchronous status cannot expose EXPORT")
        return self


def upcast_operation_output_ref_v1(
    value: OperationOutputRefV1,
) -> OperationOutputRefV2:
    return OperationOutputRefV2(
        output_kind=OperationOutputKindV2(value.output_kind.value),
        output_id=value.output_id,
        generation=value.generation,
    )


def upcast_operation_status_v2(value: OperationStatusV2) -> OperationStatusV3:
    return OperationStatusV3(
        operation_id=value.operation_id,
        execution_authority=OperationExecutionAuthorityV1.TEMPORAL,
        phase=value.phase,
        terminal_outcome=value.terminal_outcome,
        waiting_reason=value.waiting_reason,
        output_refs=tuple(
            upcast_operation_output_ref_v1(item) for item in value.output_refs
        ),
        issue_refs=value.issue_refs,
        revision=value.revision,
        updated_at=value.updated_at,
        terminal_at=value.terminal_at,
        failure_code=value.failure_code,
    )


class DatasetExportExecutionRefV1(BoundaryModel):
    operation_id: Identifier
    workflow_id: Identifier
    run_id: Identifier | None
    export_id: Identifier
    dataset_id: Identifier
    dataset_generation: PositiveInt
    dataset_snapshot_id: Identifier
    dataset_snapshot_content_hash: Sha256
    configuration_ref: Identifier
    code_version: Identifier
    submitted_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        if not self.lineage_parent_ids:
            raise ValueError("export execution requires lineage parents")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("export execution lineage must be unique")
        return self


class DatasetExportWorkflowConfigurationV1(BoundaryModel):
    configuration_ref: Identifier
    code_version: Identifier
    workflow_task_queue: Identifier
    serializer_activity_task_queue: Identifier
    schedule_to_close_seconds: Literal[900] = 900
    start_to_close_seconds: Literal[300] = 300
    heartbeat_timeout_seconds: Literal[10] = 10
    heartbeat_interval_seconds: Literal[2] = 2
    maximum_attempts: Literal[3] = 3
    initial_retry_interval_seconds: Literal[1] = 1
    retry_backoff_coefficient: Literal[2.0] = 2.0
    maximum_retry_interval_seconds: Literal[10] = 10
    cancellation_type: Literal["WAIT_CANCELLATION_COMPLETED"] = (
        "WAIT_CANCELLATION_COMPLETED"
    )
    maximum_snapshot_records: Literal[4096] = 4096
    maximum_snapshot_bytes: Literal[41943040] = 41943040
    maximum_output_bytes: Literal[67108864] = 67108864
    serializer_runtime_profile_ref: Identifier
    serializer_runtime_profile_hash: Sha256
    serializer_image_digest: Sha256
    serializer_platform_digest: Sha256
    export_schema_ref: Identifier
    export_schema_hash: Sha256
    writer_configuration_ref: Identifier
    writer_configuration_hash: Sha256
    object_store_profile_ref: Identifier
    object_store_profile_hash: Sha256
    retention_policy_ref: Identifier


DatasetExportWorkflowConfigurationWorkEnvelopeV1 = WorkEnvelopeV1[
    DatasetExportWorkflowConfigurationV1
]


class DatasetExportStartIntentV1(BoundaryModel):
    operation_id: Identifier
    workflow_id: Identifier
    export_id: Identifier
    request_message_id: Identifier
    request_content_hash: Sha256
    principal_snapshot_id: Identifier
    dataset_snapshot_ref_message_id: Identifier
    dataset_snapshot_id: Identifier
    dataset_snapshot_content_hash: Sha256
    dataset_id: Identifier
    dataset_generation: PositiveInt
    configuration: DatasetExportWorkflowConfigurationWorkEnvelopeV1
    recorded_at: datetime
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_start_intent(self) -> Self:
        configuration = self.configuration
        if (
            configuration.operation_id != self.operation_id
            or configuration.operation_kind != "dataset.export"
            or configuration.causation_id != self.request_message_id
            or configuration.observed_at != self.recorded_at
            or configuration.retrieved_at != self.recorded_at
            or configuration.system_recorded_at != self.recorded_at
        ):
            raise ValueError("export start configuration is misbound")
        required = {
            self.operation_id,
            self.workflow_id,
            self.export_id,
            self.request_message_id,
            self.principal_snapshot_id,
            configuration.message_id,
            configuration.payload.configuration_ref,
            configuration.payload.code_version,
        }
        if not required.issubset(self.lineage_parent_ids):
            raise ValueError("export start intent lineage is incomplete")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("export start intent lineage must be unique")
        return self


DatasetExportExecutionRefWorkEnvelopeV1 = WorkEnvelopeV1[DatasetExportExecutionRefV1]
DatasetExportStartIntentWorkEnvelopeV1 = WorkEnvelopeV1[DatasetExportStartIntentV1]


class OperationOutputKindV3(StrEnum):
    RAW_ARTIFACT = "RAW_ARTIFACT"
    DOCUMENT_RESULT = "DOCUMENT_RESULT"
    DATASET = "DATASET"
    DATASET_QUERY = "DATASET_QUERY"
    EXPORT = "EXPORT"
    URL_CANDIDATE_RESULT = "URL_CANDIDATE_RESULT"


class OperationOutputRefV3(BoundaryModel):
    output_kind: OperationOutputKindV3
    output_id: Identifier
    generation: PositiveInt | None

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        OperationOutputRefV2.validate_output(self)
        return self


class OperationStatusV4(BoundaryModel):
    operation_id: Identifier
    execution_authority: OperationExecutionAuthorityV1
    phase: OperationPhase
    terminal_outcome: OperationTerminalOutcomeV2 | None
    waiting_reason: OperationWaitReason | None
    output_refs: tuple[OperationOutputRefV3, ...]
    issue_refs: tuple[OperationIssueRefV1, ...]
    revision: NonNegativeInt
    updated_at: datetime
    terminal_at: datetime | None
    failure_code: ReasonCode | None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        OperationStatusV3.validate_lifecycle(self)
        return self


class OperationResultPageV2(BoundaryModel):
    output_kind: OperationOutputKindV3
    result_page: ResultPageResponseV1 | None
    url_candidate_page: UrlCandidatePageV1 | None

    @model_validator(mode="after")
    def validate_result_page(self) -> Self:
        if self.output_kind is OperationOutputKindV3.URL_CANDIDATE_RESULT:
            if self.url_candidate_page is None or self.result_page is not None:
                raise ValueError(
                    "URL candidate result requires only a URL candidate page"
                )
            return self
        if self.url_candidate_page is not None or self.result_page is None:
            raise ValueError(
                "document and dataset results require only a result page"
            )
        expected_kind = {
            OperationOutputKindV3.DOCUMENT_RESULT: (
                ResultPageResponseKind.DOCUMENT_RESULT
            ),
            OperationOutputKindV3.DATASET: ResultPageResponseKind.DATASET,
        }.get(self.output_kind)
        if expected_kind is None or self.result_page.response_kind is not expected_kind:
            raise ValueError("operation output kind does not match the result page")
        return self


def upcast_operation_output_ref_v2(
    value: OperationOutputRefV2
) -> OperationOutputRefV3:
    return OperationOutputRefV3(
        output_kind=OperationOutputKindV3(value.output_kind.value),
        output_id=value.output_id,
        generation=value.generation,
    )


def upcast_operation_status_v3(value: OperationStatusV3) -> OperationStatusV4:
    return OperationStatusV4(
        operation_id=value.operation_id,
        execution_authority=value.execution_authority,
        phase=value.phase,
        terminal_outcome=value.terminal_outcome,
        waiting_reason=value.waiting_reason,
        output_refs=tuple(
            upcast_operation_output_ref_v2(item) for item in value.output_refs
        ),
        issue_refs=value.issue_refs,
        revision=value.revision,
        updated_at=value.updated_at,
        terminal_at=value.terminal_at,
        failure_code=value.failure_code,
    )


# ── ADR-063 / HR3: the bounded synchronous research operations on the Polymath wire (request and result envelopes).
class ResearchSnapshotRefV1(BoundaryModel):
    snapshot_id: Identifier
    content_hash: Sha256


class ResearchHypothesisViewV1(BoundaryModel):
    hypothesis_id: Identifier
    revision: NonNegativeInt
    status: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=4096)]


class ResearchKnowledgeGapV1(BoundaryModel):
    gap_id: Identifier | None = None
    hypothesis_id: Identifier | None = None
    question: Annotated[str, Field(min_length=1, max_length=4096)]
    evidence_role: Identifier


class ResearchPhysicalJobV1(BoundaryModel):
    hypothesis_id: Identifier
    job: NonEmptyText
    mechanism: NonEmptyText


class ResearchPayloadV1(BoundaryModel):
    """Exactly the generic engine state Polymath assembles for a bounded operation; unused fields stay empty or null."""
    stage: Identifier | None = None
    hypotheses: tuple[ResearchHypothesisViewV1, ...] = ()
    admitted_evidence_ids: tuple[Identifier, ...] = ()
    max_priors_per_hypothesis: PositiveInt | None = None
    knowledge_gaps: tuple[ResearchKnowledgeGapV1, ...] = ()
    open_gaps: tuple[ResearchKnowledgeGapV1, ...] = ()
    action_id: Identifier | None = None
    receipt: HarnessResearchReceiptV1 | None = None
    redundancy_groups: tuple[tuple[Identifier, ...], ...] = ()
    latest_admission_id: Identifier | None = None
    physical_jobs: tuple[ResearchPhysicalJobV1, ...] = ()
    qualifications: tuple[QualificationV1, ...] = ()


class BoundedResearchRequestV1(BoundaryModel):
    request_id: Identifier
    idempotency_key: Identifier
    purpose_ref: Identifier
    run_ref: Identifier
    operation_kind: Literal["registry.project", "gaps.compile", "evidence.admit", "hypotheses.judge", "territory.project", "opportunity.qualify", "opportunity.score"]
    registry_snapshot_id: Identifier | None
    payload: ResearchPayloadV1

    @model_validator(mode="before")
    @classmethod
    def accept_json_wire(cls, value: object) -> object:
        """The MCP tool argument arrives as parsed JSON: the payload is validated in JSON mode (the wire's own encoding), so its
        arrays, ISO-8601 datetimes, and enum values meet the strict nested contracts; in-process callers pass models unchanged."""
        if isinstance(value, dict) and isinstance(value.get("payload"), dict):
            try:
                encoded = json.dumps(value["payload"])
            except TypeError:
                return value
            return {**value, "payload": ResearchPayloadV1.model_validate_json(encoded)}
        return value


class ResearchPriorV1(BoundaryModel):
    registry_record_id: Identifier
    prior_role: Identifier
    hypothesis_ids: tuple[Identifier, ...]


class ResearchCauseRefV1(BoundaryModel):
    kind: Identifier
    id: Identifier


class ResearchVerdictV1(BoundaryModel):
    hypothesis_id: Identifier
    kind: Identifier
    polymath_transition: Identifier | None
    cause_refs: tuple[ResearchCauseRefV1, ...]
    reason_code: ReasonCode
    into_hypothesis_id: Identifier | None


class ResearchTerritoryV1(BoundaryModel):
    territory_id: Identifier
    territory: Identifier
    hypothesis_ids: tuple[Identifier, ...]


class ResearchResultV1(BoundaryModel):
    """The typed result body; the operation kind decides which fields are present."""
    registry_snapshot: ResearchSnapshotRefV1 | None = None
    priors: tuple[ResearchPriorV1, ...] = ()
    redundancy_groups: tuple[tuple[Identifier, ...], ...] = ()
    unsupported_hypothesis_ids: tuple[Identifier, ...] = ()
    research_directive: ResearchDirectiveV1 | None = None
    evidence_admission: EvidenceAdmissionV1 | None = None
    verdicts: tuple[ResearchVerdictV1, ...] = ()
    open_gaps: tuple[ResearchKnowledgeGapV1, ...] = ()
    territories: tuple[ResearchTerritoryV1, ...] = ()
    qualifications: tuple[QualificationV1, ...] = ()
    trail_scores: tuple[OpportunityScoreV1, ...] = ()
    score_refusals: tuple[OpportunityScoreRefusalV1, ...] = ()


class BoundedResearchResultV1(BoundaryModel):
    operation_id: Identifier
    operation_kind: Literal["registry.project", "gaps.compile", "evidence.admit", "hypotheses.judge", "territory.project", "opportunity.qualify", "opportunity.score"]
    status_revision: NonNegativeInt
    registry_snapshot: ResearchSnapshotRefV1 | None
    result: ResearchResultV1
    result_sha256: Sha256
