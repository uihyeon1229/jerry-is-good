#!/usr/bin/env bash
# vLLM Nemotron 3 Nano FP8 기동 (tmux 세션 'vllm')
set -euo pipefail

VENV="${VENV:-/home/shadeform/track3}"
MODEL_PATH="${MODEL_PATH:-/home/shadeform/models/nemotron-3-nano-fp8}"
PORT="${PORT:-5000}"
SCRIPTS_DIR="${SCRIPTS_DIR:-/home/shadeform/scripts}"
SESSION="${SESSION:-vllm}"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session '$SESSION' already running. Attach: tmux attach -t $SESSION"
  exit 0
fi

tmux new-session -d -s "$SESSION" "source ${VENV}/bin/activate && cd ${SCRIPTS_DIR} && \
  python3 -m vllm.entrypoints.openai.api_server \
    --model ${MODEL_PATH} \
    --dtype auto --trust-remote-code \
    --served-model-name nemotron \
    --host 0.0.0.0 --port ${PORT} \
    --enable-auto-tool-choice --tool-call-parser qwen3_coder \
    --reasoning-parser-plugin ./nano_v3_reasoning_parser.py \
    --reasoning-parser nano_v3 2>&1 | tee ~/vllm_official.log"

echo "vLLM started in tmux session '$SESSION', port ${PORT}."
echo "Check readiness: curl -s http://localhost:${PORT}/v1/models"
