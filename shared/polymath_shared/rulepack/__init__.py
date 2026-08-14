"""The deterministic rule pack: YAML data + the compiled decision DAG.

GLiNER proposes spans; the compiler decides predicates. The rule pack is
data, diffable in git; the compiled form is a pure lookup structure.
"""
from polymath_shared.rulepack.compiler import (
    RulePackError,
    canonical_entity_id,
    compile_relation,
    load_rule_pack,
    normalize_trigger,
)

__all__ = [
    "RulePackError",
    "canonical_entity_id",
    "compile_relation",
    "load_rule_pack",
    "normalize_trigger",
]
