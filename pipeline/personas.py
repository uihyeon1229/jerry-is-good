"""페르소나 JSONL 로딩 + DD Sampler 호환 DataFrame 변환 + education→난이도 매핑."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .settings import settings


# education_level은 Nemotron-Personas-Korea 원본 실측값 (10K 샘플, 2026-04-21).
# 난이도 분포를 조건부로 매핑하여 자연스러움 확보 (L4).
NANDO_BY_EDUCATION: dict[str, dict[str, float]] = {
    "무학":              {"기초": 0.85, "중급": 0.14, "고급": 0.01},
    "초등학교":          {"기초": 0.75, "중급": 0.23, "고급": 0.02},
    "중학교":            {"기초": 0.65, "중급": 0.30, "고급": 0.05},
    "고등학교":          {"기초": 0.45, "중급": 0.45, "고급": 0.10},
    "2~3년제 전문대학":  {"기초": 0.30, "중급": 0.50, "고급": 0.20},
    "4년제 대학교":      {"기초": 0.20, "중급": 0.55, "고급": 0.25},
    "대학원":            {"기초": 0.08, "중급": 0.42, "고급": 0.50},
}

# Fallback (매핑에 없으면)
NANDO_DEFAULT = {"기초": 0.30, "중급": 0.45, "고급": 0.25}


def load_personas_df(path: Path | None = None) -> pd.DataFrame:
    """JSONL → pandas.DataFrame. DD의 DataFrameSeedSource / SeedDataset에서 사용."""
    src = path or (settings.cache_dir / "personas" / "korea_10k.jsonl")
    if not src.exists():
        raise FileNotFoundError(
            f"페르소나 캐시 없음: {src}. "
            f"먼저 `python -m pipeline.fetch_personas` 실행하세요."
        )
    with src.open("r", encoding="utf-8") as fp:
        rows = [json.loads(line) for line in fp if line.strip()]
    df = pd.DataFrame(rows)
    return df


def nando_weights_for(education_level: str | None) -> dict[str, float]:
    """education_level → 난이도 가중치 dict."""
    if not education_level:
        return NANDO_DEFAULT
    return NANDO_BY_EDUCATION.get(education_level, NANDO_DEFAULT)
