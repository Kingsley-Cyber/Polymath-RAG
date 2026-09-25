"""K1 noise check ($0): where replay.py saw different evidence with and without the scope, is that the scope or run noise?

Runs the given (question, mode) pairs twice WITHOUT a scope and twice WITH the reference-only scope, and compares every run
with the first no-scope run. If no-scope runs also differ from each other, the difference is the pipeline's own run-to-run
noise, not the role clause (which, on the raw collection, returned the same passages as the plain filter in 30 of 30 probes).
Run like replay.py. Writes noise_check.json next to this file."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("k1_replay", HERE / "replay.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
PAIRS = (("What do my books say about making an animated character's movement feel weighty?", "GRAPH"),
         ("What do my books say about making an animated character's movement feel weighty?", "WILDCARD"))


def main() -> int:
    import os
    from polymath_shared.code.scope import REFERENCE_ONLY
    os.environ.update({"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_CONTEXTUAL_JUDGE": "wildcard",
                       "POLYMATH_CHAT_SKELETON_PROBES": "0", "POLYMATH_CHAT_PROBE_GATE": "1", "POLYMATH_CHAT_SEEALSO_BLEND": "1",
                       "POLYMATH_CHAT_DOC_STEER": "1", "POLYMATH_GRAPH_FACT_RANK": "1", "POLYMATH_PROFILE_SCOUT": "1"})
    R._install_recorder()
    plans = {t["question"]: ((t.get("receipt") or {}).get("meta") or {}).get("chat_plan") or {}
             for t in json.loads(R.RESULTS.read_text())}
    out = []
    for question, mode in PAIRS:
        q = {"question": question, "cp": plans[question]}
        R._once(q, mode, None)                                                    # warm-up
        runs = [("none", R._once(q, mode, None)), ("none", R._once(q, mode, None)),
                ("reference", R._once(q, mode, REFERENCE_ONLY)), ("reference", R._once(q, mode, REFERENCE_ONLY))]
        first = runs[0][1]["evidence"]
        rec = {"question": question, "mode": mode,
               "differs_from_first_none": [(name, sum(1 for c in r["evidence"] if c not in first)) for name, r in runs]}
        out.append(rec)
        print(mode, rec["differs_from_first_none"], flush=True)
    (HERE / "noise_check.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
