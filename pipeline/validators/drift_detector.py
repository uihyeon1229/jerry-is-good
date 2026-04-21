"""B2 — Semantic Drift Detection.

question 임베딩 vs reasoning_cot 임베딩의 코사인 유사도 측정.
낮으면 "답변이 질문 주제에서 이탈" 의심.

BAAI/bge-m3는 이미 인스턴스 HF cache에 있음 (~2GB).
"""

from __future__ import annotations

import os
from typing import Iterable

_model = None
_torch = None


def _lazy_model():
    global _model, _torch
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        _torch = torch
        device = "cuda" if torch.cuda.is_available() and os.getenv("DRIFT_DEVICE", "").lower() != "cpu" else "cpu"
        # GPU가 vLLM에 점유된 경우 CPU 강제
        if device == "cuda":
            try:
                free, _ = torch.cuda.mem_get_info()
                if free < 3 * 1024**3:  # 3GB 미만이면 CPU로
                    device = "cpu"
            except Exception:
                device = "cpu"
        _model = SentenceTransformer("BAAI/bge-m3", device=device)
    return _model


def embed(texts: list[str]):
    """bge-m3로 임베딩 (normalize=True 이미 기본값)."""
    m = _lazy_model()
    return m.encode(
        texts,
        batch_size=int(os.getenv("DRIFT_BATCH", "16")),
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )


def drift_score(question: str, cot: str) -> float:
    """단일 쌍 코사인 유사도 (0~1)."""
    if not question or not cot:
        return 0.0
    q_emb, c_emb = embed([question, cot])
    # normalize되어 있어 dot product == cosine
    return float((q_emb * c_emb).sum())


def drift_scores_batch(pairs: list[tuple[str, str]]) -> list[float]:
    """여러 (question, cot) 쌍에 대해 코사인 유사도."""
    if not pairs:
        return []
    flat: list[str] = []
    for q, c in pairs:
        flat.append(q or "")
        flat.append(c or "")
    embs = embed(flat)
    scores: list[float] = []
    for i in range(0, len(embs), 2):
        q_emb = embs[i]
        c_emb = embs[i + 1]
        scores.append(float((q_emb * c_emb).sum()))
    return scores
