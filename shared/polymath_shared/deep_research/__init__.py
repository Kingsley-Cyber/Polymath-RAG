"""DEEP-RESEARCH-MODE-V1 (docs/wiki/plans/DEEP-RESEARCH-MODE-V1.md): multi-round research reports over the caller's libraries.

`engine` runs the breadth × depth loop over two injected ports (retrieve, complete); `prompts` holds the three prompt builders
and the tolerant line parsers. Pure: the route (DR2) supplies retrieval, the LLM lane, streaming and receipts.
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
    Learning,
    QueryRecord,
    ResearchOutcome,
    RetrievePort,
    Row,
    preset_cost,
    run_research,
    top_learnings,
    validate_report_citations,
)
from .prompts import (
    cited_ids,
    extract_prompt,
    parse_extract,
    parse_plan,
    plan_prompt,
    report_prompt,
)

__all__ = [
    "PRESETS", "QUICK", "STANDARD", "STOP_REASONS", "THOROUGH", "CompletePort", "Config", "Learning", "QueryRecord",
    "ResearchOutcome", "RetrievePort", "Row", "cited_ids", "extract_prompt", "parse_extract", "parse_plan", "plan_prompt",
    "preset_cost", "report_prompt", "run_research", "top_learnings", "validate_report_citations",
]
