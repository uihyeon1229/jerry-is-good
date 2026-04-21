# 9. 파이프라인 설계 v2 — 차별화 축 확정판

> **목적**: 8번 문서의 "스켈레톤 PoC" 결과를 바탕으로, **남들과 차별화되는 파이프라인** 구조를 박아넣기 위한 최종 설계. Day1 본 생성 시작 전에 팀 전원이 alignment해야 하는 문서.
>
> 작성: 2026-04-21 / Smoke Test 통과 이후 / 팀 논의 반영

## 9.1 왜 v2인가

v1 (8번 문서) 스켈레톤 검증 결과:
- Data Designer end-to-end 3건 완전 통과 (fill_rate 100%)
- 그러나 **모델이 뱉은 조문이 실존하지 않음** (예: "부가가치세법 제138조" — 실제론 존재 X)
- 즉 공식 가이드대로 만들면 **"환각 CoT 데이터"**가 생성됨 → 그대로 발표하면 경쟁력 없음

**v2의 질문 하나**:
> "남들과 똑같이 돌리면 똑같이 환각 생긴다. 어떻게 하면 **우리 데이터셋만 조문이 실제로 맞는가**?"

답 = **5중 차별화 레버** (아래).

## 9.2 5중 차별화 레버 (확정)

| # | 레버 | 역할 | 비용 | 효과 |
|---|-----|------|-----|------|
| **L1** | **법제처 조문을 프롬프트에 Seed Context로 주입** | 환각 **사전 차단** | 중 | 조문 실존율 ~90%+ 예상 |
| **L2** | **법제처 API로 결정론적 조문 존재성 검증** (LLM Judge 이전) | 환각 **사후 제거** | 중 | legal_accuracy 객관 지표 확보 |
| **L3** | **계산 문제의 수치를 Python으로 재계산·검증** | 수치 **정답 보장** | 상 | "계산도 맞는다" 서사 |
| **L4** | **Nemotron-Personas-Korea로 질문 다양성 주입** (+조건부 난이도 매핑) | 데이터셋 **쓸모** 차별화 | 중 | 질문 현실성↑, NVIDIA 스택 +1 |
| **L5** | **Nemotron + MCP Tool-use 라이브 데모** | 발표 **임팩트** | 하 | "Nemotron이 법제처를 직접 호출" |

보너스 (저비용):
- **L6** Curator의 semantic cluster 다양성 강제
- **L7** Nsight Systems GPU 프로파일 캡처 ("실측 증빙")
- **L8** SFT Before/After 벤치마크 — 기존 계획 (+ L2 채점자 재사용으로 객관성↑)

### 중요: L1과 L4의 역할 분리

**조문 context (L1)은 "reasoning_cot 프롬프트"에만 주입.**
**페르소나 (L4)는 "question 프롬프트"에만 주입.**

조문에 페르소나를 섞으면 "이 40대 교사는 소득세법 제20조가…" 같이 주관이 법령 해석을 오염시킴. 분리가 원칙.

## 9.3 NVIDIA 스택 9종 (확정)

| # | 기술 | 역할 |
|---|------|------|
| 1 | Brev.dev | H100 인프라 |
| 2 | Nemotron 3 Nano 30B A3B FP8 | 생성 LLM |
| 3 | vLLM + nano_v3 reasoning parser | OpenAI 호환 서빙 |
| 4 | NeMo Data Designer | 파이프라인 엔진 |
| 5 | NeMo Curator | dedup + 품질 + cluster 다양성 |
| 6 | NeMo Guardrails | 탈세/PII 차단 |
| 7 | NeMo Framework (SFT LoRA) | Nemotron 파인튜닝 |
| 8 | NVIDIA Build API / Nsight | 외부 검증 + GPU 프로파일 |
| **9** | **Nemotron-Personas-Korea** | **질문 다양성 Seed** ← 신규 |

+ 외부: **Korean Law MCP (chrisryugj/korean-law-mcp)** + **법제처 Open API**

## 9.4 최종 아키텍처 (v2)

```
┌─────────────────────────────────────────────────────────────────┐
│ [S0] 시드 준비 (Day1 아침, 1회)                                  │
│                                                                 │
│  ① 법제처 Open API → 4개 세목 × 각 법령/시행령 조문 전문         │
│     scripts/collect_seeds.py                                   │
│     → cache/seeds/{income,corporate,vat,inher}.jsonl            │
│                                                                 │
│  ② Nemotron-Personas-Korea (HF)                                 │
│     pipeline/fetch_personas.py                                  │
│     → cache/personas/korea_10k.jsonl (10,000명 샘플)             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S1] Data Designer 생성 (Day1 오후)                              │
│                                                                 │
│  Sampler (결정론적):                                             │
│    ├ 세목 (8 categories)                                         │
│    ├ 질문유형 (4 categories)                                     │
│    ├ 페르소나 (10,000명 index) ← L4                              │
│    └ 난이도 (conditional on persona.education_level) ← L4        │
│                                                                 │
│  Seed Context (DataFrameSeedSource):                            │
│    └ 세목별 조문 텍스트 lookup ← L1                              │
│                                                                 │
│  LLM Columns:                                                   │
│    ├ question (페르소나 + 세목 주입)                             │
│    ├ reasoning_cot (세목 조문 context 주입)                      │
│    ├ metadata (TaxMetadata — applied_law_mst[] 추출)             │
│    └ quality_score (legal/cot/utility × 1-5)                    │
│                                                                 │
│  → output/raw/tax_cot_{N}.jsonl                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S2] 결정론적 조문 검증 (Day1 저녁) ← L2                          │
│                                                                 │
│  pipeline/validators/citation_validator.py                      │
│    regex로 조문 후보 추출                                        │
│    → 법제처 API 조회                                             │
│    → cited_laws_valid_ratio 계산                                │
│    → < 0.7 인 행 제거                                            │
│                                                                 │
│  → output/verified/*.jsonl (예상 통과율 85%)                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S3] 계산 검증 (Day1 저녁) ← L3                                  │
│                                                                 │
│  pipeline/validators/calc_validator.py                          │
│    질문유형 == "계산문제"인 행만 처리                            │
│    최종 답과 내부 계산식을 sympy/float 파싱                      │
│    → calc_mismatch > 5% 인 행 제거                               │
│                                                                 │
│  → output/calc_ok/*.jsonl                                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S4] Guardrails (탈세/PII/폐지 조문)                             │
│  pipeline/run_guardrails.py                                    │
│  → output/safe/*.jsonl                                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S5] Curator (dedup + 품질 + 의미 cluster 다양성) ← L6           │
│  pipeline/run_curator.py                                       │
│  → output/final/{train,eval}.jsonl                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S6] SFT (Day1 밤 → Day2 새벽) ← L8                              │
│  training/sft_nemotron_nano_lora.py                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S7] Before/After 벤치마크 (Day2 오전) ← L7,L8                   │
│  benchmark/score_judge.py  (legal_accuracy는 L2 검증자 재사용)   │
│  benchmark/nsight_capture.sh                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [S8] 발표용 라이브 tool-use 데모 ← L5                            │
│  demo/nemotron_tool_call.py                                     │
│  (Nemotron이 tool_call로 법제처 조회 → 답변)                     │
└─────────────────────────────────────────────────────────────────┘
```

## 9.5 레버 L1 — Seed Context 주입 상세

### 데이터 흐름

```python
# pipeline/seeds.py
load_seed_jsonl(세목) -> pd.DataFrame(columns=["세목", "조문번호", "조문텍스트", "mst"])
```

### DataFrameSeedSource 등록

```python
# pipeline/builder.py
from data_designer.config import DataFrameSeedSource

builder.with_seed_dataset(
    DataFrameSeedSource(
        name="law_corpus",
        dataframe=load_all_seed_laws(),
        sampling_strategy="filter_by",
        filter_column="세목",
    )
)
```

### reasoning_cot 프롬프트 수정

```
...
질문: {{ question }}

**반드시 아래 조문만 인용하여 답하세요. 아래에 없는 조문 번호는 절대 만들지 마세요.**

아래는 {{ 세목 }} 관련 현행 조문입니다:
{% for row in law_corpus[:5] %}
- {{ row.조문번호 }}: {{ row.조문텍스트[:500] }}
{% endfor %}

지침: 각 단계를 명확히 구분, 조문은 위 목록에서만 인용, 계산은 숫자 근거 제시.
```

### 리스크
- 조문 텍스트 너무 길면 토큰 초과 → 조문당 500자로 자르고, 세목당 Top-5 선별 (자주 쓰이는 조문 우선)
- Top-5 선별 로직: seeds 수집 시 "중요도 순"으로 정렬 (예: 소득세법은 §20, §47, §51 먼저)

## 9.6 레버 L2 — Korean Law MCP 기반 결정론적 조문 검증 (개정)

### 왜 MCP인가 (2026-04-21 실측 기반)

- `https://korean-law-mcp.fly.dev/mcp?oc=<OC>`는 Brev 방화벽을 통과 (`law.go.kr` 직접 호출은 차단됨)
- MCP의 `verify_citations(text, maxCitations)` 한 번 호출로 **추출 + 법제처 DB 매칭 + 환각 플래그**가 모두 처리됨. 우리가 regex/캐시/배치를 다시 짤 필요 없음
- 응답 포맷: `✓ 실존 / ✗ NOT_FOUND / ⚠ 확인필요` + `[HALLUCINATION_DETECTED]` 플래그 헤더
- 발표 서사: "**법제처 공식 MCP를 Nemotron 파이프라인에 통합**" (직접 HTTP 호출 대비 훨씬 강력)

### 우리가 구현할 것

1. `pipeline/validators/citation_validator.py` — 얇은 비동기 래퍼
   - 입력: `reasoning_cot` 텍스트
   - `mcp.ClientSession` + `streamablehttp_client` 로 연결
   - `call_tool("verify_citations", {"text": cot, "maxCitations": 15})`
   - 응답 텍스트 파싱 → `{total, valid, invalid, warnings, has_hallucination, invalid_refs[]}` dict
2. `pipeline/run_verify_citations.py` — JSONL 파이프라인 단계
   - `output/raw/*.jsonl` 읽어 각 행에 대해 validator 호출
   - 컬럼 추가: `cited_laws_total`, `cited_laws_valid`, `cited_laws_valid_ratio`, `has_hallucination`
   - `valid_ratio < 0.7` 또는 `has_hallucination=True` 면 제거

### 속도 최적화

- 동시성: `asyncio.Semaphore(8)` 로 최대 8개 병렬 호출
- 캐시 레이어 (선택): `hash(cot)` → 결과 dict 로컬 디스크 캐시 (재실행 비용↓)
- fly.dev 한도 초과시 retry with backoff

### 출력 포맷 예시

```json
{
  "question": "...",
  "reasoning_cot": "...",
  "cited_laws_total": 3,
  "cited_laws_valid": 1,
  "cited_laws_warning": 1,
  "cited_laws_invalid": 1,
  "cited_laws_valid_ratio": 0.33,
  "has_hallucination": true,
  "invalid_refs": ["부가가치세법 제999조"]
}
```

## 9.7 레버 L3 — 계산 검증 상세

### 검증 대상

`질문유형 == "계산문제"` 인 행만.

### 검증 로직

1. `final_answer`에서 수치 추출 (정규식: `[\d,]+\s*원` 등)
2. `reasoning_cot`에서 계산식 블록 추출 (예: "`8000 * 0.05 = 400`" 또는 "`공제액 = 매출액 × 5%`")
3. sympy로 계산식 파싱 → 재계산
4. 재계산 결과 vs `final_answer` 비교, `|Δ|/answer > 5%` 면 실패

### 안전성

- `eval` 절대 금지 — sympy의 `sympify`로 제한
- 실패 시 제거가 아닌 **`calc_verified=false` 플래그만** 붙이고 발표용 통계 확보 (제거는 SFT 학습용 train.jsonl 만들 때)

## 9.8 레버 L4 — Nemotron-Personas-Korea 상세

### 다운로드·샘플링

```python
# pipeline/fetch_personas.py
from datasets import load_dataset
ds = load_dataset("nvidia/Nemotron-Personas-Korea", split="train")
sample = ds.shuffle(seed=42).select(range(10000))
sample.to_json("cache/personas/korea_10k.jsonl", force_ascii=False)
```

### 사용 필드 (10개)

- `age`, `gender`, `occupation`, `education_level`, `family_status`, `residence_type`, `annual_income_bracket`, `dependents_count`, `region`, `tone_preference`

### 조건부 난이도 매핑

```python
# pipeline/schema.py 추가
NANDO_CONDITIONAL_ON_EDUCATION = {
    "고졸이하":      {"기초": 0.60, "중급": 0.35, "고급": 0.05},
    "전문대/학사":   {"기초": 0.30, "중급": 0.50, "고급": 0.20},
    "석사/박사":     {"기초": 0.10, "중급": 0.40, "고급": 0.50},
    "세무사/변호사": {"기초": 0.00, "중급": 0.20, "고급": 0.80},
}
```

DD의 `SamplerColumnConfig.conditional_params` 로 구현.

### question 프롬프트 수정

```
당신은 한국 세법 전문가입니다.
아래 페르소나의 납세자가 가질 법한 질문 하나를 만드세요.

페르소나:
- 나이/성별: {{ persona.age }}세 {{ persona.gender }}
- 직업: {{ persona.occupation }}
- 학력: {{ persona.education_level }}
- 가족 상태: {{ persona.family_status }}
- 거주: {{ persona.residence_type }}, {{ persona.region }}
- 연 소득 구간: {{ persona.annual_income_bracket }}
- 부양가족: {{ persona.dependents_count }}명
- 말투: {{ persona.tone_preference }}

조건:
- 세목: {{ 세목 }}
- 질문유형: {{ 질문유형 }}
- 난이도: {{ 난이도 }}

질문 한 문장 혹은 한 단락만 출력하세요. 페르소나의 상황이 자연스럽게 배어나오도록.
```

### 발표용 분포 차트

생성된 1000건의 페르소나 분포 (나이 히스토그램, 직업 파이차트, 지역 지도)를 발표 슬라이드에 포함. *"우리는 대한민국 인구 분포를 모사한 페르소나로 질문을 생성했다"*.

## 9.9 레버 L5 — Tool-use 라이브 데모

### 구조

```python
# demo/nemotron_tool_call.py
tools = [{
    "type": "function",
    "function": {
        "name": "search_korean_law",
        "description": "한국 법령 조문을 실시간으로 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "law_name": {"type": "string"},
                "article_no": {"type": "integer"},
            },
            "required": ["law_name", "article_no"],
        },
    },
}]
# vLLM에 질문 → tool_call 발생 → 법제처 API 호출 → 결과 넣어서 재요청 → 최종 답변
```

### 시연 시나리오

```
[사용자] 소득세법 제47조의 정확한 내용은?
[Nemotron] (tool_call → 법제처 조회) 조문 내용은 다음과 같습니다: …
```

vLLM에 이미 `--enable-auto-tool-choice --tool-call-parser qwen3_coder` 가 켜져 있어 추가 세팅 거의 없음.

## 9.10 파일 구조 (v2 최종)

```
pipeline/
├── __init__.py
├── settings.py
├── providers.py            # (v1 유지)
├── schema.py               # + NANDO_CONDITIONAL_ON_EDUCATION, PERSONA_FIELDS
├── columns.py              # + persona 컬럼, seed_context 주입 프롬프트
├── builder.py              # + with_seed_dataset, persona sampler
├── seeds.py                # 신규 — 조문 JSONL → DataFrame
├── personas.py             # 신규 — 페르소나 JSONL → DataFrame, index sampler
├── fetch_personas.py       # 신규 — HF에서 1회 다운로드
├── run_generate.py
├── run_verify_citations.py # 신규 — L2
├── run_calc_validate.py    # 신규 — L3
├── run_guardrails.py
├── run_curator.py
├── validators/
│   ├── __init__.py
│   ├── citation_validator.py  # 신규 — L2 코어
│   └── calc_validator.py      # 신규 — L3 코어
├── guardrails/config.yml
└── curator_config.yaml

demo/
├── nemotron_tool_call.py   # L5
└── README.md

benchmark/
├── questions.jsonl
├── run_before.py
├── run_after.py
├── score_judge.py          # L2 citation_validator 재사용
└── nsight_capture.sh

scripts/
├── launch_vllm.sh
├── collect_seeds.py        # 기존
├── run_smoke.sh
├── run_generate_50.sh
└── run_pipeline_full.sh    # 신규 — S1 → S5 순차 실행

cache/
├── seeds/{income,corporate,vat,inher}.jsonl
├── personas/korea_10k.jsonl
└── law_exists.json          # L2 캐시
```

## 9.11 실행 순서 (Day1/Day2)

| 시간 | 단계 | 담당 |
|------|-----|------|
| Day1 09~10 | S0: `collect_seeds.py` + `fetch_personas.py` | B |
| Day1 10~13 | pipeline 모듈 구현 (seeds, personas, validators, builder) | B |
| Day1 13~14 | 50건 드라이런 (`--mode preview`) | B+C |
| Day1 14~15 | 검수, 프롬프트 튜닝 | C |
| Day1 15~18 | `run_generate --n 1000` (백그라운드) + 다른 모듈 작성 | 전원 |
| Day1 18~20 | S2 (citation), S3 (calc), S4 (guardrails), S5 (curator) 순차 실행 | B |
| Day1 20~22 | train.jsonl 확정 + Before 채점 시작 | B+D |
| Day1 22~ | SFT 학습 시작 (백그라운드 밤샘) | A |
| Day2 06~09 | SFT 완료, After 채점, 차트 제작 | A+D |
| Day2 09~12 | L5 tool-use 데모 + Nsight 캡처 + 발표자료 통합 | A+D |
| Day2 13~ | 리허설 → 발표 | 전원 |

## 9.12 성공 기준 (수치)

| 지표 | 목표 | 측정 |
|------|-----|------|
| 생성 완료 건수 | ≥ 500건 | output/final/train.jsonl |
| cot fill_rate | ≥ 95% | reasoning_cot 비어있지 않은 행 비율 |
| **cited_laws_valid_ratio 평균** | **≥ 0.90** | **L2 핵심 KPI** |
| calc_verified 비율 (계산문제 중) | ≥ 0.80 | L3 KPI |
| Judge 평균 | ≥ 3.5 | quality_score 평균 |
| SFT Before→After legal_accuracy 상승폭 | ≥ +15% | L2 검증자 채점 |
| 페르소나 분포 | 연령 3세대·지역 5권역 이상 커버 | 히스토그램 |

## 9.13 리스크 & 대응 (v2 업데이트)

| 리스크 | 감지 | 대응 |
|-------|------|------|
| 조문 seed 주입 후에도 환각 지속 | L2 valid_ratio 평균 < 0.7 | 프롬프트 강화 ("목록 외 조문 인용 금지") + Top-5 확장 |
| 페르소나 × 난이도 조건부 Sampler 복잡도 | DD preview 실패 | 단순 category Sampler로 fallback |
| `Nemotron-Personas-Korea` 접근 불가 | HF 403 | Faker 기반 간이 페르소나로 대체 (L4 축소형) |
| 계산 검증 파서 깨짐 | S3 throw | 해당 행 `calc_verified=null` 처리 (제거 안 함) |
| 법제처 API rate limit | 403/429 | L2 캐시 우선, 캐시 미스만 호출, 0.3s delay |
| tool-use 데모 라이브 실패 | 발표 직전 테스트 실패 | 미리 녹화한 영상 재생 |

## 9.14 다음 커밋 순서 (구현 착수)

1. **이 문서 (09-pipeline-design-v2.md) + 기존 문서 업데이트** 커밋
2. `pipeline/fetch_personas.py` + `pipeline/personas.py`
3. `scripts/collect_seeds.py` 실제 실행 → `cache/seeds/*.jsonl` 확보 (샘플 1건만 커밋)
4. `pipeline/seeds.py` + `builder.py` 수정 (L1)
5. `pipeline/validators/citation_validator.py` + `run_verify_citations.py` (L2)
6. `pipeline/validators/calc_validator.py` + `run_calc_validate.py` (L3)
7. 50건 드라이런 → L1/L2 효과 측정 → 프롬프트 튜닝
8. `run_guardrails.py`, `run_curator.py`
9. `training/sft_*.py`, `benchmark/*.py`
10. `demo/nemotron_tool_call.py`

각 단계마다 인스턴스 `git pull` → 실행 → 결과 확인 → 다음으로.
