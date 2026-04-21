"""DataDesignerConfigBuilder 조립."""

from __future__ import annotations

from data_designer.config import DataDesignerConfigBuilder

import os

from .columns import (
    cot_column,
    judge_column,
    metadata_column,
    nando_column,
    persona_semok_column,
    qtype_column,
    question_column,
    seed_context_column,
    semok_column,
)
from .providers import default_model_configs


def build_config(*, use_persona_affinity: bool | None = None) -> DataDesignerConfigBuilder:
    """C1(use_persona_affinity=True) 활성화 시 세목·난이도는 페르소나 affinity 기반."""
    if use_persona_affinity is None:
        use_persona_affinity = os.getenv("USE_PERSONA_AFFINITY", "1") not in ("0", "false", "False")

    b = DataDesignerConfigBuilder()

    for m in default_model_configs():
        b.add_model_config(m)

    # 1) 축 — C1 활성화 시 Custom (persona+semok+난이도), 비활성화 시 단순 Sampler
    if use_persona_affinity:
        b.add_column(persona_semok_column())  # 세목 + persona_ref + 난이도 한 번에
        b.add_column(qtype_column())
    else:
        b.add_column(semok_column())
        b.add_column(qtype_column())
        b.add_column(nando_column())

    # 2) L1 — 세목별 조문 Seed Context
    b.add_column(seed_context_column())

    # 3) 생성 컬럼 (의존성: 세목/질문유형/난이도/persona_ref → question → reasoning_cot)
    b.add_column(question_column())
    b.add_column(cot_column())

    # 4) 구조화 메타데이터
    b.add_column(metadata_column())

    # 5) 3축 Judge
    b.add_column(judge_column())

    return b
