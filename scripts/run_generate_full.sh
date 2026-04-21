#!/usr/bin/env bash
# 본 생성 (기본 1000건)
set -euo pipefail

cd "$(dirname "$0")/.."
source /home/shadeform/track3/bin/activate
N="${N:-1000}"
python -m pipeline.run_generate --n "$N" --mode create --name tax_cot_v1
