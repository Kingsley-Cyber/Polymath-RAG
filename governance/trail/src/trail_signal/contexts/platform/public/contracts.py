from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

from packageurl import PackageURL
from pydantic import AfterValidator, Field, StringConstraints, model_validator

from trail_signal.kernel.contracts import (
    BoundaryModel,
    Identifier,
    NonEmptyText,
    OperationalEnvelopeV1,
    ReasonCode,
    Sha256,
    WorkEnvelopeV1,
)

HexCommit40 = Annotated[
    str,
    StringConstraints(min_length=40, max_length=40, pattern=r"^[0-9a-f]{40}$"),
]
RetrievalLocator = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
EtagText = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
ImfFixdate = Annotated[str, StringConstraints(min_length=29, max_length=29)]
RawByteCount = Annotated[int, Field(strict=True, ge=1, le=402653184)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
FindingDispositionCount = Annotated[int, Field(strict=True, ge=0, le=4096)]
P4RuntimeArtifactByteCount = Annotated[
    int,
    Field(strict=True, ge=1, le=268435456),
]
P4RawSha256 = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{64}$"),
]
PackageUrlText = Annotated[
    str,
    StringConstraints(min_length=5, max_length=2048, pattern=r"^pkg:.+$"),
]
PackageUrlComponentText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=2048),
]
PackageUrlQualifierPair = tuple[PackageUrlComponentText, PackageUrlComponentText]

MINIO_ADVISORY_COMPONENT_ID = (
    "source:minio:minio:7aac2a2c5b7c882e68c1ce017d8256be2feea27f"
)
HAPROXY_ADVISORY_COMPONENT_ID = "source:haproxy:3.2.21:dbe43be37"


def _advisory_package_url_parts(
    value: str,
) -> tuple[
    str,
    str,
    str | None,
    str,
    str | None,
    tuple[PackageUrlQualifierPair, ...],
    str | None,
]:
    if not isinstance(value, str) or not value.startswith("pkg:"):
        raise ValueError("advisory component package URL must be a string beginning with pkg:")
    try:
        parsed = PackageURL.from_string(value)
    except (TypeError, ValueError) as error:
        raise ValueError("advisory component package URL is invalid") from error
    if parsed.to_string() != value:
        raise ValueError("advisory component package URL must be byte-canonical")
    return (
        value,
        parsed.type,
        parsed.namespace,
        parsed.name,
        parsed.version,
        tuple(sorted(parsed.qualifiers.items())),
        parsed.subpath,
    )


class AdvisoryPackageUrlV1(BoundaryModel):
    package_url: PackageUrlText
    type: PackageUrlComponentText
    namespace: PackageUrlComponentText | None
    name: PackageUrlComponentText
    version: PackageUrlComponentText | None
    qualifiers: Annotated[
        tuple[PackageUrlQualifierPair, ...],
        Field(max_length=512),
    ]
    subpath: PackageUrlComponentText | None

    @model_validator(mode="after")
    def validate_parsed_view(self) -> Self:
        expected = _advisory_package_url_parts(self.package_url)
        actual = (
            self.package_url,
            self.type,
            self.namespace,
            self.name,
            self.version,
            self.qualifiers,
            self.subpath,
        )
        if actual != expected:
            raise ValueError(
                "advisory package URL fields must equal the canonical parsed view"
            )
        qualifier_keys = tuple(key for key, _ in self.qualifiers)
        if qualifier_keys != tuple(sorted(set(qualifier_keys))):
            raise ValueError(
                "advisory package URL qualifier keys must be unique and sorted"
            )
        return self


def parse_advisory_package_url(value: str) -> AdvisoryPackageUrlV1:
    (
        package_url,
        package_type,
        namespace,
        name,
        version,
        qualifiers,
        subpath,
    ) = _advisory_package_url_parts(value)
    return AdvisoryPackageUrlV1(
        package_url=package_url,
        type=package_type,
        namespace=namespace,
        name=name,
        version=version,
        qualifiers=qualifiers,
        subpath=subpath,
    )


def _validate_advisory_component_id(value: str) -> str:
    if value in (MINIO_ADVISORY_COMPONENT_ID, HAPROXY_ADVISORY_COMPONENT_ID):
        return value
    parse_advisory_package_url(value)
    return value


AdvisoryComponentId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=2048,
        pattern=(
            r"^(?:source:minio:minio:"
            r"7aac2a2c5b7c882e68c1ce017d8256be2feea27f|"
            r"source:haproxy:3\.2\.21:dbe43be37|pkg:.+)$"
        ),
    ),
    AfterValidator(_validate_advisory_component_id),
]

REQUIRED_ADVISORY_SOURCE_IDS: frozenset[str] = frozenset(
    {
        "github_minio_repository_advisories_v2022_11_28_page_1",
        "haproxy_bugs_3_2_21",
        "alpine_secdb_v3_24_main",
        "alpine_secdb_v3_24_community",
        "red_hat_csaf_vex_ubi9",
        "haproxy_linux_arm64_sbom",
        "mc_ubi9_linux_arm64_sbom",
    }
)
REQUIRED_ADVISORY_SOURCE_IDS_V2: frozenset[str] = frozenset(
    {
        "alpine_secdb_v3_24_community",
        "alpine_secdb_v3_24_main",
        "github_minio_repository_advisories_v2022_11_28_page_1",
        "go_vulnerability_database_v1",
        "haproxy_bugs_3_2_21",
        "haproxy_linux_arm64_sbom",
        "mc_scratch_linux_arm64_supply_chain",
        "minio_scratch_linux_arm64_supply_chain",
    }
)
REQUIRED_ADVISORY_SOURCE_ARTIFACT_IDS_V2: dict[str, tuple[str, ...]] = {
    "alpine_secdb_v3_24_community": ("body",),
    "alpine_secdb_v3_24_main": ("body",),
    "github_minio_repository_advisories_v2022_11_28_page_1": ("body",),
    "go_vulnerability_database_v1": ("vulndb_zip",),
    "haproxy_bugs_3_2_21": ("body",),
    "haproxy_linux_arm64_sbom": ("oci_layout_tar", "syft_json"),
    "mc_scratch_linux_arm64_supply_chain": (
        "go_module_cache_tar",
        "govulncheck_report",
        "oci_layout_tar",
        "source_archive",
        "syft_json",
    ),
    "minio_scratch_linux_arm64_supply_chain": (
        "go_module_cache_tar",
        "govulncheck_report",
        "oci_layout_tar",
        "source_archive",
        "syft_json",
    ),
}
MINIO_SOURCE_COMMIT_V2 = "7aac2a2c5b7c882e68c1ce017d8256be2feea27f"
MC_SOURCE_COMMIT_V2 = "ed0b962588f581ebd84d3e2a21a21f24c2b37fc1"
MAX_FINDING_UNION_SIZE = 4096
MAX_CAPTURE_SPAN_SECONDS = 9000
P4_HOST_BOOTSTRAP_SCHEMA_V1 = "trailsignal.p4_export_host_bootstrap.v1"
P4_MINIO_RUNTIME_IMAGE_REFERENCE_V1 = (
    "trailsignal/minio-runtime:"
    "sha-7aac2a2c5b7c882e68c1ce017d8256be2feea27f"
)
P4_MC_RUNTIME_IMAGE_REFERENCE_V1 = (
    "trailsignal/mc-bootstrap-runtime:"
    "sha-ed0b962588f581ebd84d3e2a21a21f24c2b37fc1"
)


class PrincipalCapability(StrEnum):
    CRAWL_SUBMIT = "crawl.submit"
    OPERATION_GET = "operation.get"
    OPERATION_COMMAND = "operation.command"


class PrincipalCapabilityV2(StrEnum):
    CRAWL_SUBMIT = "crawl.submit"
    OPERATION_GET = "operation.get"
    OPERATION_COMMAND = "operation.command"
    EXTRACT_SUBMIT = "extract.submit"
    RESULT_PAGE = "result.page"


class PrincipalCapabilityV3(StrEnum):
    CRAWL_SUBMIT = "crawl.submit"
    OPERATION_GET = "operation.get"
    OPERATION_COMMAND = "operation.command"
    EXTRACT_SUBMIT = "extract.submit"
    RESULT_PAGE = "result.page"
    SCRAPE_SUBMIT = "scrape.submit"


class PrincipalCapabilityV4(StrEnum):
    CRAWL_SUBMIT = "crawl.submit"
    OPERATION_GET = "operation.get"
    OPERATION_COMMAND = "operation.command"
    EXTRACT_SUBMIT = "extract.submit"
    RESULT_PAGE = "result.page"
    SCRAPE_SUBMIT = "scrape.submit"
    DATASET_QUERY = "dataset.query"
    DATASET_EXPORT = "dataset.export"
    EXPORT_READ = "export.read"


class PrincipalCapabilityV5(StrEnum):
    CRAWL_SUBMIT = "crawl.submit"
    OPERATION_GET = "operation.get"
    OPERATION_COMMAND = "operation.command"
    EXTRACT_SUBMIT = "extract.submit"
    RESULT_PAGE = "result.page"
    SCRAPE_SUBMIT = "scrape.submit"
    DATASET_QUERY = "dataset.query"
    DATASET_EXPORT = "dataset.export"
    EXPORT_READ = "export.read"
    DISCOVER_SUBMIT = "discover.submit"


class PrincipalCapabilityV6(StrEnum):
    CRAWL_SUBMIT = "crawl.submit"
    OPERATION_GET = "operation.get"
    OPERATION_COMMAND = "operation.command"
    EXTRACT_SUBMIT = "extract.submit"
    RESULT_PAGE = "result.page"
    SCRAPE_SUBMIT = "scrape.submit"
    DATASET_QUERY = "dataset.query"
    DATASET_EXPORT = "dataset.export"
    EXPORT_READ = "export.read"
    DISCOVER_SUBMIT = "discover.submit"
    REGISTRY_PROJECT = "registry.project"
    GAPS_COMPILE = "gaps.compile"
    EVIDENCE_ADMIT = "evidence.admit"
    HYPOTHESES_JUDGE = "hypotheses.judge"
    TERRITORY_PROJECT = "territory.project"
    OPPORTUNITY_QUALIFY = "opportunity.qualify"
    OPPORTUNITY_SCORE = "opportunity.score"


class PrincipalContextV1(BoundaryModel):
    principal_id: Identifier
    audit_identity: Identifier
    capabilities: tuple[PrincipalCapability, ...]
    policy_ref: Identifier
    budget_ref: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_principal(self) -> Self:
        if not self.capabilities:
            raise ValueError("principal requires at least one capability")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("principal capabilities must be unique")
        if self.expires_at <= self.authenticated_at:
            raise ValueError("principal expiry must follow authentication")
        return self


class PrincipalContextV2(BoundaryModel):
    principal_id: Identifier
    audit_identity: Identifier
    capabilities: tuple[PrincipalCapabilityV2, ...]
    policy_ref: Identifier
    budget_ref: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_principal(self) -> Self:
        if not self.capabilities:
            raise ValueError("principal requires at least one capability")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("principal capabilities must be unique")
        if self.expires_at <= self.authenticated_at:
            raise ValueError("principal expiry must follow authentication")
        return self


def upcast_principal_context_v1(value: PrincipalContextV1) -> PrincipalContextV2:
    return PrincipalContextV2.model_validate(
        {
            **value.model_dump(),
            "capabilities": tuple(
                PrincipalCapabilityV2(capability.value)
                for capability in value.capabilities
            ),
        }
    )


class PrincipalContextV3(BoundaryModel):
    principal_id: Identifier
    audit_identity: Identifier
    capabilities: tuple[PrincipalCapabilityV3, ...]
    policy_ref: Identifier
    budget_ref: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_principal(self) -> Self:
        if not self.capabilities:
            raise ValueError("principal requires at least one capability")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("principal capabilities must be unique")
        if self.expires_at <= self.authenticated_at:
            raise ValueError("principal expiry must follow authentication")
        return self


def upcast_principal_context_v2(value: PrincipalContextV2) -> PrincipalContextV3:
    return PrincipalContextV3.model_validate(
        {
            **value.model_dump(),
            "capabilities": tuple(
                PrincipalCapabilityV3(capability.value)
                for capability in value.capabilities
            ),
        }
    )


class PrincipalContextV4(BoundaryModel):
    principal_id: Identifier
    audit_identity: Identifier
    capabilities: tuple[PrincipalCapabilityV4, ...]
    policy_ref: Identifier
    budget_ref: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_principal(self) -> Self:
        if not self.capabilities:
            raise ValueError("principal requires at least one capability")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("principal capabilities must be unique")
        if self.expires_at <= self.authenticated_at:
            raise ValueError("principal expiry must follow authentication")
        return self


def upcast_principal_context_v3(value: PrincipalContextV3) -> PrincipalContextV4:
    return PrincipalContextV4.model_validate(
        {
            **value.model_dump(),
            "capabilities": tuple(
                PrincipalCapabilityV4(capability.value)
                for capability in value.capabilities
            ),
        }
    )


class PrincipalContextV5(BoundaryModel):
    principal_id: Identifier
    audit_identity: Identifier
    capabilities: tuple[PrincipalCapabilityV5, ...]
    policy_ref: Identifier
    budget_ref: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_principal(self) -> Self:
        PrincipalContextV4.validate_principal(self)
        return self


def upcast_principal_context_v4(value: PrincipalContextV4) -> PrincipalContextV5:
    return PrincipalContextV5.model_validate(
        {
            **value.model_dump(),
            "capabilities": tuple(
                PrincipalCapabilityV5(capability.value)
                for capability in value.capabilities
            ),
        }
    )


class PrincipalContextV6(BoundaryModel):
    principal_id: Identifier
    audit_identity: Identifier
    capabilities: tuple[PrincipalCapabilityV6, ...]
    policy_ref: Identifier
    budget_ref: Identifier
    credential_binding_hash: Sha256
    authenticated_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_principal(self) -> Self:
        PrincipalContextV4.validate_principal(self)
        return self


def upcast_principal_context_v5(value: PrincipalContextV5) -> PrincipalContextV6:
    return PrincipalContextV6.model_validate(
        {
            **value.model_dump(),
            "capabilities": tuple(
                PrincipalCapabilityV6(capability.value)
                for capability in value.capabilities
            ),
        }
    )


class EngineDistributionKindV1(StrEnum):
    PACKAGE = "PACKAGE"
    IMAGE = "IMAGE"
    BINARY = "BINARY"


class EngineExecutionOutcomeV1(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    SOURCE_GAP = "SOURCE_GAP"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class EngineIdentityV1(BoundaryModel):
    engine_identity_id: Identifier
    engine_name: Identifier
    engine_version: NonEmptyText
    distribution_kind: EngineDistributionKindV1
    distribution_digest: Sha256
    configuration_hash: Sha256
    tool_profile_ref: Identifier


class EngineExecutionReceiptV1(BoundaryModel):
    engine_execution_receipt_id: Identifier
    engine_identity_ref: Identifier
    request_id: Identifier
    operation_id: Identifier
    attempt_id: Identifier
    route_decision_ref: Identifier | None
    policy_ref: Identifier
    causation_id: Identifier
    started_at: datetime
    ended_at: datetime
    latency_ms: NonNegativeInt
    byte_count: NonNegativeInt
    browser_milliseconds: NonNegativeInt
    retry_count: NonNegativeInt
    outcome: EngineExecutionOutcomeV1
    raw_artifact_ref: Identifier | None
    source_gap_ref: Identifier | None
    cost_observation_id: Identifier
    lineage_parent_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.ended_at < self.started_at:
            raise ValueError("engine execution end cannot precede start")
        if self.latency_ms != (
            self.ended_at - self.started_at
        ) // timedelta(milliseconds=1):
            raise ValueError("latency_ms must equal the measured execution interval")
        expected_references = {
            EngineExecutionOutcomeV1.SUCCEEDED: (True, False),
            EngineExecutionOutcomeV1.SOURCE_GAP: (False, True),
            EngineExecutionOutcomeV1.CANCELLED: (False, False),
            EngineExecutionOutcomeV1.FAILED: (False, False),
        }
        if (
            self.raw_artifact_ref is not None,
            self.source_gap_ref is not None,
        ) != expected_references[self.outcome]:
            raise ValueError("engine execution outcome has invalid result references")
        required_lineage = {
            self.engine_identity_ref,
            self.request_id,
            self.operation_id,
            self.attempt_id,
            self.policy_ref,
            self.causation_id,
            self.cost_observation_id,
            *((self.route_decision_ref,) if self.route_decision_ref else ()),
            *((self.raw_artifact_ref,) if self.raw_artifact_ref else ()),
        }
        if not required_lineage.issubset(self.lineage_parent_ids):
            raise ValueError("engine execution receipt lineage is incomplete")
        if (
            self.source_gap_ref is not None
            and self.source_gap_ref in self.lineage_parent_ids
        ):
            raise ValueError(
                "source_gap_ref is correlation metadata, not receipt lineage"
            )
        if len(self.lineage_parent_ids) != len(set(self.lineage_parent_ids)):
            raise ValueError("engine execution receipt lineage must be unique")
        return self


EngineExecutionReceiptWorkEnvelopeV1 = WorkEnvelopeV1[EngineExecutionReceiptV1]


class P4HostBootstrapReceiptV1(BoundaryModel):
    canonical_owner: ClassVar[str] = "platform"
    schema_version: Literal[P4_HOST_BOOTSTRAP_SCHEMA_V1]
    image_id: Sha256
    minio_image_id: Sha256
    mc_image_id: Sha256
    advisory_snapshot_ref: Sha256
    advisory_snapshot_signature_sha256: Sha256
    minio_runtime_artifact_sha256: Sha256
    minio_runtime_artifact_byte_count: P4RuntimeArtifactByteCount
    minio_runtime_manifest_sha256: Sha256
    minio_runtime_config_sha256: Sha256
    minio_runtime_image_reference: Literal[P4_MINIO_RUNTIME_IMAGE_REFERENCE_V1]
    mc_runtime_artifact_sha256: Sha256
    mc_runtime_artifact_byte_count: P4RuntimeArtifactByteCount
    mc_runtime_manifest_sha256: Sha256
    mc_runtime_config_sha256: Sha256
    mc_runtime_image_reference: Literal[P4_MC_RUNTIME_IMAGE_REFERENCE_V1]
    base_index_reference: NonEmptyText
    base_index_digest: Sha256
    base_child_manifest_digest: Sha256
    platform: NonEmptyText
    python_version: NonEmptyText
    duckdb_version: NonEmptyText
    duckdb_wheel_sha256: P4RawSha256
    docker_target_sha256: Sha256
    dockerfile_sha256: Sha256
    encoder_sha256: Sha256
    seccomp_sha256: Sha256
    control_profile_sha256: Sha256
    compose_projection_sha256: Sha256
    docker_version: NonEmptyText
    docker_target_owner_class: Literal["root", "derived_operator"]
    docker_target_device: NonNegativeInt
    docker_target_inode: NonNegativeInt
    docker_designated_requirement: NonEmptyText
    docker_identifier: Identifier
    docker_authority: NonEmptyText
    docker_team_identifier: Identifier
    verified_at: datetime

    @model_validator(mode="after")
    def validate_runtime_bindings(self) -> Self:
        if self.minio_image_id != self.minio_runtime_manifest_sha256:
            raise ValueError(
                "MinIO image ID must equal its signed runtime manifest"
            )
        if self.mc_image_id != self.mc_runtime_manifest_sha256:
            raise ValueError(
                "mc image ID must equal its signed runtime manifest"
            )
        if len({self.image_id, self.minio_image_id, self.mc_image_id}) != 3:
            raise ValueError("bootstrap runtime image identities must be distinct")
        return self


class SecretRefV1(BoundaryModel):
    secret_ref: Identifier
    backend_ref: Identifier
    alias: Identifier
    version_ref: Identifier
    purpose_ref: Identifier
    endpoint_scope_hash: Sha256
    required: bool = True
    absence_reason: ReasonCode | None

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.required and self.absence_reason is not None:
            raise ValueError("required secret reference cannot declare absence")
        if not self.required and self.absence_reason is None:
            raise ValueError("optional absent secret reference requires a reason")
        return self


class MinioAdvisoryFindingV1(BoundaryModel):
    component_id: AdvisoryComponentId
    advisory_id: Identifier


class MinioAdvisoryDispositionKindV1(StrEnum):
    AFFECTED_GUARD_MITIGATED = "AFFECTED_GUARD_MITIGATED"
    NOT_APPLICABLE_PROFILE_GUARD_UNREACHABLE = "NOT_APPLICABLE_PROFILE_GUARD_UNREACHABLE"
    PATCHED_DEFENSE_IN_DEPTH = "PATCHED_DEFENSE_IN_DEPTH"
    UNREVIEWED_BLOCKING = "UNREVIEWED_BLOCKING"


class MinioAdvisoryReadinessOutcomeV1(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class MinioAdvisorySourceArtifactReceiptV1(BoundaryModel):
    artifact_id: Identifier
    retrieval_locator: RetrievalLocator
    request_profile_id: Identifier
    retrieved_at: datetime
    http_status: Literal[200] | None
    etag: EtagText | None
    last_modified: ImfFixdate | None
    raw_byte_count: RawByteCount
    raw_sha256: Sha256


class MinioAdvisorySourceReceiptV1(BoundaryModel):
    source_id: Identifier
    request_profile_id: Identifier
    artifacts: tuple[MinioAdvisorySourceArtifactReceiptV1, ...]
    normalized_record_count: NonNegativeInt
    normalized_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if not self.artifacts:
            raise ValueError("artifacts must be nonempty")
        artifact_ids = tuple(artifact.artifact_id for artifact in self.artifacts)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact receipts must be unique")
        if artifact_ids != tuple(sorted(artifact_ids)):
            raise ValueError("artifact receipts must be sorted by artifact_id")
        if self.request_profile_id != self.source_id:
            raise ValueError("request_profile_id must equal source_id")
        return self


def _validate_finding_tuple(
    label: str,
    findings: tuple[MinioAdvisoryFindingV1, ...],
) -> None:
    keys = tuple((finding.component_id, finding.advisory_id) for finding in findings)
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} findings must be unique")
    if keys != tuple(sorted(keys)):
        raise ValueError(f"{label} findings must be sorted by component_id then advisory_id")


class MinioAdvisorySourceSnapshotV1(BoundaryModel):
    profile_ref: Identifier
    collector_version: Identifier
    collector_code_sha256: Sha256
    collector_config_sha256: Sha256
    ci_repository: Identifier
    ci_commit: HexCommit40
    ci_run_id: Identifier
    capture_started_at: datetime
    capture_completed_at: datetime
    source_receipts: tuple[MinioAdvisorySourceReceiptV1, ...]
    minio_advisories: tuple[MinioAdvisoryFindingV1, ...]
    haproxy_findings: tuple[MinioAdvisoryFindingV1, ...]
    alpine_findings: tuple[MinioAdvisoryFindingV1, ...]
    ubi_findings: tuple[MinioAdvisoryFindingV1, ...]
    minio_inventory_sha256: Sha256
    haproxy_inventory_sha256: Sha256
    alpine_inventory_sha256: Sha256
    ubi_inventory_sha256: Sha256
    haproxy_alpine_sbom_sha256: Sha256
    mc_ubi_sbom_sha256: Sha256
    canonicalization_version: Identifier

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.capture_completed_at < self.capture_started_at:
            raise ValueError("capture_completed_at cannot precede capture_started_at")
        span = self.capture_completed_at - self.capture_started_at
        if span > timedelta(seconds=MAX_CAPTURE_SPAN_SECONDS):
            raise ValueError("capture span exceeds 9000 seconds")
        if len(self.source_receipts) != 7:
            raise ValueError("source_receipts must contain exactly seven receipts")
        source_ids = tuple(receipt.source_id for receipt in self.source_receipts)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source receipts must be unique")
        if source_ids != tuple(sorted(source_ids)):
            raise ValueError("source receipts must be sorted by source_id")
        if set(source_ids) != set(REQUIRED_ADVISORY_SOURCE_IDS):
            raise ValueError("source receipts must contain the required source identity set")
        artifact_count = sum(len(receipt.artifacts) for receipt in self.source_receipts)
        if artifact_count != 11:
            raise ValueError("source receipts must contain exactly eleven artifact receipts")
        for receipt in self.source_receipts:
            for artifact in receipt.artifacts:
                if not (
                    self.capture_started_at
                    <= artifact.retrieved_at
                    <= self.capture_completed_at
                ):
                    raise ValueError(
                        "artifact retrieved_at must lie within the capture interval"
                    )
        for label, findings in (
            ("minio_advisories", self.minio_advisories),
            ("haproxy_findings", self.haproxy_findings),
            ("alpine_findings", self.alpine_findings),
            ("ubi_findings", self.ubi_findings),
        ):
            _validate_finding_tuple(label, findings)
        union_keys = {
            (finding.component_id, finding.advisory_id)
            for collection in (
                self.minio_advisories,
                self.haproxy_findings,
                self.alpine_findings,
                self.ubi_findings,
            )
            for finding in collection
        }
        if len(union_keys) > MAX_FINDING_UNION_SIZE:
            raise ValueError("finding union exceeds 4096 entries")
        return self


class MinioAdvisoryDispositionV1(BoundaryModel):
    component_id: AdvisoryComponentId
    advisory_id: Identifier
    disposition: MinioAdvisoryDispositionKindV1
    control_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_disposition(self) -> Self:
        if len(self.control_ids) != len(set(self.control_ids)):
            raise ValueError("control_ids must be unique")
        if tuple(sorted(self.control_ids)) != self.control_ids:
            raise ValueError("control_ids must be sorted lexicographically")
        return self


class MinioAdvisoryReviewReceiptV1(BoundaryModel):
    operator_principal_id: Identifier
    snapshot_ref: Sha256
    snapshot_sha256: Sha256
    snapshot_signature_sha256: Sha256
    snapshot_signing_key_id: Identifier
    snapshot_signing_key_sha256: Sha256
    source_receipt_hashes: tuple[Sha256, ...]
    minio_inventory_sha256: Sha256
    haproxy_inventory_sha256: Sha256
    alpine_inventory_sha256: Sha256
    ubi_inventory_sha256: Sha256
    haproxy_alpine_sbom_sha256: Sha256
    mc_ubi_sbom_sha256: Sha256
    reviewed_minio_advisory_identifiers: tuple[Identifier, ...]
    minio_control_set_sha256: Sha256
    finding_dispositions: tuple[MinioAdvisoryDispositionV1, ...]
    finding_disposition_count: FindingDispositionCount
    finding_dispositions_byte_count: NonNegativeInt
    finding_dispositions_sha256: Sha256
    minio_source_commit: HexCommit40
    minio_source_archive_sha256: Sha256
    mc_multi_platform_index: Sha256
    mc_linux_arm64_manifest: Sha256
    haproxy_multi_platform_index: Sha256
    haproxy_linux_arm64_manifest: Sha256
    haproxy_source_archive_sha256: Sha256
    haproxy_config_sha256: Sha256
    reviewer_command_version: Identifier
    reviewer_code_sha256: Sha256
    reviewer_config_sha256: Sha256
    freshness_anchor_at: datetime
    generated_at: datetime
    expires_at: datetime
    readiness_outcome: MinioAdvisoryReadinessOutcomeV1

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.snapshot_ref != self.snapshot_sha256:
            raise ValueError("snapshot_ref must equal snapshot_sha256")
        if len(self.source_receipt_hashes) != 7:
            raise ValueError("source_receipt_hashes must contain exactly seven hashes")
        if len(self.reviewed_minio_advisory_identifiers) != 27:
            raise ValueError(
                "reviewed_minio_advisory_identifiers must contain exactly 27 identifiers"
            )
        reviewed_ids = self.reviewed_minio_advisory_identifiers
        if len(reviewed_ids) != len(set(reviewed_ids)):
            raise ValueError("reviewed_minio_advisory_identifiers must be unique")
        if reviewed_ids != tuple(sorted(reviewed_ids)):
            raise ValueError(
                "reviewed_minio_advisory_identifiers must be lexicographically sorted"
            )
        if self.finding_disposition_count != len(self.finding_dispositions):
            raise ValueError(
                "finding_disposition_count must equal finding_dispositions length"
            )
        disposition_keys = tuple(
            (item.component_id, item.advisory_id) for item in self.finding_dispositions
        )
        if len(disposition_keys) != len(set(disposition_keys)):
            raise ValueError("finding_dispositions must be unique")
        if disposition_keys != tuple(sorted(disposition_keys)):
            raise ValueError(
                "finding_dispositions must be sorted by component_id then advisory_id"
            )
        if self.expires_at != self.freshness_anchor_at + timedelta(seconds=604800):
            raise ValueError("expires_at must equal freshness_anchor_at plus 604800 seconds")
        if self.generated_at >= self.expires_at:
            raise ValueError("generated_at must precede expires_at")
        return self


class VerifiedAdvisorySnapshotBundleV1(BoundaryModel):
    snapshot_ref: Sha256
    snapshot: MinioAdvisorySourceSnapshotV1
    snapshot_sha256: Sha256
    snapshot_signature_sha256: Sha256
    snapshot_signing_key_id: Identifier
    snapshot_signing_key_sha256: Sha256
    verified_source_body_sha256s: tuple[Sha256, ...]

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        if self.snapshot_ref != self.snapshot_sha256:
            raise ValueError("snapshot_ref must equal snapshot_sha256")
        if len(self.verified_source_body_sha256s) != 11:
            raise ValueError("verified_source_body_sha256s must contain exactly eleven digests")
        return self


class MinioAdvisorySourceSnapshotV2(BoundaryModel):
    profile_ref: Identifier
    collector_version: Identifier
    collector_code_sha256: Sha256
    collector_config_sha256: Sha256
    ci_repository: Identifier
    ci_commit: HexCommit40
    ci_run_id: Identifier
    capture_started_at: datetime
    capture_completed_at: datetime
    source_receipts: tuple[MinioAdvisorySourceReceiptV1, ...]
    minio_advisories: tuple[MinioAdvisoryFindingV1, ...]
    haproxy_findings: tuple[MinioAdvisoryFindingV1, ...]
    alpine_findings: tuple[MinioAdvisoryFindingV1, ...]
    minio_go_blocking_findings: tuple[MinioAdvisoryFindingV1, ...]
    minio_go_informational_findings: tuple[MinioAdvisoryFindingV1, ...]
    mc_go_blocking_findings: tuple[MinioAdvisoryFindingV1, ...]
    mc_go_informational_findings: tuple[MinioAdvisoryFindingV1, ...]
    minio_inventory_sha256: Sha256
    haproxy_inventory_sha256: Sha256
    alpine_inventory_sha256: Sha256
    haproxy_alpine_sbom_sha256: Sha256
    minio_go_inventory_sha256: Sha256
    mc_go_inventory_sha256: Sha256
    go_vulnerability_database_sha256: Sha256
    go_vulnerability_database_modified_at: datetime
    minio_source_commit: HexCommit40
    mc_source_commit: HexCommit40
    minio_runtime_manifest_sha256: Sha256
    minio_runtime_main_binary_sha256: Sha256
    minio_runtime_helper_binary_sha256: Sha256
    mc_runtime_manifest_sha256: Sha256
    mc_runtime_main_binary_sha256: Sha256
    mc_runtime_helper_binary_sha256: Sha256
    canonicalization_version: Identifier

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.capture_completed_at < self.capture_started_at:
            raise ValueError("capture_completed_at cannot precede capture_started_at")
        span = self.capture_completed_at - self.capture_started_at
        if span > timedelta(seconds=MAX_CAPTURE_SPAN_SECONDS):
            raise ValueError("capture span exceeds 9000 seconds")
        if (
            self.go_vulnerability_database_modified_at.tzinfo is None
            or self.go_vulnerability_database_modified_at.utcoffset()
            != timedelta(0)
        ):
            raise ValueError(
                "go_vulnerability_database_modified_at must be timezone-aware UTC"
            )
        if self.go_vulnerability_database_modified_at > self.capture_completed_at:
            raise ValueError(
                "go_vulnerability_database_modified_at cannot follow capture completion"
            )
        if self.minio_source_commit != MINIO_SOURCE_COMMIT_V2:
            raise ValueError("minio_source_commit must equal the governed source commit")
        if self.mc_source_commit != MC_SOURCE_COMMIT_V2:
            raise ValueError("mc_source_commit must equal the governed source commit")
        if len(self.source_receipts) != 8:
            raise ValueError("source_receipts must contain exactly eight receipts")
        source_ids = tuple(receipt.source_id for receipt in self.source_receipts)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source receipts must be unique")
        if source_ids != tuple(sorted(source_ids)):
            raise ValueError("source receipts must be sorted by source_id")
        if set(source_ids) != set(REQUIRED_ADVISORY_SOURCE_IDS_V2):
            raise ValueError(
                "source receipts must contain the required V2 source identity set"
            )
        artifact_count = sum(len(receipt.artifacts) for receipt in self.source_receipts)
        if artifact_count != 17:
            raise ValueError(
                "source receipts must contain exactly seventeen artifact receipts"
            )
        for receipt in self.source_receipts:
            artifact_ids = tuple(
                artifact.artifact_id for artifact in receipt.artifacts
            )
            if (
                REQUIRED_ADVISORY_SOURCE_ARTIFACT_IDS_V2.get(receipt.source_id)
                != artifact_ids
            ):
                raise ValueError(
                    "source receipt artifact IDs must equal the required V2 mapping"
                )
            for artifact in receipt.artifacts:
                if not (
                    self.capture_started_at
                    <= artifact.retrieved_at
                    <= self.capture_completed_at
                ):
                    raise ValueError(
                        "artifact retrieved_at must lie within the capture interval"
                    )
        for label, findings in (
            ("minio_advisories", self.minio_advisories),
            ("haproxy_findings", self.haproxy_findings),
            ("alpine_findings", self.alpine_findings),
            ("minio_go_blocking_findings", self.minio_go_blocking_findings),
            (
                "minio_go_informational_findings",
                self.minio_go_informational_findings,
            ),
            ("mc_go_blocking_findings", self.mc_go_blocking_findings),
            ("mc_go_informational_findings", self.mc_go_informational_findings),
        ):
            _validate_finding_tuple(label, findings)
        minio_go_keys = {
            (finding.component_id, finding.advisory_id)
            for finding in self.minio_go_blocking_findings
        }
        if minio_go_keys & {
            (finding.component_id, finding.advisory_id)
            for finding in self.minio_go_informational_findings
        }:
            raise ValueError(
                "MinIO Go findings cannot be both blocking and informational"
            )
        mc_go_keys = {
            (finding.component_id, finding.advisory_id)
            for finding in self.mc_go_blocking_findings
        }
        if mc_go_keys & {
            (finding.component_id, finding.advisory_id)
            for finding in self.mc_go_informational_findings
        }:
            raise ValueError(
                "MinIO Client Go findings cannot be both blocking and informational"
            )
        union_keys = {
            (finding.component_id, finding.advisory_id)
            for collection in (
                self.minio_advisories,
                self.haproxy_findings,
                self.alpine_findings,
                self.minio_go_blocking_findings,
                self.minio_go_informational_findings,
                self.mc_go_blocking_findings,
                self.mc_go_informational_findings,
            )
            for finding in collection
        }
        if len(union_keys) > MAX_FINDING_UNION_SIZE:
            raise ValueError("finding union exceeds 4096 entries")
        receipts = {receipt.source_id: receipt for receipt in self.source_receipts}
        if (
            receipts["minio_scratch_linux_arm64_supply_chain"].normalized_sha256
            != self.minio_go_inventory_sha256
            or receipts[
                "mc_scratch_linux_arm64_supply_chain"
            ].normalized_sha256
            != self.mc_go_inventory_sha256
        ):
            raise ValueError("scratch runtime inventory hash binding mismatch")
        go_database_artifacts = receipts[
            "go_vulnerability_database_v1"
        ].artifacts
        if (
            len(go_database_artifacts) != 1
            or go_database_artifacts[0].artifact_id != "vulndb_zip"
            or go_database_artifacts[0].raw_sha256
            != self.go_vulnerability_database_sha256
        ):
            raise ValueError("Go vulnerability database hash binding mismatch")
        return self


class MinioAdvisoryReviewReceiptV2(BoundaryModel):
    operator_principal_id: Identifier
    snapshot_ref: Sha256
    snapshot_sha256: Sha256
    snapshot_signature_sha256: Sha256
    snapshot_signing_key_id: Identifier
    snapshot_signing_key_sha256: Sha256
    source_receipt_hashes: tuple[Sha256, ...]
    minio_inventory_sha256: Sha256
    haproxy_inventory_sha256: Sha256
    alpine_inventory_sha256: Sha256
    haproxy_alpine_sbom_sha256: Sha256
    minio_go_inventory_sha256: Sha256
    mc_go_inventory_sha256: Sha256
    go_vulnerability_database_sha256: Sha256
    go_vulnerability_database_modified_at: datetime
    minio_source_commit: HexCommit40
    mc_source_commit: HexCommit40
    minio_runtime_manifest_sha256: Sha256
    minio_runtime_main_binary_sha256: Sha256
    minio_runtime_helper_binary_sha256: Sha256
    mc_runtime_manifest_sha256: Sha256
    mc_runtime_main_binary_sha256: Sha256
    mc_runtime_helper_binary_sha256: Sha256
    minio_go_informational_finding_count: FindingDispositionCount
    minio_go_informational_findings_sha256: Sha256
    mc_go_informational_finding_count: FindingDispositionCount
    mc_go_informational_findings_sha256: Sha256
    reviewed_minio_advisory_identifiers: tuple[Identifier, ...]
    minio_control_set_sha256: Sha256
    finding_dispositions: tuple[MinioAdvisoryDispositionV1, ...]
    finding_disposition_count: FindingDispositionCount
    finding_dispositions_byte_count: NonNegativeInt
    finding_dispositions_sha256: Sha256
    minio_source_archive_sha256: Sha256
    haproxy_multi_platform_index: Sha256
    haproxy_linux_arm64_manifest: Sha256
    haproxy_source_archive_sha256: Sha256
    haproxy_config_sha256: Sha256
    reviewer_command_version: Identifier
    reviewer_code_sha256: Sha256
    reviewer_config_sha256: Sha256
    freshness_anchor_at: datetime
    generated_at: datetime
    expires_at: datetime
    readiness_outcome: MinioAdvisoryReadinessOutcomeV1

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.snapshot_ref != self.snapshot_sha256:
            raise ValueError("snapshot_ref must equal snapshot_sha256")
        if len(self.source_receipt_hashes) != 8:
            raise ValueError(
                "source_receipt_hashes must contain exactly eight hashes"
            )
        if self.minio_source_commit != MINIO_SOURCE_COMMIT_V2:
            raise ValueError("minio_source_commit must equal the governed source commit")
        if self.mc_source_commit != MC_SOURCE_COMMIT_V2:
            raise ValueError("mc_source_commit must equal the governed source commit")
        if len(self.reviewed_minio_advisory_identifiers) != 27:
            raise ValueError(
                "reviewed_minio_advisory_identifiers must contain exactly 27 identifiers"
            )
        reviewed_ids = self.reviewed_minio_advisory_identifiers
        if len(reviewed_ids) != len(set(reviewed_ids)):
            raise ValueError("reviewed_minio_advisory_identifiers must be unique")
        if reviewed_ids != tuple(sorted(reviewed_ids)):
            raise ValueError(
                "reviewed_minio_advisory_identifiers must be lexicographically sorted"
            )
        if self.finding_disposition_count != len(self.finding_dispositions):
            raise ValueError(
                "finding_disposition_count must equal finding_dispositions length"
            )
        disposition_keys = tuple(
            (item.component_id, item.advisory_id)
            for item in self.finding_dispositions
        )
        if len(disposition_keys) != len(set(disposition_keys)):
            raise ValueError("finding_dispositions must be unique")
        if disposition_keys != tuple(sorted(disposition_keys)):
            raise ValueError(
                "finding_dispositions must be sorted by component_id then advisory_id"
            )
        if (
            self.go_vulnerability_database_modified_at.tzinfo is None
            or self.go_vulnerability_database_modified_at.utcoffset()
            != timedelta(0)
        ):
            raise ValueError(
                "go_vulnerability_database_modified_at must be timezone-aware UTC"
            )
        if self.expires_at != self.freshness_anchor_at + timedelta(seconds=604800):
            raise ValueError(
                "expires_at must equal freshness_anchor_at plus 604800 seconds"
            )
        if self.generated_at >= self.expires_at:
            raise ValueError("generated_at must precede expires_at")
        return self


class VerifiedAdvisorySnapshotBundleV2(BoundaryModel):
    snapshot_ref: Sha256
    snapshot: MinioAdvisorySourceSnapshotV2
    snapshot_sha256: Sha256
    snapshot_signature_sha256: Sha256
    snapshot_signing_key_id: Identifier
    snapshot_signing_key_sha256: Sha256
    verified_source_body_sha256s: tuple[Sha256, ...]

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        if self.snapshot_ref != self.snapshot_sha256:
            raise ValueError("snapshot_ref must equal snapshot_sha256")
        expected = tuple(
            artifact.raw_sha256
            for receipt in self.snapshot.source_receipts
            for artifact in receipt.artifacts
        )
        if len(expected) != 17:
            raise ValueError(
                "snapshot must bind exactly seventeen source artifact hashes"
            )
        if self.verified_source_body_sha256s != expected:
            raise ValueError(
                "verified_source_body_sha256s must exactly match flattened artifact hashes"
            )
        return self


MinioAdvisorySourceSnapshotOperationalEnvelopeV1 = OperationalEnvelopeV1[
    MinioAdvisorySourceSnapshotV1
]
MinioAdvisoryReviewReceiptOperationalEnvelopeV1 = OperationalEnvelopeV1[
    MinioAdvisoryReviewReceiptV1
]
MinioAdvisorySourceSnapshotV2OperationalEnvelopeV1 = OperationalEnvelopeV1[
    MinioAdvisorySourceSnapshotV2
]
MinioAdvisoryReviewReceiptV2OperationalEnvelopeV1 = OperationalEnvelopeV1[
    MinioAdvisoryReviewReceiptV2
]
