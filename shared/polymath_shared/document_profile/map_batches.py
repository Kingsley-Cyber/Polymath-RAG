"""Token packer / capacity model for parent mapping.

Plan of record: docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md §12-§14, §21-§22,
§36.3, slice S3.

Deterministic policy (shared/): no I/O, no model. Given the S1 skeletons and a
measured density model, it computes how many parents safely fit one Compound-Mini
request and cuts a document's parents into deterministic batch manifests.

Owner objective (§13): extract everything under ONE call whenever physically
possible; batch only the overflow, and never re-run a successfully mapped parent.

The measured Compound-Mini baseline (§12.2) seeds the density model — but it is an
EMA to be updated from real receipts, never a permanent constant (§43.2: use the
BILLED output density for capacity, not the visible ~29 tokens/parent).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Sequence

from polymath_shared.document_profile.parent_skeleton import ParentSkeleton, SkeletonManifest

# --- planning constants (canaryable — see §13.1/§14.4; not hard-coded forever) --
#: Nominal billed-completion envelope for one mapping request (§13.1).
COMPLETION_ENVELOPE_TOKENS = 6500
#: Initial mapping-only production target; 40 is proven, ~74 is the theoretical
#: edge we do NOT pack to (§13.1).
MAPPING_ONLY_TARGET = 60
MAPPING_ONLY_PROVEN = 40
#: RELIABILITY cap on aliases-per-batch, INDEPENDENT of the token envelope. Measured
#: 2026-09-08 (BACKFILL-SPREAD-V1 follow-up): `groq/compound-mini` returns a COMPLETE
#: structured map only for SMALL batches — 10-15 aliases map 100% (10/10, 15/15 across
#: attempts), 20 mostly (occasional 18/20), and >=25 flakily return EMPTY/partial even
#: though the prompt is tiny (~16 KB at 60 aliases). So the token target (60) is NOT the
#: true ceiling — the model's structured-output reliability is. Large reference docs were
#: mapping ~0 (e.g. Ken Dancyger 2/430) PURELY because they packed 60-alias batches; at 15
#: they map reliably. The effective batch size is the smaller of the token target and this.
#: Canaryable: raise it if compound-mini's big-batch reliability improves.
MAP_RELIABILITY_CAP = 15
#: Reserve so a slightly-over-density response still finishes with `stop`.
SAFETY_RESERVE_TOKENS = 512
#: Per-request total-token cap under which 4 RPM/key is token-feasible (§14.4).
PER_REQUEST_TOKEN_CAP = 15000
TPM_CEILING = 70000
TARGET_RPM = 4
#: ~4 characters per token (matches document_profile.context.est_tokens).
_CHARS_PER_TOKEN = 4


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DensityModel:
    """Per-parent token density. Seeded from the measured 40-parent Compound-Mini
    stress test (§12.2); refined by ``update`` from real request receipts."""

    input_tokens_per_parent: float = 135.7
    billed_tokens_per_parent: float = 87.0
    visible_tokens_per_parent: float = 29.0

    def update(
        self,
        *,
        input_tokens: float,
        billed_tokens: float,
        visible_tokens: float,
        parents: int,
        alpha: float = 0.3,
    ) -> "DensityModel":
        """EMA update from one measured request (its totals over ``parents``)."""
        if parents <= 0:
            return self
        blend = lambda old, new: (1 - alpha) * old + alpha * (new / parents)
        return DensityModel(
            input_tokens_per_parent=blend(self.input_tokens_per_parent, input_tokens),
            billed_tokens_per_parent=blend(self.billed_tokens_per_parent, billed_tokens),
            visible_tokens_per_parent=blend(self.visible_tokens_per_parent, visible_tokens),
        )


DEFAULT_DENSITY = DensityModel()


def skeleton_prompt_tokens(skeleton: ParentSkeleton) -> int:
    """Deterministic estimate of the tokens one skeleton contributes to the prompt
    (what the LLM actually sees: alias, heading, lead + salient excerpt, key terms,
    identifiers). lead_excerpt is empty for structured parents, so it adds nothing
    there and ~30-50 words on a headingless (transcript) parent."""
    parts = [
        skeleton.alias,
        " ".join(skeleton.heading_path),
        skeleton.lead_excerpt,
        skeleton.salient_excerpt,
        " ".join(skeleton.key_terms),
        " ".join(skeleton.identifiers),
    ]
    chars = sum(len(p) for p in parts) + len(parts)  # + separators
    return max(1, math.ceil(chars / _CHARS_PER_TOKEN))


def estimate_input_tokens(skeletons: Sequence[ParentSkeleton]) -> int:
    return sum(skeleton_prompt_tokens(s) for s in skeletons)


def mapping_only_capacity(
    density: DensityModel = DEFAULT_DENSITY,
    *,
    envelope: int = COMPLETION_ENVELOPE_TOKENS,
    target: int = MAPPING_ONLY_TARGET,
    safety: int = SAFETY_RESERVE_TOKENS,
    reliability_cap: int = MAP_RELIABILITY_CAP,
) -> int:
    """Parents per mapping-only request: the smaller of the production target, what the
    billed-completion envelope supports, and the model's structured-output RELIABILITY cap
    (`MAP_RELIABILITY_CAP`). Never the theoretical edge. The reliability cap dominates the
    token target here — compound-mini flakily returns empty above ~20 aliases regardless of
    the (small) prompt size, so packing to the token envelope silently lost large-doc maps."""
    theoretical = int((envelope - safety) // max(1.0, density.billed_tokens_per_parent))
    return max(1, min(target, theoretical, reliability_cap))


def combined_capacity(
    density: DensityModel,
    *,
    global_profile_billed_tokens: int,
    envelope: int = COMPLETION_ENVELOPE_TOKENS,
    safety: int = SAFETY_RESERVE_TOKENS,
) -> int:
    """Parents that fit ALONGSIDE the global profile in one combined call (§13.2).
    Requires the global profile's MEASURED billed output — 0 if it does not fit."""
    room = envelope - global_profile_billed_tokens - safety
    if room <= 0:
        return 0
    return max(0, int(room // max(1.0, density.billed_tokens_per_parent)))


def request_total_tokens(
    density: DensityModel, parents: int, *, global_profile_billed_tokens: int = 0
) -> float:
    """Estimated total provider tokens for a request of ``parents`` maps."""
    return parents * (density.input_tokens_per_parent + density.billed_tokens_per_parent) + global_profile_billed_tokens


def token_feasible_rpm(
    total_tokens_per_request: float,
    *,
    target_rpm: int = TARGET_RPM,
    tpm_ceiling: int = TPM_CEILING,
    per_request_cap: int = PER_REQUEST_TOKEN_CAP,
) -> int:
    """§14.4 token guard: the target RPM is a CEILING allowed ONLY when the
    per-request token estimate stays within the safe per-request cap (4 x 15,000 =
    60,000 TPM, ~10K under the 70K ceiling). Above the cap the target itself is no
    longer feasible, so the ceiling drops by one BEFORE the TPM bound is applied —
    otherwise 15,001-17,500-token requests (where `tpm_ceiling // total` still
    floors to 4) would silently keep 4 RPM."""
    if total_tokens_per_request <= 0:
        return target_rpm
    tpm_bound = int(tpm_ceiling // total_tokens_per_request)
    ceiling = target_rpm if total_tokens_per_request <= per_request_cap else target_rpm - 1
    return max(1, min(ceiling, tpm_bound))


@dataclass(frozen=True)
class MapBatch:
    ordinal: int
    aliases: tuple[str, ...]
    est_input_tokens: int
    est_billed_tokens: int
    est_total_tokens: int
    is_combined: bool
    batch_hash: str

    @property
    def parent_count(self) -> int:
        return len(self.aliases)


@dataclass(frozen=True)
class BatchPlan:
    contract: str
    density: DensityModel
    batches: tuple[MapBatch, ...]
    mapping_only_capacity: int
    combined_capacity: int
    plan_hash: str

    @property
    def total_parents(self) -> int:
        return sum(b.parent_count for b in self.batches)


BATCH_PLANNER_VERSION = "map-batches-v2"  # v2: MAP_RELIABILITY_CAP (compound-mini big-batch reliability)


def _batch(ordinal, by_alias, aliases, density, *, contract, manifest_hash, is_combined) -> MapBatch:
    skels = [by_alias[a] for a in aliases]
    est_input = estimate_input_tokens(skels)
    est_billed = int(round(len(aliases) * density.billed_tokens_per_parent))
    # Source identity: the planner contract + the document's manifest hash + each
    # alias bound to its skeleton hash + the combined flag. Two different documents
    # that both alias P0001..P0060 differ in manifest_hash and every skeleton_hash,
    # so their durable batch identities can never collide.
    batch_hash = _sha256(
        "\x1f".join(
            [contract, manifest_hash, str(is_combined)]
            + [f"{s.alias}\x1e{s.skeleton_hash}" for s in skels]
        )
    )
    return MapBatch(
        ordinal=ordinal,
        aliases=tuple(aliases),
        est_input_tokens=est_input,
        est_billed_tokens=est_billed,
        est_total_tokens=est_input + est_billed,
        is_combined=is_combined,
        batch_hash=batch_hash,
    )


def plan_batches(
    manifest: SkeletonManifest,
    density: DensityModel = DEFAULT_DENSITY,
    *,
    combined_global_profile_billed_tokens: int | None = None,
    contract: str = BATCH_PLANNER_VERSION,
) -> BatchPlan:
    """Cut a document's eligible parents into deterministic mapping batches.

    If ``combined_global_profile_billed_tokens`` is given, the FIRST batch is a
    combined global-profile + MAP batch sized by ``combined_capacity`` (the
    one-call-first fast path, §13.3); the remainder are mapping-only batches of
    ``mapping_only_capacity``. Same (manifest, density) => identical boundaries.
    """
    aliases = [s.alias for s in manifest.skeletons]  # ordinal order from S1
    by_alias = {s.alias: s for s in manifest.skeletons}
    cap = mapping_only_capacity(density)
    comb_cap = (
        combined_capacity(density, global_profile_billed_tokens=combined_global_profile_billed_tokens)
        if combined_global_profile_billed_tokens is not None
        else 0
    )
    batches: list[MapBatch] = []
    idx = 0
    ordinal = 0
    mh = manifest.manifest_hash
    if combined_global_profile_billed_tokens is not None and comb_cap > 0 and aliases:
        first = aliases[:comb_cap]
        batches.append(_batch(ordinal, by_alias, first, density, contract=contract, manifest_hash=mh, is_combined=True))
        idx = len(first)
        ordinal += 1
    while idx < len(aliases):
        chunk = aliases[idx : idx + cap]
        batches.append(_batch(ordinal, by_alias, chunk, density, contract=contract, manifest_hash=mh, is_combined=False))
        idx += len(chunk)
        ordinal += 1
    # Bind source identity into the plan hash too, so even an empty (noise-only)
    # document's plan cannot collide with another's.
    plan_hash = _sha256("\x1d".join([contract, mh] + [b.batch_hash for b in batches]))
    return BatchPlan(
        contract=contract,
        density=density,
        batches=tuple(batches),
        mapping_only_capacity=cap,
        combined_capacity=comb_cap,
        plan_hash=plan_hash,
    )
