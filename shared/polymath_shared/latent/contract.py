"""parent-enrichment-v1 — the model output contract (plan §1.1 as
reconciled by §1.7: integer child refs on the wire; the worker owns the
mapping back to real chunk ids; the model NEVER produces ids,
provenance, hashes, or storage identity)."""
from __future__ import annotations

from dataclasses import dataclass, field

COMPILER_CONTRACT = "parent-enrichment-v1"
LATENT_KINDS = ("latent_abstraction", "latent_transfer")

LATENT_KIND_ABSTRACTION = "latent_abstraction"
LATENT_KIND_TRANSFER = "latent_transfer"


@dataclass(frozen=True)
class EnrichmentBounds:
    """Hard application-side caps (§1.1). Over-cap LISTS are trimmed in
    order (budget, not rejection — same pattern as the extraction
    gate's budget enforcement); over-cap STRINGS are clipped."""
    summary_chars: int = 1000
    gist_chars: int = 320
    abstraction_chars: int = 400
    mechanism_chars: int = 240
    affordance_chars: int = 200
    question_chars: int = 160
    max_mechanisms: int = 2
    max_affordances: int = 2
    max_questions: int = 3
    max_tokens: int = 700              # 700 qualification / 900 production
    # §1.7 subset-hard / coverage-floor: unknown or duplicate refs hard-
    # reject; MISSING gists are a counted shortfall until this floor.
    gist_coverage_floor: float = 0.8


QUALIFICATION_BOUNDS = EnrichmentBounds()
PRODUCTION_BOUNDS = EnrichmentBounds(max_tokens=900)


@dataclass
class ChildGist:
    ref: int                            # integer wire ref (0..N-1)
    gist: str


@dataclass
class EnrichmentOutput:
    """Validated, trimmed model output. Semantic strings only."""
    summary: str
    children: list[ChildGist]
    abstraction: str
    mechanisms: list[str] = field(default_factory=list)
    affordances: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


@dataclass
class EnrichmentGateResult:
    ok: bool
    error_class: str | None = None
    detail: str = ""
    gist_coverage: float = 0.0          # covered_refs / sent_refs
    trimmed: dict | None = None         # what the budget cut, by field
    raw_chars: int = 0
