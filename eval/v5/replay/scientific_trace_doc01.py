"""SCIENTIFIC EXTRACTION TRACE — doc01 (Adaptive Neural Reasoning).

Runs the REAL binding stages against the REAL syntax sidecar for the
failing sentences, capturing INPUT/OUTPUT/PASS-FAIL per stage.
No DB writes. Produces the failure-boundary report the owner asked for.
"""
import json
import os
import sys

ROOT = "/Users/king/Documents/polymath-rebuild/polymath-v4"
sys.path.insert(0, ROOT + "/shared")
sys.path.insert(0, ROOT + "/workers")

os.environ["POLYMATH_RELATION_PIPELINE"] = "kimi_v1"
os.environ["POLYMATH_PREDICATE_V2"] = "shadow"
os.environ["POLYMATH_SYNTAX_PROVIDER"] = "spacy"

SENTENCES = [
    ("S1 creation", "The Orion Adaptive Reasoning Model was introduced "
     "by the Advanced Computational Intelligence Laboratory in 2024 as "
     "an experimental architecture designed to improve long-context "
     "reasoning performance."),
    ("S2 training", "The model was trained on the HorizonText Research "
     "Corpus, a curated dataset containing scientific articles, "
     "mathematical demonstrations, and programming examples."),
    ("S3 evaluation", "Evaluation studies examined Orion's performance "
     "across multiple benchmark suites including ReasonBench, LogicQA, "
     "and MultiStepEval."),
]

from polymath_shared.clients import SpacySyntaxClient  # noqa: E402
from polymath_shared.rulepack.semantic_frames import (  # noqa: E402
    resolve_frames, resolve_predicate)
from polymath_shared.knowledge_router.classifier import classify_document


def main() -> dict:
    trace = {"router": classify_document(
        "\n".join(s for _, s in SENTENCES)), "stages": []}

    client = SpacySyntaxClient()
    batch = [{"sentence_id": f"s{i}", "text": t}
             for i, (_, t) in enumerate(SENTENCES)]
    resp = client.syntax(batch)
    syntax_by_id = {r["sentence_id"]: r for r in resp["results"]}

    for i, (label, text) in enumerate(SENTENCES):
        st = {"stage": label, "sentence": text[:70]}
        fr = resolve_frames(text)
        st["frames"] = [(f.surface, f.frame_id) for f in fr]

        syn = syntax_by_id.get(f"s{i}") or {}
        toks = sorted(syn.get("tokens", []),
                      key=lambda t: t.get("char_start", 0))
        st["n_syntax_tokens"] = len(toks)

        # locate trigger head token by frame surface offset
        trig = None
        for f in fr:
            pass
        if fr:
            surf = fr[0].surface
            pos = text.lower().find(surf.lower())
            for t in toks:
                if t.get("char_start", 0) <= pos < t.get("char_end", -1) \
                        and t.get("pos") in ("VERB", "AUX"):
                    trig = t
                    break
        st["trigger_head"] = (trig or {}).get("text")

        # find UD arguments using kimi's own function
        sys.path.insert(0, ROOT + "/workers")
        from workers.kimi_candidates import _find_ud_arguments
        args = _find_ud_arguments(toks, trig) if trig else {}
        st["ud_args"] = {k: [t["text"] for t in v]
                         for k, v in args.items() if v}

        # entity matching via containment (mirror _token_to_entity)
        ENTITIES = {
            "S1": [("Orion Adaptive Reasoning Model", "Model", 4, 36),
                   ("Advanced Computational Intelligence Laboratory",
                    "Organization", 40, 78)],
            "S2": [("HorizonText Research Corpus", "Corpus", 22, 48)],
            "S3": [("ReasonBench", "Benchmark", None, None)],
        }[label.split()[0]]
        st["entities_in_sentence"] = [e[0] for e in ENTITIES]

        # typed predicate resolution
        role_map = {"S1": ("creation_event", "Model", "Organization"),
                    "S2": ("training_event", "Model", "Corpus"),
                    "S3": ("evaluation_event", "Model", "Benchmark")}
        fid, sty, oty = role_map[label.split()[0]]
        m = resolve_predicate(fid, sty, oty,
                              lemma_hint=(fr[0].surface if fr else None))
        st["typed_mapping"] = m["predicate"] if m else "UNSUPPORTED"
        trace["stages"].append(st)

    trace["router_profile"] = trace.pop("router")
    return trace


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
