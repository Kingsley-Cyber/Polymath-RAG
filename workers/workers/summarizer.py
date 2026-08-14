"""Deterministic extractive summarizer. No LLM, no model call, no randomness.

Used for document routing cards and parent-chunk summaries. The score is a
pure function of the input text: same text in, same summary out, byte for
byte. Position-weighted log term-frequency centroid scoring with
deterministic tie-breaks (earlier sentence wins).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n+")
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
_STOPWORDS = frozenset(
    "a an the and or but if then else of to in on at by for with from as is are was were be been being "
    "that this these those it its it's they them their there here which who whom whose what when where why how "
    "not no nor so such than too very can could may might must shall should will would do does did done have has had "
    "i you he she we us our your his her him me my".split()
)


@dataclass(frozen=True)
class Sentence:
    index: int
    text: str
    words: tuple[str, ...]
    score: float


def split_sentences(text: str) -> list[str]:
    """Deterministic sentence split. Never splits mid-sentence."""
    parts = [p.strip() for p in _SENTENCE_RE.split(text.strip())]
    return [p for p in parts if p]


def _word_frequencies(sentences: list[list[str]]) -> dict[str, float]:
    df: dict[str, int] = {}
    total = 0
    for words in sentences:
        for word in set(words):
            df[word] = df.get(word, 0) + 1
        total += len(words)
    if not total:
        return {}
    n_docs = max(len(sentences), 1)
    return {
        word: (count / total) * math.log((n_docs + 1) / (1 + df.get(word, 0)) + 1.0)
        for word, count in df.items()
    }


def _content_words(sentence: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(sentence) if w.lower() not in _STOPWORDS]


def score_sentences(sentences: list[list[str]], *, lead_bias: float = 0.6) -> list[float]:
    """Position-biased centroid scoring. Pure function of the sentence list.

    The lead bias decays as 1/(index+1): first sentences are the strongest
    summary signal in technical prose, but a document that keeps returning
    to one concept still ranks that concept up.
    """
    freqs = _word_frequencies(sentences)
    scores: list[float] = []
    for idx, words in enumerate(sentences):
        if not words:
            scores.append(0.0)
            continue
        content = sum(freqs.get(word, 0.0) for word in words) / len(words)
        position = lead_bias / (1.0 + idx)
        scores.append(content + position)
    return scores


def summarize(text: str, *, max_sentences: int = 4, max_chars: int = 900) -> str:
    """Deterministic extractive summary of `text`.

    Selects the highest-scoring sentences in original document order
    (tie-break: earlier sentence), truncating the last selected sentence
    to a word boundary so the summary never exceeds `max_chars` mid-word.
    Empty input returns an empty string.
    """
    raw = split_sentences(text)
    if not raw:
        return ""
    tokenized = [_content_words(s) for s in raw]
    scores = score_sentences(tokenized)
    ranked = sorted(range(len(raw)), key=lambda i: (-scores[i], i))
    selected = sorted(ranked[:max_sentences])

    summary = " ".join(raw[i] for i in selected).strip()
    if len(summary) <= max_chars:
        return summary
    cut = summary[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:-") if cut else summary[:max_chars]


def summarize_children(children: list[str], *, max_sentences: int = 3, max_chars: int = 600) -> str:
    """Parent summary over child chunk texts. Deterministic composition:
    summarize each child, then summarize the concatenation of the child
    summaries (a two-level centroid, stable under chunk reorder)."""
    child_summaries = [summarize(child, max_sentences=1, max_chars=220) for child in children]
    return summarize("\n".join(child_summaries), max_sentences=max_sentences, max_chars=max_chars)
