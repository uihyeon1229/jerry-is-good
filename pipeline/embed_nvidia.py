"""NVIDIA Build API 임베딩 공통 래퍼 (llama-nemotron-embed-1b-v2).

기본 모델: nvidia/llama-nemotron-embed-1b-v2 (2048 dim)
환경변수:
    NVIDIA_BUILD_API_KEY  (필수)
    NVIDIA_EMBED_MODEL    (기본 'nvidia/llama-nemotron-embed-1b-v2')
    NVIDIA_EMBED_BATCH    (기본 32)
"""

from __future__ import annotations

import os
import time
from typing import Literal

import numpy as np

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


BUILD_API_URL = "https://integrate.api.nvidia.com/v1"
BUILD_API_KEY = os.getenv("NVIDIA_BUILD_API_KEY", "")
EMBED_MODEL = os.getenv("NVIDIA_EMBED_MODEL", "nvidia/llama-nemotron-embed-1b-v2")
BATCH_SIZE = int(os.getenv("NVIDIA_EMBED_BATCH", "32"))


_client = None


def _get_client():
    global _client
    if not BUILD_API_KEY:
        raise RuntimeError(
            "NVIDIA_BUILD_API_KEY 환경변수가 필요합니다."
        )
    if OpenAI is None:
        raise RuntimeError("openai 패키지가 필요합니다.")
    if _client is None:
        _client = OpenAI(base_url=BUILD_API_URL, api_key=BUILD_API_KEY)
    return _client


def embed(
    texts: list[str],
    *,
    input_type: Literal["passage", "query"] = "passage",
    normalize: bool = True,
) -> np.ndarray:
    """NVIDIA Build API로 배치 임베딩 (반환: float32 ndarray).

    429 rate limit 발생 시 exponential backoff 재시도.
    """
    if not texts:
        return np.zeros((0, 2048), dtype=np.float32)

    client = _get_client()
    all_vecs: list[list[float]] = []
    i = 0
    while i < len(texts):
        batch = texts[i : i + BATCH_SIZE]
        retries = 0
        while True:
            try:
                resp = client.embeddings.create(
                    model=EMBED_MODEL,
                    input=batch,
                    extra_body={"input_type": input_type},
                )
                all_vecs.extend([d.embedding for d in resp.data])
                break
            except Exception as e:  # noqa: BLE001
                msg = str(e).lower()
                if "429" in msg or "rate" in msg or "too many" in msg:
                    wait = min(2 ** retries, 30)
                    print(
                        f"  [embed] rate limit, retry in {wait}s (attempt {retries+1})",
                        flush=True,
                    )
                    time.sleep(wait)
                    retries += 1
                    if retries > 6:
                        raise
                    continue
                raise
        i += BATCH_SIZE
        if i % 200 == 0 or i >= len(texts):
            print(f"  [embed] {min(i, len(texts))}/{len(texts)}", flush=True)

    arr = np.asarray(all_vecs, dtype=np.float32)
    if normalize:
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        arr = arr / norms
    return arr


def embed_pairs_similarity(pairs: list[tuple[str, str]]) -> list[float]:
    """(question, cot) 쌍 → 코사인 유사도 리스트 (B2 drift용)."""
    flat: list[str] = []
    for q, c in pairs:
        flat.append(q or "")
        flat.append(c or "")
    embs = embed(flat)
    sims: list[float] = []
    for i in range(0, len(embs), 2):
        q = embs[i]
        c = embs[i + 1]
        sims.append(float((q * c).sum()))
    return sims
