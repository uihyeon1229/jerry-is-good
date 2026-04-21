# 8. track3 파이프라인 구축 계획 (v1 — 스켈레톤)

> ⚠️ **이 문서는 v1 (스켈레톤 PoC)입니다.** Smoke Test 통과 후 차별화 레버를 추가한 **실전 설계 v2**는 [09-pipeline-design-v2.md](./09-pipeline-design-v2.md) 를 보세요. 최신 구현은 v2 기준.
>
> **전제**: Brev H100 인스턴스 `jerryisgood-h100-80gib-vram-sxm5`에서 venv `/home/shadeform/track3` 이 이미 구성되어 있고, vLLM + NeMo 스택이 설치된 상태에서 실제 파이프라인을 구축하기 위한 실행 계획서. 논리 설계는 [02-architecture.md](./02-architecture.md) · [03-schema.md](./03-schema.md) 참조.

## 8.0 현 시점 환경 스냅샷 (Smoke Test 결과 반영)

| 항목 | 값 |
|------|-----|
| 인스턴스 | `jerryisgood-h100-80gib-vram-sxm5` (H100 PCIe, 80GB) |
| 기본 사용자 | `shadeform` |
| venv | `/home/shadeform/track3` |
| 레포 clone 위치 | `/home/shadeform/jerry-is-good` (origin = 이 저장소) |
| vLLM | 0.17.1, tmux 세션명 `vllm` |
| vLLM 기동 명령 | `python3 -m vllm.entrypoints.openai.api_server --model /home/shadeform/models/nemotron-3-nano-fp8 --dtype auto --trust-remote-code --served-model-name nemotron --host 0.0.0.0 --port 5000 --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser-plugin ~/scripts/nano_v3_reasoning_parser.py --reasoning-parser nano_v3` |
| OpenAI 호환 엔드포인트 | `http://localhost:5000/v1`, 모델명 `nemotron` |
| Torch / CUDA | 2.10.0+cu128 / 가용 |
| Data Designer | `data-designer==0.5.7` (import: `from data_designer.interface import DataDesigner`) |
| NeMo Curator | `nemo-curator==1.1.0` |
| NeMo Guardrails | `nemoguardrails==0.21.0` |
| 추가 로컬 자산 | BAAI/bge-m3 (semantic dedup용), Qwen2.5-1.5B (백업 후보) — `.cache/huggingface/hub/` |

### 공유 포트 규칙 (중요)
- **7000~7010 사용 금지** — 다른 트랙(XBRL)이 사용.
- 우리 팀은 **5xxx / 8xxx** 대역만 사용.

## 8.1 Smoke Test 결과 (Level 0~2, 2026-04-21)

| 레벨 | 항목 | 결과 |
|-----|------|------|
| L0 | vLLM `/v1/models` ready | ✅ ready |
| L1 | `curl /v1/chat/completions` (max_tokens=2048) | ✅ content + reasoning 분리 정상 |
| L1 | `reasoning` 필드 존재 | ✅ (nano_v3 parser) |
| L2 | Data Designer `preview(num_records=5)` | ✅ 5 ok / 0 failed, ~0.23 rec/s, 479 tok/s |
| L2 | JSONL 저장 | ✅ `output/smoke/dd_5.jsonl` |

**실측 주의점**:
- Nano의 thinking이 매우 길어 `max_tokens=2048`로는 **5건 중 3건이 content 빈값**(reasoning 단계에서 예산 소진). 실전에서는 **`max_tokens>=4096`** 으로 상향 필수.
- DD는 OpenAI `message.content` 만 컬럼에 담기 때문에, content=null이면 해당 행은 `reasoning_cot=""` 로 기록됨 → 후속 필터에서 length 컷 적용.
- 생성된 2건(중급)의 CoT는 **조문 번호 환각** 포함(예: 존재하지 않는 "부가가치세법 제138조", "제115조의2"). → 우리의 **MCP 조문 context 주입 + verify_citations**가 파이프라인의 핵심 이유임이 실증됨.

### 실측 성능 (참고)
- 입력 461 tokens / 출력 10,240 tokens / total 10,701 tokens, 479 tok/s
- 4 동시 요청 (`max_parallel_requests=4` 기본값)
- 1000건 생성 예상: **~1시간** (동시성 증가 시 절반 가능)

## 8.2 디렉터리 스캐폴딩 (레포 루트 기준)

```
nvidia-hackathon/        # git repo
├── scripts/
│   ├── smoke/           # 최소 동작 확인 (이미 생성됨)
│   │   ├── 01_vllm_hello.py
│   │   ├── 02_vllm_reasoning.py
│   │   └── 03_datadesigner_5.py
│   ├── launch_vllm.sh           # tmux 세션으로 vLLM 기동 (재시작용)
│   └── collect_seeds.py         # 법제처 MCP로 시드 수집
├── pipeline/
│   ├── __init__.py
│   ├── providers.py             # ModelProvider/ModelConfig 공통 정의
│   ├── schema.py                # Sampler 축, Pydantic metadata, Judge 루브릭
│   ├── columns.py               # LLMTextColumnConfig, LLMStructuredColumnConfig 모음
│   ├── builder.py               # DataDesignerConfigBuilder 조립
│   ├── run_generate.py          # 본 생성 (N=1000 → output/raw/)
│   ├── run_guardrails.py        # NeMo Guardrails 필터
│   ├── run_curator.py           # NeMo Curator 중복/품질 필터
│   ├── run_verify_citations.py  # MCP verify → 최종 환각 제거
│   ├── curator_config.yaml
│   └── guardrails/              # rails/config.yml + flow 정의
├── training/
│   ├── sft_nemotron_nano_lora.py
│   └── configs/
├── benchmark/
│   ├── questions.jsonl          # 20문제 (수작업)
│   ├── run_before.py
│   ├── run_after.py
│   └── score_judge.py
├── cache/seeds/                 # MCP JSONL 캐시
└── output/
    ├── smoke/
    ├── raw/
    ├── filtered/
    ├── verified/
    ├── train.jsonl
    ├── eval.jsonl
    └── full.parquet
```

**왜 코드를 `/home/shadeform/jerry-is-good`가 아닌 이 레포 구조에 두는가**: 로컬에서 편집 → git push → 인스턴스 `git pull`로 동기화하는 루프가 가장 안전. 인스턴스 직접 편집은 금지.

## 8.3 핵심 파이썬 모듈 설계

### 8.3.1 `pipeline/providers.py`

```python
from data_designer.config import ModelProvider, ModelConfig, ChatCompletionInferenceParams

VLLM_PROVIDER = ModelProvider(
    name="local_vllm",
    endpoint="http://localhost:5000/v1",
    provider_type="openai",
    api_key="not-used",
)

def nemotron_model(alias: str, **overrides) -> ModelConfig:
    """역할별(alias) 생성 파라미터 프리셋."""
    params = dict(temperature=0.7, max_tokens=2048)
    params.update(overrides)
    return ModelConfig(
        alias=alias,
        model="nemotron",
        provider="local_vllm",
        inference_parameters=ChatCompletionInferenceParams(**params),
    )
```

**역할별 프리셋**:
- `question_gen`: temp=0.9, max_tokens=1024
- `cot_gen`: temp=0.7, max_tokens=2048 (thinking 포함)
- `structured`: temp=0.1, max_tokens=512 (JSON)
- `judge`: temp=0.1, max_tokens=1024, `enable_thinking=False` (빠르게)

### 8.3.2 `pipeline/builder.py`

03-schema.md의 Sampler 3축(세목/질문유형/난이도) + LLMTextColumn 2개(question, reasoning_cot) + LLMStructuredColumn 1개(metadata) + LLMJudgeColumn 1개를 조립.

```python
def build_config() -> DataDesignerConfigBuilder:
    b = DataDesignerConfigBuilder()
    for m in (nemotron_model("question_gen", temperature=0.9),
              nemotron_model("cot_gen"),
              nemotron_model("structured", temperature=0.1, max_tokens=512),
              nemotron_model("judge", temperature=0.1, max_tokens=1024)):
        b.add_model_config(m)
    _add_samplers(b)      # 세목 / 질문유형 / 난이도
    _add_law_context(b)   # applied_law_context (seed lookup)
    _add_question(b)      # LLMTextColumnConfig(name="question")
    _add_cot(b)           # LLMTextColumnConfig(name="reasoning_cot")
    _add_metadata(b)      # LLMStructuredColumnConfig
    _add_judge(b)         # LLMJudgeColumnConfig × 3축
    return b
```

### 8.3.3 `pipeline/run_generate.py`

`DataDesigner(model_providers=[VLLM_PROVIDER]).create(builder, num_records=1000, dataset_name="tax_cot_v1")` 를 실행하고 결과를 `output/raw/tax_cot_v1.jsonl` + `.parquet` 로 저장.

## 8.4 실행 순서 (Day1 오후 ~ Day2)

| 단계 | 스크립트 | 선행 조건 | 예상 시간 | 산출물 |
|-----|---------|---------|---------|-------|
| S1 | `scripts/smoke/01_vllm_hello.py` | vLLM ready | 10초 | stdout 확인 |
| S2 | `scripts/smoke/03_datadesigner_5.py` | S1 pass | 1~2분 | `output/smoke/dd_5.jsonl` |
| S3 | `scripts/collect_seeds.py` | OC 키 | 1~2시간 | `cache/seeds/*.jsonl` |
| S4 | `python -m pipeline.run_generate --n 50` | S2+S3 | 15~20분 | `output/raw/50.jsonl` (검증용) |
| S5 | 품질 수작업 검수 (C 담당) | S4 | 30분 | Go/NoGo 판정 |
| S6 | `python -m pipeline.run_generate --n 1000` | S5 GO | 3~4시간 | `output/raw/1000.jsonl` |
| S7 | `python -m pipeline.run_guardrails` | S6 | 30분 | `output/filtered/` |
| S8 | `python -m pipeline.run_curator` | S7 | 30분 | Curator 통과본 |
| S9 | `python -m pipeline.run_verify_citations` | S8 | 30분 | `output/verified/` → train.jsonl |
| S10 | `python training/sft_nemotron_nano_lora.py` | S9 | 4~6시간 | LoRA 체크포인트 |
| S11 | `python benchmark/run_before.py` | S6 (base는 이미 서빙 중) | 1시간 | answers_base.jsonl |
| S12 | `python benchmark/run_after.py` | S10 | 1시간 | answers_sft.jsonl |
| S13 | `python benchmark/score_judge.py` | S11+S12 | 30분 | report.md |

## 8.5 리스크 & 대응

| 리스크 | 감지 방법 | 대응 |
|-------|---------|------|
| max_tokens 부족으로 content=null 빈번 | S4에서 null 비율 > 10% | `max_tokens` 3072로 상향 |
| Nano의 조문 환각 | judge의 법령정확성 평균 < 3.0 | MCP `applied_law_context` 주입 필수화, prompt에 "조문은 context에서만 인용" 강제 |
| Data Designer create가 오래 걸림 | S6 단계 1시간당 진척 300건 미만 | `max_parallel_requests` 튜닝, vLLM 배치 크기 증가 |
| 다른 개발자의 포트 7xxx 충돌 | 시작 전 `ss -ltn` 확인 | 5xxx/8xxx만 사용 (이미 규칙화) |
| 인스턴스 재기동 후 vLLM 중단 | `tmux ls`로 `vllm` 세션 확인 | `scripts/launch_vllm.sh` 재실행 |
| SFT OOM (H100 80GB) | 학습 로그 OOM | LoRA rank 축소(16→8) 또는 gradient_checkpointing 활성화 |

## 8.6 다음 액션 (이 문서를 읽은 직후)

1. 로컬 레포에 `scripts/smoke/*.py` 커밋 → push (이미 작성됨)
2. Brev 인스턴스에서 `cd /home/shadeform/jerry-is-good && git pull`
3. `source /home/shadeform/track3/bin/activate`
4. `python scripts/smoke/03_datadesigner_5.py` 로 L2 smoke 통과 확인
5. `pipeline/` 모듈 스캐폴딩 (빈 파일 + 시그니처 먼저)
6. `pipeline/run_generate.py --n 5` 로 전체 체인 end-to-end 1회 스모크
7. **여기까지 PASS** → 시드 수집(S3)으로 진입

## 8.7 팀 분담 매핑 (04-roles-timeline.md 기준)

| 담당 | 이 계획서에서의 책임 구간 |
|------|----------------------|
| A (인프라) | 8.0 환경 유지, vLLM 재기동, S10 SFT, 모니터링 |
| B (파이프라인) | 8.3 모듈 구현, S4~S9 파이프라인 |
| C (도메인) | S3 시드 수집/검수, S5 품질 게이트, S13 하이라이트 |
| D (평가/발표) | S11~S13 벤치마크, 최종 report.md → 발표자료 |
