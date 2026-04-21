"""Nemotron-Personas-Korea에서 N명 샘플링 → cache/personas/korea_10k.jsonl 저장.

한 번만 실행. 이후 파이프라인은 JSONL 캐시만 사용.

사용법:
    python -m pipeline.fetch_personas            # 기본 10000명
    N=500 python -m pipeline.fetch_personas      # 500명만
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from datasets import load_dataset

DATASET = "nvidia/Nemotron-Personas-Korea"

# 질문 생성에 실제로 쓸 필드만 추림 (토큰 절약)
KEEP_FIELDS = [
    "uuid",
    "sex",
    "age",
    "marital_status",
    "family_type",
    "housing_type",
    "education_level",
    "bachelors_field",
    "occupation",
    "district",
    "province",
    "persona",                 # 요약 1~2줄 (핵심)
    "professional_persona",    # 직업 관점 (세법 질문에 유용)
    "family_persona",          # 가족 관점 (상속/증여 질문에 유용)
    "cultural_background",     # 지역·세대 맥락
]

OUT = Path(os.getenv("PERSONA_OUT", "./cache/personas/korea_10k.jsonl"))
N = int(os.getenv("N", "10000"))
SEED = int(os.getenv("SEED", "42"))

OUT.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    print(f"=== loading {DATASET} (split=train) ===", flush=True)
    ds = load_dataset(DATASET, split="train")
    print(f"=== full size: {len(ds)} rows ===", flush=True)

    sample = ds.shuffle(seed=SEED).select(range(min(N, len(ds))))
    print(f"=== sampled {len(sample)} rows ===", flush=True)

    with OUT.open("w", encoding="utf-8") as fp:
        for row in sample:
            trimmed = {k: row.get(k) for k in KEEP_FIELDS}
            fp.write(json.dumps(trimmed, ensure_ascii=False) + "\n")

    print(f"=== wrote {OUT} ===")


if __name__ == "__main__":
    main()
