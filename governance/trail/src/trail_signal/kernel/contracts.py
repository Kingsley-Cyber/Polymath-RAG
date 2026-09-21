from __future__ import annotations
from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, Self, TypeVar
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator
Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]
NonEmptyText = Annotated[str, StringConstraints(min_length=1, max_length=512)]
ReasonCode = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Z][A-Z0-9_]*$"),
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
WireSchemaName = Annotated[
    str,
    StringConstraints(
        min_length=5,
        max_length=160,
        pattern=r"^[a-z][a-z0-9_]*(?:[._-][a-z0-9_]+)*\.v[1-9][0-9]*$",
    ),
]
class BoundaryModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    @field_validator("*")
    @classmethod
    def require_utc_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("datetime must be timezone-aware")
            if value.utcoffset() != timezone.utc.utcoffset(value):
                raise ValueError("datetime must use UTC")
        return value
PayloadT = TypeVar("PayloadT", bound=BoundaryModel)
class WorkEnvelopeV1(BoundaryModel, Generic[PayloadT]):
    schema_name: WireSchemaName
    schema_version: Literal["1.0"]
    message_id: Identifier
    operation_id: Identifier
    operation_kind: Identifier
    purpose_ref: Identifier
    policy_ref: Identifier
    correlation_id: Identifier
    causation_id: Identifier | None
    producer: Identifier
    lineage_parent_ids: tuple[Identifier, ...]
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    payload: PayloadT
    @classmethod
    def model_parametrized_name(
        cls,
        params: tuple[type[BoundaryModel], ...],
    ) -> str:
        return f"{params[0].__name__.removesuffix('V1')}WorkEnvelopeV1"
    @model_validator(mode="after")
    def validate_time_and_source_semantics(self) -> Self:
        payload_name = type(self.payload).__name__.removesuffix("V1")
        payload_wire_name = "".join(
            f"_{character.lower()}" if character.isupper() else character
            for character in payload_name
        ).lstrip("_")
        expected_schema_name = (
            f"trail_signal.work_envelope.{payload_wire_name}.v1"
        )
        if self.schema_name != expected_schema_name:
            raise ValueError(
                f"schema_name must be {expected_schema_name}"
            )
        if (self.source_event_at is None) == (
            self.source_event_absence_reason is None
        ):
            raise ValueError(
                "source_event_at and source_event_absence_reason are mutually exclusive"
            )
        if self.observed_at > self.retrieved_at:
            raise ValueError("observed_at cannot follow retrieved_at")
        if self.retrieved_at > self.system_recorded_at:
            raise ValueError("retrieved_at cannot follow system_recorded_at")
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError("source_event_at cannot follow observed_at")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("lineage_parent_ids must be unique")
        return self


class OperationalEnvelopeV1(BoundaryModel, Generic[PayloadT]):
    schema_name: WireSchemaName
    schema_version: Literal["1.0"]
    message_id: Identifier
    operational_event_id: Identifier
    operation_kind: Identifier
    scope_ref: Identifier
    correlation_id: Identifier
    causation_id: Identifier | None
    producer: Identifier
    lineage_parent_ids: tuple[Identifier, ...]
    source_event_at: datetime | None
    source_event_absence_reason: ReasonCode | None
    observed_at: datetime
    retrieved_at: datetime
    system_recorded_at: datetime
    payload: PayloadT

    @classmethod
    def model_parametrized_name(
        cls,
        params: tuple[type[BoundaryModel], ...],
    ) -> str:
        return f"{params[0].__name__.removesuffix('V1')}OperationalEnvelopeV1"

    @model_validator(mode="after")
    def validate_time_and_source_semantics(self) -> Self:
        payload_name = type(self.payload).__name__.removesuffix("V1")
        payload_wire_name = "".join(
            f"_{character.lower()}" if character.isupper() else character
            for character in payload_name
        ).lstrip("_")
        expected_schema_name = (
            f"trail_signal.operational_envelope.{payload_wire_name}.v1"
        )
        if self.schema_name != expected_schema_name:
            raise ValueError(
                f"schema_name must be {expected_schema_name}"
            )
        if (self.source_event_at is None) == (
            self.source_event_absence_reason is None
        ):
            raise ValueError(
                "source_event_at and source_event_absence_reason are mutually exclusive"
            )
        if self.observed_at > self.retrieved_at:
            raise ValueError("observed_at cannot follow retrieved_at")
        if self.retrieved_at > self.system_recorded_at:
            raise ValueError("retrieved_at cannot follow system_recorded_at")
        if self.source_event_at is not None and self.source_event_at > self.observed_at:
            raise ValueError("source_event_at cannot follow observed_at")
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("lineage_parent_ids must be unique")
        return self
