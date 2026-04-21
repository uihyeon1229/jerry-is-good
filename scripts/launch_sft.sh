#!/usr/bin/env bash
# SFT 학습 tmux 세션 기동 (vLLM kill 후 실행)
set -euo pipefail

cd "$(dirname "$0")/.."

# vLLM 종료 (GPU 공유 불가)
tmux kill-session -t vllm 2>/dev/null || true
sleep 3

SESSION="${SESSION:-sft}"
TRAIN_INPUT="${TRAIN_INPUT:-output/refined/tax_cot_v3_refined.jsonl}"

tmux kill-session -t "$SESSION" 2>/dev/null || true

tmux new-session -d -s "$SESSION" "source /home/shadeform/track3/bin/activate && \
  TRAIN_INPUT=${TRAIN_INPUT} \
  python training/sft_nemotron_nano_lora.py 2>&1 | tee training/logs/sft.log"

echo "SFT started in tmux session '$SESSION'."
echo "View: tmux attach -t $SESSION"
echo "Log:  tail -f training/logs/sft.log"
