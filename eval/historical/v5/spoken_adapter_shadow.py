"""SPOKEN-RELATION-ADAPTER-V1 shadow qualification (owner Option A).

Runs a bounded positive/hard-negative panel through the REAL pipeline
pieces — live pinned spaCy parses, the real rule pack, the real kimi
binding layer, the real predicate compiler — under BOTH the current
pack (1.4.0) and the candidate pack (1.5.0, `created` object_core +=
Technology). No stores are touched.

Precision bar (stricter than the documented ≤5%-wrong dev bar): ZERO
false ACCEPTs on the negative panel, and every positive must reach its
expected adjudication. NO EDGE > WRONG EDGE.

Usage: .venv/bin/python eval/v5/spoken_adapter_shadow.py [--pack 1.4.0]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from polymath_shared.clients import SpacySyntaxClient  # noqa: E402
from polymath_shared.contracts import CoreType, EntitySpan  # noqa: E402
from polymath_shared.rulepack import (  # noqa: E402
    compile_relation_kimi,
    load_rule_pack,
)
from workers.candidates import SentenceSlice  # noqa: E402
from workers.evidence_proposer import propose_evidence  # noqa: E402
from tests.historical_boundary import build_candidates_kimi  # noqa: E402

# (id, sentence, [(entity surface, CoreType)], expectation)
# expectation:
#   ("accept", subj, pred, obj)      – must be ACCEPT under the candidate pack
#   ("no_accept",)                   – no candidate may be ACCEPT
#   ("none",)                        – no candidate may exist at all
PANEL = [
    # ---- positives ---------------------------------------------------
    ("P1_transcript_verbatim",
     "Now, when I saw this, I was like, wow, this is a great example of "
     "how Andromeda, which is the new update Facebook made.",
     [("Andromeda", "Technology"), ("Facebook", "Organization")],
     ("accept", "Facebook", "created", "Andromeda")),
    ("P2_main_clause_equation",
     "Hermes is the model that Nous Research built.",
     [("Hermes", "Product"), ("Nous Research", "Organization")],
     ("accept", "Nous Research", "created", "Hermes")),
    ("P3_direct_antecedent_technology",
     "Kubernetes, which Google created, orchestrates deployment.",
     [("Kubernetes", "Technology"), ("Google", "Organization")],
     ("accept", "Google", "created", "Kubernetes")),
    ("P4_reduced_relative_technology",
     "PyTorch is a framework Meta built.",
     [("PyTorch", "Technology"), ("Meta", "Organization")],
     ("accept", "Meta", "created", "PyTorch")),
    # ---- hard negatives ----------------------------------------------
    ("N1_role_possessive",
     "Meta's CEO announced the update.",
     [("Meta", "Organization")], ("no_accept",)),
    ("N2_object_possession",
     "John's laptop is broken.",
     [("John", "Person")], ("no_accept",)),
    ("N3_customer_possessive",
     "OpenAI's customer canceled the contract.",
     [("OpenAI", "Organization")], ("no_accept",)),
    ("N4_event_possessive",
     "Google's conference is in May.",
     [("Google", "Organization")], ("no_accept",)),
    ("N5_possessive_copula_measured",
     "From a high-level overview, Andromeda is Meta's new retrieval engine.",
     [("Andromeda", "Technology"), ("Meta", "Organization")],
     ("no_accept",)),
    ("N6_negation",
     "Andromeda is not the update Facebook made.",
     [("Andromeda", "Technology"), ("Facebook", "Organization")],
     ("no_accept",)),
    ("N7_modality",
     "Andromeda might be the update Facebook made.",
     [("Andromeda", "Technology"), ("Facebook", "Organization")],
     ("no_accept",)),
    ("N8_attribution",
     "He said Facebook made the update.",
     [("Facebook", "Organization")], ("no_accept",)),
    ("N9_pp_modifier",
     "Jon Loomer is an OG in the Facebook advertising space.",
     [("Jon Loomer", "Person"), ("Facebook", "Organization")],
     ("no_accept",)),
    ("N10_light_verb_idiom",
     "Meta made headlines yesterday.",
     [("Meta", "Organization")], ("no_accept",)),
    ("N11_pronoun_subject",
     "They made the update everyone wanted.",
     [], ("none",)),
    ("N12_narrative",
     "The hero made the kingdom whole again.",
     [], ("none",)),
    ("N13_relativizer_subject_inversion",
     "Facebook, which made the announcement, is hiring.",
     [("Facebook", "Organization")], ("no_accept",)),
    ("N14_question",
     "Did Facebook make the Andromeda update?",
     [("Facebook", "Organization"), ("Andromeda", "Technology")],
     ("no_accept",)),
]


def _entities(text: str, spec: list[tuple[str, str]]) -> list[EntitySpan]:
    out = []
    for surface, core in spec:
        start = text.find(surface)
        assert start >= 0, (surface, text)
        out.append(EntitySpan(
            doc_id="d", chunk_id="c", start=start, end=start + len(surface),
            text=surface, core_type=CoreType(core), score=0.8,
            extractor_version="shadow", raw_label=core,
            pass_kind="discovery"))
    return out


def run(pack_version: str) -> dict:
    pack = load_rule_pack(pack_version=pack_version)
    client = SpacySyntaxClient()
    results = []
    failures = []
    try:
        parses = client.syntax([
            {"sentence_id": f"s{i}", "text": text}
            for i, (_, text, _, _) in enumerate(PANEL)])["results"]
    finally:
        client.close()

    # PRODUCTION-FAITHFUL: the extract worker attaches the syntactic
    # record from workers.syntax.parse_sentence to every slice and
    # passes it to the compiler — the shadow does exactly the same
    # (a None parse would flip orientation to surface_weak and change
    # which gates fire).
    from workers.syntax import parse_sentence

    for (case_id, text, espec, expect), parse in zip(PANEL, parses):
        entities = _entities(text, espec)
        evidence = propose_evidence(text, "c", pack)
        syn_record = parse_sentence(text)
        sl = SentenceSlice(
            text=text, sentence_start=0, sentence_end=len(text),
            entities=entities, evidence=evidence, parse=syn_record,
            syntax={"sentence_id": "s:0", "tokens": parse["tokens"],
                    "noun_chunks": parse.get("noun_chunks", [])})
        cands = build_candidates_kimi(
            [sl], doc_id="d", ontology_profile="core",
            extractor_version="shadow", rule_pack=pack, enrich=True)
        rows = []
        for cand in cands:
            decision = compile_relation_kimi(cand, syn_record, pack,
                                             syntax=sl.syntax)
            rows.append({
                "subject": cand.subject.span.text,
                "object": cand.object.span.text,
                "decision": getattr(decision, "decision", str(decision)),
                "predicate": (getattr(getattr(decision, "fact", None), "predicate", None)
                              or getattr(decision, "rule_id", None)),
                "reason": (getattr(decision, "reason", "") or "")[:120],
            })
        accepted = [r for r in rows if r["decision"] == "ACCEPT"]

        ok = True
        why = ""
        if expect[0] == "accept":
            want = {"subject": expect[1], "predicate": expect[2],
                    "object": expect[3]}
            hit = [r for r in accepted
                   if r["subject"] == want["subject"]
                   and r["object"] == want["object"]
                   and r["predicate"] == want["predicate"]]
            stray = [r for r in accepted if r not in hit]
            ok = bool(hit) and not stray
            why = f"want {want}; accepted={accepted}"
        elif expect[0] == "no_accept":
            ok = not accepted
            why = f"accepted={accepted}"
        elif expect[0] == "none":
            ok = not rows
            why = f"candidates={rows}"
        results.append({"case": case_id, "ok": ok, "expect": expect[0],
                        "rows": rows})
        if not ok:
            failures.append((case_id, why))
        print(f"  [{'ok' if ok else 'FAIL':4s}] {case_id:34s} "
              f"cands={len(rows)} accepted={len(accepted)}"
              + (f"  {why[:110]}" if not ok else ""))

    return {"pack": pack_version, "results": results,
            "failures": failures}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default="1.4.0")
    args = ap.parse_args()
    print(f"== spoken-adapter shadow panel · pack {args.pack} ==")
    out = run(args.pack)
    outfile = Path(__file__).parent / f"SPOKEN-ADAPTER-SHADOW-{args.pack}.json"
    outfile.write_text(json.dumps(out, indent=1))
    n_fail = len(out["failures"])
    print(f"\n  => {'PASS' if not n_fail else 'FAIL'} "
          f"({len(out['results']) - n_fail}/{len(out['results'])})"
          f"  results: {outfile}")
    return 0 if not n_fail else 1


if __name__ == "__main__":
    sys.exit(main())
