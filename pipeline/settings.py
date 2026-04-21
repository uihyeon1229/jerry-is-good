"""환경변수 기반 파이프라인 설정."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    # vLLM
    vllm_base_url: str = os.getenv("VLLM_BASE_URL", "http://localhost:5000/v1")
    vllm_model: str = os.getenv("VLLM_MODEL", "nemotron")

    # 법제처
    law_oc: str = os.getenv("LAW_OC", "")

    # 파이프라인 크기 / 토큰 예산
    num_records: int = _int("PIPELINE_NUM_RECORDS", 1000)
    max_tokens_cot: int = _int("PIPELINE_MAX_TOKENS_COT", 16384)
    max_tokens_question: int = _int("PIPELINE_MAX_TOKENS_QUESTION", 1024)
    max_tokens_metadata: int = _int("PIPELINE_MAX_TOKENS_METADATA", 512)
    max_tokens_judge: int = _int("PIPELINE_MAX_TOKENS_JUDGE", 1024)
    max_parallel: int = _int("PIPELINE_MAX_PARALLEL", 4)

    # 경로
    cache_dir: Path = Path(os.getenv("PIPELINE_CACHE_DIR", "./cache"))
    output_dir: Path = Path(os.getenv("PIPELINE_OUTPUT_DIR", "./output"))
    seed_dir: Path = Path(os.getenv("PIPELINE_SEED_DIR", "./cache/seeds"))


settings = Settings()


def ensure_dirs() -> None:
    for d in (settings.cache_dir, settings.output_dir, settings.seed_dir):
        d.mkdir(parents=True, exist_ok=True)
