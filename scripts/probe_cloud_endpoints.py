"""MULTI-PROVIDER-AUTH-V1 preflight: one-token probe per pool endpoint.

Owner canary law: prove every enabled provider is live and authed BEFORE
batch spend. Probes carry NO document content (policy). Exit non-zero if
any ACTIVE endpoint fails, so this is an assertable gate:

    python scripts/probe_cloud_endpoints.py
"""
from __future__ import annotations

import sys

from polymath_shared.llm_extraction.client import LLMExtractionClient
from polymath_shared.llm_extraction.pool import cloud_endpoints


def main() -> int:
    failures = 0
    roster = cloud_endpoints()
    print(f"pool roster ({len(roster)}):")
    for ep in roster:
        client = LLMExtractionClient(
            "cloud", url=ep.url, model=ep.model,
            limiter_key=ep.limiter_key, api_key=ep.api_key,
            cloud_opts=ep.cloud_opts if ep.name != "primary" else None)
        try:
            out = client.probe()
            print(f"  {ep.name:<10} OK   {out['wall_ms']:>5} ms  "
                  f"model={out.get('served_model') or ep.model}  "
                  f"auth={'key' if ep.api_key else 'none(loopback)'}")
        except Exception as exc:
            failures += 1
            print(f"  {ep.name:<10} FAIL {type(exc).__name__}: "
                  f"{str(exc)[:160]}")
    if failures:
        print(f"{failures} endpoint(s) failing — fix or park (enabled:false) "
              "before batch spend")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
