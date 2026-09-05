"""P1.c part 2: rerank prefix 20 -> 28 (measured) + test pin. Apply after p1c_patch.py."""
import pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")
p = ROOT / "shared/polymath_shared/candidate_engine.py"; s = p.read_text(encoding="utf-8")
old = "    rerank_max: int = 20\n    synthesis_max: int = 15"
new = ("    #: P1.c: 28. Measured on the P1.b clean B run — of the 5 gold chunks that were\n"
       "    #: in the union but never seated, 4 sat at union ranks 21 / 21 / 27 / 38 (never\n"
       "    #: judged) and 1 was judged 17th; survival|union was 22 / 27 = 0.815 against a\n"
       "    #: gate of 0.85. +8 pairs ≈ +1.9 s at ~235 ms/pair on a fresh sidecar.\n"
       "    rerank_max: int = 28\n    synthesis_max: int = 15")
assert s.count(old) == 1; s = s.replace(old, new); p.write_text(s, encoding="utf-8")
p = ROOT / "tests/determinism/test_candidate_engine.py"; t = p.read_text(encoding="utf-8")
old = 'and b.rerank_max == 20 and b.synthesis_max == 15'
assert t.count(old) == 1; t = t.replace(old, 'and b.rerank_max == 28 and b.synthesis_max == 15'); p.write_text(t, encoding="utf-8")
print("rerank_max 28 + test pin")
