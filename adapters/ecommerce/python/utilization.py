"""docs/21 §1 — the evidence-utilization receipt.

Every run reports which evidence actually earned its keep: what the corpus
lane returned by kind, what primitives and hypothesis hops cited, what the
web lane contributed, how many independent threads, how the leads spread
across concepts and mechanisms. Pure and deterministic; computed at qualify,
shown by status, triage-run and the report. It is the instrument for the
Polymath-native before/after experiment — no change ships without moving it.
"""
from __future__ import annotations

import collections


def _kind_of_row(rows_by_id: dict, rid: str) -> str:
    r = rows_by_id.get(rid)
    if r:
        return r.get("kind") or "chunk"
    return "observation" if rid.startswith("obs_") or rid.startswith("o") else "unknown"


def compute(state: dict) -> dict:
    d = state.get("data") or {}
    rows = [r for r in d.get("corpus_evidence") or [] if isinstance(r, dict)]
    rows_by_id = {r.get("id"): r for r in rows}
    prim_refs = [rid for v in ((d.get("primitives") or {}).get("evidence_refs") or {}).values() for rid in (v or [])]
    hop_refs = [rid for h in d.get("hypotheses") or [] for v in (h.get("hop_refs") or {}).values() for rid in (v or [])]
    obs = [o for o in d.get("observations") or [] if isinstance(o, dict)]
    gaps = [g for g in d.get("gaps") or [] if isinstance(g, dict)]
    leads = [l for l in d.get("leads") or [] if isinstance(l, dict)]
    concepts = [c for c in d.get("product_concepts") or [] if isinstance(c, dict)]
    threads = {((o.get("source_identity") or {}).get("platform"), (o.get("source_identity") or {}).get("thread_key")) for o in obs}
    from_corpus = [o for o in obs if o.get("corpus_row_id")]
    gaps_with_corpus = {o.get("gap_id") for o in from_corpus if not o.get("contradicts")}
    backend = d.get("corpus_backend") or {}
    packets = [p for p in d.get("corpus_packets") or [] if isinstance(p, dict)]
    legacy_answers = [a for a in d.get("corpus_answers") or [] if isinstance(a, dict)]
    return {
        "corpus": {"backend": backend.get("name") or ("polymath" if str(state.get("corpus", "")).startswith("polymath:") else None),
                   "mode": backend.get("mode") or "generic", "version": backend.get("version"), "plan_source": backend.get("plan_source"),
                   "rows": len(rows), "rows_by_kind": dict(collections.Counter(r.get("kind") or "chunk" for r in rows)),
                   "rows_with_query_provenance": sum(1 for r in rows if r.get("query_ids")),
                   "typed_rows": sum(1 for r in rows if r.get("claim_kind")),
                   "rows_by_claim_kind": dict(collections.Counter(r.get("claim_kind") for r in rows if r.get("claim_kind"))),
                   "field_evidence_rows": sum(1 for r in rows if "field_evidence" in (r.get("tags") or [])),
                   # docs/22 (v2.2.0): the corpus is asked for EVIDENCE. One packet = one evidence-boundary call.
                   "packets": len(packets), "packets_with_evidence": sum(1 for p in packets if p.get("n_evidence")),
                   "packet_rows": sum(1 for r in rows if "evidence_packet" in (r.get("tags") or [])),
                   "rows_by_ca4_grade": dict(collections.Counter(r.get("ca4_grade") for r in rows if r.get("ca4_grade"))),
                   "rows_by_utility_role": dict(collections.Counter(r.get("utility_role") for r in rows if r.get("utility_role"))),
                   "polymath_evidence_calls": len(packets),
                   # a LEGACY (< v2.2.0) answer was one synthesis call; a v2.2.0 run has none and the adapter cannot make one
                   "polymath_chat_calls": len(legacy_answers) + int(backend.get("polymath_chat_calls") or 0),
                   "legacy_answers": len(legacy_answers),
                   "legacy_answers_admitted": len([a for a in legacy_answers if not a.get("abstained")]),
                   "legacy_answer_citations": sum(len(a.get("citations") or []) for a in legacy_answers),
                   "documents": len({r.get("doc_id") for r in rows if r.get("doc_id")})},
        "citations": {"primitives": len(prim_refs), "primitives_by_kind": dict(collections.Counter(_kind_of_row(rows_by_id, r) for r in prim_refs)),
                      "hops": len(hop_refs), "hops_by_kind": dict(collections.Counter(_kind_of_row(rows_by_id, r) for r in hop_refs)),
                      "distinct_corpus_rows_cited": len({r for r in prim_refs + hop_refs if r in rows_by_id}),
                      "typed_rows_cited": len({r for r in prim_refs + hop_refs if (rows_by_id.get(r) or {}).get("claim_kind")}),
                      "cited_by_claim_kind": dict(collections.Counter((rows_by_id.get(r) or {}).get("claim_kind") for r in prim_refs + hop_refs if (rows_by_id.get(r) or {}).get("claim_kind")))},
        "analogies_by_authority": dict(collections.Counter(a.get("authority") for a in d.get("cross_domain_analogies") or [])),
        "observations": {"total": len(obs), "by_source_family": dict(collections.Counter((o.get("source_identity") or {}).get("source_family") for o in obs)),
                         "by_platform": dict(collections.Counter((o.get("source_identity") or {}).get("platform") for o in obs)),
                         "by_freshness": dict(collections.Counter((o.get("freshness") or {}).get("class") for o in obs)),
                         "distinct_threads": len(threads), "with_query_provenance": sum(1 for o in obs if o.get("query_id") or o.get("query_used")),
                         "from_corpus_rows": len(from_corpus)},
        "gaps": {"total": len(gaps), "by_status": dict(collections.Counter(g.get("status") for g in gaps)),
                 "with_corpus_support": len([g for g in gaps if g.get("id") in gaps_with_corpus])},
        "rounds": dict(state.get("rounds") or {}),
        "leads": {"total": len(leads), "by_concept": dict(collections.Counter(l.get("concept") or l.get("concept_id") for l in leads)),
                  "concepts_with_leads": len({l.get("concept_id") for l in leads if l.get("concept_id")}), "concepts": len(concepts),
                  "mechanisms_with_leads": len({l.get("mechanism_id") for l in leads}), "by_channel": dict(collections.Counter(l.get("channel") or "alibaba" for l in leads)), "mechanisms_supported": sum(1 for m in d.get("mechanisms") or [] if m.get("status") == "SUPPORTED")},
        "registry_candidates_by_kind": dict(collections.Counter(c.get("kind") for c in d.get("registry_candidates") or [])),
        # LIVED-WORLD-V2 (docs/25): the receipt that proves semantic behaviour, not execution
        "lived_world": __import__("lived_world").summary(state),
        "interpretation": {"latent_structures": len(d.get("latent_structures") or []),
                           "by_kind": dict(collections.Counter(x.get("kind") for x in d.get("latent_structures") or [] if isinstance(x, dict))),
                           "corpus_observations": dict(collections.Counter(x.get("kind") for x in d.get("corpus_observations") or [] if isinstance(x, dict))),
                           "rows_classified": len(d.get("row_relevance") or {}),
                           "relevance": dict(collections.Counter((d.get("row_relevance") or {}).values()))},
        "corpus_contribution": __import__("provenance").corpus_contribution(state),
        "provenance": {"verdicts": dict(collections.Counter(r.get("verdict") for r in d.get("provenance") or [])),
                       "field_originated_concepts": sum(1 for r in d.get("provenance") or [] if r.get("field_originated")),
                       "field_origins": dict(collections.Counter((r.get("field_origin") or {}).get("origin") or "UNKNOWN" for r in d.get("provenance") or [])),
                       "corpus_named_concepts": sum(1 for r in d.get("provenance") or [] if r.get("corpus_named")),
                       "corpus_presence_audited": sum(1 for r in d.get("provenance") or [] if r.get("corpus_presence")),
                       "excluded_leads": len(d.get("excluded_leads") or []),
                       "concepts_outside_seed": sum(1 for r in d.get("provenance") or [] if r.get("seed_population_only") is False)},
    }


def to_markdown(u: dict) -> str:
    c, ci, o, gp, ld = u["corpus"], u["citations"], u["observations"], u["gaps"], u["leads"]
    lines = ["| measure | value |", "|---|---|",
             f"| corpus backend / mode | {c['backend']} / {c['mode']}" + (f" ({c['version']})" if c.get("version") else "") + " |",
             f"| corpus rows retrieved (by kind) | {c['rows']} {c['rows_by_kind']} over {c['documents']} docs |",
             f"| corpus evidence packets / with evidence / packet rows | {c.get('packets', 0)} / {c.get('packets_with_evidence', 0)} / {c.get('packet_rows', 0)} |",
             f"| packet rows by CA4 grade / utility role | {c.get('rows_by_ca4_grade', {})} / {c.get('rows_by_utility_role', {})} |",
             f"| Polymath calls: evidence / synthesis | {c.get('polymath_evidence_calls', 0)} / {c.get('polymath_chat_calls', 0)} |",
             *([f"| LEGACY synthesis answers asked / admitted / citations (not evidence) | {c.get('legacy_answers', 0)} / {c.get('legacy_answers_admitted', 0)} / {c.get('legacy_answer_citations', 0)} |"] if c.get("legacy_answers") else []),
             f"| typed rows / field-evidence rows | {c.get('typed_rows', 0)} {c.get('rows_by_claim_kind', {})} / {c.get('field_evidence_rows', 0)} |",
             f"| typed rows cited | {ci.get('typed_rows_cited', 0)} {ci.get('cited_by_claim_kind', {})} |",
             f"| corpus rows cited by primitives / hops | {ci['primitives']} {ci['primitives_by_kind']} / {ci['hops']} {ci['hops_by_kind']} |",
             f"| analogies by authority | {u['analogies_by_authority']} |",
             f"| observations (threads, provenance, from corpus) | {o['total']} ({o['distinct_threads']} threads, {o['with_query_provenance']} with query, {o['from_corpus_rows']} from corpus rows) |",
             f"| observation freshness | {o['by_freshness']} |",
             f"| gaps (status, with corpus support) | {gp['total']} {gp['by_status']}, corpus-supported {gp['with_corpus_support']} |",
             f"| research rounds | {u['rounds'].get('research')} |",
             f"| leads across concepts / mechanisms / channels | {ld['total']} leads, {ld['concepts_with_leads']}/{ld['concepts']} concepts, {ld['mechanisms_with_leads']}/{ld['mechanisms_supported']} mechanisms, {ld.get('by_channel', {})} |",
             f"| observations by platform | {o.get('by_platform', {})} |",
             f"| registry candidates | {u['registry_candidates_by_kind']} |"]
    lw, cc, pv = u.get("lived_world") or {}, u.get("corpus_contribution") or {}, u.get("provenance") or {}
    if lw:
        lines += [f"| population leads (lane / status / seed) | {lw.get('leads')} {lw.get('leads_by_lane')} {lw.get('leads_by_status')} seed={lw.get('seed_population_leads')} |",
                  f"| field records / cards / clusters | {lw.get('field_records')} {lw.get('records_by_origin')} / {lw.get('participant_cards')} / {lw.get('clusters_by_authority')} (outside seed {lw.get('clusters_outside_seed')}) |",
                  f"| lived situations (authority, unknowns kept) | {lw.get('situations_by_authority')} / {lw.get('unknowns_preserved')} |",
                  f"| population rounds / loop | {lw.get('rounds')} / {(lw.get('loop') or {}).get('reason')} |"]
    it = u.get("interpretation") or {}
    if it:
        lines += [f"| interpretation: latent structures (by kind) / corpus observations / rows classified | {it.get('latent_structures')} {it.get('by_kind')} / {it.get('corpus_observations')} / {it.get('rows_classified')} {it.get('relevance')} |"]
    if cc:
        lines += [f"| corpus contribution: cited rows / docs cited of retrieved | {cc.get('rows_cited')}/{cc.get('rows_retrieved')} / {cc.get('documents_cited')}/{cc.get('documents_retrieved')} ({cc.get('cited_share_of_shelf')}) |",
                  f"| corpus example rows retrieved / cited; mechanism-only contributions | {cc.get('example_rows_retrieved')} / {cc.get('example_rows_cited')}; {cc.get('mechanism_only_contributions')} |"]
    if pv:
        lines += [f"| provenance verdicts / field-originated / excluded echo leads | {pv.get('verdicts')} / {pv.get('field_originated_concepts')} / {pv.get('excluded_leads')} |",
                  f"| field origins / corpus-named / presence-audited | {pv.get('field_origins')} / {pv.get('corpus_named_concepts')} / {pv.get('corpus_presence_audited')} |"]
    return "\n".join(lines)
