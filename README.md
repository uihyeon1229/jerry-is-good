# Jerry Is Good — Korean Legal Reasoning Synthetic Data Pipeline

> **NVIDIA Nemotron 해커톤 2026 · Track C (합성 데이터 생성)**
>
> 한국 법률 CoT 합성 데이터를 생성하고, **정부 법령 DB**가 직접 채점하는 파이프라인.
> LLM Judge가 아닌 외부 결정론적 검증 → 환각 조문 **80% → 0%**, 실존 조문 커버리지 **35% → 79.5%**.

---

## 🎯 핵심 결과 (2026-04-22 실측)

| 지표 | Before | After | 검증자 |
|------|:---:|:---:|:---:|
| **Hallucinated citations** | 80% | **0%** | Korean Law MCP (정부 DB) |
| **Cited articles found in gov.kr** | 35% | **79.5%** | Korean Law MCP (정부 DB) |
| **Guardrails negative test** | — | **5 / 5** | 문서 [15](./15-guardrails-negative-validation.md) |
| **SFT loss (FP8→BF16 전환)** | 226 | **0.395** (600×) | 문서 [14](./14-stack-change-sft-unsloth.md) |
| **SFT 속도 (Unsloth 채용)** | 110s/step | **13s/step** (8.5×) | 문서 [14](./14-stack-change-sft-unsloth.md) |
| **Qwen 1.5B ablation · 면책 고지** | 0% | **100%** (+100pp) | 문서 [21](./21-model-size-ablation-qwen15b.md) |
| **Qwen 1.5B ablation · expected_laws cov** | 0.242 | **0.308** (+27%) | 문서 [21](./21-model-size-ablation-qwen15b.md) |

---

## 🏗️ 아키텍처 요약

```
Nemotron-Personas-Korea (1M → 10K sample → k-means → 200 대표)
    + 세목 × 질문유형 × 난이도 grid
    │
    ▼
NeMo Data Designer ─► Nemotron 3 Nano FP8 (vLLM) ─► 999 raw
    │
    ▼
Korean Law MCP verify_citations (환각 조문 검출 ← 정부 DB)
    │
    ▼
Build API Super 49B 교차검증 + A1 partial refine
    │
    ▼
NeMo Curator 8-stage (dedup · length · language · citation · judge · cluster balance)
    │                                                                  999 → 901
    ▼
NeMo Guardrails 2-tier (Regex + LLM self_check_output)       901 → 901
    │                                                                  negative 5/5
    ▼
ChatML Finalize ─► 803 train / 42 eval
    │
    ▼
Unsloth SFT (Nemotron 3 Nano 30B A3B BF16 + LoRA r=16)        loss 226→0.395 (66min)
    │
    ▼
Benchmark (score_judge + score_qualitative + NeMo Evaluator wrap)
```

**스택 14종**: Brev H100 · Nemotron 3 Nano BF16/FP8 · vLLM · NeMo Data Designer · NeMo Curator · NeMo Guardrails · NeMo Evaluator · NVIDIA Build API (embed + cross-verify) · NVIDIA NIM · Nemotron-Personas-Korea · Nsight Systems · Unsloth · Korean Law MCP · sklearn(cuML 대체) — 상세 [문서 22](./22-tech-stack-and-pipeline-summary.md) / [문서 18](./18-stack-usage-actual-vs-planned.md).

---

## 🛠️ 환경 설정

### 재현 대상

- **1× NVIDIA H100 80GB SXM5** (Brev Cloud 검증; A100 80GB도 동작)
- Ubuntu 22.04
- Python 3.10

### 1) 레포 클론

```bash
git clone https://github.com/uihyeon1229/jerry-is-good.git
cd jerry-is-good
```

### 2) 시스템 환경

```bash
# (Brev 인스턴스의 경우) 기본 파이프라인용 venv
python3 -m venv ~/venv_pipeline
source ~/venv_pipeline/bin/activate

pip install -U pip
pip install -r requirements.txt   # NeMo Data Designer / Curator / Guardrails / Evaluator, vLLM, Build API 등
pip install datasketch             # Curator fuzzy dedup용
pip install python-pptx streamlit openai mcp
```

### 3) SFT 전용 venv (Unsloth + torch 2.7.1)

```bash
# /ephemeral 가 없으면 ~/venvs 로 변경 가능
python3 -m venv /ephemeral/venvs/unsloth
source /ephemeral/venvs/unsloth/bin/activate

TMPDIR=/ephemeral/tmp PIP_CACHE_DIR=/ephemeral/cache/pip \
uv pip install "torch==2.7.1" "triton>=3.3.0" numpy pillow torchvision bitsandbytes \
    "transformers==4.56.2" "trl==0.22.2" \
    "unsloth_zoo @ git+https://github.com/unslothai/unsloth-zoo" \
    "unsloth @ git+https://github.com/unslothai/unsloth" \
    datasets accelerate peft pyyaml

# Mamba kernels (--no-build-isolation 필수)
TMPDIR=/ephemeral/tmp PIP_CACHE_DIR=/ephemeral/cache/pip \
pip install --no-build-isolation "mamba_ssm==2.2.5" "causal_conv1d==1.5.2"
```

### 4) 필수 환경변수

```bash
export LAW_OC=<본인 법제처 Open API OC>          # Korean Law MCP 인증
export NVIDIA_BUILD_API_KEY=nvapi-xxxxx          # Build API (embed + cross-verify)
export VLLM_BASE_URL=http://localhost:5000/v1
export VLLM_MODEL=nemotron
export USE_PERSONA_AFFINITY=1
export PIPELINE_MAX_PARALLEL=16
```

### 5) vLLM 기동 (Nemotron 3 Nano 30B, 생성·서빙용)

```bash
# 생성·추론용 (FP8)
tmux new -d -s vllm_gen 'python -m vllm.entrypoints.openai.api_server \
    --model nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 \
    --served-model-name nemotron \
    --host 0.0.0.0 --port 5000 \
    --max-model-len 8192 --trust-remote-code \
    --gpu-memory-utilization 0.92'

# Tool-use 데모용 (파서 포함)
#   --enable-auto-tool-choice --tool-call-parser qwen3_coder  추가
```

상세: 문서 [22 §5](./22-tech-stack-and-pipeline-summary.md), [19](./19-live-demo-tool-use.md).

---

## 📈 학습 방법

### 합성 데이터 생성 → SFT 전 과정

```bash
# [0] 페르소나 준비 (한 번만)
python -m pipeline.fetch_personas           # 1M → 10K 샘플
python -m scripts.cluster_personas          # 10K → 200 대표 (NVIDIA embed + k-means)

# [1] L1 raw 생성 (Nemotron Data Designer, ~55분)
python -m pipeline.run_generate --mode create --n 1000 --name tax_cot_v3 \
    --out output/raw/tax_cot_v3_1000.jsonl

# [2] L2 조문 실존 검증 (Korean Law MCP)
python -m pipeline.run_verify_citations \
    --input output/raw/tax_cot_v3_1000.jsonl \
    --output output/verified/tax_cot_v3_verified.jsonl

# [3] A1 부분 refine (저품질 세목만 재생성)
python -m pipeline.run_partial_refine \
    --input output/verified/tax_cot_v3_verified.jsonl \
    --output output/refined/tax_cot_v3_refined.jsonl

# [4] NeMo Curator 8단계 (~11분)
python -m pipeline.run_curator --config pipeline/curator_config.yaml \
    --input output/refined/tax_cot_v3_refined.jsonl \
    --output output/curated/tax_cot_v3_curated.jsonl

# [5] NeMo Guardrails 2-tier (~40초, Build API 경유)
python -m pipeline.run_guardrails --config pipeline/guardrails/config.yml \
    --input output/curated/tax_cot_v3_curated.jsonl \
    --output output/safe/tax_cot_v3_safe.jsonl \
    --base-url https://integrate.api.nvidia.com/v1 \
    --model "nvidia/llama-3.3-nemotron-super-49b-v1"

# [6] ChatML Finalize (train/eval split)
python -m pipeline.run_finalize_train \
    --input output/safe/tax_cot_v3_safe.jsonl \
    --output-dir output/final
# → output/final/train.jsonl (803) + eval.jsonl (42) + filter_stats.json
```

### SFT 실행 (Unsloth, H100 1장, ~66분)

```bash
# Unsloth venv 활성화
source /ephemeral/venvs/unsloth/bin/activate

# 2-phase 자동 체인 (Phase 1 dry-run 500×1ep → Phase 2 전량 3ep resume)
bash scripts/launch_sft_chain.sh

# 출력: training/checkpoints/tax_cot_lora_v2/final (LoRA 어댑터)
```

개별 실행:

```bash
# Phase 1 dry-run
SFT_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
TRAIN_INPUT=output/final/train.jsonl \
OUTPUT_DIR=training/checkpoints/tax_cot_lora_v2 \
NUM_EPOCHS=1 SFT_MAX_SAMPLES=500 SFT_RESUME=0 LR=2e-4 \
python training/sft_unsloth.py

# Phase 2 full
NUM_EPOCHS=3 SFT_MAX_SAMPLES=0 SFT_RESUME=1 LR=2e-4 \
python training/sft_unsloth.py
```

### (부록) Model Size Ablation — Qwen 2.5-1.5B

```bash
UNSLOTH_FORCE_COMPILE=0 ATTN_IMPL=sdpa \
SFT_MODEL=Qwen/Qwen2.5-1.5B-Instruct \
TRAIN_INPUT=output/final/train.jsonl \
OUTPUT_DIR=/ephemeral/training_checkpoints/qwen15b_tax_lora \
NUM_EPOCHS=3 BATCH_SIZE=4 GRAD_ACCUM=2 LR=2e-4 \
python training/sft_unsloth.py
# → 132초에 학습 완료, train_loss 0.601
```

---

## 🔬 평가 단계

### 1) vLLM에 Base + LoRA 핫어태치 서빙

```bash
tmux new -d -s vllm_serve 'python -m vllm.entrypoints.openai.api_server \
    --model nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    --served-model-name nemotron-base \
    --enable-lora \
    --lora-modules tax_lora=training/checkpoints/tax_cot_lora_v2/final \
    --max-lora-rank 16 --max-loras 2 \
    --host 0.0.0.0 --port 5000 --max-model-len 8192 \
    --trust-remote-code --gpu-memory-utilization 0.90'
```

### 2) Before/After 답변 수집

```bash
# Base
VLLM_MODEL=nemotron-base python -m benchmark.run_generate \
    --questions benchmark/questions.jsonl \
    --output benchmark/answers_base.jsonl --tag base \
    --model nemotron-base --max-tokens 3000 --temperature 0.3

# Fine-tuned
VLLM_MODEL=tax_lora python -m benchmark.run_generate \
    --questions benchmark/questions.jsonl \
    --output benchmark/answers_sft.jsonl --tag sft \
    --model tax_lora --max-tokens 3000 --temperature 0.3
```

### 3) 4축 정량 채점 (score_judge) + 정성 보조 (score_qualitative) + 샘플 diff

```bash
NVIDIA_BUILD_API_KEY=... LAW_OC=... python -m benchmark.score_judge \
    --before benchmark/answers_base.jsonl \
    --after benchmark/answers_sft.jsonl \
    --output benchmark/report.md

python -m benchmark.score_qualitative \
    --before benchmark/answers_base.jsonl \
    --after benchmark/answers_sft.jsonl \
    --output benchmark/report_qualitative.md

python -m benchmark.extract_diff_samples \
    --before benchmark/answers_base.jsonl \
    --after benchmark/answers_sft.jsonl \
    --top-k 4 --output benchmark/sample_diffs.md
```

### 4) NeMo Evaluator 공식 스키마로 래핑

```bash
python -m benchmark.nemo_evaluator_wrap \
    --in benchmark/report.json \
    --out benchmark/nemo_evaluator_result.json
```

**채점자 편향 주의**: 우리는 **외부 Korean Law MCP(정부 DB)** 와 **NVIDIA Build API Super 49B** 를 독립 평가자로 쓰고, L2 valid_ratio 는 학습 필터에 사용했으므로 **보조 지표**로만 다룹니다. 상세: 문서 [17 §1.1](./17-benchmark-report-and-analysis.md).

---

## 🎥 데모 실행 가이드

### Demo 1 — Tool-use 라이브 (발표 최대 하이라이트)

Nemotron이 질문을 받자마자 `search_korean_law` tool을 호출 → Korean Law MCP가 법제처 DB에서 조문 실시간 조회 → Nemotron이 그 조문 원문을 인용해 최종 답변.

```bash
# vLLM 기동 (tool-use 파서 포함)
tmux new -d -s vllm_tool 'python -m vllm.entrypoints.openai.api_server \
    --model nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    --served-model-name nemotron \
    --host 0.0.0.0 --port 5000 --max-model-len 8192 \
    --trust-remote-code --gpu-memory-utilization 0.92 \
    --enable-auto-tool-choice --tool-call-parser qwen3_coder'

# CLI 실행
LAW_OC=... python demo/nemotron_tool_call.py \
    --q "소득세법 제47조의 근로소득공제 내용을 알려주세요."

# 또는 Streamlit 3단계 UI (1차 tool_call → MCP → 2차 답변)
LAW_OC=... VLLM_BASE_URL=http://localhost:5000/v1 VLLM_MODEL=nemotron \
    streamlit run demo/app_toolcall.py --server.port 8700 --server.address 0.0.0.0
```

Smoke test 결과 (4/4 성공): [`artifacts/toolcall_smoke_log.md`](./artifacts/toolcall_smoke_log.md) · 실행 가이드: [문서 19](./19-live-demo-tool-use.md).

### Demo 2 — Base vs Fine-tuned 병렬 비교

동일 질문을 좌(원본)·우(우리 LoRA) 두 모델에 동시 발송, 차이를 시각적으로 확인.

```bash
# Qwen 1.5B 기준 비교 (ablation, 가장 차이 큼)
tmux new -d -s vllm_qwen 'python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-1.5B-Instruct \
    --served-model-name qwen15b-base \
    --enable-lora \
    --lora-modules qwen_tax_lora=/ephemeral/training_checkpoints/qwen15b_tax_lora/final \
    --max-lora-rank 16 --max-loras 2 \
    --host 0.0.0.0 --port 5000 --max-model-len 4096 \
    --trust-remote-code --gpu-memory-utilization 0.60'

MODEL_BASE=qwen15b-base MODEL_FT=qwen_tax_lora \
LABEL_BASE="⚪ Base (Qwen 2.5-1.5B)" LABEL_FT="🟢 Fine-tuned (+ 한국 법률 LoRA)" \
VLLM_BASE_URL=http://localhost:5000/v1 \
    streamlit run demo/app_compare.py --server.port 8700 --server.address 0.0.0.0
```

### Windows에서 영상 녹화

로컬 Windows 쪽은 [`demo/record_windows_guide.md`](./demo/record_windows_guide.md) — PowerShell Claude Code에 문서 통째로 전달하면 ffmpeg 설치·Chrome 오픈·화면 녹화·종료까지 자동화.

---

## 📁 디렉토리 구조

```
jerry-is-good/
├── pipeline/                   # NeMo Data Designer + Curator + Guardrails 파이프라인
│   ├── builder.py / columns.py / providers.py / refine_loop.py
│   ├── run_generate.py         # L1 raw 생성
│   ├── run_verify_citations.py # L2 MCP 조문 검증
│   ├── run_partial_refine.py   # A1 부분 재생성 루프
│   ├── run_curator.py          # Curator 8-stage (하이브리드)
│   ├── curator_config.yaml
│   ├── run_guardrails.py       # Guardrails 2-tier (고속 배치)
│   ├── run_guardrails_llmrails_smoke.py  # LLMRails SDK smoke
│   ├── guardrails/config.yml · guardrails_sdk/config.yml
│   ├── run_finalize_train.py   # ChatML 변환
│   ├── embed_nvidia.py         # NVIDIA Build API 임베딩 래퍼
│   ├── personas.py · fetch_personas.py
│   └── validators/             # citation_validator, build_api_cross, drift_detector
│
├── training/
│   └── sft_unsloth.py          # Unsloth LoRA SFT (Nemotron 30B + Qwen 1.5B 공통)
│
├── benchmark/
│   ├── questions.jsonl         # 20문제
│   ├── run_generate.py         # base/FT 답변 수집
│   ├── score_judge.py          # 4축 정량 (expected_laws · cross_overlap · L2)
│   ├── score_qualitative.py    # 정성 (disclaimer · refusal · CoT · citation)
│   ├── extract_diff_samples.py # Top-K Before/After diff
│   └── nemo_evaluator_wrap.py  # NeMo Evaluator 스키마 래핑
│
├── demo/
│   ├── nemotron_tool_call.py   # Tool-use CLI
│   ├── app_toolcall.py         # Tool-use Streamlit 3단계 UI
│   ├── app_compare.py          # Base vs FT 좌/우 분할 UI (env var로 모델 교체 가능)
│   ├── ask_compare.sh          # CLI 비교 호출
│   ├── demo_questions.txt      # 시연 질문 7종
│   └── record_windows_guide.md # Windows PowerShell 녹화 자동화 가이드
│
├── scripts/
│   ├── launch_vllm.sh          # vLLM 기동
│   ├── launch_sft_chain.sh     # SFT 2-phase 자동 체인
│   ├── cluster_personas.py     # k=200 페르소나 클러스터링
│   ├── nsight_capture.sh       # Nsight 프로파일 캡처
│   └── ...
│
├── artifacts/
│   ├── nsight/vllm_base_startup.nsys-rep   # Nsight Systems 트레이스
│   ├── toolcall_smoke_log.md               # Tool-use 4/4 성공 trace
│   ├── nemoguardrails_llmrails_smoke.json  # LLMRails SDK smoke 결과
│   ├── guardrails_negative_test.jsonl      # Guardrails negative set
│   └── guardrails_negative_result*.jsonl   # 5/5 실측
│
├── output/                     # 파이프라인 산출물 (raw/verified/refined/curated/safe/final) — gitignore
├── requirements.txt
├── README.md                   # (이 파일) 심사 제출용
├── README_INTERNAL.md          # 팀 내부 브리핑 (초기 계획·타임라인·역할)
└── 01~22-*.md                  # 단계별 설계·구현·결과 문서 (아래 '문서 목록' 참조)
```

---

## 📚 문서 목록 (필수 읽기 순서)

| 번호 | 제목 | 역할 |
|:-:|------|------|
| **22** | [기술 스택·파이프라인 1페이지 요약](./22-tech-stack-and-pipeline-summary.md) | **제일 먼저** (전체 30분 이해) |
| **17** | [벤치마크 리포트 (정량·정성)](./17-benchmark-report-and-analysis.md) | 실측 수치 근거 |
| **21** | [Qwen 1.5B Model Size Ablation](./21-model-size-ablation-qwen15b.md) | 데이터 효과 변수 통제 증명 |
| **14** | [SFT 스택 교체 (FP8→BF16, HF→Unsloth)](./14-stack-change-sft-unsloth.md) | 학습 기술 의사결정 |
| **15** | [Guardrails Negative Validation 5/5](./15-guardrails-negative-validation.md) | 안전성 양방향 실증 |
| **18** | [스택 실구현 vs 계획 매핑](./18-stack-usage-actual-vs-planned.md) | Q&A 방어 |
| **19** | [Tool-use 라이브 데모 가이드](./19-live-demo-tool-use.md) | 발표 하이라이트 실행 |
| **16** | [Base vs FT 데모 설계 · 발표자 핸드오프](./16-demo-video-finetuned-vs-base.md) | 데모 2종 설계 |
| **20** | [발표 경쟁력 평가 + 전략](./20-presentation-competitiveness-strategy.md) | 레버·Go/No-Go·백업 |
| 12 | [발표 최종 오버뷰 (단일 소스)](./12-presentation-final.md) | 슬라이드 대본 |
| 13 | [합성 데이터 대표 샘플](./13-sample-outputs.md) | PPT 복붙용 |
| 10 | [아키텍처 개요 (원 계획)](./10-architecture-overview.md) | 초기 설계 |
| 11 | [파이프라인 고도화 9종](./11-pipeline-advanced.md) | 구현 상세 |
| 09 | [5대 레버 상세 설계](./09-pipeline-design-v2.md) | 전략 근거 |
| 01–08 | 초기 전략·아키텍처·스키마·일정 | 배경 |

---

## ⚠️ 채점 편향 주의 (Evaluator Bias Disclosure)

1. **L2 `valid_ratio`** 는 **학습 데이터 필터에 사용**했으므로 채점 지표로는 **보조**로만 쓰고, 상승폭을 과대 해석하지 않습니다.
2. **주 지표**는 (a) 사람 지정 `expected_laws` 커버리지, (b) NVIDIA Build API Super 49B 독립 교차 검증(`cross_overlap`) 입니다.
3. **정부 DB 기반 hallucination 80→0%, gov.kr 존재 커버리지 35→79.5%** 수치는 **Korean Law MCP(외부 결정론)** 가 매긴 것이며, LLM Judge와 무관합니다.

상세: [문서 17 §1.1](./17-benchmark-report-and-analysis.md), [문서 12 §7-3](./12-presentation-final.md).

---

## 👥 팀 · 라이선스

- **팀**: jerryisgood (회계법인 소속 개발자 4인)
- **코드 라이선스**: MIT
- **데이터셋·어댑터 공개**: HuggingFace Hub MIT / CC-BY 검토 중
- **발표 자료**: `C:\Users\ejeong015\Downloads\jerry_is_good (1) _with_notes.pptx`

### 발표 영상

- **Tool-use 라이브 데모** (Windows 녹화, 가이드 [`demo/record_windows_guide.md`](./demo/record_windows_guide.md))
- **Base vs Fine-tuned 비교**
- 최종 편집본은 YouTube unlisted + 본 README 업데이트 예정

### 감사

- NVIDIA Nemotron Developer Hackathon 2026 운영진
- [nvidia/Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) 공개 데이터
- Korean Law MCP (`https://korean-law-mcp.fly.dev`) — 법제처 Open API 래퍼
- Unsloth AI — 단일 H100 Nemotron 3 Nano LoRA SFT 공식 레시피

---

**재현 문의**: GitHub Issues
