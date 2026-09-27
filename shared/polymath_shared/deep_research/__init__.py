"""DEEP-RESEARCH-MODE-V1 (docs/wiki/plans/DEEP-RESEARCH-MODE-V1.md): multi-round research reports over the caller's libraries.

`engine` runs the breadth × depth loop over two injected ports (retrieve, complete); `prompts` holds the three prompt builders
and the tolerant line parsers; `moves` (DR6, §10) is the controller that gives every planned search a move; `evidence`
(DR7b, §11.4) is the deterministic evidence model and the report's sentence audit. Pure: the route (DR2) supplies retrieval,
the LLM lane, the relevance gate, streaming and receipts.
Loop after dzhng/deep-research, MIT; no text copied.
"""
from .engine import (
    PRESETS,
    QUICK,
    STANDARD,
    STOP_REASONS,
    THOROUGH,
    CompletePort,
    Config,
    GatePort,
    Goal,
    Learning,
    PlanDraft,
    QueryRecord,
    ResearchOutcome,
    RetrievePort,
    Row,
    estimate,
    plan_goals,
    preset_cost,
    run_research,
    top_learnings,
    validate_report_citations,
)
from .evidence import (
    SENTENCE_PATTERN,
    audit_report,
    coverage,
    coverage_complete,
    evidence_model,
    split_sentences,
)
from .moves import MOVES, allocate, is_evaluative, question_intent
from .prompts import (
    cited_ids,
    extract_prompt,
    parse_extract,
    parse_plan,
    plan_prompt,
    report_prompt,
)

__all__ = [
    "MOVES", "PRESETS", "QUICK", "SENTENCE_PATTERN", "STANDARD", "STOP_REASONS", "THOROUGH", "CompletePort", "Config",
    "GatePort", "Goal", "Learning", "PlanDraft", "QueryRecord", "ResearchOutcome", "RetrievePort", "Row", "allocate",
    "audit_report", "cited_ids", "coverage", "coverage_complete", "estimate", "evidence_model", "extract_prompt",
    "is_evaluative", "parse_extract", "parse_plan", "plan_goals", "plan_prompt", "preset_cost", "question_intent",
    "report_prompt", "run_research", "split_sentences", "top_learnings", "validate_report_citations",
]
