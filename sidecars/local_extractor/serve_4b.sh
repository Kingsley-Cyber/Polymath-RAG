#!/usr/bin/env bash
# LOCAL-LLM-EXTRACTION-V1 — local MLX extraction sidecar launcher.
#
# Serves the pinned Qwen3.5-4B MLX 4bit model behind an OpenAI-compatible
# /v1 API (mlx_lm.server). Model-window discipline (plan §3 rule 2): the
# sidecar is a PROCESS — spawn, poll /v1/models until ready, work,
# SIGTERM, confirm dead. It holds no document state and never touches the
# stores. Memory: 2.83 GB weights + batch-only KV.
#
# Usage: sidecars/local_extractor/serve_4b.sh [port]   (default 8755)
set -euo pipefail

PORT="${1:-8755}"
PIN_SNAPSHOT="32f3e8ecf65426fc3306969496342d504bfa13f3"
HF_DIR="${HOME}/.cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit"
MODEL_PATH="${HF_DIR}/snapshots/${PIN_SNAPSHOT}"

if [[ ! -d "${MODEL_PATH}" ]]; then
  echo "pinned model snapshot missing: ${MODEL_PATH}" >&2
  echo "resolve with: huggingface-cli download mlx-community/Qwen3.5-4B-MLX-4bit" >&2
  exit 1
fi

PY="$(cd "$(dirname "$0")/../.." && pwd)/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then PY="$(command -v python3)"; fi

echo "serving ${MODEL_PATH} on 127.0.0.1:${PORT}"
exec "${PY}" -m mlx_lm server \
  --model "${MODEL_PATH}" \
  --host 127.0.0.1 \
  --port "${PORT}"
