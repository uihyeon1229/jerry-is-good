#!/usr/bin/env bash
# 50건 검증용 생성
set -euo pipefail

cd "$(dirname "$0")/.."
source /home/shadeform/track3/bin/activate
python -m pipeline.run_generate --n 50 --mode preview --name tax_cot_v1
