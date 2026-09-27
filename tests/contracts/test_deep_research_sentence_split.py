"""DEEP-RESEARCH DR7: the sentence audit's split is shared with the page. `audit.uncited` indexes `split_sentences`' list, and the
page marks those sentences with its own copy of the rule, so both are pinned to one fixture
(`frontend-v2/src/__tests__/fixtures/deep-sentence-split.json`, read by `deep-sentence-split.test.ts` too)."""
from __future__ import annotations

import json
import pathlib

from polymath_shared.deep_research.evidence import SENTENCE_PATTERN, split_sentences

SHARED = pathlib.Path(__file__).resolve().parents[2] / "frontend-v2" / "src" / "__tests__" / "fixtures" / "deep-sentence-split.json"


def test_the_backend_split_matches_the_shared_fixture():
    data = json.loads(SHARED.read_text(encoding="utf-8"))
    assert SENTENCE_PATTERN == data["pattern"], "the page copies this pattern: change both, then regenerate the fixture"
    assert split_sentences(data["fixture"]) == data["expected"]
