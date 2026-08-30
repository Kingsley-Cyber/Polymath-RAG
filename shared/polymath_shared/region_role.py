"""REGION-ROLE-V1 — chunker-independent region classification.

Every chunk row carries a durable `region_role` so extraction, summaries
and routing agree on what is prose and what is structural noise. The
classifier is pure, deterministic and cheap: heading-kind rules from
`chunk_kind` (TOC / index / bibliography / front & back matter) plus
text-shape rules that the heading path cannot see — OCR garbage pages,
index page-lists, legal boilerplate, log/packet dumps, practice-test
question banks.

MEASURED trigger (2026-08-30, corpus cysa-study-v1): Learning SQL pages
1–8 are OCR garbage ("cucxtulaee ence ee oe ee …") and CySA+ pages 750+
are the book index; both were sent to the LLM (empty digests, tokens
burned) and both became routing summaries (the Learning SQL DOCUMENT
card was 1,594 chars of garbage). `chunks.region_role` existed
(migration 0037) but was NULL on every row.

Roles (string constants; `NOISE_ROLES` never enter an LLM neighborhood or
a routing summary; everything else is retrievable evidence):
    body            prose
    question_bank   practice-test question stems + answer options (prose
                    for retrieval; extraction is told to ignore stems)
    output          log / packet / table dumps (digit-dominated)
    code            source listings (heading-classified)
    stub            < MIN_WORDS words
    noise_ocr       OCR failure text (no function words)
    legal           copyright / trademark / permissions boilerplate
    index, toc, bibliography, appendix, front_matter, back_matter, links
                    heading- or shape-classified structural matter
"""
from __future__ import annotations

import re
from collections import Counter

REGION_CONTRACT = "region-role-v1"

ROLE_BODY = "body"
ROLE_QUESTION_BANK = "question_bank"
ROLE_OUTPUT = "output"
ROLE_CODE = "code"
ROLE_STUB = "stub"
ROLE_NOISE_OCR = "noise_ocr"
ROLE_LEGAL = "legal"
ROLE_INDEX = "index"
ROLE_TOC = "toc"
ROLE_BIBLIOGRAPHY = "bibliography"
ROLE_APPENDIX = "appendix"
ROLE_FRONT_MATTER = "front_matter"
ROLE_BACK_MATTER = "back_matter"
ROLE_LINKS = "links"

NOISE_ROLES: frozenset[str] = frozenset({
    ROLE_STUB, ROLE_NOISE_OCR, ROLE_LEGAL, ROLE_INDEX, ROLE_TOC,
    ROLE_BIBLIOGRAPHY, ROLE_APPENDIX, ROLE_FRONT_MATTER, ROLE_BACK_MATTER,
    ROLE_LINKS,
})

#: heading kinds (workers.chunk_kind) that map 1:1 onto a noise role
_HEADING_NOISE_KINDS: frozenset[str] = frozenset({
    ROLE_INDEX, ROLE_TOC, ROLE_BIBLIOGRAPHY, ROLE_APPENDIX,
    ROLE_FRONT_MATTER, ROLE_BACK_MATTER, ROLE_LINKS,
})

MIN_WORDS = 15                 # same floor as LLM_MIN_CHUNK_WORDS

# Thresholds are part of the contract (hashed into the extract contract
# identity through `contract_fingerprint`); change = re-extraction.
THRESHOLDS: dict[str, float] = {
    # MEASURED 2026-08-30 over 1,024 live child chunks: prose carries
    # >= 0.25 common-English tokens (p10 = 0.34); OCR garbage and OCR'd
    # scanner screenshots sit at 0.04-0.14; book index pages 0.05-0.14
    # (caught earlier by the index-line rule).
    "common_share_noise": 0.15,
    # OCR garbage is short non-words ("ee", "oe", "Se"): mean alpha-token
    # length 2.5-3.2; structural term lists (exam objectives, product
    # names) share the low common-word share but carry long real words.
    "ocr_max_mean_token_len": 4.5,
    "symbol_share_code": 0.06,    # XML / code listings (body max 0.051)
    "digit_share_output": 0.35,   # log / packet / table dumps
    "index_line_share": 0.40,
    "toc_line_share": 0.30,
    "legal_markers": 2,
    "legal_max_words": 250,
    "question_stems": 2,
    "question_marks_per_kchar": 3.0,
}

_COMMON_WORDS = frozenset("""
the of and to a in is that for it as with on be are this by an or from at
which you can your will not have has was were if but they their we all one
more when each into than then them these those there may use used also
should such so two only other its any what how i he she his her who do does
did been being would could about after before over under between through
during out up down off again further once here where why some no nor too
very just because while both few most own same s t don now new many much
like make made get take see know want need first last next well way year
years work works system data time information example following question
questions answer answers table page chapter""".split())
_SYMBOL_RE = re.compile(r"[<>{}\[\]=;/\\|@#$%^&*~`]")

_LEGAL_RE = re.compile(
    r"all rights reserved|\btrademarks?\b|\bcopyright\b|©|\bisbn\b|"
    r"permission(s)? (of|should be addressed)|no part of this (book|publication)|"
    r"library of congress|printed in the|\baffiliated with\b|\bregistered trademark",
    re.IGNORECASE)
_QUESTION_STEM_RE = re.compile(
    r"which (one )?of the following|what (is|are|should|type|term|would|does|kind)\b|"
    r"which (statement|option|tool|control|action|term)\b|best describes|most likely",
    re.IGNORECASE)
_INDEX_LINE_RE = re.compile(r"^\s*[A-Za-z][A-Za-z\s,'\-&()/]{1,60},\s*\d+(?:[\s,\-–]+\d+)*\s*$")
_TOC_LINE_RE = re.compile(r"\.{3,}\s*\d+\s*$|\[[^\]]{1,100}\]\(#[\w\-]+\)")
_TOKEN_RE = re.compile(r"[A-Za-z]+")


def signals(text: str) -> dict:
    """Deterministic text-shape signals (all ratios in [0, 1])."""
    tokens = text.split()
    words = len(tokens)
    alpha_tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    alnum = sum(ch.isalnum() for ch in text) or 1
    digits = sum(ch.isdigit() for ch in text)
    common = sum(1 for t in alpha_tokens if t in _COMMON_WORDS)
    top_share = (Counter(alpha_tokens).most_common(1)[0][1] / len(alpha_tokens)) if alpha_tokens else 0.0
    lines = [ln for ln in text.splitlines() if ln.strip()]
    n_lines = len(lines) or 1
    index_lines = sum(1 for ln in lines if _INDEX_LINE_RE.match(ln))
    toc_lines = sum(1 for ln in lines if _TOC_LINE_RE.search(ln))
    kchars = max(1.0, len(text) / 1000.0)
    return {
        "words": words,
        "alpha_tokens": len(alpha_tokens),
        "common_share": (common / len(alpha_tokens)) if alpha_tokens else 0.0,
        "mean_alpha_len": (sum(len(t) for t in alpha_tokens) / len(alpha_tokens)) if alpha_tokens else 0.0,
        "symbol_share": len(_SYMBOL_RE.findall(text)) / max(1, len(text)),
        "digit_share": digits / alnum,
        "top_token_share": top_share,
        "index_line_share": index_lines / n_lines,
        "toc_line_share": toc_lines / n_lines,
        "legal_markers": len(_LEGAL_RE.findall(text[:1500])),
        "question_stems": len(_QUESTION_STEM_RE.findall(text)),
        "question_marks_per_kchar": text.count("?") / kchars,
    }


def classify_region(text: str | None, heading_kind: str | None = None) -> tuple[str, str]:
    """Return (role, reason). `heading_kind` is the chunk_kind heading
    classification when the caller has one (it wins for structural
    matter); text-shape rules cover what headings cannot see."""
    text = text or ""
    s = signals(text)
    t = THRESHOLDS
    if s["words"] < MIN_WORDS:
        return ROLE_STUB, f"words={s['words']}<{MIN_WORDS}"
    if heading_kind in _HEADING_NOISE_KINDS:
        return heading_kind, f"heading:{heading_kind}"
    if heading_kind == ROLE_CODE:
        return ROLE_CODE, "heading:code"
    if s["index_line_share"] >= t["index_line_share"]:
        return ROLE_INDEX, f"index_lines={s['index_line_share']:.2f}"
    if s["toc_line_share"] >= t["toc_line_share"]:
        return ROLE_TOC, f"toc_lines={s['toc_line_share']:.2f}"
    if s["legal_markers"] >= t["legal_markers"] and s["words"] <= t["legal_max_words"]:
        return ROLE_LEGAL, f"legal_markers={s['legal_markers']}"
    if s["digit_share"] >= t["digit_share_output"]:
        return ROLE_OUTPUT, f"digit_share={s['digit_share']:.2f}"
    if s["symbol_share"] >= t["symbol_share_code"]:
        return ROLE_CODE, f"symbol_share={s['symbol_share']:.3f}"
    if (s["common_share"] < t["common_share_noise"]
            and s["mean_alpha_len"] < t["ocr_max_mean_token_len"]):
        return ROLE_NOISE_OCR, f"common_share={s['common_share']:.3f} mean_len={s['mean_alpha_len']:.1f}"
    if (s["question_stems"] >= t["question_stems"]
            or (s["question_marks_per_kchar"] >= t["question_marks_per_kchar"]
                and s["question_stems"] >= 1)):
        return ROLE_QUESTION_BANK, f"stems={s['question_stems']} q/kchar={s['question_marks_per_kchar']:.1f}"
    return ROLE_BODY, "prose"


def is_noise(role: str | None) -> bool:
    return bool(role) and role in NOISE_ROLES


def parent_role(child_roles: list[str | None]) -> tuple[str, str]:
    """A parent is noise only when EVERY child is noise (then it takes the
    most common child noise role); otherwise it is prose-bearing. A
    parent whose children are mostly question_bank is question_bank."""
    roles = [r or ROLE_BODY for r in child_roles]
    if not roles:
        return ROLE_STUB, "no_children"
    if all(is_noise(r) for r in roles):
        role = Counter(roles).most_common(1)[0][0]
        return role, "all_children_noise"
    live = [r for r in roles if not is_noise(r)]
    if live and sum(1 for r in live if r == ROLE_QUESTION_BANK) * 2 > len(live):
        return ROLE_QUESTION_BANK, "majority_question_bank"
    return ROLE_BODY, "has_prose_children"


def contract_fingerprint() -> dict:
    """Everything that changes a role verdict; hashed into the extract
    contract identity (a threshold change must re-extract)."""
    return {"contract": REGION_CONTRACT, "min_words": MIN_WORDS,
            "thresholds": dict(sorted(THRESHOLDS.items())),
            "noise_roles": sorted(NOISE_ROLES)}
