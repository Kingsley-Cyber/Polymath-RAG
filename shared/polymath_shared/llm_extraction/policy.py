"""Cloud lane policy — the byte threshold as a THROUGHPUT router.

Owner rule v2 (2026-08-30, supersedes the 2026-08-29 exfiltration
framing): the threshold exists to guarantee LARGE work lands on
high-throughput resources — a document above it must never crawl through
the local lane by accident. Small documents PREFER local, but the cloud
lane spins up to assist whenever it has idle capacity and local has
backlog ("it defeats the purpose if the local worker has a lot of files
to churn through… cloud should spin up to assist until all work or job
is done").

Enforced at BOTH boundaries, fail-closed in the direction that matters:

1. SELECTION — `select_lane` routes from the document's durable byte
   length (documents.byte_length) plus the claiming worker's lane
   affinity: above threshold -> cloud (throughput law, no exceptions);
   at/below -> local, unless a cloud-affinity worker is the one holding
   the work — that worker only holds it because its own lane was dry,
   so the small document rides cloud as an ASSIST.
2. DISPATCH — `require_cloud_eligible` still runs inside the cloud
   client before any network call: a sub-threshold document reaches a
   cloud endpoint ONLY on an explicit assist dispatch. A caller bug
   that routes small work to cloud without declaring assist is still
   refused loudly — the guard now verifies INTENT, not secrecy.

`CLOUD_MIN_BYTES` is a FLOOR for the throughput rule: a configured
threshold may raise it (route more documents local-first) but can never
lower it. Every lane decision is durable in the stage artifact (lane +
reason + endpoint), so which resource extracted a document is always
auditable even though assist makes the lane operational, not
replay-deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

# CLOUD-FIRST-V1 (owner-blessed 2026-09-02): floor 0 — every document
# rides the cloud ring; the 4B local lane measured 76-89% quarantine on
# small books while cloud lanes measured 0-5%. The 2026-08-29 rule
# (300_000) assumed scarce, paid cloud; the fleet is 14 cheap lanes,
# family-interleaved, and small-doc lane choice was worker-affinity luck.
CLOUD_MIN_BYTES = 0

LANES = ("local", "cloud")


class CloudBoundaryViolation(RuntimeError):
    """A cloud dispatch was attempted for a small source WITHOUT the
    explicit assist declaration."""


@dataclass(frozen=True)
class LaneDecision:
    lane: str                 # "local" | "cloud"
    source_bytes: int
    threshold: int            # the EFFECTIVE threshold (owner floor applied)
    reason: str

    @property
    def assist(self) -> bool:
        return self.reason.startswith("assist")


def effective_threshold(threshold: int | None) -> int:
    """The owner rule is a floor: configured thresholds may only raise it."""
    if threshold is None:
        return CLOUD_MIN_BYTES
    value = int(threshold)
    if value < 0:
        raise ValueError(f"negative cloud threshold: {value}")
    return max(value, CLOUD_MIN_BYTES)


def select_lane(source_bytes: int, threshold: int = CLOUD_MIN_BYTES,
                affinity: str | None = None) -> LaneDecision:
    """Selection boundary: durable source size + claiming worker's lane.

    CLOUD-ASSIST-V1: `affinity` is the claiming worker's lane affinity.
    A cloud-affinity worker holding sub-threshold work only holds it
    because the cloud lane's own backlog is dry — the assist decision
    routes that work to cloud so both resources drain the job.
    """
    if source_bytes < 0:
        raise ValueError(f"negative source size: {source_bytes}")
    threshold = effective_threshold(threshold)
    if source_bytes > threshold:
        return LaneDecision(
            lane="cloud", source_bytes=source_bytes, threshold=threshold,
            reason=f"source {source_bytes} B > {threshold} B throughput floor")
    if affinity == "cloud":
        return LaneDecision(
            lane="cloud", source_bytes=source_bytes, threshold=threshold,
            reason=f"assist: cloud lane idle, source {source_bytes} B "
                   f"<= {threshold} B rides the pool")
    return LaneDecision(
        lane="local", source_bytes=source_bytes, threshold=threshold,
        reason=f"source {source_bytes} B <= {threshold} B prefers local")


def require_cloud_eligible(source_bytes: int,
                           threshold: int = CLOUD_MIN_BYTES,
                           *, assist: bool = False) -> LaneDecision:
    """Dispatch boundary: refuse a small-source cloud call unless the
    caller explicitly declares it an assist dispatch.

    Called inside the cloud transport immediately before the network
    call. The guard verifies intent: assist dispatches carry the flag
    end-to-end from the lane decision; anything else routing small work
    to cloud is a caller bug and fails loudly.
    """
    decision = select_lane(source_bytes, threshold,
                           affinity="cloud" if assist else None)
    if decision.lane != "cloud":
        raise CloudBoundaryViolation(
            f"cloud dispatch refused: {decision.reason} and no assist "
            f"declared (POLYMATH_CLOUD_MIN_BYTES={decision.threshold})")
    return decision
