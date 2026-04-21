# Smoke Tests

Brev H100 인스턴스(`jerryisgood-h100-80gib-vram-sxm5`)에서 설치된 환경으로 **실제 데이터 1~5건이 생성되는지** 최단 경로로 검증하기 위한 스크립트.

## 전제

- vLLM 서버가 `http://localhost:5000/v1`에서 Nemotron 3 Nano 30B A3B FP8를 서빙 중 (`--served-model-name nemotron`)
- `/home/shadeform/track3` venv 활성화 상태
- `data-designer`, `openai`, `nemoguardrails`, `nemo-curator` 패키지 설치 완료 확인됨

## 실행 순서

```bash
# 인스턴스 접속
brev shell jerryisgood-h100-80gib-vram-sxm5

# venv + 레포
source /home/shadeform/track3/bin/activate
cd /home/shadeform/jerry-is-good   # 또는 git pull 후 ~/nvidia-hackathon

# 1) 최소 호출 — chat completion 1회
python scripts/smoke/01_vllm_hello.py

# 2) reasoning parser 분리 확인
python scripts/smoke/02_vllm_reasoning.py

# 3) Data Designer 5건 생성 → output/smoke/dd_5.jsonl
python scripts/smoke/03_datadesigner_5.py
```

## 통과 기준

| 스크립트 | 성공 판정 |
|----------|----------|
| `01_vllm_hello.py` | content 필드에 의미 있는 한국어 문장 출력 |
| `02_vllm_reasoning.py` | `reasoning_content` / `content` 둘 다 비어있지 않음 |
| `03_datadesigner_5.py` | 5행 JSONL 생성 + 각 행의 `reasoning_cot` 200자 이상 |

## 환경 변수 (옵션)

- `VLLM_BASE_URL` (기본 `http://localhost:5000/v1`)
- `VLLM_MODEL` (기본 `nemotron`)
- `SMOKE_N` (기본 5)
- `SMOKE_OUT` (기본 `./output/smoke/dd_5.jsonl`)
