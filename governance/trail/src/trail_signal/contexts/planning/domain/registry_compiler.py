"""Registry snapshot compiler (ADR-063, HR1). Pure and deterministic: the nine curated CSVs, the additive
``data/source_capabilities.csv`` side table, ``config/evidence_gates.json``, ``config/scoring_weights.json``, and
``config/weights.yaml`` compile into one immutable ``TrailRegistrySnapshotV1``. The same inputs always yield the same
content hash; ``compiled_at`` is excluded from the hash. Every record is a prior (``authority_class == "PRIOR"``):
a prior is never an observation, demand, proof, or market reality. Search intents name no engine. Adding a source is a
row in the side table, never code. No network, browser, database, workflow, or model access exists here."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from trail_signal.kernel.contracts import BoundaryModel, Identifier, NonEmptyText

SCHEMA_VERSION = "1.0"
COMPILER_VERSION = "registry-compiler-1.0.0"
CURATED_CSVS = (
    "outdoor_activity_niche_seed", "activity_taxonomy", "friction_library", "product_territories", "search_query_templates",
    "source_registry", "niche_candidates", "seasonal_calendar", "scoring_rubric",
)
EvidenceRole = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,40}$")]
LongText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
CellText = Annotated[str, StringConstraints(max_length=4096)]
NonNegInt = Annotated[int, Field(strict=True, ge=0)]
PosInt = Annotated[int, Field(strict=True, ge=1)]


class ResearchStage(StrEnum):
    FIELD_EVIDENCE = "field_evidence"
    PRODUCT_REALITY = "product_reality"
    SUPPLY = "supply"


class AuthorityClass(StrEnum):
    PRIOR = "PRIOR"
    ADMITTED_OBSERVATION = "ADMITTED_OBSERVATION"
    QUALIFIED_FINDING = "QUALIFIED_FINDING"


# evidence_goal (search_query_templates.csv) -> evidence roles the intent may serve; community is a non-evidence goal.
GOAL_ROLES: dict[str, tuple[str, ...]] = {
    "complaint": ("friction", "behavior"), "workaround": ("workaround",), "context": ("behavior", "friction"),
    "competition": ("competition",), "price": ("price",), "seasonality": ("seasonality",), "falsification": ("contradiction",),
    "community": (), "behavior": ("behavior",),
}
STAGE_OF_GOAL: dict[str, ResearchStage] = {
    "complaint": ResearchStage.FIELD_EVIDENCE, "workaround": ResearchStage.FIELD_EVIDENCE, "context": ResearchStage.FIELD_EVIDENCE,
    "behavior": ResearchStage.FIELD_EVIDENCE, "community": ResearchStage.FIELD_EVIDENCE, "falsification": ResearchStage.FIELD_EVIDENCE,
    "competition": ResearchStage.PRODUCT_REALITY, "price": ResearchStage.PRODUCT_REALITY, "seasonality": ResearchStage.PRODUCT_REALITY,
}


class SnapshotField(BoundaryModel):
    name: Identifier
    value: CellText


class SnapshotPrior(BoundaryModel):
    record_id: Identifier
    prior_role: Identifier
    fields: tuple[SnapshotField, ...]
    authority_class: Literal[AuthorityClass.PRIOR]


class SnapshotSourceRole(BoundaryModel):
    source_id: Identifier
    source_name: NonEmptyText | None
    source_class: Identifier | None
    access_mode: Identifier | None
    official_url: LongText | None
    domains_or_patterns: tuple[NonEmptyText, ...]
    supported_research_stages: tuple[ResearchStage, ...]
    supported_evidence_roles: tuple[EvidenceRole, ...]
    search_intent_support: tuple[Identifier, ...]
    freshness_policy: Identifier | None
    independence_group: NonEmptyText
    product_search_capability: bool
    supplier_search_capability: bool
    limitations: LongText | None
    enabled: bool
    registry_backed: bool


class SnapshotSearchIntent(BoundaryModel):
    intent_id: Identifier
    evidence_goal: Identifier
    intent: NonEmptyText
    template: NonEmptyText
    evidence_roles: tuple[EvidenceRole, ...]
    research_stage: ResearchStage
    enabled: bool


class HardGate(BoundaryModel):
    id: Identifier
    name: Identifier
    minimum: PosInt
    unit: NonEmptyText


class RubricDimension(BoundaryModel):
    dimension: Identifier
    weight: float
    anchors: tuple[CellText, CellText, CellText, CellText, CellText]
    evidence_required: CellText


class ScoringPolicy(BoundaryModel):
    rubric: tuple[RubricDimension, ...]
    rubric_weights_version: Identifier
    rubric_scale: Identifier
    penalties: tuple[SnapshotField, ...]
    bands: tuple[SnapshotField, ...]
    hard_gates: tuple[HardGate, ...]
    promotion_rule: Identifier
    engine_weights_version: Identifier
    engine_axis_weights: tuple[SnapshotField, ...]


class RegistrySnapshotRef(BoundaryModel):
    snapshot_id: Identifier
    content_hash: Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]


class RegistryInputError(ValueError):
    """A registry input file is missing, malformed, or outside the admitted shape."""


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise RegistryInputError(f"missing registry input {path.name}")
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _multi(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(";") if item.strip())


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def _prior(record_id: str, role: str, row: dict[str, str], names: tuple[str, ...]) -> SnapshotPrior:
    return SnapshotPrior(record_id=record_id, prior_role=role, authority_class=AuthorityClass.PRIOR,
                         fields=tuple(SnapshotField(name=name, value=(row.get(name) or "").strip()) for name in names))


def parse_simple_yaml(text: str) -> dict[str, dict[str, str]]:
    """Deterministic parser for the two-level ``config/weights.yaml`` shape (top-level ``key: value`` or ``key:`` with
    two-space-indented ``sub: value`` scalars, comments, blank lines). Anything else is refused."""
    out: dict[str, dict[str, str]] = {}
    section: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  "):
            key, sep, value = line.strip().partition(":")
            if section is None or not sep or not key or not value.strip():
                raise RegistryInputError(f"weights.yaml line {number}: unsupported nested value")
            out[section][key.strip()] = value.strip().strip('"')
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip() or key.startswith(" "):
            raise RegistryInputError(f"weights.yaml line {number}: unsupported line")
        if value.strip():
            out.setdefault("_scalars", {})[key.strip()] = value.strip().strip('"')
            section = None
        else:
            section = key.strip()
            out[section] = {}
    return out


def canonical_json(payload: object) -> str:
    """Canonical JSON text (sorted keys, no whitespace); hashing encodes it as UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compile_registry_snapshot(data_dir: Path, config_dir: Path, capabilities_csv: Path, *, compiled_at: datetime):
    """Compile the registry inputs into a ``TrailRegistrySnapshotV1`` (imported lazily: the public contract composes
    these domain value models). ``compiled_at`` must be timezone-aware UTC and is excluded from the content hash."""
    from trail_signal.contexts.planning.public.contracts import TrailRegistrySnapshotV1

    tables = {name: _rows(data_dir / f"{name}.csv") for name in CURATED_CSVS}
    capabilities = {row["source_id"]: row for row in _rows(capabilities_csv)}
    registry = {row["source_id"]: row for row in tables["source_registry"]}
    sources: list[SnapshotSourceRole] = []
    for source_id in sorted(set(capabilities) | set(registry)):
        base, cap = registry.get(source_id, {}), capabilities.get(source_id)
        if cap is None:  # registry-only source: known but not routable for directives
            sources.append(SnapshotSourceRole(
                source_id=source_id, source_name=base.get("source_name") or None, source_class=None, access_mode=base.get("access_mode") or None,
                official_url=base.get("official_url") or None, domains_or_patterns=(), supported_research_stages=(), supported_evidence_roles=(),
                search_intent_support=(), freshness_policy=None, independence_group=source_id, product_search_capability=False,
                supplier_search_capability=False, limitations=base.get("limitations") or None, enabled=False, registry_backed=True))
            continue
        sources.append(SnapshotSourceRole(
            source_id=source_id, source_name=cap.get("source_name") or base.get("source_name") or None, source_class=cap["source_class"] or None,
            access_mode=cap.get("access_mode") or base.get("access_mode") or None, official_url=cap.get("official_url") or base.get("official_url") or None,
            domains_or_patterns=_multi(cap.get("domains_or_patterns")), supported_research_stages=tuple(ResearchStage(s) for s in _multi(cap.get("supported_research_stages"))),
            supported_evidence_roles=_multi(cap.get("supported_evidence_roles")), search_intent_support=_multi(cap.get("search_intent_support")),
            freshness_policy=cap.get("freshness_policy") or None, independence_group=cap["independence_group"],
            product_search_capability=_flag(cap.get("product_search_capability")), supplier_search_capability=_flag(cap.get("supplier_search_capability")),
            limitations=cap.get("limitations") or base.get("limitations") or None, enabled=_flag(cap.get("enabled")), registry_backed=source_id in registry))
    intents = tuple(SnapshotSearchIntent(
        intent_id=row["template_id"], evidence_goal=row["evidence_goal"], intent=row["notes"].rstrip(".") or row["template_id"], template=row["template"],
        evidence_roles=GOAL_ROLES.get(row["evidence_goal"], ()), research_stage=STAGE_OF_GOAL.get(row["evidence_goal"], ResearchStage.FIELD_EVIDENCE),
        enabled=_flag(row.get("enabled"))) for row in tables["search_query_templates"])
    gates_doc = json.loads((config_dir / "evidence_gates.json").read_text(encoding="utf-8"))
    weights_doc = json.loads((config_dir / "scoring_weights.json").read_text(encoding="utf-8"))
    engine = parse_simple_yaml((config_dir / "weights.yaml").read_text(encoding="utf-8"))
    policy = ScoringPolicy(
        rubric=tuple(RubricDimension(dimension=row["dimension"], weight=float(row["weight"]), anchors=tuple(row[f"score_{i}"] for i in range(1, 6)),
                                     evidence_required=row.get("evidence_required", "")) for row in tables["scoring_rubric"]),
        rubric_weights_version=str(weights_doc["version"]), rubric_scale=str(weights_doc["scale"]),
        penalties=tuple(SnapshotField(name=k, value=str(v)) for k, v in sorted(weights_doc.get("penalties", {}).items())),
        bands=tuple(SnapshotField(name=k, value=json.dumps(v, separators=(",", ":"))) for k, v in sorted(weights_doc.get("bands", {}).items())),
        hard_gates=tuple(HardGate(id=g["id"], name=g["name"], minimum=int(g["minimum"]), unit=g["unit"]) for g in gates_doc["hard_gates"]),
        promotion_rule=str(gates_doc["promotion_rule"]), engine_weights_version=engine.get("_scalars", {}).get("version", "unversioned"),
        engine_axis_weights=tuple(SnapshotField(name=k, value=v) for k, v in sorted(engine.get("axis_weights", {}).items())))
    body = {
        "schema_version": SCHEMA_VERSION, "compiler_version": COMPILER_VERSION,
        "activity_taxonomy": tuple(_prior(r["domain_id"], "activity_domain", r, ("domain", "display_name", "research_priority")) for r in tables["activity_taxonomy"]),
        "niche_seeds": tuple(_prior(r["seed_id"], "niche_seed", r, ("activity_id", "domain", "activity", "participant", "task", "context", "body_or_hand_state",
                             "friction_family", "friction_hypothesis", "observed_workaround_hypothesis", "product_territory", "seasonal_tags", "shared_predicates", "fact_status"))
                             for r in tables["outdoor_activity_niche_seed"]),
        "friction_primitives": tuple(_prior(r["friction_id"], "friction_primitive", r, ("friction_family", "definition", "observable_metric", "workaround_markers")) for r in tables["friction_library"]),
        "product_territories": tuple(_prior(r["territory_id"], "product_territory", r, ("territory", "definition", "preferred_first_product", "common_risks")) for r in tables["product_territories"]),
        "search_intents": intents, "source_roles": tuple(sources),
        "prior_candidates": tuple(_prior(r["candidate_id"], "prior_candidate", r, ("activity_id", "candidate_title", "product_hypothesis", "primary_friction", "product_territory",
                                  "score_basis", "hard_gates_passed", "research_state")) for r in tables["niche_candidates"]),
        "seasonal_priors": tuple(_prior(r["season_id"], "seasonal_prior", r, ("season_name", "signal_type", "region", "hemisphere", "research_window_start", "research_window_end", "fact_status"))
                                 for r in tables["seasonal_calendar"]),
        "scoring_policy": policy,
    }
    digest = hashlib.sha256(canonical_json({k: _dump(v) for k, v in body.items()}).encode("utf-8")).hexdigest()
    return TrailRegistrySnapshotV1(snapshot_id="trs-" + digest[:16], content_hash="sha256:" + digest, compiled_at=compiled_at, **body)


def _dump(value):
    if isinstance(value, BoundaryModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_dump(item) for item in value]
    return value


def snapshot_ref(snapshot) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(snapshot_id=snapshot.snapshot_id, content_hash=snapshot.content_hash)


def prior_sections(snapshot) -> tuple[tuple[str, tuple[SnapshotPrior, ...]], ...]:
    """The prior-bearing snapshot sections, named, without dynamic attribute access."""
    return (("activity_taxonomy", snapshot.activity_taxonomy), ("niche_seeds", snapshot.niche_seeds), ("friction_primitives", snapshot.friction_primitives),
            ("product_territories", snapshot.product_territories), ("prior_candidates", snapshot.prior_candidates), ("seasonal_priors", snapshot.seasonal_priors))


def prior_record_ids(snapshot) -> frozenset[str]:
    return frozenset(prior.record_id for _, priors in prior_sections(snapshot) for prior in priors)
