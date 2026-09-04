"""Deterministic transform/gate executors (the python.* nodes).

Everything here must be reproducible from state + registry + policies alone:
lens gating, gap compilation, query compilation, observation curation,
supplier normalization, scoring. No LLM calls, ever.
"""
from __future__ import annotations

import csv
import os
import re

import yaml

import verifiers as _ver

from models import stable_id

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "registry")


# ---------------------------------------------------------------- registry --
def load_lenses() -> dict:
    with open(os.path.join(REG, "lenses.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)["lenses"]


def load_csv(name: str) -> list[dict]:
    with open(os.path.join(REG, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------- lens gate --
_SUFFIXES = ("", "s", "es", "ed", "ing", "er", "ers", "ment", "ments", "able")


def _keyword_hit(keyword: str, text: str) -> bool:
    """Whole-word match with bounded English morphology ("move" hits
    "movement"/"moving"; "saw" does NOT hit "sawdust"). Bare substring
    matching selected lenses on accidents of spelling."""
    k = keyword.lower().strip()
    if not k:
        return False
    stems = {k}
    if k.endswith("e"):
        stems.add(k[:-1])
    alts = sorted({re.escape(st) + suf for st in stems for suf in _SUFFIXES}, key=len, reverse=True)
    return re.search(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])", text) is not None


def lens_gate(state: dict, policies: dict) -> str:
    """Select lenses whose keywords appear in signal + corpus evidence text."""
    corpus = (state["data"]["signal"] + " " + " ".join(
        str(e.get("summary") or e.get("text") or "") for e in state["data"]["corpus_evidence"]
    )).lower()
    selected = []
    for name, spec in load_lenses().items():
        if any(_keyword_hit(k, corpus) for k in spec.get("keywords", [])):
            selected.append({"name": name, "question": spec["question"]})
    if not selected:  # never proceed lens-less; minimal-interference is the universal probe
        selected = [{"name": "minimal-interference",
                     "question": load_lenses()["minimal-interference"]["question"]}]
    state["data"]["lenses"] = selected
    return f"selected {len(selected)} lenses: " + ", ".join(l["name"] for l in selected)


# -------------------------------------------------- breadth layer (docs/07) --
def signal_gate(state: dict, policies: dict) -> str:
    """NO_GENERATIVE_SIGNAL is a SUCCESS outcome: most knowledge should
    produce zero products. Only sets the verdict; the edge does the routing."""
    prim = state["data"].get("primitives") or {}
    if not prim.get("generative_signal"):
        state["verdict"] = "NO_GENERATIVE_SIGNAL"
        return "no behaviorally/physically useful signal — retained as knowledge only"
    return (f"generative signal present: {len(prim.get('physical_jobs') or [])} physical jobs, "
            f"{len(prim.get('transferable_invariants') or [])} invariants")


def structural_lookup(state: dict, policies: dict) -> str:
    """Cross-domain analogies via the compiled registry — bounded by a shared
    invariant (no invariant, no expansion: associative wandering is banned)."""
    prim = state["data"].get("primitives") or {}
    bp = policies.get("breadth") or {}
    if bp.get("require_invariant_for_transfer", True) and not prim.get("transferable_invariants"):
        state["data"]["cross_domain_analogies"] = []
        return "no transferable invariant declared — cross-domain expansion skipped"
    try:
        import registry as _reg
        snap = _reg.load_snapshot()
    except Exception:
        snap = None
    if not snap:
        state["data"]["cross_domain_analogies"] = []
        return "no registry snapshot — structural pass skipped"
    preds = [str(x).lower() for x in prim.get("shared_predicates") or []]
    fams = [str(x) for x in (prim.get("frictions") or []) if x in snap["friction_families"]]
    hits, seen = [], set()
    for pred in preds:
        for fam in fams or [None]:
            key_idx = (snap["index_by_predicate_friction"].get(f"{pred}|{fam}", []) if fam
                       else snap["index_by_predicate"].get(pred, []))
            for i in key_idx:
                sd = snap["seeds"][i]
                k = (sd["domain"], sd["friction_family"], sd["product_territory"])
                if k in seen:
                    continue
                seen.add(k)
                hits.append({"seed_id": sd["seed_id"], "domain": sd["domain"],
                             "activity": sd["activity"], "task": sd["task"],
                             "friction_family": sd["friction_family"],
                             "workaround_hypothesis": sd["workaround_hypothesis"],
                             "product_territory": sd["product_territory"],
                             "matched": {"predicate": pred, "friction": fam},
                             "authority": "SEED_HYPOTHESIS"})
    hits = hits[: bp.get("max_cross_domain_analogies", 8)]
    # docs/19: the CORPUS supplies analogies too — graph facts and entity hops
    # (rows the adapter tagged graph_fact / graph_hop, provenance attached)
    # whose subject/object/predicate tokens overlap the primitives' physical
    # jobs, frictions or invariants. Same cap; authority stays hypothesis-level.
    corpus_hits = _corpus_analogies(state, prim, bp.get("max_cross_domain_analogies", 8) - len(hits))
    state["data"]["cross_domain_analogies"] = hits + corpus_hits
    return (f"{len(hits)} registry + {len(corpus_hits)} corpus cross-domain analogies attached "
            f"(invariant-bounded)")


_CQ_STOP = {"with", "from", "that", "this", "their", "when", "where", "which", "into", "than", "then", "them", "they",
            "have", "been", "were", "will", "would", "should", "could", "about", "after", "before", "under", "over"}


def _corpus_analogies(state: dict, prim: dict, budget: int) -> list[dict]:
    if budget <= 0:
        return []
    vocab = set()
    for key in ("physical_jobs", "frictions", "transferable_invariants", "shared_predicates", "behaviors"):
        for item in prim.get(key) or []:
            vocab.update(w for w in re.findall(r"[a-z][a-z\-]{3,}", str(item).lower()) if w not in _CQ_STOP)
    out, seen = [], set()
    _rel = state["data"].get("row_relevance") or {}
    for r in state["data"].get("corpus_evidence") or []:
        if _rel.get(r.get("id")) in (None, "IRRELEVANT"):
            continue                            # docs/26 §2 (fail-closed): only CLASSIFIED, non-irrelevant rows become analogies
        tags = set(r.get("tags") or []) | {r.get("kind") or ""}
        if not (tags & {"graph_fact", "graph_hop"}):
            continue
        fact = r.get("fact") or r.get("via_fact") or {}
        text = " ".join(str(fact.get(k) or "") for k in ("subject", "predicate", "object")) or (r.get("summary") or "")
        toks = set(re.findall(r"[a-z][a-z\-]{3,}", text.lower()))
        overlap = sorted(toks & vocab)
        if not overlap:
            continue
        key = (r.get("title") or r.get("doc_id"), fact.get("predicate"), fact.get("object"))
        if key in seen:
            continue
        seen.add(key)
        out.append({"seed_id": r.get("id"), "domain": r.get("title") or r.get("doc_id") or "corpus",
                    "activity": str(fact.get("subject") or "")[:80],
                    "task": f"{fact.get('predicate') or ''} {fact.get('object') or ''}".strip()[:120],
                    "friction_family": next((f for f in (prim.get("frictions") or []) if f in overlap), "?"),
                    "workaround_hypothesis": "", "product_territory": "corpus",
                    "matched": {"tokens": overlap[:5]}, "source": r.get("source"),
                    "authority": "CORPUS_FACT_HYPOTHESIS"})
        if len(out) >= budget:
            break
    return out


def triage(state: dict, policies: dict) -> str:
    """Pre-research triage: a deterministic RESEARCH PRIORITY (a prior, never
    evidence). Research budget goes where evidence could teach the most."""
    tp = policies.get("triage") or {}
    live = [h for h in state["data"]["hypotheses"]
            if h.get("status") in ("WORKING_HYPOTHESIS", "WORKING_ANALOGY", "CHALLENGED")]
    for h in live:
        pri = 0
        pri += min(len(h.get("falsifiers") or []), 2)          # falsifiability
        pri += min(len(h.get("gaps") or []), 2)                # researchability
        pri += 1 if h.get("alternatives") else 0               # thought-through
        pri += 1 if h.get("exploratory") else 0                # info-gain of the wildcard
        h["research_priority"] = pri
    ranked = sorted(live, key=lambda h: -h["research_priority"])
    keep = {h["id"] for h in ranked[: tp.get("max_research_ready", 3)]
            if h["research_priority"] >= tp.get("min_priority", 2)}
    held = 0
    for h in live:
        if h["id"] not in keep and h.get("status") != "SUPPORTED":
            h["status"] = "HOLD"; held += 1
    return f"triage: {len(keep)} research-ready, {held} held (priority is a prior, not evidence)"


# ------------------------------------------------------ gaps + query compile --
# channel -> (template, source_family, why, expected roles). Every query
# declares WHY its source was chosen and what it CANNOT satisfy (docs/04 §8).
# docs/24 §1 — evidence CHANNELS. Each carries the exact tool chain an agent runs
# (OpenCLI / agent-reach verbs verified 2026-09-03), the source family (docs/04
# authority decides what it may establish), and how independence is keyed.
# Enabled/ordered by policies.evidence_channels; the query form is SHORT keywords.
_CHANNEL_TEMPLATES = [
    ("reddit", "{q}", "community",
     "first-person complaint, workaround, and comparison language",
     ["FRICTION_EVIDENCE", "WORKAROUND_EVIDENCE", "PRODUCT_COMPARISON", "PURCHASE_INTENT"],
     {"tools": ['opencli reddit search "{q}" --subreddit <hint> --sort relevance --time year --limit 10 -f json',
                "opencli reddit read <post-id> -f json"],
      "identity": "platform=reddit author_key=u/<author> thread_key=<post-id>", "freshness": "post date → LIVE ≤90d / FAST ≤2y"}),
    ("amazon_reviews", "{q}", "review",
     "post-purchase language: what broke, what they did instead, what they compared it to",
     ["PRODUCT_COMPLAINT", "WORKAROUND_EVIDENCE", "PRODUCT_COMPARISON", "PRODUCT_REQUEST", "CURRENT_PRODUCT_REFERENCE"],
     {"tools": ['opencli amazon search "{q}" -f json', "opencli amazon discussion <asin-or-url> -f json"],
      "identity": "platform=amazon author_key=<reviewer> thread_key=<ASIN>", "freshness": "review date",
      "law": "a review is a product complaint or request, never FRICTION_EVIDENCE about life without the product (docs/04)"}),
    ("youtube", "{q}", "community",
     "creator-audience discussion under demonstration videos",
     ["FRICTION_EVIDENCE", "BEHAVIOR_SUPPORT", "WORKAROUND_EVIDENCE"],
     {"tools": ['opencli youtube search "{q}" -f json', "opencli youtube comments <video-url> -f json"],
      "identity": "platform=youtube author_key=<channel/handle> thread_key=<video-id>", "freshness": "comment date"}),
    ("tiktok", "{q}", "community",
     "short-video captions and on-screen text where people show the workaround",
     ["BEHAVIOR_SUPPORT", "WORKAROUND_EVIDENCE", "FRICTION_EVIDENCE"],
     {"tools": ['opencli tiktok search "{q}" -f json'],
      "identity": "platform=tiktok author_key=@<creator> thread_key=<video-id>", "freshness": "video date",
      "limits": "OpenCLI reads videos, not their comment threads — quote the caption/on-screen text, or read comments through the browser lane"}),
    ("xiaohongshu", "{q}", "community",
     "consumer notes + threaded comments (Chinese; translate the quote, keep the original)",
     ["BEHAVIOR_SUPPORT", "WORKAROUND_EVIDENCE", "FRICTION_EVIDENCE", "PRODUCT_COMPARISON"],
     {"tools": ['opencli xiaohongshu search "{q}" -f json', "opencli xiaohongshu comments <note-id> -f json"],
      "identity": "platform=xiaohongshu author_key=<user> thread_key=<note-id>", "freshness": "note date"}),
    ("twitter", "{q}", "community",
     "public complaint and comparison language in threads",
     ["FRICTION_EVIDENCE", "PRODUCT_COMPARISON", "PURCHASE_INTENT"],
     {"tools": ['opencli twitter search "{q}" -f json', "opencli twitter thread <tweet-id> -f json"],
      "identity": "platform=twitter author_key=@<handle> thread_key=<tweet-id>", "freshness": "tweet date"}),
    ("forum", "{q} forum", "community",
     "niche practitioners describing real behavior and adaptations",
     ["BEHAVIOR_SUPPORT", "WORKAROUND_EVIDENCE", "FRICTION_EVIDENCE"],
     {"tools": ['mcporter call exa.web_search_exa query="{q} forum" numResults=10', 'curl -s "https://r.jina.ai/<url>"'],
      "identity": "platform=<forum host> author_key=<handle> thread_key=<thread url>", "freshness": "post date"}),
]
# not compiled (honest): instagram — OpenCLI searches USERS only, no post/comment search; facebook — groups need membership
_GAP_DEFAULT_ROLES = ["FRICTION_EVIDENCE", "WORKAROUND_EVIDENCE",
                      "BEHAVIOR_SUPPORT", "PURCHASE_INTENT"]
_GAP_STOP = {"evidence", "missing", "intermediate", "does", "do", "they", "their", "what", "which", "where", "when",
             "that", "this", "with", "from", "into", "have", "has", "are", "and", "the", "for", "about", "report",
             "describe", "communities", "community", "people", "users", "say", "mention", "anyone", "specific",
             "actually", "these", "those", "than", "then", "there", "still", "just", "also", "any", "how", "whether"}


def _gap_keywords(question: str, n: int = 8) -> list[str]:
    toks = re.findall(r"[a-zA-Z][a-zA-Z\-']{2,}", question or "")
    out: list[str] = []
    for t in toks:
        tl = t.lower()
        if tl in _GAP_STOP or tl in out or len(tl) < 3:
            continue
        out.append(tl)
    return out[:n]


def channel_queries(gid: str, question: str, state: dict, policies: dict, id_prefix: str = "q") -> list[dict]:
    """docs/24: one query per enabled evidence channel (policy order) for one gap.
    The SHORT keyword form is the search string; every row names the exact tool
    chain, the identity key and the freshness source for its channel."""
    kw = _gap_keywords(question)
    short = " ".join(kw[:6])
    hints = list(state["data"].get("communities") or [])
    enabled = list(policies.get("evidence_channels") or [t[0] for t in _CHANNEL_TEMPLATES])
    out = []
    for channel, tpl, family, why, expected, how in sorted((t for t in _CHANNEL_TEMPLATES if t[0] in enabled), key=lambda t: enabled.index(t[0])):
        out.append({
            "id": stable_id(id_prefix, gid, channel), "gap_id": gid,
            # docs/19: the question is NOT the search string
            "query": tpl.format(q=short), "question": question, "keywords": kw,
            "subreddit_hints": hints[:6] if channel == "reddit" else [],
            "tools": [t.replace("{q}", short) for t in how.get("tools") or []],
            "identity": how.get("identity"), "freshness_hint": how.get("freshness"),
            **({"law": how["law"]} if how.get("law") else {}), **({"limits": how["limits"]} if how.get("limits") else {}),
            "channel": channel, "source_family": family, "why_this_source": why,
            "expected_evidence_roles": expected,
            "cannot_satisfy": ["SUPPLIER_AVAILABILITY", "PRICE_EVIDENCE", "MOQ_EVIDENCE", "CURRENT_PRODUCT_REFERENCE"]})
    return out


def gap_compiler(state: dict, policies: dict) -> str:
    gaps, queries = state["data"]["gaps"], state["data"]["queries"]
    known = {g["id"] for g in gaps}
    added_g = added_q = 0
    for h in state["data"]["hypotheses"]:
        if h.get("status") in ("REJECTED", "HOLD"):
            continue
        for gap_q in h.get("gaps", []):
            gid = stable_id("gap", h["id"], gap_q)
            if gid in known:
                continue
            known.add(gid)
            fresh = ["LIVE"] if h.get("genesis") in ("TREND_LED", "SHIFT_LED") \
                else ["FAST", "LIVE"]
            gaps.append({"id": gid, "hypothesis_id": h["id"], "question": gap_q,
                         "status": "open", "genesis": h.get("genesis"),
                         "required_evidence_roles": list(_GAP_DEFAULT_ROLES),
                         "required_freshness": fresh})
            added_g += 1
            try:
                import registry as _reg
                _snap = _reg.load_snapshot()
                _grammars = [t for t in (_snap or {}).get("query_templates", [])
                             if set(t.get("expected_roles") or []) & set(_GAP_DEFAULT_ROLES)]
            except Exception:
                _grammars = []
            if _grammars:
                gaps[-1]["registry_query_grammars"] = [
                    {"id": t["id"], "grammar": t["grammar"], "goal": t["evidence_goal"],
                     "expected_roles": t["expected_roles"]} for t in _grammars[:6]]
            for cq in channel_queries(gid, gap_q, state, policies):
                queries.append(cq)
                added_q += 1
    # docs/20 §1: allocation — starved hypotheses first, queries interleaved
    import allocation as _alloc
    alloc = _alloc.hypothesis_allocation(state, policies)
    state["data"]["research_allocation"] = alloc
    state["data"]["queries"] = _alloc.interleave_queries(queries, alloc, gaps)
    starved = [a["hypothesis_id"] for a in alloc if a["starved"]]
    return (f"compiled {added_g} new gaps, {added_q} queries ({len([g for g in gaps if g['status']=='open'])} open)"
            + (f" | allocation: starved first {starved}" if starved else ""))


# ---------------------------------------------------------------- curation --
def comments(state: dict, policies: dict) -> str:
    """Dedupe observations, close gaps with enough independent sources."""
    obs = state["data"]["observations"]
    # Registry workaround lexicon: deterministic DETECTION only — a marker
    # flags possible WORKAROUND_EVIDENCE for the model to consider; it never
    # assigns a friction family or role by itself (docs/06 §2).
    try:
        import registry as _reg
        _snap = _reg.load_snapshot()
        _lex = set((_snap or {}).get("workaround_lexicon") or [])
    except Exception:
        _lex = set()
    if _lex:
        for o in obs:
            text = f"{o.get('quote_ref','')} {o.get('workaround','')}".lower()
            hits = sorted(m for m in _lex if m in text)
            if hits and "WORKAROUND_EVIDENCE" not in (o.get("evidence_roles") or []):
                o["lexicon_flags"] = [f"workaround_marker:{m}" for m in hits[:4]]
    seen, unique = set(), []
    for o in obs:
        # docs/19: one quote may answer two questions — dedupe per (quote, gap)
        key = ((o.get("quote_ref") or "").strip().lower() or stable_id("obs", o.get("source", ""), o.get("problem", "")),
               o.get("gap_id") or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(o)
    state["data"]["observations"] = unique
    min_src = policies["evidence"]["min_independent_sources"]
    closed = contradicted = 0
    for gap in state["data"]["gaps"]:
        if gap["status"] != "open":
            continue
        need = set(gap.get("required_evidence_roles") or [])
        fresh_ok = set(gap.get("required_freshness") or [])

        def _counts(o):
            if fresh_ok and ((o.get("freshness") or {}).get("class") not in fresh_ok):
                return False  # docs/19: required_freshness is enforced, not decorative
            return not need or need.intersection(o.get("evidence_roles") or [])
        support = [o for o in unique
                   if o.get("gap_id") == gap["id"] and not o.get("contradicts") and _counts(o)]
        against = [o for o in unique if o.get("gap_id") == gap["id"] and o.get("contradicts")]
        # ONE definition of "independent" for the whole run: the same
        # (platform, author) grouping coverage uses (verifiers.independence_groups).
        # Counting distinct `source` strings let a gap close on three URLs
        # from one author while coverage reported one voice.
        groups = _ver.independence_groups(support)["independent_groups"]
        if len(against) > len(support):
            gap["status"] = "contradicted"; contradicted += 1
        elif groups >= min_src:
            gap["status"] = "supported"; closed += 1
    state["rounds"]["research"] += 1
    import satisfaction as _sat
    cov = _sat.recompute(state, policies)
    import allocation as _alloc
    alloc = _alloc.hypothesis_allocation(state, policies)
    state["data"]["research_allocation"] = alloc
    starved = [a["hypothesis_id"] for a in alloc if a["starved"]]
    return (f"curated {len(unique)} unique observations; gaps supported+{closed} "
            f"contradicted+{contradicted}; round {state['rounds']['research']}; "
            f"coverage missing: {cov['missing'] or 'none'}"
            + (f"; STARVED (cannot be rejected yet): {starved}" if starved else ""))


# ---------------------------------------------------------------- supplier --
_PRICE = re.compile(r"(?:US?\s*\$|USD\s*)?([\d,]+(?:\.\d+)?)(?:\s*[-–~]\s*(?:US?\s*\$|USD\s*)?([\d,]+(?:\.\d+)?))?")
# A price is USD only when it says so (or carries a bare `$`); any other
# currency marker means "not parsed" rather than "25 dollars". A quantity
# is a number WITH a unit (the last one wins: "1-10 pieces" is MOQ 10) or a
# lone integer; a price-looking string is never a quantity.
_NON_USD = re.compile(r"(?:¥|€|£|₹|₩|(?:\bA|\bC|\bHK|\bNZ|\bS)\$|\b(?:RMB|CNY|EUR|GBP|JPY|INR|AUD|CAD|KRW)\b)", re.I)
_USD_MARK = re.compile(r"(?:(?:\bUS?\s*)?\$|\bUSD\b)", re.I)
_MOQ_UNIT = re.compile(r"(\d[\d,]*)\s*(?:pcs?|pieces?|sets?|units?|pairs?|bags?|boxes?|cartons?|packs?|rolls?|kgs?|kilograms?|meters?)\b", re.I)
_INT = re.compile(r"\d[\d,]*")
_MOQ = _MOQ_UNIT  # kept for callers that imported the old name


def _parse_price(raw) -> tuple[float | None, float | None]:
    raw = str(raw or "")
    if _NON_USD.search(raw) and not _USD_MARK.search(raw):
        return None, None
    pm = _PRICE.search(raw)
    if not pm:
        return None, None
    lo = _num(pm.group(1))
    hi = _num(pm.group(2)) if pm.group(2) else lo
    return lo, hi


def _parse_moq(raw) -> int | None:
    raw = str(raw or "").strip()
    if not raw or _NON_USD.search(raw) or "$" in raw or re.search(r"\d\.\d", raw):
        return None
    with_unit = _MOQ_UNIT.findall(raw)
    if with_unit:
        n = _num(with_unit[-1])
    else:
        ints = _INT.findall(raw)
        if len(ints) != 1:        # "1-10" with no unit is ambiguous: refuse to guess
            return None
        n = _num(ints[0])
    return int(n) if n and n > 0 else None


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


_SOURCING_TOOLS = {
    "alibaba": ['python3 python/sourcing_exa.py --state run.json --out cands.json --channels alibaba',
                'mcporter call exa.web_search_exa query="<term> site:alibaba.com wholesale MOQ price" numResults=6'],
    "cjdropshipping": ['python3 python/sourcing_exa.py --state run.json --out cands.json --channels cjdropshipping',
                       'mcporter call exa.web_search_exa query="<term> site:cjdropshipping.com" numResults=6'],
}


def sourcing_plan_compiler(state: dict, policies: dict) -> str:
    """docs/20 §2: one sourcing job PER CONCEPT, compiled the moment the run
    arrives at supplier_search. The agent searches each concept's terms and
    stamps concept_id on every candidate; a concept nobody sourced is reported
    as UNSOURCED — never quietly covered by another concept's listing."""
    d = state["data"]
    pol = policies.get("sourcing") or {}
    channels = list(pol.get("channels") or ["alibaba", "cjdropshipping"])
    mechs = {m.get("id"): m for m in d.get("mechanisms") or []}
    plan = []
    for c in d.get("product_concepts") or []:
        terms = [c.get("name"), c.get("form_factor")]
        terms += [v.get("name") for v in c.get("variations") or [] if isinstance(v, dict)]
        terms += [p.get("name") for p in d.get("product_candidates") or [] if p.get("mechanism_id") == c.get("mechanism_id")]
        terms = list(dict.fromkeys(str(t).strip() for t in terms if t))
        for ch in channels:
            plan.append({"id": f"sp_{c.get('id')}_{ch}", "concept_id": c.get("id"), "concept": c.get("name"), "channel": ch,
                         "mechanism_id": c.get("mechanism_id"), "mechanism": (mechs.get(c.get("mechanism_id")) or {}).get("name"),
                         "search_terms": terms[:8], "min_candidates": int(pol.get("min_candidates_per_concept", 1)),
                         "tools": _SOURCING_TOOLS.get(ch, []),
                         "rule": f"search {ch} for THIS concept; every candidate carries concept_id + channel; price_raw / moq_raw verbatim "
                                 f"({'CJ: per-unit price incl. processing, MOQ is usually 1 — record ship-from warehouse' if ch == 'cjdropshipping' else 'Alibaba: tier price + MOQ text as shown'}); "
                                 "if nothing fits, submit nothing for it — an unsourced concept is a finding"})
    d["sourcing_plan"] = plan
    return f"sourcing plan: {len(plan)} jobs = {len(plan)//max(1,len(channels))} concepts × {channels} — no borrowing across concepts"


def _resolve_concept(s: dict, d: dict) -> None:
    """Stamp concept_id / mechanism_id on a candidate that arrived without them,
    when exactly one concept matches its product name."""
    if s.get("concept_id"):
        c = next((c for c in d.get("product_concepts") or [] if c.get("id") == s["concept_id"]), None)
        if c and not s.get("mechanism_id"):
            s["mechanism_id"] = c.get("mechanism_id")
        return
    hits = []
    for m in d.get("mechanisms") or []:
        if s.get("mechanism_id") and s["mechanism_id"] != m.get("id"):
            continue
        c = _concept_for(s, m, d)
        if c:
            hits.append(c)
    if len({c.get("id") for c in hits}) == 1:
        s["concept_id"] = hits[0].get("id")
        s.setdefault("mechanism_id", hits[0].get("mechanism_id"))
        s["concept_resolved_by"] = "name_overlap"


def sourcing_coverage(state: dict) -> list[dict]:
    d = state["data"]
    cov = []
    for c in d.get("product_concepts") or []:
        cs = [s for s in d.get("supplier_candidates") or [] if s.get("concept_id") == c.get("id")]
        parsed = [s for s in cs if s.get("price_usd_low") is not None and s.get("moq_units")]
        leads = [l for l in d.get("leads") or [] if l.get("concept_id") == c.get("id")]
        cov.append({"id": f"cov_{c.get('id')}", "concept_id": c.get("id"), "concept": c.get("name"),
                    "mechanism_id": c.get("mechanism_id"), "candidates": len(cs), "parsed": len(parsed), "leads": len(leads),
                    "status": "sourced" if parsed else ("unparsed" if cs else "unsourced")})
    d["sourcing_coverage"] = cov
    return cov


def supplier(state: dict, policies: dict) -> str:
    seen, normalized = set(), []
    for s in state["data"]["supplier_candidates"]:
        key = (s.get("product_name", "").strip().lower(), s.get("supplier_name", "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        lo, hi = _parse_price(s.get("price_raw", ""))
        s["price_usd_low"], s["price_usd_high"] = lo, hi
        s["moq_units"] = _parse_moq(s.get("moq_raw", ""))
        # docs/24 §2: dropship channels sell single units — a missing MOQ means 1, said so on the row
        _defaults = (policies.get("supplier") or {}).get("moq_default_by_channel") or {}
        if not s["moq_units"] and s.get("channel") in _defaults:
            s["moq_units"] = int(_defaults[s["channel"]]); s["moq_note"] = f"{s['channel']} default MOQ {s['moq_units']}"
        _resolve_concept(s, state["data"])
        normalized.append(s)
    state["data"]["supplier_candidates"] = normalized
    ok = [s for s in normalized if s["price_usd_low"] is not None and s["moq_units"]]
    cov = sourcing_coverage(state)
    unsourced = [c["concept"] for c in cov if c["status"] == "unsourced"]
    note = f"normalized {len(normalized)} suppliers ({len(ok)} with parsed price+MOQ)"
    if cov:
        note += f" | concepts sourced {sum(1 for c in cov if c['status'] == 'sourced')}/{len(cov)}"
        if unsourced:
            note += f"; UNSOURCED: {unsourced}"
    return note


# ----------------------------------------------------------------- scoring --
def scoring(state: dict, policies: dict) -> str:
    """Hard qualification gate: role COVERAGE decides the tier (docs/04 §6);
    evidence counts only rank the leads within it."""
    import satisfaction as _sat
    d, pol = state["data"], policies
    cov = _sat.recompute(state, policies)
    supported_mechs = [m for m in d["mechanisms"] if m.get("status") == "SUPPORTED"]
    if (not supported_mechs or not cov["core_satisfied"]
            or len(d["observations"]) < pol["evidence"]["min_total_observations"]):
        state["verdict"] = "NO_DEFENSIBLE_BRIDGE"
        d["leads"] = []
        return (f"verdict: NO_DEFENSIBLE_BRIDGE (coverage missing: "
                f"{cov['missing'] or 'evidence floor/mechanism'})")
    obs_by_id = {o["id"]: o for o in d["observations"]}
    leads = []
    for mech in supported_mechs:
        support = [obs_by_id[i] for i in mech.get("supporting_observation_ids", []) if i in obs_by_id]
        score = len(support) + pol["scoring"]["purchase_language_bonus"] * sum(
            1 for o in support if o.get("purchase_language"))
        if len(support) < pol["scoring"]["min_mechanism_support"]:
            continue
        for s in d["supplier_candidates"]:
            need_price = pol["supplier"]["require_price"] and s.get("price_usd_low") is None
            need_moq = pol["supplier"]["require_moq"] and not s.get("moq_units")
            if need_price or need_moq:
                continue
            if pol["supplier"].get("require_mechanism_fit", True) and not _supplier_fits(s, mech, d):
                continue  # docs/19: a lead pairs a supplier with the mechanism it embodies
            concept = _concept_for(s, mech, d)
            leads.append({
                "id": stable_id("lead", mech["id"], s["id"]),
                "concept_id": concept.get("id") if concept else None,
                "concept": concept.get("name") if concept else None,
                "mechanism": mech["name"], "mechanism_id": mech["id"],
                "product_name": s["product_name"], "supplier_name": s["supplier_name"], "channel": s.get("channel") or "alibaba",
                "url": s.get("url"), "images": s.get("images"),
                "price_usd_low": s["price_usd_low"], "price_usd_high": s["price_usd_high"],
                "moq_units": s["moq_units"], "evidence_score": score,
                "supporting_quotes": [o.get("quote_ref") for o in support][:5],
            })
    leads.sort(key=lambda x: -x["evidence_score"])
    leads = interleave_leads(leads)
    import settings as _settings
    max_leads = int(_settings.effective(state, "opportunity_research.max_leads",
                                        pol["supplier"]["max_leads"]))
    d["leads"] = leads[: min(max_leads, pol["supplier"]["max_leads"] + 2)]
    # docs/25 §7: lineage decides what may count — leads whose concept is
    # CORPUS_ECHO_UNGROUNDED are excluded (kept visible with the reason)
    import provenance as _prov
    had_leads = bool(d["leads"])
    prov = _prov.enforce(state, policies)
    tier = _sat.lead_tier(state, policies)
    if d["leads"] and tier == "QUALIFIED_LEAD":
        state["verdict"] = "QUALIFIED_LEADS"
    elif d["leads"]:
        state["verdict"] = "PROVISIONAL_LEADS"
    elif had_leads:
        state["verdict"] = (pol.get("provenance") or {}).get("echo_verdict", "CORPUS_ECHO_UNGROUNDED")
    else:
        state["verdict"] = "MECHANISM_WITHOUT_SUPPLY"
    import candidates as _cand
    note = _cand.auto_emit(state, policies)
    note += f" | provenance {prov['verdicts']}" + (f", excluded {prov['excluded_leads']} echo leads" if prov["excluded_leads"] else "")
    cov = sourcing_coverage(state)
    import utilization as _util
    d["utilization"] = _util.compute(state)          # docs/21 §1: the receipt every run carries
    cov_note = (f" | concepts with leads {sum(1 for c in cov if c['leads'])}/{len(cov)}"
                + (f", unsourced {[c['concept'] for c in cov if c['status'] == 'unsourced']}" if any(c['status'] == 'unsourced' for c in cov) else "")
                if cov else "")
    return f"verdict: {state['verdict']} (tier={tier}, {len(d['leads'])} leads{cov_note}) | {note}"


def interleave_leads(leads: list[dict]) -> list[dict]:
    """docs/20 §2: the lead cap must not re-collapse the portfolio. Leads
    arrive sorted by evidence score, which is a MECHANISM property, so a
    global top-N hands every slot to the best-evidenced mechanism (R4: the
    dose-staging concepts had parsed suppliers and still got 0 of 8 slots).
    Round-robin across concepts (mechanism when a lead has no concept),
    concepts ordered by their best score, score order kept within a concept."""
    by_c: dict = {}
    for l in leads:
        by_c.setdefault(l.get("concept_id") or l.get("mechanism_id") or "?", []).append(l)
    order = sorted(by_c, key=lambda k: (-by_c[k][0].get("evidence_score", 0), str(k)))
    merged: list[dict] = []
    while any(by_c.values()):
        for k in order:
            if by_c[k]:
                merged.append(by_c[k].pop(0))
    return merged


def _concept_for(s: dict, mech: dict, d: dict) -> dict | None:
    concepts = [c for c in d.get("product_concepts") or [] if c.get("mechanism_id") == mech.get("id")]
    if s.get("concept_id"):
        return next((c for c in concepts if c.get("id") == s["concept_id"]), None)
    toks = set(re.findall(r"[a-z]{4,}", (s.get("product_name") or "").lower()))
    best, best_n = None, 0
    for c in concepts:
        vnames = " ".join(v.get("name", "") for v in c.get("variations") or [] if isinstance(v, dict))
        ct = set(re.findall(r"[a-z]{4,}", f"{c.get('name', '')} {c.get('form_factor', '')} {vnames}".lower()))
        n = len(toks & ct)
        if n > best_n:
            best, best_n = c, n
    return best


def _supplier_fits(s: dict, mech: dict, d: dict) -> bool:
    """A supplier candidate fits a mechanism when it declares it (mechanism_id
    or concept_id), or when its product name shares a content token with the
    mechanism's name / product_terms / a concept of that mechanism."""
    if s.get("mechanism_id"):
        return s["mechanism_id"] == mech.get("id")
    if s.get("concept_id"):
        return any(c.get("id") == s["concept_id"] and c.get("mechanism_id") == mech.get("id")
                   for c in d.get("product_concepts") or [])
    toks = set(re.findall(r"[a-z]{4,}", (s.get("product_name") or "").lower()))
    terms = set(re.findall(r"[a-z]{4,}", (mech.get("name") or "").lower()))
    for t in mech.get("product_terms") or []:
        terms.update(re.findall(r"[a-z]{4,}", str(t).lower()))
    for c in d.get("product_concepts") or []:
        if c.get("mechanism_id") == mech.get("id"):
            terms.update(re.findall(r"[a-z]{4,}", f"{c.get('name', '')} {c.get('form_factor', '')}".lower()))
    return bool(toks & terms)


def apply_evaluations(state: dict, policies: dict) -> str:
    import evaluator as _ev
    return _ev.apply_evaluations(state, policies)


# ---------------------------------------------- NICHE_LOADOUT (docs/09) ----
def frontier_gate(state: dict, policies: dict) -> str:
    import loadout_math as lm
    ranked = lm.rank_frontier(state["data"].get("frontier_branches") or [], policies)
    state["data"]["frontier_rankings"] = ranked
    keep = [r for r in ranked if r["disposition"] in ("EXPLORE", "MAYBE")]
    return (f"frontier: {len([r for r in ranked if r['disposition']=='EXPLORE'])} explore, "
            f"{len([r for r in ranked if r['disposition']=='MAYBE'])} maybe, "
            f"{len(ranked)-len(keep)} pruned — U(b|s) decided, not vibes")


def voi_gate(state: dict, policies: dict) -> str:
    import loadout_math as lm
    questions = []
    for ls in state["data"].get("lived_situations") or []:
        for fr in ls.get("inferred_frictions") or []:
            questions.append({"id": f"{ls.get('id','ls')}:{fr}", "source_family": "community",
                              "missing_role_importance": 0.8, "decision_impact": 0.7,
                              "expected_cost": 1.0})
    plan = lm.rank_questions(questions, policies)
    state["data"]["research_plan"] = plan
    return f"VoI ranked {len(plan)} research questions — highest expected information first"


def portfolio_gate(state: dict, policies: dict) -> str:
    import loadout_math as lm
    import settings as _settings
    cands = state["data"].get("slot_candidates") or []
    # user's desired final size lives INSIDE the constitutional 3-6 contract
    target = _settings.effective(state, "niche_loadout.final_product_target", None)
    if target:
        pmax = policies["portfolio"]
        policies = {**policies, "portfolio": {**pmax,
                    "size_max": max(pmax["size_min"], min(int(target), pmax["size_max"]))}}
    result = lm.select_portfolio(cands, policies)
    by_id = {c["id"]: c for c in cands}
    state["data"]["loadout"] = [by_id[i] for i in result["selected"] if i in by_id]
    state["data"]["loadout_receipt"] = result
    return (f"portfolio F(S): selected {result['size']} covering jobs "
            f"{result['covered_jobs']} roles {result['covered_roles']} (set value {result['set_value']})")


def discovery_loop_gate(state: dict, policies: dict) -> str:
    """Docs/16: the user controls the DESIRED stopping condition (dig until N
    slot candidates); φ retains the ceilings — max extra rounds and stagnation
    detection. 'Keep looping until you find enough' never means forever."""
    import settings as _settings
    target = int(_settings.effective(state, "niche_loadout.discovery_product_target", 0) or 0)
    limit = int((policies.get("system_limits") or {}).get("loadout_discovery_rounds_max", 3))
    count = len(state["data"].get("slot_candidates") or [])
    prev = state.get("discovery_loop") or {}
    rounds = int(prev.get("rounds", 0)) + 1
    progressed = count > int(prev.get("last_count", -1))
    wants_more = bool(target) and count < target
    cont = wants_more and rounds <= limit and progressed
    if wants_more and not cont:
        why = "stagnation (no new candidates last round)" if not progressed \
            else f"round ceiling {limit} reached"
        outcome = f"target unmet ({count}/{target}) — stopping honestly: {why}"
    elif wants_more:
        outcome = f"{count}/{target} — one more discovery round"
    else:
        outcome = f"{count} candidates satisfy the request"
    state["discovery_loop"] = {"rounds": rounds, "last_count": count,
                               "target": target or None, "continue": cont}
    return f"discovery loop: {outcome}"


def loadout_ready(state: dict, policies: dict) -> str:
    import loadout_math as lm
    d = state["data"]
    loadout = d.get("loadout") or []
    traceable = sum(1 for p in loadout if p.get("why_this")) / max(1, len(loadout))
    fid = lm.insider_fidelity({
        "situation_specificity": min(1, len(d.get("lived_situations") or []) / 3),
        "task_coverage": min(1, len({j for p in loadout for j in p.get("physical_jobs") or []}) / 3),
        "workaround_realism": 1.0 if any("WORKAROUND_EVIDENCE" in (o.get("evidence_roles") or [])
                                          for o in d.get("observations") or []) else 0.0,
        "constraint_fidelity": min(1, len(d.get("world_model", {}).get("constraints", []) or []) / 3)
                               if isinstance(d.get("world_model"), dict) else 0.5,
        "insider_language": 1.0 if any(o.get("insider_language") for o in d.get("observations") or []) else 0.3,
        "experience_differentiation": 1.0 if (d.get("scope_request") or {}).get("experience_level") else 0.0,
        "traceability": traceable,
        "genericness": sum(1 for p in loadout if not p.get("why_this")) / max(1, len(loadout)),
    }, policies)
    state.setdefault("l4_receipts", [])
    skeptic_fail = any(r.get("status") == "REJECT" for r in state.get("l4_receipts") or [])
    checks = {
        "coherent_scope": bool(d.get("scope_request")),
        "experience_context": bool((d.get("scope_request") or {}).get("experience_level")),
        "lived_situation_coverage": len(d.get("lived_situations") or []) >= 2,
        "field_evidence": len(d.get("observations") or []) >= 3,
        "insider_language_grounding": fid["dimensions"]["insider_language"] >= 0.5,
        "non_obvious_item_present": any(set(p.get("collection_roles") or []) & {"INSIDER_GEM", "DISCOVERY"}
                                         for p in loadout),
        "distinct_physical_jobs": len({j for p in loadout for j in p.get("physical_jobs") or []}) >= 2,
        "sellable_products_3_6": 3 <= len(loadout) <= 6,
        "collection_coherence": (d.get("loadout_receipt") or {}).get("set_value", 0) > 0,
        "moment_traceability": traceable >= 0.75,
        "community_skeptic_pass": not skeptic_fail and bool(state.get("l4_receipts")),
    }
    state["insider_fidelity"] = fid
    missing = [k for k, v in checks.items() if not v]
    state["verdict"] = "LOADOUT_READY" if not missing and fid["status"] == "PASS" else "LOADOUT_INCOMPLETE"
    state["loadout_checklist"] = checks
    import candidates as _cand
    _cand.auto_emit(state, policies)
    return f"verdict: {state['verdict']}" + (f" (missing: {missing})" if missing else "") +            f" | insider fidelity {fid['score']} ({fid['status']})"


EXECUTORS = {
    # discovery modes (docs/12-14) — registered from their owning modules,
    # imported at the bottom of this file to avoid import-time cycles
    "python.frontier_gate": frontier_gate,
    "python.voi_gate": voi_gate,
    "python.portfolio_gate": portfolio_gate,
    "python.loadout_ready": loadout_ready,
    "python.apply_evaluations": apply_evaluations,
    "python.signal_gate": signal_gate,
    "python.structural_lookup": structural_lookup,
    "python.triage": triage,
    "python.lens_gate": lens_gate,
    "python.gap_compiler": gap_compiler,
    "python.comments": comments,
    "python.discovery_loop_gate": discovery_loop_gate,
    "python.supplier": supplier,
    "python.scoring": scoring,
}
import corpus_queries as _cq  # noqa: E402
EXECUTORS["python.corpus_query_compiler"] = _cq.corpus_query_compiler
EXECUTORS["python.sourcing_plan_compiler"] = sourcing_plan_compiler
import maintenance as _maint  # noqa: E402  docs/23 registry maintenance lifecycle
for _name in ("collect_candidates", "normalize_candidates", "resolve_candidate_types", "dedupe_candidates", "novelty_check",
              "candidate_evidence", "promotion_satisfaction", "csv_patch", "registry_compile", "regression_tests"):
    EXECUTORS[f"python.{_name}"] = getattr(_maint, _name)

import gap_analysis as _ga  # noqa: E402
import market_discovery as _md  # noqa: E402  (safe: only attribute access at call time)
import product_anchored as _pa  # noqa: E402
EXECUTORS["python.demand_gap_analysis"] = _ga.demand_gap_analysis
EXECUTORS.update(_md.EXECUTORS)
EXECUTORS.update(_pa.EXECUTORS)
import lived_world as _lw  # noqa: E402  LIVED-WORLD-V2 (docs/25)
EXECUTORS.update(_lw.EXECUTORS)
