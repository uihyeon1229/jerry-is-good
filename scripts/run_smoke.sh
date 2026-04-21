#!/usr/bin/env bash
# smoke 테스트: vLLM → Data Designer preview 5건
set -euo pipefail

cd "$(dirname "$0")/.."
source /home/shadeform/track3/bin/activate
python -m pipeline.run_generate --n 5 --mode preview --name smoke
