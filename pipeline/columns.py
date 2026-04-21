"""각 LLM 컬럼 config 팩토리."""

from __future__ import annotations

from data_designer.config import (
    CategorySamplerParams,
    CustomColumnConfig,
    LLMJudgeColumnConfig,
    LLMStructuredColumnConfig,
    LLMTextColumnConfig,
    SamplerColumnConfig,
    SamplerType,
    Score,
)
from data_designer.config.custom_column import custom_column_generator

from .personas import (
    affinity_weights,
    load_personas_df,
    nando_weights_for,
    weighted_sample_semok,
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
from .seeds import seed_context_for


# =====================================================================
# Sampler 컬럼 (3축)
# =====================================================================


def semok_column() -> SamplerColumnConfig:
    """L4 없이 쓸 때의 단순 Sampler (fallback)."""
    return SamplerColumnConfig(
        name="세목",
        sampler_type=SamplerType.CATEGORY,
        params=CategorySamplerParams(values=SEMOK_VALUES, weights=SEMOK_WEIGHTS),
    )


# =====================================================================
# C1 — Persona-Law Affinity: 페르소나 + 세목을 하나의 Custom 컬럼에서 동시 생성
# =====================================================================

_PERSONAS_CACHE = None


def _get_personas():
    global _PERSONAS_CACHE
    if _PERSONAS_CACHE is None:
        import random

        df = load_personas_df()
        # dict 리스트로 변환
        _PERSONAS_CACHE = df.to_dict(orient="records")
    return _PERSONAS_CACHE


@custom_column_generator(side_effect_columns=["persona_ref", "난이도"])
def _persona_and_semok_generator(row: dict) -> dict:
    """C1 — 페르소나 하나를 고르고, affinity에 따라 세목 + 학력 조건부 난이도 생성.

    side_effect로 persona_ref(프롬프트 주입용 요약)·난이도를 동시 주입.
    """
    import random

    personas = _get_personas()
    persona = random.choice(personas)
    semok = weighted_sample_semok(persona, rng=random)

    # 프롬프트용 페르소나 요약 문자열
    parts = []
    if persona.get("age"):
        parts.append(f"{persona['age']}세")
    if persona.get("sex"):
        parts.append(persona["sex"])
    if persona.get("occupation"):
        parts.append(f"직업 {persona['occupation']}")
    if persona.get("education_level"):
        parts.append(f"학력 {persona['education_level']}")
    if persona.get("family_type"):
        parts.append(persona["family_type"])
    if persona.get("housing_type"):
        parts.append(persona["housing_type"])
    if persona.get("province"):
        parts.append(persona["province"])
    persona_ref = ", ".join(parts) or "(페르소나 미지정)"

    # 학력 조건부 난이도 샘플링
    nando_w = nando_weights_for(persona.get("education_level"))
    nando = random.choices(
        list(nando_w.keys()),
        weights=list(nando_w.values()),
        k=1,
    )[0]

    return {
        **row,
        "세목": semok,
        "persona_ref": persona_ref,
        "난이도": nando,
    }


def persona_semok_column() -> CustomColumnConfig:
    """C1 — 세목(+persona_ref/난이도 side_effect) 생성 컬럼."""
    return CustomColumnConfig(
        name="세목",
        generator_function=_persona_and_semok_generator,
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


QUESTION_PROMPT = """당신은 한국 법률 전문가입니다.
아래 납세자/의뢰인의 현실 상황에 맞는 **구체적인 질문** 하나를 만들어 주세요.

[의뢰인 페르소나]
{{ persona_ref }}

[조건]
- 도메인/세부: {{ 세목 }}
- 질문유형: {{ 질문유형 }}
- 난이도: {{ 난이도 }}

출력은 질문 한 문장 혹은 한 단락으로만 작성하세요. 의뢰인의 상황(나이·직업·가족)이 자연스럽게 녹아들어야 합니다. 서두/설명 없이 질문만 출력.
"""


COT_PROMPT = """당신은 한국 법률 전문가입니다. 다음 질문에 대해 **적용 조문 → 사실관계 → 해석/계산 → 결론** 4단계의 Chain-of-Thought 추론을 한국어로 작성하세요.

도메인/세부: {{ 세목 }}
질문유형: {{ 질문유형 }}
난이도: {{ 난이도 }}

질문:
{{ question }}

**아래는 {{ 세목 }}와 관련된 실제 한국 법령 조문입니다. 답변에서는 반드시 이 목록 안에 있는 조문만 인용하세요. 목록에 없는 조문 번호는 절대 만들어내지 마세요.**

{{ seed_context }}

지침:
- 각 단계를 명확히 구분 (예: "1. 적용 조문", "2. 사실관계", "3. 해석/계산", "4. 결론")
- **조문 인용은 위 목록에서만** (법령명 + 조문번호를 반드시 명시)
- 세법의 계산문제는 숫자 근거를 제시, 민법·노동법은 조문 해석 중심
- 결론은 한두 문장으로 요약
- 답변 말미에 한 줄 고지: "※ 본 답변은 일반적인 정보 제공이며, 구체적 사건에 대한 법률 자문이 아닙니다. 실제 처리 시 전문가 상담을 권합니다."
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


@custom_column_generator(required_columns=["세목"])
def _seed_context_generator(row: dict) -> dict:
    """L1 — 세목별 실제 조문 Top-N을 프롬프트 context로 주입.

    DD custom generator 규약: 기존 row 전체 + 새 컬럼(seed_context) dict 반환.
    """
    return {**row, "seed_context": seed_context_for(row.get("세목") or "")}


def seed_context_column() -> CustomColumnConfig:
    return CustomColumnConfig(
        name="seed_context",
        generator_function=_seed_context_generator,
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
