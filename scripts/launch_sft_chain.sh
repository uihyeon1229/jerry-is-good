#!/usr/bin/env bash
# SFT 2단 체인: dry-run → 자동 풀 학습
# Phase 1: epoch=1, n=500 (환경 검증, ~30m)
# Phase 2: epoch=3, n=전량, resume_from_checkpoint (~3~4h)
#
# 사용법:
#   bash scripts/launch_sft_chain.sh
#   또는 tmux 세션에 올려두기:
#     tmux new -d -s sft "bash scripts/launch_sft_chain.sh 2>&1 | tee training/logs/chain.log"

set -euo pipefail

cd "$(dirname "$0")/.."
source /ephemeral/venvs/unsloth/bin/activate
export TMPDIR=/ephemeral/tmp
export HF_HOME=${HF_HOME:-/home/shadeform/.cache/huggingface}

# GPU 해제 — vLLM이 있으면 학습 못 함
echo "[$(date)] === vLLM 세션 종료 (GPU 확보) ==="
tmux kill-session -t vllm 2>/dev/null || true
sleep 5

LOG_DIR=training/logs
OUTPUT_DIR=${OUTPUT_DIR:-training/checkpoints/tax_cot_lora_v2}
TRAIN_INPUT=${TRAIN_INPUT:-output/final/train.jsonl}
LOSS_THRESHOLD=${LOSS_THRESHOLD:-3.0}  # Phase 1 통과 loss 임계치 (느슨)
export SFT_MODEL=${SFT_MODEL:-nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16}
export LR=${LR:-2e-4}  # LoRA SFT 표준 LR

mkdir -p "$LOG_DIR"

if [[ ! -s "$TRAIN_INPUT" ]]; then
    echo "!! 학습 데이터 없음: $TRAIN_INPUT" >&2
    exit 2
fi

# =======================================================
# Phase 1: dry-run (epoch 1, 500건)
# =======================================================
echo ""
echo "[$(date)] ============================================"
echo "[$(date)]  PHASE 1: dry-run (epoch=1, n=500)"
echo "[$(date)] ============================================"

NUM_EPOCHS=1 \
SFT_MAX_SAMPLES=500 \
SFT_RESUME=0 \
TRAIN_INPUT="$TRAIN_INPUT" \
OUTPUT_DIR="$OUTPUT_DIR" \
python training/sft_unsloth.py \
    2>&1 | tee "$LOG_DIR/sft_phase1.log"

# Phase 1 loss 파싱 (trl SFTTrainer는 {'loss': X.XXX, ...} 형식)
LAST_LOSS=$(grep -oE "'loss': [0-9]+\.[0-9]+" "$LOG_DIR/sft_phase1.log" | tail -1 | grep -oE "[0-9]+\.[0-9]+" || echo "")

echo ""
echo "[$(date)] === Phase 1 완료. last loss = ${LAST_LOSS:-N/A} ==="

if [[ -z "$LAST_LOSS" ]]; then
    echo "!! Phase 1 loss를 찾을 수 없음 → 로그 확인 후 수동 결정"
    echo "   로그: $LOG_DIR/sft_phase1.log"
    exit 10
fi

# bc 없는 환경 대비: python으로 비교
PHASE1_OK=$(python3 -c "print(1 if float('$LAST_LOSS') < float('$LOSS_THRESHOLD') else 0)")
if [[ "$PHASE1_OK" != "1" ]]; then
    echo "!! Phase 1 실패 (loss=$LAST_LOSS >= $LOSS_THRESHOLD) — Phase 2 중단"
    echo "   하이퍼파라미터 조정 후 재시작 필요"
    exit 11
fi

echo "[$(date)] === Phase 1 통과. Phase 2 진입 ==="

# =======================================================
# Phase 2: 풀 학습 (epoch 3, 전량, resume)
# =======================================================
echo ""
echo "[$(date)] ============================================"
echo "[$(date)]  PHASE 2: 풀 학습 (epoch=3, n=전량, resume)"
echo "[$(date)] ============================================"

NUM_EPOCHS=3 \
SFT_MAX_SAMPLES=0 \
SFT_RESUME=1 \
TRAIN_INPUT="$TRAIN_INPUT" \
OUTPUT_DIR="$OUTPUT_DIR" \
python training/sft_unsloth.py \
    2>&1 | tee "$LOG_DIR/sft_phase2.log"

echo ""
echo "[$(date)] === SFT 전체 체인 완료 ==="
echo "   최종 어댑터: $OUTPUT_DIR/final"
echo "   Phase 1 로그: $LOG_DIR/sft_phase1.log"
echo "   Phase 2 로그: $LOG_DIR/sft_phase2.log"
