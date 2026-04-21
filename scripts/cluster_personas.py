"""페르소나 10K → bge-m3 임베딩 → k-means 클러스터링 → 200 대표 선별.

산출물:
  cache/personas/korea_10k_embeddings.npy  — 임베딩 캐시
  cache/personas/korea_reps_200.jsonl      — 200명 대표 (cluster별 centroid 최근접)
  cache/personas/cluster_stats.json        — cluster 분포·silhouette 통계
  pipeline/persona_evidence.md             — 발표 증거 문서

사용:
  PERSONA_SRC=cache/personas/korea_10k.jsonl \
  K=200 \
  python scripts/cluster_personas.py
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import numpy as np


def _persona_text(p: dict) -> str:
    """임베딩 입력용 페르소나 요약 텍스트."""
    fields = [
        f"나이 {p.get('age')}세",
        f"성별 {p.get('sex') or ''}",
        f"직업 {p.get('occupation') or ''}",
        f"학력 {p.get('education_level') or ''}",
        f"가족 {p.get('family_type') or ''}",
        f"거주 {p.get('housing_type') or ''} {p.get('province') or ''}",
        f"요약 {p.get('persona') or ''}",
        f"직업상세 {p.get('professional_persona') or ''}",
        f"가족관계 {p.get('family_persona') or ''}",
    ]
    return " | ".join(f for f in fields if f)


def load_personas(path: Path) -> list[dict]:
    return [
        json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()
    ]


def embed_all(personas: list[dict], batch_size: int, device: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    texts = [_persona_text(p) for p in personas]
    print(f"=== loading bge-m3 on {device} ===", flush=True)
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    print(f"=== encoding {len(texts)} personas (batch={batch_size}) ===", flush=True)
    embs = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embs.astype(np.float32)


def cluster_and_pick(embs: np.ndarray, k: int, seed: int = 42):
    from sklearn.cluster import KMeans

    print(f"=== k-means (k={k}) ===", flush=True)
    km = KMeans(n_clusters=k, random_state=seed, n_init=10)
    labels = km.fit_predict(embs)

    # 각 cluster centroid에 가장 가까운 원본 인덱스 찾기
    reps = []
    for c in range(k):
        members = np.where(labels == c)[0]
        if len(members) == 0:
            continue
        centroid = km.cluster_centers_[c]
        sub = embs[members]
        # cosine이 normalize된 상태라 dot product == similarity
        sims = sub @ centroid
        best_local = int(np.argmax(sims))
        reps.append(int(members[best_local]))
    return labels, reps


def silhouette_sample(embs: np.ndarray, labels: np.ndarray, sample_n: int = 2000) -> float:
    """대용량은 일부 샘플만 — sklearn silhouette은 O(n²)."""
    from sklearn.metrics import silhouette_score

    rng = np.random.default_rng(0)
    n = embs.shape[0]
    idx = rng.choice(n, size=min(sample_n, n), replace=False)
    return float(silhouette_score(embs[idx], labels[idx], metric="cosine"))


def main() -> None:
    src = Path(os.getenv("PERSONA_SRC", "cache/personas/korea_10k.jsonl"))
    k = int(os.getenv("K", "200"))
    batch = int(os.getenv("BATCH_SIZE", "32"))
    device = os.getenv("DEVICE", "cpu")  # GPU가 vLLM에 점유되면 CPU
    out_dir = src.parent
    emb_path = out_dir / "korea_10k_embeddings.npy"
    reps_path = out_dir / f"korea_reps_{k}.jsonl"
    stats_path = out_dir / "cluster_stats.json"

    personas = load_personas(src)
    print(f"=== loaded {len(personas)} personas ===", flush=True)

    # 임베딩 (캐시)
    if emb_path.exists() and not os.getenv("FORCE_EMBED"):
        print(f"=== cached embeddings: {emb_path} ===", flush=True)
        embs = np.load(emb_path)
    else:
        embs = embed_all(personas, batch_size=batch, device=device)
        np.save(emb_path, embs)
        print(f"=== saved {emb_path} shape={embs.shape} ===", flush=True)

    # 클러스터링
    labels, reps_idx = cluster_and_pick(embs, k=k)
    print(f"=== reps: {len(reps_idx)} selected ===", flush=True)

    # 대표 저장
    with reps_path.open("w", encoding="utf-8") as fp:
        for i in reps_idx:
            p = {**personas[i], "_cluster_id": int(labels[i])}
            fp.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"=== saved {reps_path} ===", flush=True)

    # 통계
    cluster_sizes = Counter(int(x) for x in labels)
    sizes_sorted = sorted(cluster_sizes.values())
    sil = silhouette_sample(embs, labels)

    # 직업·연령 분포 (대표 200)
    rep_occs = Counter(personas[i].get("occupation") for i in reps_idx)
    rep_ages_bucket = Counter()
    for i in reps_idx:
        a = personas[i].get("age") or 0
        rep_ages_bucket[
            "<30" if a < 30 else ("30-49" if a < 50 else "50+")
        ] += 1
    rep_edu = Counter(personas[i].get("education_level") for i in reps_idx)
    rep_province = Counter(personas[i].get("province") for i in reps_idx)

    stats = {
        "n_personas": len(personas),
        "k": k,
        "n_reps": len(reps_idx),
        "cluster_size_min": sizes_sorted[0] if sizes_sorted else 0,
        "cluster_size_median": sizes_sorted[len(sizes_sorted) // 2] if sizes_sorted else 0,
        "cluster_size_max": sizes_sorted[-1] if sizes_sorted else 0,
        "silhouette_sample": sil,
        "rep_age_distribution": dict(rep_ages_bucket),
        "rep_education_distribution": dict(rep_edu),
        "rep_province_top10": dict(rep_province.most_common(10)),
        "rep_occupation_top15": dict(rep_occs.most_common(15)),
    }
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== saved {stats_path} ===", flush=True)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
