#!/usr/bin/env bash
# Nsight Systems GPU 프로파일 캡처 (SFT 또는 생성 중 실행)
# 사용:
#   scripts/nsight_capture.sh <PID> <OUT_NAME>
# 예:
#   scripts/nsight_capture.sh 408006 training/nsight/sft_run
set -euo pipefail

PID="${1:-}"
OUT="${2:-training/nsight/capture}"
DURATION_SEC="${DURATION_SEC:-60}"

if [[ -z "$PID" ]]; then
    echo "Usage: $0 <PID> [<OUT_NAME>]"
    echo ""
    echo "PID를 찾으려면:"
    echo "  pgrep -af 'vllm serve' | head   # vLLM 서빙"
    echo "  pgrep -af 'sft_nemotron'        # SFT 학습"
    exit 1
fi

if ! command -v nsys > /dev/null 2>&1; then
    echo "nsys not found. Nsight Systems가 설치되어 있는지 확인하세요:"
    echo "  which nsys  or  /usr/local/cuda/bin/nsys"
    exit 1
fi

OUT_DIR="$(dirname "$OUT")"
mkdir -p "$OUT_DIR"

echo "=== Nsight 캡처 시작 (PID=$PID, duration=${DURATION_SEC}s) ==="
echo "=== 출력: ${OUT}.nsys-rep ==="

nsys profile \
    --trace=cuda,nvtx,osrt \
    --sample=cpu \
    --output="${OUT}" \
    --force-overwrite=true \
    --duration="${DURATION_SEC}" \
    --attach-pid="${PID}"

echo ""
echo "=== 캡처 완료 → ${OUT}.nsys-rep ==="
echo "발표용 변환:"
echo "  nsys stats --report cudaapisum ${OUT}.nsys-rep"
echo "  nsys export --type=sqlite ${OUT}.nsys-rep"
echo ""
echo "Nsight GUI로 열기:"
echo "  로컬에서: brev copy jerryisgood-h100-80gib-vram-sxm5:${OUT}.nsys-rep ."
echo "  Nsight Systems GUI 실행 → Open → ${OUT}.nsys-rep"
