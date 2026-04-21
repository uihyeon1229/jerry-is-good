"""B2 — Semantic Drift Detection (NVIDIA Build API 임베딩 기반).

question 임베딩 vs reasoning_cot 임베딩의 코사인 유사도 측정.
낮으면 "답변이 질문 주제에서 이탈" 의심.

기본 모델: nvidia/llama-nemotron-embed-1b-v2 (Build API, 2048 dim)
"""

from __future__ import annotations

from ..embed_nvidia import embed, embed_pairs_similarity


def drift_score(question: str, cot: str) -> float:
    """단일 쌍 코사인 유사도 (0~1)."""
    if not question or not cot:
        return 0.0
    embs = embed([question, cot])
    return float((embs[0] * embs[1]).sum())


def drift_scores_batch(pairs: list[tuple[str, str]]) -> list[float]:
    """여러 (question, cot) 쌍에 대해 코사인 유사도 (NVIDIA Embed)."""
    if not pairs:
        return []
    return embed_pairs_similarity(pairs)
