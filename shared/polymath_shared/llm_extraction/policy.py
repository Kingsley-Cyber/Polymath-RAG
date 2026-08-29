"""Cloud boundary policy — the 300 KB rule, enforced fail-closed.

Owner rule (2026-08-29): a document of 300,000 bytes or fewer may never
select or call a cloud provider; cloud is PERMITTED (not mandatory) above
the threshold. The rule is enforced at BOTH boundaries:

1. SELECTION — `select_lane` decides local vs cloud from the document's
   durable byte length (documents.byte_length), never from a manifest
   claim.
2. DISPATCH — `require_cloud_eligible` runs again inside the cloud client
   immediately before any network call, so a caller bug cannot exfiltrate
   a small document: the transport refuses to send it.

`CloudBoundaryViolation` is a typed, loud failure — there is no silent
fallback to local for cloud-ineligible documents, because a silent
fallback would hide which lane actually processed the evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

CLOUD_MIN_BYTES = 300_000

LANES = ("local", "cloud")


class CloudBoundaryViolation(RuntimeError):
    """A cloud dispatch was attempted for a cloud-ineligible source."""


@dataclass(frozen=True)
class LaneDecision:
    lane: str                 # "local" | "cloud"
    source_bytes: int
    threshold: int
    reason: str


def select_lane(source_bytes: int, threshold: int = CLOUD_MIN_BYTES) -> LaneDecision:
    """Selection boundary: derive the lane from durable source size."""
    if source_bytes < 0:
        raise ValueError(f"negative source size: {source_bytes}")
    if source_bytes > threshold:
        return LaneDecision(
            lane="cloud", source_bytes=source_bytes, threshold=threshold,
            reason=f"source {source_bytes} B > {threshold} B cloud threshold")
    return LaneDecision(
        lane="local", source_bytes=source_bytes, threshold=threshold,
        reason=f"source {source_bytes} B <= {threshold} B cloud threshold")


def require_cloud_eligible(source_bytes: int,
                           threshold: int = CLOUD_MIN_BYTES) -> LaneDecision:
    """Dispatch boundary: raise unless the source is cloud-eligible.

    Called inside the cloud transport immediately before the network call.
    """
    decision = select_lane(source_bytes, threshold)
    if decision.lane != "cloud":
        raise CloudBoundaryViolation(
            f"cloud dispatch refused: {decision.reason} "
            f"(POLYMATH_CLOUD_MIN_BYTES={threshold})")
    return decision
