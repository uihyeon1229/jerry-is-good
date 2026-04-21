"""DataDesignerConfigBuilder 조립."""

from __future__ import annotations

from data_designer.config import DataDesignerConfigBuilder

from .columns import (
    cot_column,
    judge_column,
    metadata_column,
    nando_column,
    qtype_column,
    question_column,
    semok_column,
)
from .providers import default_model_configs


def build_config() -> DataDesignerConfigBuilder:
    b = DataDesignerConfigBuilder()

    for m in default_model_configs():
        b.add_model_config(m)

    # 1) 결정론적 Sampler (세목 × 질문유형 × 난이도)
    b.add_column(semok_column())
    b.add_column(qtype_column())
    b.add_column(nando_column())

    # 2) 생성 컬럼 (의존성: 세목/질문유형/난이도 → question → reasoning_cot)
    b.add_column(question_column())
    b.add_column(cot_column())

    # 3) 구조화 메타데이터
    b.add_column(metadata_column())

    # 4) 3축 Judge
    b.add_column(judge_column())

    return b
