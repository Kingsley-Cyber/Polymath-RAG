"""PRODUCTION-REALITY-V1: conditional liveness for promoted lanes.

THE FAILURE CLASS THIS EXISTS FOR
---------------------------------
Repeatedly in this codebase a capability has been present, unit-tested,
configured and documented — and delivered nothing in production, with
nothing detecting it:

  - global_child_rescue configured at 3, delivering 0 of 10 chunks
    (rescue candidates were appended AFTER the truncation point)
  - the vocabulary stage completing while producing 0 families
    (caller dropped the support identity)
  - concept_vocabulary never written at all
  - concept_families.definition never written while ASK matched on it
  - evidence truncated to 900 chars against 1,200-char chunks
  - the documented launch path unable to boot (TCC, exit 126)

Every one had passing component tests. The gap is that a component test
answers "does this function work?", never "did the production path
actually let it act?".

THE MODEL
---------
Liveness is CONDITIONAL, never `count == 0 -> FAIL`. Zero is frequently
correct: a corpus with no procedures should yield no procedures, and a
query naming no entities should traverse no graph. So each lane
declares two predicates over a production trace:

    opportunity(trace) -> did this lane have a real chance to act?
    contributed(trace) -> did it actually act?

and the verdict is:

    no opportunity            -> NO_OPPORTUNITY   (uninformative, fine)
    opportunity + contributed -> LIVE
    opportunity + nothing     -> SUSPECT          (the dead-feature signal)

Only PROMOTED, contracted capabilities are registered. Rejected or
unqualified mechanisms (R1E reach, the vocabulary family layer) must
NOT raise alerts merely by producing zero — they are supposed to.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

CONTRACT = "production-reality-v1"

STATUS_LIVE = "LIVE"
STATUS_SUSPECT = "SUSPECT"
STATUS_NO_OPPORTUNITY = "NO_OPPORTUNITY"
STATUS_DISABLED = "DISABLED"


@dataclass(frozen=True)
class Lane:
    """One promoted capability and how to tell whether it acted."""
    name: str
    #: why a zero here would be a real defect rather than a normal day
    rationale: str
    enabled: Callable[[dict], bool]
    opportunity: Callable[[dict], bool]
    contributed: Callable[[dict], bool]


def _lane_size(trace: dict, key: str) -> int:
    return int((trace.get("lane_sizes") or {}).get(key) or 0)


def _arrivals(trace: dict) -> dict:
    return trace.get("arrival_counts") or {}


#: The promoted retrieval lanes. Each predicate reads ONLY a production
#: trace — the same dict the live routes already emit — so liveness is
#: evaluated on real traffic, not on a mock.
LANES: tuple[Lane, ...] = (
    Lane(
        name="document_summary_routing",
        rationale="the routing layer that decides WHICH document; a "
                  "silent zero means summaries are unprojected or the "
                  "representation_kind filter can never match",
        enabled=lambda t: True,
        opportunity=lambda t: True,
        contributed=lambda t: _lane_size(t, "document_summary") > 0,
    ),
    Lane(
        name="section_summary_routing",
        rationale="decides WHICH neighbourhood inside a document",
        enabled=lambda t: True,
        opportunity=lambda t: True,
        contributed=lambda t: _lane_size(t, "section_summary") > 0,
    ),
    Lane(
        name="global_child",
        rationale="direct child search; protects recall when summaries "
                  "route poorly",
        enabled=lambda t: True,
        opportunity=lambda t: True,
        contributed=lambda t: _lane_size(t, "global_child") > 0,
    ),
    Lane(
        name="global_child_rescue",
        rationale="THE measured dead lane: configured at 3 and "
                  "delivering 0 because rescue candidates were appended "
                  "after the truncation point. Opportunity exists when "
                  "the child lane found candidates the hierarchy did "
                  "not already select.",
        enabled=lambda t: int(t.get("rescue_reserved_slots") or 0) > 0,
        opportunity=lambda t: _lane_size(t, "global_child") > 0
                              and int(t.get("rescue_candidates") or 0) > 0,
        contributed=lambda t: int(t.get("rescue_seated") or 0) > 0,
    ),
    Lane(
        name="lexical",
        rationale="HYBRID's exact-terminology lane; zero on a query "
                  "whose terms appear verbatim in the corpus means the "
                  "lane is detached",
        enabled=lambda t: "child_lexical" in (t.get("lane_sizes") or {}),
        opportunity=lambda t: "child_lexical" in (t.get("lane_sizes") or {}),
        contributed=lambda t: _lane_size(t, "child_lexical") > 0,
    ),
    Lane(
        name="reranker",
        rationale="G3 cross-encoder; it may legitimately keep the "
                  "existing order, so contribution is 'it ran and "
                  "scored', not 'it changed the order'",
        enabled=lambda t: bool(t.get("rerank_enabled", True)),
        opportunity=lambda t: len(t.get("pre_g3_order") or []) > 1,
        contributed=lambda t: bool(t.get("g3_scores")),
    ),
    Lane(
        name="neighbor_expansion",
        rationale="contiguity repair for answers spanning a chunk "
                  "boundary; only active under the depth profile",
        enabled=lambda t: int(t.get("neighbor_expansion") or 0) > 0,
        opportunity=lambda t: int(t.get("neighbor_expansion") or 0) > 0
                              and len(t.get("post_g3_order") or []) > 0,
        contributed=lambda t: int(t.get("neighbors_added") or 0) > 0,
    ),
    Lane(
        name="region_demotion",
        rationale="DOCUMENT-REGION-V1; opportunity exists only when a "
                  "demoted-role candidate was actually in the pool, "
                  "otherwise zero demotions is correct",
        enabled=lambda t: bool(t.get("demote_noisy_regions", False)),
        opportunity=lambda t: int(t.get("noisy_candidates") or 0) > 0,
        contributed=lambda t: int(t.get("noisy_demoted") or 0) > 0,
    ),
    Lane(
        name="graph_hop1",
        rationale="GRAPH traversal; zero is CORRECT with no qualified "
                  "seeds, so opportunity requires seeds to exist",
        enabled=lambda t: t.get("mode") == "GRAPH",
        opportunity=lambda t: len(t.get("graph_seed_surfaces") or []) > 0,
        contributed=lambda t: int(t.get("graph_fact_count") or 0) > 0,
    ),
)

LANES_BY_NAME = {lane.name: lane for lane in LANES}


def evaluate_lane(lane: Lane, trace: dict) -> dict:
    """Status for one lane against one production trace."""
    if not lane.enabled(trace):
        status = STATUS_DISABLED
    elif not lane.opportunity(trace):
        status = STATUS_NO_OPPORTUNITY
    elif lane.contributed(trace):
        status = STATUS_LIVE
    else:
        status = STATUS_SUSPECT
    return {"lane": lane.name, "status": status, "rationale": lane.rationale}


def evaluate(trace: dict) -> dict:
    """Evaluate every promoted lane against one trace.

    SUSPECT is the signal that matters: the lane was enabled, it had a
    genuine opportunity, and it produced nothing.
    """
    results = [evaluate_lane(lane, trace) for lane in LANES]
    return {
        "contract": CONTRACT,
        "lanes": results,
        "suspect": [r["lane"] for r in results if r["status"] == STATUS_SUSPECT],
        "live": [r["lane"] for r in results if r["status"] == STATUS_LIVE],
    }


# ==================================================== SEMANTIC LANES
# Retrieval lanes are evaluated per-query from a trace. Ingestion lanes
# are evaluated from DURABLE state, because their opportunities occur
# once at ingest and must remain answerable long afterwards.

STATUS_CAPPED = "LIVE_BUT_CAPPED"
STATUS_UNOBSERVABLE = "UNOBSERVABLE"


def semantic_lane_status(*, opportunities: int | None, accepted: int,
                         capped_documents: int = 0,
                         documents: int = 0) -> str:
    """Status for an ingestion lane from durable counters.

    The distinction that matters, and the one an artifact count alone
    cannot make:

      opportunities is None -> UNOBSERVABLE (no instrumentation; NOT zero)
      opportunities == 0    -> NO_OPPORTUNITY (correct silence)
      accepted == 0         -> SUSPECT (evidence existed, nothing came out)
      cap binding on most   -> LIVE_BUT_CAPPED (working, but truncating
                               real recall by construction, which is a
                               DESIGN limit and not a defect to alert on
                               every night)
      otherwise             -> LIVE
    """
    if opportunities is None:
        return STATUS_UNOBSERVABLE
    if opportunities <= 0:
        return STATUS_NO_OPPORTUNITY
    if accepted <= 0:
        return STATUS_SUSPECT
    if documents and capped_documents >= documents:
        return STATUS_CAPPED
    return STATUS_LIVE
