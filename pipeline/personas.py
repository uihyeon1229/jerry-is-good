"""페르소나 JSONL 로딩 + DD Sampler 호환 DataFrame 변환 + education→난이도 매핑
+ C1 Persona-Law Affinity (페르소나 → 세목 가중치)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .schema import SEMOK_VALUES, SEMOK_WEIGHTS
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


# =====================================================================
# C1 — Persona-Law Affinity: 페르소나 → 세목 가중치 매핑
# =====================================================================


# 나이대별 기본 분포 (합 1.0 근사)
_AGE_DISTRIBUTION = {
    "20s": {
        "노동법-임금퇴직금": 0.28,
        "노동법-해고연차": 0.22,
        "세법-소득세": 0.15,
        "민법-계약임대차": 0.15,
        "세법-부가가치세": 0.05,
        "세법-법인세": 0.05,
        "민법-상속증여": 0.05,
        "세법-상속증여세": 0.05,
    },
    "30-40s": {
        "세법-소득세": 0.22,
        "민법-계약임대차": 0.18,
        "노동법-임금퇴직금": 0.14,
        "세법-법인세": 0.12,
        "세법-부가가치세": 0.10,
        "노동법-해고연차": 0.10,
        "민법-상속증여": 0.08,
        "세법-상속증여세": 0.06,
    },
    "50s+": {
        "세법-상속증여세": 0.22,
        "민법-상속증여": 0.20,
        "세법-소득세": 0.14,
        "민법-계약임대차": 0.12,
        "세법-법인세": 0.10,
        "세법-부가가치세": 0.08,
        "노동법-임금퇴직금": 0.08,
        "노동법-해고연차": 0.06,
    },
}


# occupation 키워드별 부스트 (+가산 후 정규화)
_OCCUPATION_BOOST: list[tuple[tuple[str, ...], dict[str, float]]] = [
    # 사업자/자영업자/대표 → 법인세·부가세↑
    (
        ("대표", "자영업", "사업자", "법인장", "경영자", "사장"),
        {"세법-법인세": 0.15, "세법-부가가치세": 0.12},
    ),
    # 은퇴/무직 → 상속·증여↑
    (
        ("무직", "은퇴", "퇴직", "연금"),
        {"세법-상속증여세": 0.10, "민법-상속증여": 0.10},
    ),
    # 일반 근로자 → 노동법↑
    (
        (
            "근로자",
            "직장인",
            "사무원",
            "경비원",
            "청소원",
            "상담원",
            "비서",
            "하역",
            "보조원",
            "조리사",
            "판매",
            "운전원",
            "영업원",
            "회계 사무원",
        ),
        {"노동법-임금퇴직금": 0.12, "노동법-해고연차": 0.10},
    ),
    # 임대/부동산 관련 → 민법 계약임대차↑
    (
        ("공인중개사", "임대", "부동산"),
        {"민법-계약임대차": 0.15},
    ),
]


def _age_bucket(age) -> str:
    try:
        a = int(age)
    except (TypeError, ValueError):
        return "30-40s"
    if a < 30:
        return "20s"
    if a < 50:
        return "30-40s"
    return "50s+"


def affinity_weights(persona: dict) -> dict[str, float]:
    """페르소나 → 세목별 가중치 (합 1.0 정규화).

    1) 나이대 기본 분포
    2) occupation 키워드 매칭 시 부스트
    3) 정규화
    """
    bucket = _age_bucket(persona.get("age"))
    weights = dict(_AGE_DISTRIBUTION.get(bucket, _AGE_DISTRIBUTION["30-40s"]))

    occ = (persona.get("occupation") or "") + " " + (
        persona.get("professional_persona") or ""
    )
    for keywords, boost in _OCCUPATION_BOOST:
        if any(k in occ for k in keywords):
            for k, v in boost.items():
                weights[k] = weights.get(k, 0.0) + v

    # 모든 세목을 최소 0.01 보장 (다양성 유지)
    for s in SEMOK_VALUES:
        weights.setdefault(s, 0.01)

    total = sum(weights.values())
    if total <= 0:
        return {s: w for s, w in zip(SEMOK_VALUES, SEMOK_WEIGHTS)}
    return {k: v / total for k, v in weights.items()}


def weighted_sample_semok(persona: dict, rng=None) -> str:
    """페르소나 기반 세목 1건 샘플링."""
    import random as _random

    r = rng or _random
    weights = affinity_weights(persona)
    items = list(weights.items())
    keys = [k for k, _ in items]
    probs = [v for _, v in items]
    return r.choices(keys, weights=probs, k=1)[0]
