"""각 LLM 컬럼 config 팩토리."""

from __future__ import annotations

from data_designer.config import (
    CategorySamplerParams,
    LLMJudgeColumnConfig,
    LLMStructuredColumnConfig,
    LLMTextColumnConfig,
    SamplerColumnConfig,
    SamplerType,
    Score,
)

from .schema import (
    NANDO_VALUES,
    NANDO_WEIGHTS,
    QTYPE_VALUES,
    QTYPE_WEIGHTS,
    SEMOK_VALUES,
    SEMOK_WEIGHTS,
    TaxMetadata,
)


# =====================================================================
# Sampler 컬럼 (3축)
# =====================================================================


def semok_column() -> SamplerColumnConfig:
    return SamplerColumnConfig(
        name="세목",
        sampler_type=SamplerType.CATEGORY,
        params=CategorySamplerParams(values=SEMOK_VALUES, weights=SEMOK_WEIGHTS),
    )


def qtype_column() -> SamplerColumnConfig:
    return SamplerColumnConfig(
        name="질문유형",
        sampler_type=SamplerType.CATEGORY,
        params=CategorySamplerParams(values=QTYPE_VALUES, weights=QTYPE_WEIGHTS),
    )


def nando_column() -> SamplerColumnConfig:
    return SamplerColumnConfig(
        name="난이도",
        sampler_type=SamplerType.CATEGORY,
        params=CategorySamplerParams(values=NANDO_VALUES, weights=NANDO_WEIGHTS),
    )


# =====================================================================
# 생성 컬럼
# =====================================================================


QUESTION_PROMPT = """당신은 한국 세법 전문가입니다.
다음 조건에 맞는 **납세자 관점의 현실적인 질문** 하나를 만들어 주세요.

- 세목: {{ 세목 }}
- 질문유형: {{ 질문유형 }}
- 난이도: {{ 난이도 }}

출력은 질문 한 문장 혹은 한 단락으로만 작성하세요. 서두/설명 없이 질문만 출력.
"""


COT_PROMPT = """당신은 한국 세법 전문가입니다. 다음 질문에 대해 **적용 조문 → 사실관계 → 계산/해석 → 결론** 4단계의 Chain-of-Thought 추론을 한국어로 작성하세요.

세목: {{ 세목 }}
질문유형: {{ 질문유형 }}
난이도: {{ 난이도 }}

질문:
{{ question }}

지침:
- 각 단계를 명확히 구분 (예: "1. 적용 조문", "2. 사실관계", "3. 계산/해석", "4. 결론")
- 조문은 실제 존재하는 번호만 인용 (추정 번호 금지)
- 계산문제는 숫자 근거를 제시
- 결론은 한두 문장으로 요약
"""


METADATA_PROMPT = """다음 질문과 CoT 답변에서 메타데이터를 추출하세요.

질문: {{ question }}

답변:
{{ reasoning_cot }}

JSON 스키마에 맞게 추출하세요.
"""


def question_column() -> LLMTextColumnConfig:
    return LLMTextColumnConfig(
        name="question",
        prompt=QUESTION_PROMPT,
        model_alias="question_gen",
    )


def cot_column() -> LLMTextColumnConfig:
    return LLMTextColumnConfig(
        name="reasoning_cot",
        prompt=COT_PROMPT,
        model_alias="cot_gen",
        extract_reasoning_content=True,
    )


def metadata_column() -> LLMStructuredColumnConfig:
    return LLMStructuredColumnConfig(
        name="metadata",
        prompt=METADATA_PROMPT,
        model_alias="structured",
        output_format=TaxMetadata,
    )


# =====================================================================
# Judge 컬럼 (3축)
# =====================================================================


JUDGE_PROMPT = """당신은 한국 세법 CoT 품질 평가자입니다.

질문:
{{ question }}

답변:
{{ reasoning_cot }}

아래 3가지 축에 대해 각 1-5점으로 채점하세요.
"""


SCORE_1_TO_5 = {
    1: "매우 나쁨 — 거의 완전히 잘못되거나 부실",
    2: "나쁨 — 상당한 오류 또는 부족",
    3: "보통 — 부분적으로 맞음",
    4: "좋음 — 대체로 정확하고 유용",
    5: "매우 좋음 — 완전하고 모범적",
}


def judge_column() -> LLMJudgeColumnConfig:
    return LLMJudgeColumnConfig(
        name="quality_score",
        prompt=JUDGE_PROMPT,
        model_alias="judge",
        scores=[
            Score(
                name="legal_accuracy",
                description="조문 인용의 정확성과 개정사항 반영 정도 (법령정확성, 1-5)",
                options=SCORE_1_TO_5,
            ),
            Score(
                name="cot_depth",
                description="조문→사실→계산→결론 4단계의 명확성 (CoT 깊이, 1-5)",
                options=SCORE_1_TO_5,
            ),
            Score(
                name="practical_utility",
                description="실제 납세자/실무자가 적용 가능한 구체성 (실무 유용성, 1-5)",
                options=SCORE_1_TO_5,
            ),
        ],
    )
