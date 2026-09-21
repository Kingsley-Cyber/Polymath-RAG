"""Scoring engine (ADR-063, HR2; LAW 1). The retained doc-08 deterministic engine (coverage gate, tier discount, hostile-dependence
cap, confidence shrink toward neutral, weighted geometric mean, interaction bonuses, rounding, opportunity.v1 payload, content hash)
ported into the v2 scoring context and proven byte-identical on its golden fixture; plus the composition that turns ADMITTED evidence
into per-axis, per-tier signals (doc-08 section 5 saturation and confidence laws with the versioned constants of config/weights.yaml).
No model, harness, prior, or Polymath field is ever read for a score value."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from trail_signal.kernel.contracts import BoundaryModel, Identifier, NonEmptyText, Sha256

SCORING_VERSION = "score-1.0.0"
NORMALIZE_VERSION = "normalize-1.0.0"
COMPOSITION_VERSION = "evidence-composition-1.0.0"
OPPORTUNITY_SCHEMA_VERSION = "opportunity.v1"
AXES = ("demand", "growth", "pain", "competition", "content")
CONFIDENCE_AXES = AXES
HARD_AXES, SOFT_AXES = ("demand", "pain"), ("growth", "competition", "content")
HOSTILE_CAP = 0.50
AXIS_ROLES = {"demand": ("demand", "behavior"), "growth": ("seasonality",), "pain": ("friction", "workaround"), "competition": ("competition", "price"), "content": ("content",)}
# doc 06 / doc 08 section 9 source tiers by access class, as a rank into the weights file's tier order (best-weighted tier first).
CLASS_TIER_RANK = {"first_party": 0, "community_discussion": 0, "official_statistics": 0, "search_interest": 0, "video_platform": 1, "social_trend": 1, "retailer": 1,
                   "ad_library": 1, "marketplace_listing": 2, "supplier_listing": 2}
Unit = Annotated[float, Field(ge=0.0, le=1.0)]
Axis = Literal["demand", "growth", "pain", "competition", "content"]


class ScoreRefused(ValueError):
    """The deterministic engine refuses to score (a hard gate is unmet or an input is outside the law)."""


class ScoreWeights(BoundaryModel):
    version: Identifier
    axis_weights: dict[str, float]
    interactions: dict[str, float]
    confidence: dict[str, float]
    tier_weight: dict[str, float]
    n_ref: dict[str, int]
    half_life_days: dict[str, int]
    min_cell_confidence: Unit

    def tiers(self) -> tuple[str, ...]:
        """Tier names in the versioned weights file order (best-weighted first); the last one is the hostile tier (doc 08 section 9)."""
        return tuple(sorted(self.tier_weight, key=lambda tier: -self.tier_weight[tier]))


class ScoreSignal(BoundaryModel):
    signal_id: Identifier
    niche_id: Identifier
    signal_type: Axis
    source_tier: Identifier
    normalized_score: Unit
    confidence: Unit


class AxisScore(BoundaryModel):
    axis: Axis
    value: float


class AdIntensity(BoundaryModel):
    normalized_score: Unit
    confidence: Unit | None


class CoverageGap(BoundaryModel):
    signal_type: Identifier
    source_tier: Identifier
    reason: NonEmptyText


class ScoreOutcome(BoundaryModel):
    score: Unit
    subscores: dict[str, float]
    confidence: Unit
    coverage_gaps: tuple[CoverageGap, ...]
    hostile_dependent: bool
    scored_from: tuple[Identifier, ...]


class GateView(BoundaryModel):
    name: Identifier
    minimum: Annotated[int, Field(strict=True, ge=1)]
    observed: Annotated[int, Field(strict=True, ge=0)]
    passed: bool


class QualificationView(BoundaryModel):
    record_id: Identifier
    stage: Literal["market_delta", "supply"]
    state: Literal["PROMOTED", "PROVISIONAL", "REJECTED", "UNPROVEN", "NO_DEFENSIBLE_BRIDGE"]
    gate_results: tuple[GateView, ...]


class SnapshotRef(BoundaryModel):
    snapshot_id: Identifier
    content_hash: Sha256


class EvidenceSignalInput(BoundaryModel):
    """The admitted-evidence view scoring reads: ids, roles, groups, polarity, and anchors only (never a confidence or score)."""
    admitted_evidence_id: Identifier
    evidence_role: Identifier
    source_class: Identifier
    independence_group: NonEmptyText
    polarity: Literal["supporting", "contradicting"]
    hypothesis_ids: tuple[Identifier, ...]
    anchored_at: datetime


def load_score_weights(config_dir: Path) -> ScoreWeights:
    """Strict two-level parser for config/weights.yaml (the domain may import only pydantic and typing_extensions)."""
    sections: dict[str, dict[str, str]] = {}; scalars: dict[str, str] = {}; current: str | None = None
    for raw in (config_dir / "weights.yaml").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            key, _, value = line.partition(":"); current = None if value.strip() else key.strip()
            if current: sections[current] = {}
            else: scalars[key.strip()] = value.strip().strip('"')
        else:
            key, _, value = line.strip().partition(":"); sections[current or ""][key] = value.strip()
    return ScoreWeights(version=scalars["version"], axis_weights={k: float(v) for k, v in sections["axis_weights"].items()},
                        interactions={k: float(v) for k, v in sections["interactions"].items()}, confidence={k: float(v) for k, v in sections["confidence"].items()},
                        tier_weight={k: float(v) for k, v in sections["tier_weight"].items()}, n_ref={k: int(v) for k, v in sections["n_ref"].items()},
                        half_life_days={k: int(v) for k, v in sections["half_life_days"].items()}, min_cell_confidence=float(scalars["min_cell_confidence"]))


def shrink_toward_neutral(value: float, confidence: float) -> float:
    return 0.5 + (value - 0.5) * max(0.0, min(1.0, confidence))


def _grid(signals: tuple[ScoreSignal, ...]) -> dict[tuple[str, str], float]:
    best: dict[tuple[str, str], float] = {}
    for s in signals:
        best[(s.signal_type, s.source_tier)] = max(best.get((s.signal_type, s.source_tier), 0.0), s.confidence)
    return best


def _best(grid: dict[tuple[str, str], float], axis: str, tiers: tuple[str, ...]) -> float:
    return max((grid.get((axis, tier), 0.0) for tier in tiers), default=0.0)


def _hard_met(grid: dict[tuple[str, str], float], minimum: float, hard_tiers: tuple[str, ...]) -> bool:
    return all(_best(grid, axis, hard_tiers) >= minimum for axis in HARD_AXES)


def _coverage(signals: tuple[ScoreSignal, ...], minimum: float, deadline_reached: bool, tiers: tuple[str, ...]) -> tuple[bool, bool, tuple[CoverageGap, ...]]:
    grid = _grid(signals); hard_tiers = tiers[:-1]; first = tiers[0]
    gaps = [CoverageGap(signal_type=a, source_tier=first, reason=f"hard-required: best {'|'.join(hard_tiers)} confidence {_best(grid, a, hard_tiers):.3f} < {minimum:.2f}")
            for a in HARD_AXES if _best(grid, a, hard_tiers) < minimum]
    soft = [CoverageGap(signal_type=a, source_tier=first, reason=f"soft-required: best any-tier confidence {_best(grid, a, tiers):.3f} < {minimum:.2f}")
            for a in SOFT_AXES if _best(grid, a, tiers) < minimum]
    hard_met = _hard_met(grid, minimum, hard_tiers)
    if hard_met and not gaps and not soft:
        return True, False, ()
    if hard_met and soft:
        return False, True, tuple(soft)
    if not hard_met and deadline_reached:
        return False, False, tuple(gaps + soft)
    return False, False, ()


def _hostile_dependent(signals: tuple[ScoreSignal, ...], minimum: float, tiers: tuple[str, ...]) -> bool:
    if not _hard_met(_grid(signals), minimum, tiers[:-1]):
        return False
    return not _hard_met(_grid(tuple(s for s in signals if s.source_tier != tiers[-1])), minimum, tiers[:-1])


def _wgm(values: dict[str, float], weights: dict[str, float]) -> float:
    total = sum(weights.values())
    if total <= 0 or any(values[k] <= 0 for k in weights):
        raise ScoreRefused("GEOMETRIC_MEAN_DOMAIN: weights must be positive and every input above zero")
    return math.exp(sum(w * math.log(values[k]) for k, w in weights.items()) / total)


def compute_score(signals: tuple[ScoreSignal, ...], weights: ScoreWeights, *, niche_id: str, as_of: datetime, ad_intensity: AdIntensity | None = None,
                  dossier_deadline_at: datetime | None = None) -> ScoreOutcome:
    """Doc 08 sections 6, 7, and 9 exactly as the retained engine computes them."""
    if not signals:
        raise ScoreRefused("NO_SIGNALS: at least one signal is required")
    tiers = weights.tiers()
    if any(s.niche_id != niche_id or s.source_tier not in tiers for s in signals):
        raise ScoreRefused("NICHE_MISMATCH: every signal belongs to the scored niche and a weighted source tier")
    admitted, with_gaps, coverage_gaps = _coverage(signals, weights.min_cell_confidence, dossier_deadline_at is not None and as_of >= dossier_deadline_at, tiers)
    if not admitted and not with_gaps:
        raise ScoreRefused("HARD_GATE_UNMET: coverage gate blocked scoring")
    selected: dict[str, ScoreSignal] = {}
    for s in signals:
        best = selected.get(s.signal_type)
        if best is None or s.confidence > best.confidence or (s.confidence == best.confidence and s.signal_id < best.signal_id):
            selected[s.signal_type] = s
    normalized = {a: (selected[a].normalized_score if a in selected else 0.5) for a in AXES}
    confidences = {a: (selected[a].confidence if a in selected else 0.0) for a in AXES}
    shrunk = {a: shrink_toward_neutral(normalized[a], confidences[a]) for a in AXES}
    shrunk["competition"] = 1.0 - shrunk["competition"]
    ad_value = 0.5 if ad_intensity is None else (ad_intensity.normalized_score if ad_intensity.confidence is None else shrink_toward_neutral(ad_intensity.normalized_score, ad_intensity.confidence))
    base = _wgm(shrunk, {a: weights.axis_weights[a] for a in AXES})
    raw = base * (1.0 + weights.interactions["lambda_gap"] * shrunk["demand"] * shrunk["competition"] + weights.interactions["lambda_pain"] * shrunk["pain"] * (1.0 - ad_value))
    raw = max(0.0, min(1.0, raw))
    product = math.prod(confidences[a] for a in CONFIDENCE_AXES)
    if product <= 0:
        raise ScoreRefused("GEOMETRIC_MEAN_DOMAIN: every required axis needs a positive confidence")
    confidence = product ** (1.0 / len(CONFIDENCE_AXES))
    hostile = _hostile_dependent(signals, weights.min_cell_confidence, tiers)
    confidence = min(confidence, HOSTILE_CAP) if hostile else confidence
    return ScoreOutcome(score=round(raw, 2), subscores={a: round(shrunk[a], 3) for a in AXES}, confidence=round(confidence, 2), coverage_gaps=coverage_gaps,
                        hostile_dependent=hostile, scored_from=tuple(selected[a].signal_id for a in CONFIDENCE_AXES if a in selected))


def opportunity_payload(outcome: ScoreOutcome, *, opportunity_id: str, niche_id: str, candidate: dict, weights: ScoreWeights, config_hash: str, as_of: str,
                        generating_queries: tuple[str, ...], created_at: str) -> dict:
    """The retained engine's opportunity.v1 record (key order and provenance identical to signal_engine.score.build_opportunity_v1)."""
    return {"opportunity_id": opportunity_id, "niche_id": niche_id, "candidate": dict(candidate), "score": outcome.score, "subscores": dict(outcome.subscores),
            "confidence": outcome.confidence, "coverage_gaps": [g.model_dump() for g in outcome.coverage_gaps], "hostile_dependent": outcome.hostile_dependent,
            "scored_from": list(outcome.scored_from), "generating_queries": list(generating_queries),
            "provenance": {"scoring_version": SCORING_VERSION, "weights_version": weights.version, "normalize_version": NORMALIZE_VERSION, "config_hash": config_hash, "created_at": created_at},
            "as_of": as_of, "schema_version": OPPORTUNITY_SCHEMA_VERSION}


def content_hash_for_opportunity(payload: dict) -> str:
    keys = ("niche_id", "candidate", "score", "subscores", "confidence", "scored_from", "provenance")
    return "sha256:" + hashlib.sha256(json.dumps({k: payload[k] for k in keys}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def signal_confidence(*, sample_n: int, axis: str, tier: str, newest: datetime, as_of: datetime, weights: ScoreWeights) -> float:
    """Doc 08 section 5: w_n * sat(log1p(n) / log1p(N_ref)) + w_t * tier_weight + w_r * exp(-age / half_life)."""
    sample = min(1.0, math.log1p(sample_n) / math.log1p(weights.n_ref[axis]))
    age_days = max(0.0, (as_of - newest).total_seconds() / 86400.0)
    value = weights.confidence["w_n"] * sample + weights.confidence["w_t"] * weights.tier_weight[tier] + weights.confidence["w_r"] * math.exp(-age_days / weights.half_life_days[axis])
    return max(0.0, min(1.0, value))


def compose_signals(evidence: tuple[EvidenceSignalInput, ...], weights: ScoreWeights, *, niche_id: str, as_of: datetime) -> tuple[ScoreSignal, ...]:
    """Admitted evidence -> one signal per (axis, tier): value = doc-08 saturation of net independent support against N_ref; confidence = the
    section 5 law. Doc 08 section 6 allows scoring with unfilled SOFT axes at a confidence penalty: an evidence-free soft axis gets a neutral
    fill signal (value 0.5) at half the cell threshold, so it is recorded as a coverage gap and never adds value; hard axes need evidence."""
    signals: list[ScoreSignal] = []
    tiers = weights.tiers()
    for axis in AXES:
        if axis in SOFT_AXES and not any(e.evidence_role in AXIS_ROLES[axis] and e.polarity == "supporting" for e in evidence):
            signals.append(ScoreSignal(signal_id=f"sig-{axis}-none", niche_id=niche_id, signal_type=axis, source_tier=tiers[0], normalized_score=0.5,
                                       confidence=round(weights.min_cell_confidence / 2.0, 6)))
            continue
        for tier in tiers:
            cell = [e for e in evidence if e.evidence_role in AXIS_ROLES[axis] and tiers[min(CLASS_TIER_RANK.get(e.source_class, 2), len(tiers) - 1)] == tier]
            support = {e.independence_group for e in cell if e.polarity == "supporting"}
            against = {e.independence_group for e in cell if e.polarity == "contradicting"}
            if not support:
                continue
            net = max(0, len(support) - len(against))
            value = min(1.0, math.log1p(net) / math.log1p(weights.n_ref[axis])) if net else 0.0
            newest = max(e.anchored_at for e in cell)
            signals.append(ScoreSignal(signal_id=f"sig-{axis}-{tier}", niche_id=niche_id, signal_type=axis, source_tier=tier, normalized_score=round(value, 6),
                                       confidence=round(signal_confidence(sample_n=len(support), axis=axis, tier=tier, newest=newest, as_of=as_of, weights=weights), 6)))
    return tuple(signals)
