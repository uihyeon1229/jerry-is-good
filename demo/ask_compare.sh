#!/usr/bin/env bash
# Fine-tuned vs Base 동일 질문 비교 호출 (CLI 데모)
# 사용:
#   bash demo/ask_compare.sh "부가가치세 면세 재화의 범위와 조문을 알려주세요."
#
# Base URL / port 는 환경변수로 오버라이드 가능.

set -euo pipefail

Q="${1:-}"
if [[ -z "$Q" ]]; then
    cat <<EOF >&2
Usage: $0 "<질문>"
Example: $0 "종합부동산세 공정시장가액비율 산정식은?"
EOF
    exit 1
fi

BASE_URL="${VLLM_BASE_URL:-http://localhost:5000/v1}"
MAX_TOK="${MAX_TOKENS:-800}"
TEMP="${TEMPERATURE:-0.3}"

ask() {
    local model="$1"
    curl -s "${BASE_URL}/chat/completions" \
        -H 'Content-Type: application/json' \
        -d "$(python3 -c "
import json, sys
print(json.dumps({
    'model': '$model',
    'messages': [{'role':'user','content': '''$Q'''}],
    'max_tokens': $MAX_TOK,
    'temperature': $TEMP,
}))
")" | python3 -c "
import json, sys
d = json.load(sys.stdin)
try:
    print(d['choices'][0]['message']['content'])
except Exception:
    print(json.dumps(d, indent=2, ensure_ascii=False))
"
}

echo "============================================================"
echo "QUESTION: $Q"
echo "============================================================"

echo ""
echo "━━━━━━━━━━━━ ⚪ BASE (nemotron-base) ━━━━━━━━━━━━"
ask "nemotron-base"

echo ""
echo "━━━━━━━━━━━━ 🟢 FINE-TUNED (tax_lora) ━━━━━━━━━━━━"
ask "tax_lora"
echo ""
