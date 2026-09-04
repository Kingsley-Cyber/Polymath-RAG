"""docs/25 §7 — provenance enforcement and cited-contribution receipts.

Lineage decides what may count; no category blacklist ever does. A product
that overlaps a corpus example stays LEGAL when its hypothesis is
independently grounded in enough external participants, threads and
communities. A product whose lineage is only `corpus example → same noun →
same-noun search` is CORPUS_ECHO_UNGROUNDED. Corpus contribution is measured
by CITED rows, never by documents returned (the shelf comes back whole every
time — measured 2026-09-03: 18 of 19 documents shared across three unrelated
lives).
"""
from __future__ import annotations

import collections
import re

import verifiers as _ver

_STOP = {"that", "this", "with", "from", "they", "their", "what", "when", "have", "which", "into", "than", "then",
         "there", "these", "those", "would", "could", "about", "where", "does", "being", "more", "most", "only",
         "people", "class", "kit", "lite", "pro", "mini", "pack", "set"}
_GENERIC_ENTITIES = {"people", "market", "product", "products", "brand", "brands", "customer", "customers", "video",
                     "business", "company", "money", "time", "world", "life", "thing", "things", "everyone", "everything"}
EXAMPLE_TAG = "CORPUS_EXAMPLE"


def _stem(t: str) -> str:
    """Light, deterministic plural folding so 'supplements' meets 'supplement'
    and 'caddies' meets 'caddy' — provenance compares nouns, not spellings."""
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith(("sses", "shes", "ches", "xes", "zes")):
        return t[:-2]
    if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _toks(text) -> set:
    return {_stem(t) for t in re.findall(r"[a-z][a-z\-]{3,}", str(text or "").lower()) if t not in _STOP}


# ------------------------------------------------------- example tagging --
def tag_corpus_examples(rows: list[dict], example_terms: list | None = None) -> int:
    """Deterministic: a row is a CORPUS_EXAMPLE when its text names a
    document-level major entity that appears capitalized in the text (a
    proper noun: a brand, a product, a person's company), or a term the
    understand node listed in `example_terms`. Tags the row; never drops it —
    an example is still knowledge, it just cannot seed a qualified product
    on its own."""
    ents_by_doc: dict[str, set] = {}
    for r in rows:
        ds = r.get("document_summary") if isinstance(r, dict) else None
        if ds and r.get("doc_id"):
            for e in ds.get("major_entities") or []:
                e = str(e).strip()
                if len(e) >= 4 and e.lower() not in _GENERIC_ENTITIES:
                    ents_by_doc.setdefault(r["doc_id"], set()).add(e)
    given = {str(t).strip() for t in example_terms or [] if str(t).strip()}
    n = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        text = f"{r.get('text') or ''} {r.get('summary') or ''}"
        found = set()
        for e in ents_by_doc.get(r.get("doc_id"), set()) | given:
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(e) + r"(?![A-Za-z0-9])", text) and (e[:1].isupper() or e in given):
                found.add(e)
        if found:
            tags = list(r.get("tags") or [])
            if EXAMPLE_TAG not in tags:
                tags.append(EXAMPLE_TAG)
            r["tags"] = tags
            r["example_terms"] = sorted(found)
            r["corpus_observation"] = {"observed_entities": sorted(found), "semantic_role": "EXAMPLE",
                                       "evidentiary_authority": "NONE_FOR_CURRENT_DEMAND"}   # docs/26 §3: recorded, never stripped
            n += 1
    return n


def observation_terms(state: dict) -> set:
    """docs/26 §3: products / examples / populations the corpus NAMED, as θ
    recorded them (corpus_observations) — recorded, never stripped."""
    out = set()
    for o in state["data"].get("corpus_observations") or []:
        if isinstance(o, dict) and o.get("kind") in ("OBSERVED_PRODUCT", "EXAMPLE"):
            out |= _toks(o.get("name"))
    return out


def corpus_named(concept: dict, state: dict) -> dict:
    """Canary 1 (docs/26 §6): is this concept explicitly NAMED by a source
    passage? True when a bigram of its name occurs in corpus text, or it shares
    a brand token / two tokens with a recorded corpus observation or example."""
    name = str(concept.get("name") or "").lower()
    words = [w for w in re.findall(r"[a-z][a-z\-]+", name) if w not in _STOP]
    bigrams = {f"{a} {b}" for a, b in zip(words, words[1:])}
    text = " ".join(str(r.get("text") or r.get("summary") or "").lower() for r in state["data"].get("corpus_evidence") or []
                    if isinstance(r, dict) and "field_evidence" not in (r.get("tags") or []))
    phrase_hits = sorted(b for b in bigrams if b in text)
    ctoks = concept_tokens(concept)
    obs = ctoks & (observation_terms(state) | corpus_example_terms(state))
    named = bool(phrase_hits) or len(obs) >= 2 or bool(ctoks & corpus_example_terms(state))
    return {"named": named, "phrase_hits": phrase_hits, "observation_overlap": sorted(obs)}


def corpus_example_terms(state: dict) -> set:
    d = state["data"]
    terms = set()
    for r in d.get("corpus_evidence") or []:
        if isinstance(r, dict):
            for t in r.get("example_terms") or []:
                terms |= _toks(t) | {str(t).lower()}
    for t in d.get("example_terms") or []:
        terms |= _toks(t) | {str(t).lower()}
    return terms


_GENERIC_ROW_TOKENS = {"women", "people", "market", "markets", "products", "product", "specific", "proven", "segment", "brands", "brand",
                       "business", "customers", "customer", "company", "selling", "sells", "money", "example", "things", "something"}


def corpus_example_row_tokens(state: dict) -> set:
    """Content tokens of CORPUS_EXAMPLE rows: the category the named brand
    illustrates ('organ supplements', 'insoles'). A concept that shares them
    with no independent grounding is echoing the teacher's example."""
    out = set()
    for r in state["data"].get("corpus_evidence") or []:
        if isinstance(r, dict) and EXAMPLE_TAG in (r.get("tags") or []):
            out |= {t for t in _toks(f"{r.get('text') or ''} {r.get('summary') or ''}") if t not in _GENERIC_ROW_TOKENS}
    return out


def example_overlap(concept: dict, state: dict) -> list:
    ctoks = concept_tokens(concept)
    brand = ctoks & (corpus_example_terms(state) | observation_terms(state))
    rows = ctoks & corpus_example_row_tokens(state)
    strong = {t for t in rows if len(t) >= 6}
    hits = brand | strong | (rows if len(rows) >= 2 else set())
    return sorted(hits)


def corpus_text_tokens(state: dict) -> set:
    out = set()
    for r in state["data"].get("corpus_evidence") or []:
        if isinstance(r, dict) and "field_evidence" not in (r.get("tags") or []):
            out |= _toks(f"{r.get('text') or ''} {r.get('summary') or ''}")
    return out


# --------------------------------------------------------------- lineage --
def _hypothesis_for(concept: dict, state: dict) -> dict | None:
    d = state["data"]
    mech = next((m for m in d.get("mechanisms") or [] if m.get("id") == concept.get("mechanism_id")), None)
    hid = (mech or {}).get("hypothesis_id")
    return next((h for h in d.get("hypotheses") or [] if h.get("id") == hid), None)


def concept_tokens(concept: dict) -> set:
    return _toks(f"{concept.get('name') or ''} {concept.get('form_factor') or ''}")


def lineage(concept: dict, state: dict, policies: dict) -> dict:
    d = state["data"]
    pp = policies.get("provenance") or {}
    min_voices = int(pp.get("min_independent_voices", 3))
    min_comm = int(pp.get("min_communities", 2))
    echo = pp.get("echo_verdict", "CORPUS_ECHO_UNGROUNDED")
    obs = {o["id"]: o for o in d.get("observations") or [] if isinstance(o, dict) and o.get("id")}
    recs = {r["id"]: r for r in d.get("field_records") or [] if isinstance(r, dict) and r.get("id")}
    clusters = {c["id"]: c for c in d.get("lived_clusters") or [] if isinstance(c, dict)}
    hyp = _hypothesis_for(concept, state) or {}
    refs = list(concept.get("evidence_refs") or [])
    cited = [recs[x] for x in refs if x in recs] + [obs[x] for x in refs if x in obs]
    # the hypothesis' own lived anchors count as grounding lineage too
    for cid in hyp.get("lived_anchor_ids") or []:
        for rid in (clusters.get(cid) or {}).get("record_ids") or []:
            if rid in recs and recs[rid] not in cited:
                cited.append(recs[rid])
    voices = _ver.independence_groups(cited)["independent_groups"] if cited else 0
    communities = {re.sub(r"^r/", "", str(x.get("community") or "").lower()) for x in cited if x.get("community")}
    anchors = [cid for cid in hyp.get("lived_anchor_ids") or [] if (clusters.get(cid) or {}).get("authority") == "ANCHOR"]
    ctoks = concept_tokens(concept)
    overlap = example_overlap(concept, state)
    field_refs = [x for x in refs if x in recs]
    gap_refs = [x for x in refs if x in obs]
    grounded = voices >= min_voices and len(communities) >= min_comm
    if grounded:
        verdict = "GROUNDED"
    elif overlap and not anchors and not field_refs:
        verdict = echo
    elif overlap:
        verdict = "ECHO_WEAKLY_GROUNDED"
    else:
        verdict = "UNGROUNDED"
    # field-originated: the noun lives in the records, not in the corpus
    corpus_toks = corpus_text_tokens(state)
    named = set()
    for r in list(recs.values()) + list(obs.values()):
        for p in r.get("products_named") or []:
            named |= _toks(p)
        named |= _toks(r.get("workaround"))
    content = {t for t in ctoks if len(t) >= 4}
    # docs/26 §6 canary 6: field-originated = positive FIELD lineage (the noun lives in what
    # people named or rigged) AND the corpus never NAMED it (corpus_named) — not "zero token
    # overlap with the whole corpus", which no ordinary noun survives at 100 books
    field_lineage = bool(content & named)
    field_originated = field_lineage and not corpus_named(concept, state)["named"]
    named = corpus_named(concept, state)
    return {"concept_id": concept.get("id"), "concept": concept.get("name"), "hypothesis_id": hyp.get("id"),
            "verdict": verdict, "independent_voices": voices, "communities": sorted(communities),
            "corpus_named": named["named"], "corpus_named_by": named["phrase_hits"] or named["observation_overlap"],
            "field_lineage": field_lineage,
            "hop_cites_corpus": bool([rid for v in (hyp.get("hop_refs") or {}).values() for rid in v or [] if str(rid).startswith("polymath:") or rid in {r.get("id") for r in d.get("corpus_evidence") or [] if isinstance(r, dict)}]),
            "field_record_refs": len(field_refs), "gap_observation_refs": len(gap_refs),
            "lived_anchor_ids": anchors, "example_overlap": overlap, "field_originated": field_originated,
            "seed_population_only": bool(cited) and all(
                (clusters.get(next((c for c in clusters if x.get("id") in (clusters[c].get("record_ids") or [])), "")) or {}).get("seed_population", False)
                for x in cited if x.get("id") in recs) if field_refs else None,
            "thresholds": {"min_independent_voices": min_voices, "min_communities": min_comm}}


def enforce(state: dict, policies: dict) -> dict:
    """Annotate every concept, drop leads whose concept is CORPUS_ECHO_UNGROUNDED
    (kept in excluded_leads with the reason), return the summary."""
    d = state["data"]
    echo = (policies.get("provenance") or {}).get("echo_verdict", "CORPUS_ECHO_UNGROUNDED")
    rows = []
    for c in d.get("product_concepts") or []:
        if not isinstance(c, dict):
            continue
        ln = lineage(c, state, policies)
        c["provenance"] = ln["verdict"]
        c["field_originated"] = ln["field_originated"]
        rows.append(ln)
    d["provenance"] = rows
    verdict_by_concept = {r["concept_id"]: r["verdict"] for r in rows}
    keep, excluded = [], list(d.get("excluded_leads") or [])
    for lead in d.get("leads") or []:
        v = verdict_by_concept.get(lead.get("concept_id"))
        if v == echo:
            excluded.append(dict(lead, excluded_reason=f"{echo}: lineage is corpus example → same noun → same-noun search only"))
        else:
            keep.append(dict(lead, provenance=v))
    d["leads"] = keep
    d["excluded_leads"] = excluded
    return {"verdicts": dict(collections.Counter(r["verdict"] for r in rows)), "excluded_leads": len(excluded),
            "field_originated_concepts": sum(1 for r in rows if r["field_originated"])}


# ------------------------------------------------- corpus contribution --
def corpus_contribution(state: dict) -> dict:
    d = state["data"]
    rows = {r["id"]: r for r in d.get("corpus_evidence") or [] if isinstance(r, dict) and r.get("id")}
    cited: dict[str, set] = collections.defaultdict(set)      # row id -> who cited it
    for k, v in ((d.get("primitives") or {}).get("evidence_refs") or {}).items():
        for rid in v or []:
            cited[rid].add(f"primitives.{k}")
    for h in d.get("hypotheses") or []:
        for i, v in (h.get("hop_refs") or {}).items():
            for rid in v or []:
                cited[rid].add(f"hop:{h.get('id')}#{i}")
    for a in d.get("corpus_answers") or []:
        if isinstance(a, dict) and not a.get("abstained"):
            for rid in a.get("citations") or []:
                cited[rid].add(f"answer:{a.get('query_id')}")
    for s in d.get("lived_situations") or []:
        for fr in (s.get("frictions") or []) if isinstance(s, dict) else []:
            for rid in (fr.get("refs") or []) if isinstance(fr, dict) else []:
                cited[rid].add(f"situation:{s.get('id')}")
    for m in d.get("mechanisms") or []:
        for rid in m.get("corpus_refs") or []:
            cited[rid].add(f"mechanism:{m.get('id')}")
    cited_rows = {rid: who for rid, who in cited.items() if rid in rows}
    by_doc_ret = collections.Counter(rows[r].get("doc_id") or rows[r].get("title") or "?" for r in rows)
    by_doc_cit = collections.Counter(rows[r].get("doc_id") or rows[r].get("title") or "?" for r in cited_rows)
    concept_toks = set()
    for c in d.get("product_concepts") or []:
        concept_toks |= concept_tokens(c)
    mech_only = [rid for rid in cited_rows
                 if EXAMPLE_TAG not in (rows[rid].get("tags") or []) and not (_toks(rows[rid].get("summary")) & concept_toks)]
    rel = collections.Counter(r.get("relevance") for r in rows.values() if r.get("relevance"))
    return {"relevance_receipts": dict(rel), "rows_classified_irrelevant": rel.get("IRRELEVANT", 0),
            "rows_retrieved": len(rows), "rows_cited": len(cited_rows),
            "documents_retrieved": len(by_doc_ret), "documents_cited": len(by_doc_cit),
            "cited_share_of_shelf": round(len(by_doc_cit) / max(1, len(by_doc_ret)), 3),
            "cited_by_document": dict(by_doc_cit.most_common()),
            "example_rows_retrieved": sum(1 for r in rows.values() if EXAMPLE_TAG in (r.get("tags") or [])),
            "example_rows_cited": sum(1 for rid in cited_rows if EXAMPLE_TAG in (rows[rid].get("tags") or [])),
            "mechanism_only_contributions": len(mech_only),
            "question_level_rows": sum(1 for r in rows.values() if r.get("question_id"))}
