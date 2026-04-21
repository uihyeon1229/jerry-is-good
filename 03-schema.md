# 3. 데이터 스키마 설계

## 3.1 대상 세목 (4개)

| 세목 | 하위 주제 | 비중 (약) | 대표 조문 |
|------|----------|----------|----------|
| **소득세** | 근로소득, 사업소득, 필요경비, 공제 | 30% | 소득세법 §20, §24, §27, §51 |
| **상속·증여세** | 상속공제, 증여재산가액, 평가, 신고 | 20% | 상증세법 §13, §18, §60 |
| **법인세** | 세무조정, 감가상각, 손금불산입 | 25% | 법인세법 §15, §23, §25 |
| **부가가치세** | 과세·면세, 매입세액공제, 신고 | 25% | 부가세법 §3, §29, §38 |

## 3.2 Sampler 축 (결정론적 분포)

### 축 1: 세목
```python
values = [
    "소득세-근로소득",
    "소득세-사업소득",
    "상속세",
    "증여세",
    "법인세-세무조정",
    "법인세-감가상각",
    "부가가치세-과세면세",
    "부가가치세-매입세액공제",
]
weights = [0.18, 0.12, 0.10, 0.10, 0.15, 0.10, 0.13, 0.12]
```

### 축 2: 질문유형
```python
values = [
    "계산문제",        # 구체적 숫자 주고 세액 계산
    "법령해석",        # 조문 의미 해석
    "사례적용",        # 실무 상황에 적용
    "개념설명",        # 용어/원리 설명
]
weights = [0.35, 0.20, 0.30, 0.15]
```

### 축 3: 난이도
```python
values = [
    "기초",    # 신고실무, 기본 공제
    "중급",    # 복수 공제·감면, 조건 충돌
    "고급",    # 세무조정, 쟁점 판례
]
weights = [0.30, 0.45, 0.25]
```

## 3.3 컬럼 전체 정의

### 컬럼 목록 및 의존성

```
[독립]
  ├─ 세목 (Sampler)
  ├─ 질문유형 (Sampler)
  └─ 난이도 (Sampler)

[세목 → 의존]
  └─ applied_law_context (MCP Pull, ExpressionColumn 대체)

[세목 + 질문유형 + 난이도 + applied_law_context → 의존]
  └─ question (LLMTextColumn)

[question + 모든 상위 → 의존]
  └─ reasoning_cot (LLMTextColumn)

[question + reasoning_cot → 의존]
  ├─ metadata (LLMStructuredColumn)
  └─ quality_score (LLMJudgeColumn)

[question + reasoning_cot → 의존]
  └─ chat_formatted (ExpressionColumn)
```

## 3.4 Pydantic 스키마 (LLMStructuredColumn용)

```python
from pydantic import BaseModel, Field
from typing import List

class TaxMetadata(BaseModel):
    """세법 CoT 메타데이터"""
    applied_law_mst: List[str] = Field(
        description="적용된 법령의 MST (예: ['소득세법 제20조', '시행령 제38조'])"
    )
    final_answer: str = Field(
        description="최종 결론 (수치 또는 명제)"
    )
    num_reasoning_steps: int = Field(
        description="CoT 추론 단계 수",
        ge=1, le=20
    )
    concepts_used: List[str] = Field(
        description="사용된 세법 개념 (예: ['근로소득공제', '종합소득과세표준'])"
    )
    requires_calculation: bool = Field(
        description="실제 계산이 필요한 문제인지"
    )
    references_precedent: bool = Field(
        description="판례/해석례를 참조했는지"
    )
```

## 3.5 Judge 루브릭 (3축 × 1-5점)

### 축 1: 법령정확성 (legal_accuracy)

| 점수 | 기준 |
|------|------|
| 5 | 조문 번호·내용 모두 정확, 개정사항 반영 |
| 4 | 조문 번호 정확, 내용 해석 약간 미흡 |
| 3 | 조문 방향 맞으나 번호 애매하거나 부분 오류 |
| 2 | 조문 번호 틀렸으나 내용 의도 전달 |
| 1 | 존재하지 않는 조문 인용, 명백한 오류 |

### 축 2: CoT 깊이 (cot_depth)

| 점수 | 기준 |
|------|------|
| 5 | 조문→사실→계산→결론 4단계 모두 명확, 각 단계 설득력 있음 |
| 4 | 4단계 존재, 한두 단계 설명 부족 |
| 3 | 단계 구분은 있으나 설명 얕음 |
| 2 | 2~3단계만 있고 추론 부실 |
| 1 | 답만 있고 추론 과정 거의 없음 |

### 축 3: 실무 유용성 (practical_utility)

| 점수 | 기준 |
|------|------|
| 5 | 실제 납세자/실무자가 즉시 적용 가능, 구체적·친절 |
| 4 | 적용 가능하나 약간의 추가 조사 필요 |
| 3 | 교과서적으로 맞으나 실무 적용 애매 |
| 2 | 원론적이거나 상황 반영 부족 |
| 1 | 추상적, 현실과 괴리 |

### Judge 통과 기준

```python
THRESHOLD_MIN = 3           # 각 축 최소 3점
THRESHOLD_AVG = 3.5         # 3축 평균 3.5점 이상

# 추가 하드 필터
- applied_law_mst 비어있지 않음
- num_reasoning_steps >= 3
- CoT 길이 >= 200자
```

## 3.6 Guardrails 규칙

### rails/config.yml (NeMo Guardrails)

```yaml
models:
  - type: main
    engine: openai
    model: nemotron
    parameters:
      base_url: http://localhost:5000/v1
      api_key: not-used

rails:
  output:
    flows:
      - check tax evasion advice
      - check fake attorney
      - check pii
      - check outdated law

prompts:
  - task: self_check_output
    content: |
      당신은 한국 세법 AI 데이터 검증자입니다.
      다음 출력에 아래 중 하나라도 해당되면 "YES"로 답하세요:

      1. 탈세 방법을 구체적으로 안내하는가?
         (참고: 절세는 허용, 탈세는 차단)
      2. 세무사/변호사 자격을 사칭하거나 법률 자문을 대체한다고 주장하는가?
      3. 실제 개인의 주민등록번호/계좌번호/법인등록번호가 포함되는가?
      4. 폐지되거나 개정 전 조문을 현행으로 인용하는가?

      출력:
      {{ bot_response }}

      답변 (YES/NO):
```

### 블랙리스트 키워드 (정규식 보완)

```python
TAX_EVASION_PATTERNS = [
    r"세금을?\s*(안\s*내|회피|빼돌리|숨기)",
    r"차명\s*(계좌|거래)",
    r"허위\s*(세금계산서|매출|매입)",
    r"비자금",
]

FAKE_ATTORNEY_PATTERNS = [
    r"저는?\s*세무사",
    r"제가\s*대리",
    r"저에게\s*위임",
]

PII_PATTERNS = [
    r"\d{6}-\d{7}",              # 주민번호
    r"\d{3}-\d{2}-\d{5}",        # 사업자번호 (예시)
    r"\d{11}-\d{7}",             # 법인번호
]
```

## 3.7 Curator 설정

### config.yaml (NeMo Curator)

```yaml
input:
  path: /workspace/output/raw/*.jsonl
  format: jsonl

steps:
  - name: exact_dedup
    type: ExactDuplicatesFilter
    field: reasoning_cot

  - name: fuzzy_dedup
    type: FuzzyDuplicatesFilter
    field: reasoning_cot
    threshold: 0.85

  - name: semantic_dedup
    type: SemanticDeduplicator
    field: question
    threshold: 0.90
    model: BAAI/bge-m3

  - name: length_filter
    type: WordCountFilter
    min_words: 50
    max_words: 1500

  - name: language_filter
    type: FastTextLangId
    target_lang: ko
    min_score: 0.85

  - name: quality_filter
    type: ThresholdFilter
    field: quality_score.avg
    min_value: 3.5

output:
  path: /workspace/output/filtered/
  format: parquet
```

## 3.8 ChatML 최종 포맷 (SFT용)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "당신은 한국 세법 전문가 AI입니다. 질문에 대해 적용 법령을 인용하며 단계별로 추론하여 답변하세요."
    },
    {
      "role": "user",
      "content": "<question 컬럼 내용>"
    },
    {
      "role": "assistant",
      "content": "<reasoning_cot 컬럼 내용>"
    }
  ],
  "metadata": {
    "세목": "...",
    "질문유형": "...",
    "난이도": "...",
    "applied_law_mst": [...],
    "quality_scores": {...}
  }
}
```

## 3.9 목표 규모

| 단계 | 목표 건수 |
|------|----------|
| 원본 생성 | 1,000건 |
| Guardrails 통과 (예상 90%) | 900건 |
| Curator 통과 (예상 80%) | 720건 |
| MCP verify 통과 (예상 95%) | 684건 |
| Judge 3.5+ 통과 (예상 70%) | **~480건** |
| SFT 학습 데이터 | 480건 (train) |
| 평가 세트 | 20문제 (수작업) |

→ **최종 목표: 고품질 500건** (학습용으로 충분, SFT 4시간 내 완료 가능)
