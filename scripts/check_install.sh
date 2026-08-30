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
check_http gliner-runtime http://127.0.0.1:8740/ready
check_http embedder http://127.0.0.1:8742/ready
check_http reranker http://127.0.0.1:8743/ready
check_http orchestrator http://127.0.0.1:8000/health
check_http control http://127.0.0.1:7100/health

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
