"""CORPUS-PLAN (docs/19): compile 3–5 corpus reformulations BEFORE retrieval.

The web lane already compiles queries deterministically (gap_compiler); the
corpus lane asked the agent to improvise. Now the `corpus_plan` transform
derives a small, diverse query set from the signal alone — no LLM — and the
adapter runs every one of them across every configured corpus, recording
which query produced each row (`query_ids`). θ may add reformulations at the
corpus node; it can no longer skip breadth by accident.

Shapes (each with a stable id and a WHY):
  seed        the first sentence of the raw seed (the concrete situation)
  tension     the latent interpretation's core sentence (the abstract pull)
  communities the named communities line (where the tension is lived)
  invariant   the sentence naming a capacity / aspiration (cross-domain hook)
  contrast    a "why do people keep …" probe from the strongest verbs/nouns
"""
from __future__ import annotations

import re

from models import stable_id

_STOP = set("""a an and are as at be been being by for from has have how i if in into is it its of on or that the their them
there these they this to was were what when where which who why will with would you your about after also because before
between both can could do does did each even every few had here him his how just like made make many may me more most much
my never no nor not now off once only other our out over own same she should so some still such than then through too under
until up very we well while whole""".split())
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“(])")


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    return [s.strip() for s in _SENT.split(text) if len(s.strip()) > 20]


def _section(signal: str, marker: str) -> str:
    i = signal.upper().find(marker.upper())
    if i == -1:
        return ""
    rest = signal[i + len(marker):]
    j = re.search(r"\n\s*\n|(?:LATENT INTERPRETATION|SEED)\s*\(", rest)
    return rest[: j.start()] if j else rest


def _keywords(text: str, n: int = 8) -> list[str]:
    toks = re.findall(r"[a-zA-Z][a-zA-Z\-']{3,}", (text or "").lower())
    freq: dict[str, int] = {}
    for t in toks:
        if t in _STOP:
            continue
        freq[t] = freq.get(t, 0) + 1
    return [t for t, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def _trim(s: str, n: int = 220) -> str:
    s = re.sub(r"\s+", " ", s).strip().strip('"“”')
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0]


def compile_queries(state: dict, policies: dict) -> list[dict]:
    signal = state["data"].get("signal") or ""
    seed = _section(signal, "SEED") or signal
    latent = _section(signal, "LATENT INTERPRETATION")
    out: list[dict] = []

    def add(kind: str, text: str, why: str, minlen: int = 12):
        text = _trim(text)
        if len(text) < minlen or any(q["query"] == text for q in out):
            return
        out.append({"id": stable_id("cq", kind, text), "kind": kind, "query": text, "why": why})

    ss = _sentences(re.sub(r"^\s*\([^)]*\):?\s*", "", seed))
    if ss:
        add("seed", ss[0], "the concrete situation the seed describes")
    ls = _sentences(latent)
    if ls:
        add("tension", ls[0], "the latent human tension beneath the topic")
    for s in ls[1:]:
        low = s.lower()
        if "communit" in low or "forum" in low or "subreddit" in low or "r/" in low:
            add("communities", s.split(":", 1)[-1], "where the tension is lived — recall across contexts")
            break
    for s in ls[1:]:
        low = s.lower()
        if any(w in low for w in ("capacity", "aspiration", "tension is", "sense of", "wants", "want to")):
            add("invariant", s, "the capacity / aspiration — the cross-domain hook")
            break
    kws = _keywords(seed + " " + latent, 10)
    if len(kws) >= 4:
        add("contrast", "why do people keep " + " ".join(kws[:6]), "behaviour-level probe from the strongest terms")
    pol = (policies.get("corpus") or {})
    lo, hi = int(pol.get("min_queries", 3)), int(pol.get("max_queries", 5))
    if len(out) < lo:
        for s in (ss + ls)[1:]:
            if len(out) >= lo:
                break
            add("sentence", s, "additional reformulation to reach the minimum breadth")
    # a short or plain signal still gets a plan: the seed verbatim, its strongest
    # terms, and a behaviour probe — never an empty corpus lane
    if len(out) < lo:
        add("seed", seed.strip() or signal.strip(), "the seed verbatim", minlen=3)
        kws = kws or _keywords(signal, 6)
        if kws:
            add("keywords", " ".join(kws[:6]), "the strongest terms, unordered — recall over precision", minlen=3)
            add("behaviour", "how people cope with " + " ".join(kws[:4]), "behaviour-level probe", minlen=3)
    return out[:hi]


def corpus_query_compiler(state: dict, policies: dict) -> str:
    qs = compile_queries(state, policies)
    state["data"]["corpus_queries"] = qs
    return f"compiled {len(qs)} corpus reformulations: " + ", ".join(q["kind"] for q in qs)
