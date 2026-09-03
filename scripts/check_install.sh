#!/usr/bin/env bash
# Read-only reachability report. See AGENTS.md and scripts/README.md.
set -u

check_tcp() {
  local name="$1"
  local port="$2"
  nc -z 127.0.0.1 "$port" >/dev/null 2>&1     && echo "$name: reachable"     || echo "$name: unavailable"
}

check_http() {
  local name="$1"
  local url="$2"
  curl -fsS "$url" >/dev/null     && echo "$name: ready"     || echo "$name: unavailable"
}

check_tcp postgres 5432
check_http qdrant http://127.0.0.1:6333/healthz
check_http neo4j http://127.0.0.1:7474
check_tcp redis 6379
# (gliner-runtime :8740 and spacy :8744 deleted 2026-09-03 — LLM-DIRECT-CANON)
check_http embedder http://127.0.0.1:8742/ready
check_http reranker http://127.0.0.1:8743/ready
check_http "local-extractor (parked when no extraction is queued)" http://127.0.0.1:8755/ready
check_http orchestrator http://127.0.0.1:7200/health
check_http mcp http://127.0.0.1:8930/health

.venv/bin/python - <<'PY'
from polymath_shared.clients import probe_local_llm

try:
    report = probe_local_llm()
except Exception as exc:
    print(f"local-llm: unavailable ({type(exc).__name__}: {exc})")
else:
    if report["status"] == "disabled":
        print("local-llm: disabled")
    else:
        print(
            "local-llm: ready "
            f"model={report['model']} digest={report['digest']}"
        )
PY
