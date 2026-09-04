"""LIVED-WORLD-V2 (docs/25) — population discovery BEFORE product ideation.

The field co-generates the opportunity space; it does not merely validate
nouns the corpus happened to mention. Deterministic φ owns every step here:

  nominate   corpus / registry / signal / prior field records propose
             PopulationLead + CommunityLead objects (authority LEAD, never demand)
  queue      a VOI-ranked work queue hands the agent ONE batch of leads per
             round (sequential controller, no fan-out)
  cards      admitted field_records become ParticipantEvidenceCards (per real
             author) and LivedEvidenceClusters (per community × friction
             family) whose authority is THIN or ANCHOR by independent records
  gate       rounds continue until enough ANCHOR clusters exist, bounded by
             max_rounds, stagnation and a wall clock
  validate   lived situations may claim FIELD_ANCHORED only on ANCHOR clusters;
             reconstructions keep their unknowns; nothing invents biography
  questions  the corpus is asked at friction / mechanism / question level,
             never per person (docs/25 §6)

No LLM calls, ever. Same input state + policies → same output.
"""
from __future__ import annotations

import collections
import datetime as _dt
import re

import verifiers as _ver
from models import now, stable_id

_STOP = {"that", "this", "with", "from", "they", "their", "what", "when", "have", "which", "into", "than", "then",
         "there", "these", "those", "would", "could", "about", "where", "does", "being", "more", "most", "only",
         "people", "users", "community", "communities", "members", "someone", "anyone", "every", "other", "also"}
_CORE_ROLES = ("FRICTION_EVIDENCE", "WORKAROUND_EVIDENCE", "BEHAVIOR_SUPPORT", "PURCHASE_INTENT")


def _toks(text) -> set:
    return {t for t in re.findall(r"[a-z][a-z\-]{3,}", str(text or "").lower()) if t not in _STOP}


def _norm_community(name) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"^(?:r/|/r/|https?://(?:www\.)?reddit\.com/r/)", "", s)
    return s.strip("/ ") or "unknown"


def _lw(policies: dict) -> dict:
    return policies.get("lived_world") or {}


def all_leads(state: dict) -> list[dict]:
    d = state["data"]
    return [l for l in (d.get("population_leads") or []) + (d.get("community_leads") or []) if isinstance(l, dict)]


def lead_by_id(state: dict) -> dict:
    return {l["id"]: l for l in all_leads(state) if l.get("id")}


# ------------------------------------------------------------ thresholds --
def anchor_threshold(state: dict, policies: dict) -> dict:
    """Policy floor; a run's settings may only TIGHTEN it (docs/16 law)."""
    base = dict((_lw(policies).get("anchor_threshold") or {}))
    base.setdefault("min_records", 5); base.setdefault("min_threads", 2); base.setdefault("min_independent_voices", 3)
    try:
        import settings as _settings
        for key in ("min_records", "min_threads", "min_independent_voices"):
            val = _settings.effective(state, f"lived_world.anchor_{key}", None)
            if val is not None:
                base[key] = max(int(base[key]), int(val))
    except Exception:  # noqa: BLE001 — settings are optional
        pass
    return base


# ------------------------------------------------------------- nomination --
def _seed_terms(state: dict) -> set:
    """Tokens of the population the SIGNAL itself named: its communities line
    plus the seed passage. Leads that restate them are `seed_population`."""
    d = state["data"]
    sig = d.get("signal") if isinstance(d.get("signal"), str) else str(d.get("signal") or "")
    terms = _toks(sig[:600])
    for c in d.get("communities") or []:
        terms |= _toks(_norm_community(c)) | {_norm_community(c)}
    return {t for t in terms if len(t) >= 5}


def _is_seed(name: str, extra: list, seed_terms: set) -> bool:
    toks = _toks(name) | {t for x in extra or [] for t in _toks(x)}
    return bool({t for t in toks if len(t) >= 5} & seed_terms)


def _lead(kind: str, name: str, lane: str, nominated_by: list, seed_terms: set, **extra) -> dict:
    lead = {"id": stable_id("lead", kind, lane, name.strip().lower()), "kind": kind, "name": name.strip(),
            "source_lane": lane, "nominated_by": sorted({str(x) for x in nominated_by if x})[:10] or [lane.lower()],
            "authority": "LEAD", "status": "NOMINATED", "rounds_visited": 0, "record_ids": []}
    for k, v in extra.items():
        if v not in (None, "", [], {}):
            lead[k] = v
    lead["seed_population"] = _is_seed(name, (lead.get("activities") or []) + (lead.get("contexts") or []), seed_terms)
    return lead


def _registry_nominations(state: dict, policies: dict, seed_terms: set) -> list[dict]:
    """Registry SITUATIONS whose predicates / friction families overlap the
    primitives become PopulationLeads (participant × activity × context).
    The seed table stays a reusable activity/context/friction prior — it is
    never a people database (docs/25 §1)."""
    prim = state["data"].get("primitives") or {}
    try:
        import registry as _reg
        snap = _reg.load_snapshot()
    except Exception:  # noqa: BLE001
        snap = None
    if not snap:
        return []
    preds = [str(x).lower() for x in prim.get("shared_predicates") or []]
    fams = [str(x) for x in (prim.get("frictions") or []) if x in (snap.get("friction_families") or [])]
    idx = []
    for pred in preds:
        for fam in fams or [None]:
            idx += (snap["index_by_predicate_friction"].get(f"{pred}|{fam}", []) if fam
                    else snap["index_by_predicate"].get(pred, []))
    for fam in fams:                                   # friction-only matches when no predicate hit
        idx += [i for i, sd in enumerate(snap["seeds"]) if sd.get("friction_family") == fam]
    out, seen = [], set()
    cap = int(_lw(policies).get("nominate_max_registry", 6))
    for i in idx:
        sd = snap["seeds"][i]
        key = (sd.get("participant"), sd.get("activity"))
        if key in seen:
            continue
        seen.add(key)
        name = f"{sd.get('participant') or 'participant'} — {sd.get('activity') or sd.get('domain')}"
        out.append(_lead("POPULATION", name, "REGISTRY", [sd.get("seed_id")], seed_terms,
                         activities=[sd.get("activity")], contexts=[c for c in (sd.get("context"),) if c],
                         expected_frictions=[f for f in (sd.get("friction_family"),) if f],
                         why=f"registry situation {sd.get('seed_id')}: {sd.get('friction_hypothesis') or ''}"[:200]))
        if len(out) >= cap:
            break
    return out


def _corpus_nominations(state: dict, seed_terms: set) -> list[dict]:
    """θ named populations while extracting primitives (optional
    `primitives.population_leads`). Each becomes a lead citing the rows it
    came from — a book may say 'shift workers'; that is a place to look."""
    prim = state["data"].get("primitives") or {}
    out = []
    for item in prim.get("population_leads") or []:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict) or not item.get("name"):
            continue
        kind = "COMMUNITY" if item.get("community_key") else "POPULATION"
        out.append(_lead(kind, str(item["name"]), "CORPUS", item.get("evidence_refs") or ["primitives"], seed_terms,
                         why=item.get("why"), activities=item.get("activities") or [], contexts=item.get("contexts") or [],
                         expected_frictions=item.get("frictions") or item.get("expected_frictions") or [],
                         community_key=item.get("community_key"), platform=item.get("platform")))
    return out


def _signal_nominations(state: dict, seed_terms: set) -> list[dict]:
    out = []
    for c in state["data"].get("communities") or []:
        key = _norm_community(c)
        out.append(_lead("COMMUNITY", str(c), "SIGNAL", ["signal"], seed_terms, community_key=key, platform="reddit"))
    return out


def _field_record_nominations(state: dict, seed_terms: set) -> list[dict]:
    """Prior field evidence in the corpus (rows tagged field_evidence) names
    the communities earlier runs already heard from — leads, not demand."""
    by_comm: dict[str, dict] = {}
    for r in state["data"].get("corpus_evidence") or []:
        if "field_evidence" not in (r.get("tags") or []):
            continue
        fm = ((r.get("document") or {}).get("frontmatter")) or {}
        comm = fm.get("community")
        if not comm:
            continue
        slot = by_comm.setdefault(_norm_community(comm), {"platform": fm.get("platform") or "reddit", "rows": [], "name": str(comm)})
        slot["rows"].append(r.get("id"))
    out = []
    for key, slot in sorted(by_comm.items()):
        out.append(_lead("COMMUNITY", slot["name"], "FIELD_RECORDS", slot["rows"][:5], seed_terms,
                         community_key=key, platform=slot["platform"], why=f"{len(slot['rows'])} prior field rows"))
    return out


_LATENT_SEARCHABLE = {"FRICTION", "WORKAROUND", "ADAPTATION", "TRANSFERABLE_INVARIANT", "OBJECT_INTERACTION", "ACCESS_PROBLEM",
                      "COORDINATION_PROBLEM", "REPETITION", "COMFORT_PROBLEM", "ATTENTION_PROBLEM", "STATUS_PROBLEM", "TRANSITION",
                      "FAILURE_MODE", "ROUTINE", "CONSTRAINT", "TRADEOFF", "DESIRE"}


def _latent_nominations(state: dict, policies: dict, seed_terms: set) -> list[dict]:
    """docs/26 §4 — the reverse direction: LATENT PROBLEM → population search.
    A structure read out of ANY passage (a novel, a manual) becomes a lead
    whose population is unknown; its queries carry the friction language so
    the scout can discover WHO repeatedly experiences it. Named populations
    the structure proposes become ordinary NAMED leads citing the same rows."""
    out = []
    cap = int(_lw(policies).get("nominate_max_latent", 6))
    structures = [x for x in state["data"].get("latent_structures") or [] if isinstance(x, dict)]
    for st in structures:
        refs = st.get("evidence_refs") or ["primitives"]
        for pop in st.get("possible_populations") or []:
            out.append(_lead("POPULATION", str(pop), "CORPUS", refs, seed_terms, search_mode="NAMED",
                             latent_structure_id=st.get("id"), why=f"named by structure {st.get('id')}: {str(st.get('text'))[:80]}",
                             expected_frictions=[str(st.get("text"))[:60]] if st.get("kind") in ("FRICTION", "WORKAROUND", "ADAPTATION") else []))
        if st.get("kind") in _LATENT_SEARCHABLE and len([l for l in out if l.get("search_mode") == "LATENT"]) < cap:
            name = f"who repeatedly experiences: {str(st.get('text'))[:70]}"
            out.append(_lead("POPULATION", name, "LATENT", refs, seed_terms, search_mode="LATENT", latent_structure_id=st.get("id"),
                             expected_frictions=[str(st.get("text"))[:80]], why=st.get("applicability_outside_source") or "population unknown — search by the friction language"))
    return out


def _compile_lead_queries(lead: dict, state: dict, policies: dict) -> list[dict]:
    import executors as _ex
    if lead.get("search_mode") == "LATENT":
        # the population is unknown: search by the structure's own language, never by a group name
        parts = list(lead.get("expected_frictions") or [])[:2] or [lead["name"].split(":", 1)[-1]]
    else:
        parts = [lead["name"]] + list(lead.get("expected_frictions") or [])[:2] + list(lead.get("activities") or [])[:1]
    question = " ".join(str(p).replace("_", " ").replace("—", " ") for p in parts if p)
    qs = _ex.channel_queries(lead["id"], question, state, policies, id_prefix="pq")
    for q in qs:
        q["lead_id"] = lead["id"]
        if lead.get("community_key") and q.get("channel") == "reddit":
            q["subreddit_hints"] = [lead["community_key"]]
    return qs


def nominate(state: dict, policies: dict) -> str:
    """Executor python.population_nominate."""
    d = state["data"]
    seed_terms = _seed_terms(state)
    existing = lead_by_id(state)
    fresh = (_signal_nominations(state, seed_terms) + _corpus_nominations(state, seed_terms)
             + _latent_nominations(state, policies, seed_terms)
             + _registry_nominations(state, policies, seed_terms) + _field_record_nominations(state, seed_terms))
    seen_names = {l["name"].strip().lower() for l in existing.values()}
    added = collections.Counter()
    for lead in fresh:
        key = lead["name"].strip().lower()
        if lead["id"] in existing or key in seen_names:
            continue
        seen_names.add(key)
        lead["channel_queries"] = _compile_lead_queries(lead, state, policies)
        target = "community_leads" if lead["kind"] == "COMMUNITY" else "population_leads"
        d.setdefault(target, []).append(lead)
        existing[lead["id"]] = lead
        added[lead["source_lane"]] += 1
    rank_leads(state, policies)
    total = len(all_leads(state))
    seeded = sum(1 for l in all_leads(state) if l.get("seed_population"))
    return (f"nominated {sum(added.values())} leads {dict(added)} ({total} total, {seeded} restate the seed population)"
            " — leads are places to look, never demand")


# ------------------------------------------------------------- VOI queue --
def _cluster_index(state: dict) -> dict:
    by_lead: dict[str, list] = {}
    for c in state["data"].get("lived_clusters") or []:
        if c.get("lead_id"):
            by_lead.setdefault(c["lead_id"], []).append(c)
    return by_lead


def _prim_vocab(state: dict) -> set:
    prim = state["data"].get("primitives") or {}
    vocab = set()
    for key in ("frictions", "physical_jobs", "behaviors", "shared_predicates", "drivers", "constraints"):
        for item in prim.get(key) or []:
            vocab |= _toks(item)
    return vocab


def rank_leads(state: dict, policies: dict) -> list[str]:
    """VOI = source yield × missing-information importance × decision impact
    / expected cost, discounted for leads that restate the seed population.
    Writes `voi` on every lead; returns ids best-first."""
    lw = _lw(policies)
    yields = (lw.get("value_of_information") or {}).get("default_source_yield") or {}
    vocab = _prim_vocab(state)
    clusters = _cluster_index(state)
    thr = anchor_threshold(state, policies)
    ranked = []
    for lead in all_leads(state):
        status = lead.get("status")
        anchored = any(c.get("authority") == "ANCHOR" for c in clusters.get(lead["id"], []))
        if status == "DROPPED" or anchored:
            missing = 0.1
        elif status == "NOMINATED":
            missing = 1.0
        elif status == "EXHAUSTED":
            missing = 0.2
        else:                                   # instantiated but still THIN
            recs = len(lead.get("record_ids") or [])
            missing = 0.4 + 0.5 * max(0.0, 1 - recs / max(1, thr["min_records"]))
        toks = _toks(lead.get("name")) | {t for x in (lead.get("expected_frictions") or []) + (lead.get("activities") or []) for t in _toks(x)}
        impact = 0.5 + 0.5 * min(1.0, len(toks & vocab) / 3.0)
        cost = max(0.5, len(lead.get("channel_queries") or []) / 4.0)
        voi = yields.get(lead.get("source_lane"), 0.5) * missing * impact / cost
        if lead.get("seed_population"):
            voi *= float(lw.get("seed_population_discount", 0.5))
        lead["voi"] = round(voi, 4)
        ranked.append((voi, lead["id"]))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [i for _, i in ranked]


def eligible_leads(state: dict, policies: dict) -> list[str]:
    clusters = _cluster_index(state)
    out = []
    for lid in rank_leads(state, policies):
        lead = lead_by_id(state)[lid]
        anchored = any(c.get("authority") == "ANCHOR" for c in clusters.get(lid, []))
        if lead.get("status") == "NOMINATED" or (lead.get("status") == "INSTANTIATED" and not anchored
                                                 and int(lead.get("rounds_visited") or 0) < 2):
            out.append(lid)
    return out


def queue(state: dict, policies: dict) -> str:
    """Executor python.population_queue — hands the agent ONE batch."""
    lw = _lw(policies)
    prev = state.get("population_queue") or {}
    batch = eligible_leads(state, policies)[: int(lw.get("batch_size", 4))]
    by_id = lead_by_id(state)
    for lid in batch:
        by_id[lid]["status"] = "INSTANTIATING"
        by_id[lid]["rounds_visited"] = int(by_id[lid].get("rounds_visited") or 0) + 1
    state["population_queue"] = {"round": int(prev.get("round", 0)) + 1, "batch": batch,
                                 "started_at": prev.get("started_at") or now(),
                                 "batch_queries": sum(len(by_id[l].get("channel_queries") or []) for l in batch),
                                 "remaining_eligible": max(0, len(eligible_leads(state, policies)))}
    names = [by_id[l]["name"][:40] for l in batch]
    return (f"population round {state['population_queue']['round']}: {len(batch)} leads to instantiate {names} "
            f"({state['population_queue']['batch_queries']} channel queries) — VOI order, sequential")


# ------------------------------------------------------- cards + clusters --
def _ident(rec: dict) -> tuple:
    ident = rec.get("source_identity") or {}
    return (ident.get("platform") or "?", ident.get("author_key") or rec.get("source") or rec.get("id"),
            ident.get("thread_key") or rec.get("source") or rec.get("id"))


def cards(state: dict, policies: dict) -> str:
    """Executor python.evidence_cards — deterministic recompute from records."""
    d = state["data"]
    recs = [r for r in d.get("field_records") or [] if isinstance(r, dict) and not r.get("contradicts")]
    by_id = lead_by_id(state)
    thr = anchor_threshold(state, policies)
    # participant cards: one per real (platform, author)
    by_author: dict[tuple, list] = collections.defaultdict(list)
    for r in recs:
        p, a, _ = _ident(r)
        by_author[(p, a)].append(r)
    cards_out = []
    for (p, a), items in sorted(by_author.items()):
        threads = {_ident(r)[2] for r in items}
        roles = sorted({x for r in items for x in (r.get("evidence_roles") or [])})
        unknown = [f"no {x} recorded" for x in _CORE_ROLES if x not in roles]
        cards_out.append({"id": stable_id("card", p, a), "platform": p, "author_key": a,
                          "record_ids": [r["id"] for r in items], "record_count": len(items), "thread_count": len(threads),
                          "communities": sorted({_norm_community(r.get("community")) for r in items}),
                          "roles_present": roles, "freshness_classes": sorted({(r.get("freshness") or {}).get("class") or "?" for r in items}),
                          "lead_ids": sorted({r.get("lead_id") for r in items if r.get("lead_id")}),
                          "products_named": sorted({str(x) for r in items for x in (r.get("products_named") or [])}),
                          "unknowns": unknown})
    card_by_author = {(c["platform"], c["author_key"]): c["id"] for c in cards_out}
    # clusters: community × friction family
    groups: dict[tuple, list] = collections.defaultdict(list)
    for r in recs:
        groups[(_norm_community(r.get("community")), str(r.get("friction_family") or "unassigned"))].append(r)
    clusters_out = []
    for (comm, fam), items in sorted(groups.items()):
        ind = _ver.independence_groups(items)["independent_groups"]
        threads = {_ident(r)[2] for r in items}
        roles = sorted({x for r in items for x in (r.get("evidence_roles") or [])})
        anchor = (len(items) >= thr["min_records"] and len(threads) >= thr["min_threads"] and ind >= thr["min_independent_voices"])
        unknowns = [f"no {x} recorded" for x in _CORE_ROLES if x not in roles]
        if not any(r.get("moment") for r in items):
            unknowns.append("moment (before/during/transition/after) unknown")
        if not any((r.get("workaround") or "").strip() for r in items):
            unknowns.append("workaround unknown")
        if len(threads) < thr["min_threads"]:
            unknowns.append(f"only {len(threads)} thread(s) — independence unproven")
        lead_ids = collections.Counter(r.get("lead_id") for r in items if r.get("lead_id"))
        lead_id = lead_ids.most_common(1)[0][0] if lead_ids else None
        clusters_out.append({"id": stable_id("cluster", comm, fam), "lead_id": lead_id, "community": comm, "friction_family": fam,
                             "card_ids": sorted({card_by_author[_ident(r)[:2]] for r in items}),
                             "record_ids": [r["id"] for r in items], "record_count": len(items), "thread_count": len(threads),
                             "independent_voices": ind, "authority": "ANCHOR" if anchor else "THIN",
                             "roles_present": roles,
                             "sample_quotes": [str(r.get("quote_ref"))[:160] for r in items[:3]],
                             "products_named": sorted({str(x) for r in items for x in (r.get("products_named") or [])}),
                             "seed_population": bool((by_id.get(lead_id) or {}).get("seed_population")) if lead_id else False,
                             "unknowns": unknowns, "threshold": dict(thr)})
    d["participant_cards"] = cards_out
    d["lived_clusters"] = clusters_out
    # lead statuses: the batch just visited either produced records or is exhausted for now
    rec_by_lead: dict[str, list] = collections.defaultdict(list)
    for r in d.get("field_records") or []:
        if r.get("lead_id"):
            rec_by_lead[r["lead_id"]].append(r["id"])
    for lid, lead in by_id.items():
        lead["record_ids"] = rec_by_lead.get(lid, [])
        if lead.get("status") == "INSTANTIATING":
            lead["status"] = "INSTANTIATED" if rec_by_lead.get(lid) else "EXHAUSTED"
    anchors = sum(1 for c in clusters_out if c["authority"] == "ANCHOR")
    return (f"{len(cards_out)} participant cards, {len(clusters_out)} clusters ({anchors} ANCHOR, {len(clusters_out) - anchors} THIN) "
            f"from {len(recs)} records — threshold {thr}")


# ------------------------------------------------------------------ gate --
def gate(state: dict, policies: dict) -> str:
    """Executor python.population_gate: continue rounds only while it pays."""
    lw = _lw(policies)
    d = state["data"]
    clusters = d.get("lived_clusters") or []
    anchors = sum(1 for c in clusters if c.get("authority") == "ANCHOR")
    records = len(d.get("field_records") or [])
    prev = state.get("population_loop") or {}
    q = state.get("population_queue") or {}
    rounds = int(q.get("round", 0))
    try:
        started = _dt.datetime.fromisoformat(q.get("started_at") or now())
        elapsed = (_dt.datetime.now(_dt.timezone.utc) - started).total_seconds() / 60.0
    except ValueError:
        elapsed = 0.0
    progressed = records > int(prev.get("records", -1)) or anchors > int(prev.get("anchors", -1))
    stagnant = (not progressed) and rounds > int(lw.get("stagnation_rounds", 1))
    need = anchors < int(lw.get("min_anchor_clusters", 2))
    remaining = eligible_leads(state, policies)
    reasons = []
    if not need:
        reasons.append(f"{anchors} ANCHOR clusters satisfy min {lw.get('min_anchor_clusters', 2)}")
    if rounds >= int(lw.get("max_rounds", 3)):
        reasons.append(f"round ceiling {lw.get('max_rounds', 3)} reached")
    if stagnant:
        reasons.append("stagnation: no new record or ANCHOR last round")
    if elapsed >= float(lw.get("wall_clock_minutes", 45)):
        reasons.append(f"wall clock {lw.get('wall_clock_minutes', 45)} min reached")
    if not remaining:
        reasons.append("no eligible leads left")
    cont = need and not reasons
    state["population_loop"] = {"continue": cont, "rounds": rounds, "anchors": anchors, "records": records,
                                "elapsed_min": round(elapsed, 1), "remaining_eligible": len(remaining),
                                "reason": "another round" if cont else "; ".join(reasons) or "proceed"}
    return (f"population gate: {anchors} ANCHOR / {len(clusters) - anchors} THIN clusters, {records} records, round {rounds}, "
            f"{state['population_loop']['elapsed_min']} min — {'ONE MORE ROUND' if cont else 'proceed: ' + state['population_loop']['reason']}")


# ------------------------------------------------------- lineage law (docs/26 §2, fail-closed) --
def lineage_ref_errors(refs, state: dict, relevance: dict, label: str) -> list[str]:
    """Anything consumed as reasoning lineage must exist and, when it is a
    corpus row, be CLASSIFIED and not IRRELEVANT. Unclassified rows may sit in
    the retrieval context; they can never become latent-structure evidence,
    corpus-observation evidence, an analogy or a hypothesis hop."""
    d = state["data"]
    rows = {r.get("id") for r in d.get("corpus_evidence") or [] if isinstance(r, dict)}
    other = {x.get("id") for key in ("observations", "field_records", "lived_clusters", "latent_structures", "corpus_observations")
             for x in d.get(key) or [] if isinstance(x, dict)}
    errs = []
    for ref in refs or []:
        if ref in rows:
            cls = (relevance or {}).get(ref)
            if cls is None:
                errs.append(f"{label}: corpus row {ref!r} is UNCLASSIFIED — classify it in row_relevance before it becomes lineage (fail-closed)")
            elif cls == "IRRELEVANT":
                errs.append(f"{label}: corpus row {ref!r} is classified IRRELEVANT — dead for lineage")
        elif ref not in other:
            errs.append(f"{label}: ref {ref!r} does not exist in this run (corpus rows, observations, field records, clusters, structures)")
    return errs


def validate_relevance_map(rel: dict, state: dict, policies: dict) -> list[str]:
    classes = set((policies.get("corpus") or {}).get("relevance_classes") or [])
    rows = {r.get("id") for r in state["data"].get("corpus_evidence") or [] if isinstance(r, dict)}
    errs = []
    for rid, cls in (rel or {}).items():
        if cls not in classes:
            errs.append(f"row_relevance[{rid}]: {cls!r} not in {sorted(classes)}")
        elif rid not in rows:
            errs.append(f"row_relevance[{rid}]: unknown corpus row")
    return errs


def merge_relevance(state: dict, rel: dict) -> None:
    cur = dict(state["data"].get("row_relevance") or {})
    cur.update(rel or {})
    state["data"]["row_relevance"] = cur
    for r in state["data"].get("corpus_evidence") or []:
        if isinstance(r, dict) and r.get("id") in cur:
            r["relevance"] = cur[r["id"]]


# ------------------------------------------------------------ validation --
def validate_leads(items: list[dict], state: dict) -> list[str]:
    errs = []
    for l in items:
        if not isinstance(l, dict):
            continue
        if l.get("kind") == "COMMUNITY" and not (l.get("community_key") or l.get("platform")):
            errs.append(f"{l.get('id')}: a COMMUNITY lead needs community_key or platform — where would anyone look?")
        if l.get("status") not in (None, "NOMINATED"):
            errs.append(f"{l.get('id')}: a submitted lead starts NOMINATED — only instantiation changes status")
        if l.get("authority") not in (None, "LEAD"):
            errs.append(f"{l.get('id')}: lead authority is LEAD — a lead never establishes demand")
    return errs


def validate_records(items: list[dict], state: dict, policies: dict) -> list[str]:
    """Same evidence contract as observations (roles × source × freshness) +
    the lead must exist."""
    _, errs = _ver.admit_observations(items, policies)
    known = set(lead_by_id(state))
    for r in items:
        if isinstance(r, dict) and r.get("lead_id") not in known:
            errs.append(f"{r.get('id')}: lead_id {r.get('lead_id')!r} is not a nominated lead in this run")
        if isinstance(r, dict) and not (r.get("quote_ref") or "").strip():
            errs.append(f"{r.get('id')}: quote_ref is required — a record without a recoverable quote is hearsay")
    return errs


def validate_situations(items: list[dict], state: dict, policies: dict) -> list[str]:
    d = state["data"]
    clusters = {c["id"]: c for c in d.get("lived_clusters") or [] if isinstance(c, dict)}
    known = {r.get("id") for r in (d.get("field_records") or []) + (d.get("observations") or []) if isinstance(r, dict)}
    errs = []
    for s in items:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", "?")
        auth = s.get("authority")
        cl = clusters.get(s.get("cluster_id")) if s.get("cluster_id") else None
        if s.get("cluster_id") and not cl:
            errs.append(f"{sid}: cluster_id {s.get('cluster_id')!r} does not exist in this run")
        for fr in s.get("frictions") or []:
            if isinstance(fr, dict) and fr.get("authority") == "FIELD_OBSERVATION":
                refs = fr.get("refs") or []
                bad = [x for x in refs if x not in known]
                if not refs or bad:
                    errs.append(f"{sid}: FIELD_OBSERVATION friction {str(fr.get('text'))[:40]!r} must cite known record ids ({'none' if not refs else bad[:2]})")
        if auth == "FIELD_ANCHORED":
            if not cl:
                errs.append(f"{sid}: FIELD_ANCHORED requires a cluster_id")
            elif cl.get("authority") != "ANCHOR":
                errs.append(f"{sid}: cluster {cl['id']} is THIN ({cl.get('record_count')} records, {cl.get('thread_count')} threads, "
                            f"{cl.get('independent_voices')} voices) — below the anchor threshold it may only feed RECONSTRUCTED")
            if not any(isinstance(fr, dict) and fr.get("authority") == "FIELD_OBSERVATION" for fr in s.get("frictions") or []):
                errs.append(f"{sid}: FIELD_ANCHORED needs at least one friction carrying FIELD_OBSERVATION refs")
        elif auth == "RECONSTRUCTED":
            if not cl and not [x for x in (s.get("evidence_refs") or []) if x in known]:
                errs.append(f"{sid}: RECONSTRUCTED must sit on a cluster_id or cite known evidence_refs — otherwise it is SIMULATED")
            if not s.get("unknowns"):
                errs.append(f"{sid}: a reconstruction with no unknowns is a biography — list what the records do not say")
        elif auth == "SIMULATED":
            if cl:
                errs.append(f"{sid}: a situation on a cluster is RECONSTRUCTED (or FIELD_ANCHORED), not SIMULATED")
    return errs


def validate_hypothesis_anchors(hypotheses: list[dict], state: dict, policies: dict) -> list[str]:
    """docs/25 §5: a hypothesis names ANCHOR clusters (lived_anchor_ids) or
    declares grounding CORPUS_ONLY; the portfolio needs min_lived_anchored."""
    if not (policies.get("bridge") or {}).get("require_lived_anchor"):
        return []
    clusters = {c["id"]: c for c in state["data"].get("lived_clusters") or [] if isinstance(c, dict)}
    errs, anchored = [], 0
    for h in hypotheses:
        if not isinstance(h, dict):
            continue
        ids = h.get("lived_anchor_ids") or []
        if ids:
            for cid in ids:
                c = clusters.get(cid)
                if not c:
                    errs.append(f"{h.get('id')}: lived_anchor_ids names unknown cluster {cid!r}")
                elif c.get("authority") != "ANCHOR":
                    errs.append(f"{h.get('id')}: cluster {cid} is THIN — it cannot anchor a hypothesis (reconstruct or research it first)")
            if not [e for e in errs if e.startswith(str(h.get("id")))]:
                anchored += 1
            h["grounding"] = "LIVED"
        elif h.get("grounding") not in ("CORPUS_ONLY",):
            errs.append(f"{h.get('id')}: name lived_anchor_ids (ANCHOR clusters) or declare grounding: CORPUS_ONLY — silence is not a lane")
    return errs


def validate_portfolio_anchors(hypotheses: list[dict], state: dict, policies: dict) -> list[str]:
    if not (policies.get("bridge") or {}).get("require_lived_anchor"):
        return []
    need = int((policies.get("portfolio") or {}).get("min_lived_anchored", 2))
    anchors_exist = any(c.get("authority") == "ANCHOR" for c in state["data"].get("lived_clusters") or [])
    got = sum(1 for h in hypotheses if isinstance(h, dict) and h.get("lived_anchor_ids"))
    if anchors_exist and got < need:
        return [f"portfolio: {got} hypotheses anchor in lived clusters, policy wants >= {need} — the field co-generates, it does not only validate"]
    return []


# ------------------------------------------------- corpus question compiler --
def compile_corpus_questions(state: dict, policies: dict) -> str:
    """Executor python.corpus_question_compiler (on_enter of corpus_mechanisms)."""
    d = state["data"]
    forms = list((policies.get("corpus") or {}).get("question_forms") or [])
    cap = int((policies.get("corpus") or {}).get("max_questions", 12))
    recs = {r["id"]: r for r in d.get("field_records") or [] if isinstance(r, dict)}
    clusters = sorted(d.get("lived_clusters") or [], key=lambda c: (c.get("authority") != "ANCHOR", -int(c.get("independent_voices") or 0)))
    out, seen = [], set()
    for c in clusters:
        items = [recs[i] for i in c.get("record_ids") or [] if i in recs]
        friction = (c.get("friction_family") or "").replace("_", " ").strip()
        if not friction or friction == "unassigned":
            probs = collections.Counter(t for r in items for t in _toks(r.get("problem")))
            friction = " ".join(t for t, _ in probs.most_common(3))
        workaround = next(((r.get("workaround") or "").strip() for r in items if (r.get("workaround") or "").strip()), "")
        behavior = next(((r.get("problem") or "").strip() for r in items if "BEHAVIOR_SUPPORT" in (r.get("evidence_roles") or [])), "")
        slots = {"friction": friction, "workaround": workaround[:90], "context": c.get("community"), "behavior": behavior[:90]}
        for i, form in enumerate(forms):
            needed = re.findall(r"{(\w+)}", form)
            if any(not slots.get(k) for k in needed):
                continue
            text = form.format(**slots)
            if text in seen:
                continue
            seen.add(text)
            out.append({"id": stable_id("cq", c["id"], i), "cluster_id": c["id"], "community": c.get("community"),
                        "kind": ["workaround", "mechanism", "analogy", "behavior"][i % 4] if len(forms) == 4 else f"form{i}",
                        "question": text, "authority_of_answer": "CORPUS_SYNTHESIS",
                        "cluster_authority": c.get("authority")})
            if len(out) >= cap:
                break
        if len(out) >= cap:
            break
    d["corpus_questions"] = out
    return f"compiled {len(out)} corpus questions at friction/mechanism level from {len(clusters)} clusters (never per person)"


# --------------------------------------------------------------- summary --
def summary(state: dict) -> dict:
    d = state["data"]
    leads = all_leads(state)
    sits = [s for s in d.get("lived_situations") or [] if isinstance(s, dict)]
    return {"leads": len(leads), "leads_by_lane": dict(collections.Counter(l.get("source_lane") for l in leads)),
            "leads_by_status": dict(collections.Counter(l.get("status") for l in leads)),
            "seed_population_leads": sum(1 for l in leads if l.get("seed_population")),
            "latent_leads": sum(1 for l in leads if l.get("search_mode") == "LATENT"),
            "latent_leads_instantiated": sum(1 for l in leads if l.get("search_mode") == "LATENT" and l.get("record_ids")),
            "field_records": len(d.get("field_records") or []),
            "records_by_origin": dict(collections.Counter(r.get("origin") or "CHANNEL" for r in d.get("field_records") or [])),
            "participant_cards": len(d.get("participant_cards") or []),
            "clusters_by_authority": dict(collections.Counter(c.get("authority") for c in d.get("lived_clusters") or [])),
            "clusters_outside_seed": sum(1 for c in d.get("lived_clusters") or [] if not c.get("seed_population")),
            "situations_by_authority": dict(collections.Counter(s.get("authority") for s in sits)),
            "unknowns_preserved": sum(len(s.get("unknowns") or []) for s in sits),
            "corpus_questions": len(d.get("corpus_questions") or []),
            "rounds": (state.get("population_queue") or {}).get("round", 0),
            "loop": state.get("population_loop") or {}}


EXECUTORS = {
    "python.population_nominate": nominate,
    "python.population_queue": queue,
    "python.evidence_cards": cards,
    "python.population_gate": gate,
    "python.corpus_question_compiler": compile_corpus_questions,
}
