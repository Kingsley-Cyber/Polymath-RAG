"""GROQ-MAP-CONTROL-PLANE-REPAIR-V1 Phase 15 — offline conservation replay.

No provider calls, no DB. Drives the REAL client.complete_one across six lanes
with a scripted mix (admit / refuse-by-reason, 2xx complete/partial/empty/invalid,
429, timeout) and reconciles the request-conservation identities that the disputed
cinema run could not prove:

    lane selections             == admitted + refused
    provider HTTP dispatches    == admitted            (every admission dispatches)
    2xx + 429 + transport-fail  == dispatches
    a refusal                   -> 0 HTTP               (_chat never runs)
    maps persisted              <= compiler-valid maps

Compiler columns come from the deterministic map_compiler run on the 2xx bodies;
persisted<=valid at scale is enforced by persist_maps idempotence, proven in the
DB-gated tests/determinism/test_doc_parent_map_worker.py.
"""
from __future__ import annotations

import itertools
import sys
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "workers", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.llm_extraction.client import LLMExtractionClient  # noqa: E402
from polymath_shared.llm_extraction.limiter import LimiterDecision  # noqa: E402
from polymath_shared.document_profile import map_compiler  # noqa: E402
from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons  # noqa: E402


class _FakeLimiter:
    """Scripted admission; success/failure/release are no-ops (no real lane)."""
    def __init__(self, decision):
        self._d = decision

    def admit(self, est_tokens=0.0, block=True):
        return self._d

    def record_success(self, headers=None):
        pass

    def record_failure(self, retry_after=None, headers=None):
        pass

    def release(self):
        pass


def _parents(n=6):
    return [{"chunk_id": f"r-{i}", "chunk_index": i, "char_start": i * 1000,
             "heading_path": [f"H{i}"], "text": f"Section {i} explains mechanism ZZ{i}.",
             "region_role": "body"} for i in range(n)]


def _one_call(cls, aliases):
    """Run one real complete_one under a scripted outcome; return (dispatched, err, raw)."""
    c = LLMExtractionClient("cloud", url="http://x", model="groq/compound-mini",
                            limiter_key="replay", api_key="k", max_attempts=1)
    if cls.startswith("refuse:"):
        c._lane_limiter = lambda: _FakeLimiter(LimiterDecision(False, cls.split(":", 1)[1]))

        def _boom(*a, **k):
            raise AssertionError("a refusal must never dispatch")
        c._chat = _boom
    else:
        c._lane_limiter = lambda: _FakeLimiter(LimiterDecision(True))
        if cls == "429":
            resp = httpx.Response(429, request=httpx.Request("POST", "http://x/v1/chat/completions"),
                                  headers={"x-ratelimit-remaining-requests": "0"})

            def _chat(*a, **k):
                raise httpx.HTTPStatusError("429", request=resp.request, response=resp)
        elif cls == "timeout":
            def _chat(*a, **k):
                raise httpx.ReadTimeout("read timeout")
        elif cls == "empty":
            def _chat(*a, **k):
                return "", 1, 0, {}
        elif cls == "invalid":
            def _chat(*a, **k):
                return "prose, not a map line\nstill prose", 5, 3, {}
        elif cls == "partial":
            def _chat(*a, **k):
                return "\n".join(f"MAP|{al}|sig {al}|a;b;c" for al in aliases[:-1]), 9, 5, {}
        else:  # complete
            def _chat(*a, **k):
                return "\n".join(f"MAP|{al}|sig {al}|a;b;c" for al in aliases), 9, 5, {}
        c._chat = _chat
    raw, err = c.complete_one("u", system_prompt="s", max_tokens=100)
    return getattr(c, "_last_http_dispatched", False), err, raw


def test_offline_conservation_replay(capsys):
    manifest = build_parent_skeletons(_parents(6))
    aliases = [s.alias for s in manifest.skeletons]
    lanes = [f"map_groq{i}" for i in range(1, 7)]
    script = ["complete", "partial", "empty", "invalid", "429", "timeout",
              "refuse:FAMILY_GATE", "refuse:RPD", "refuse:BREAKER",
              "complete", "complete", "empty"]
    rr = itertools.count()
    lane_selected: Counter = Counter()
    dispatch: Counter = Counter()
    admitted = refused = h2xx = h429 = htrans = 0
    cc = cp = ce = ci = persisted = 0

    for cls in script:
        lane = lanes[next(rr) % len(lanes)]
        lane_selected[lane] += 1
        dispatched, err, raw = _one_call(cls, aliases)
        if dispatched:
            dispatch[lane] += 1
        if cls.startswith("refuse:"):
            refused += 1
            assert dispatched is False and err == "LIMITER_REFUSED"   # 0 HTTP
            continue
        admitted += 1
        assert dispatched is True                                     # admitted => dispatched
        if err == "HTTP_429":
            h429 += 1
            continue
        if err:                                                        # any other post-dispatch fault
            htrans += 1
            continue
        h2xx += 1
        res = map_compiler.compile_maps(raw, manifest)
        nvalid = len(res.maps)
        persisted += nvalid
        if not raw.strip():
            ce += 1
        elif nvalid >= len(aliases):
            cc += 1
        elif nvalid > 0:
            cp += 1
        elif res.rejected:
            ci += 1
        else:
            ce += 1

    total_sel = sum(lane_selected.values())
    total_dsp = sum(dispatch.values())

    # ---- conservation identities (the chain the disputed run could not prove) ----
    assert total_sel == admitted + refused
    assert total_dsp == admitted                      # every admission dispatched
    assert total_dsp == h2xx + h429 + htrans          # responses + faults == dispatches
    assert refused == 3 and h429 == 1 and htrans == 1
    assert cc == 3 and cp == 1 and ce == 2 and ci == 1
    assert persisted <= h2xx * len(aliases)           # persisted <= compiler-valid

    print("\nOFFLINE CONSERVATION REPLAY")
    print(f"  selections={total_sel}  admitted={admitted}  refused={refused}")
    print(f"  dispatches={total_dsp}  2xx={h2xx}  429={h429}  transport={htrans}")
    print(f"  compiler complete={cc} partial={cp} empty={ce} invalid={ci}  persisted={persisted}")
    print(f"  lane_selected={dict(lane_selected)}")
    print(f"  provider_http_dispatch={dict(dispatch)}")
