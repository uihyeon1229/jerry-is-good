"""NeMo Curator 실행 스크립트 (하이브리드: CPU dedup + 실 NeMo Curator Filter).

cudf/RAPIDS 미설치 환경에서도 돌아가도록 설계:
  - Exact dedup: sha256 (stdlib)
  - Fuzzy dedup: datasketch MinHash LSH (CPU)
  - Semantic dedup: NVIDIA Build API embed + cosine (배치)
  - Length filter: nemo_curator.stages.text.filters.WordCountFilter (공식)
  - Language filter: nemo_curator.stages.text.filters.FastTextLangId (공식, 모델 자동 다운로드)
  - Threshold filters: plain Python
  - Cluster balance: sklearn KMeans

입력: pipeline/curator_config.yaml + --input jsonl
출력: --output jsonl + 통계 JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml

try:
    from datasketch import MinHash, MinHashLSH  # type: ignore
except ImportError:
    MinHash = MinHashLSH = None  # type: ignore


def _get_nested(d: dict, path: str, default: Any = None) -> Any:
    cur: Any = d
    for p in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


def _ngrams(text: str, n: int = 3) -> set[str]:
    toks = re.findall(r"\w+", text)
    if len(toks) < n:
        return set(toks) or {text[:50]}
    return {" ".join(toks[i : i + n]) for i in range(len(toks) - n + 1)}


# =========================================================
# Step impls
# =========================================================


def step_exact_dedup(rows: list[dict], cfg: dict, stats: Counter) -> list[dict]:
    field = cfg.get("field", "reasoning_cot")
    seen: set[str] = set()
    kept = []
    for r in rows:
        text = (r.get(field) or "").strip()
        if not text:
            stats["exact_dedup_empty"] += 1
            continue
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if h in seen:
            stats["exact_dedup_dup"] += 1
            continue
        seen.add(h)
        kept.append(r)
    return kept


def step_fuzzy_dedup(rows: list[dict], cfg: dict, stats: Counter) -> list[dict]:
    if MinHash is None:
        print("  [fuzzy] datasketch 미설치 → 스킵", flush=True)
        stats["fuzzy_skipped"] = 1
        return rows
    field = cfg.get("field", "reasoning_cot")
    threshold = float(cfg.get("threshold", 0.85))
    num_perm = int(cfg.get("num_perm", 128))
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    sigs: dict[int, MinHash] = {}
    kept = []
    for i, r in enumerate(rows):
        text = (r.get(field) or "").strip()
        if not text:
            continue
        m = MinHash(num_perm=num_perm)
        for shingle in _ngrams(text, n=3):
            m.update(shingle.encode("utf-8"))
        if lsh.query(m):
            stats["fuzzy_dedup_dup"] += 1
            continue
        key = str(i)
        lsh.insert(key, m)
        sigs[i] = m
        kept.append(r)
    return kept


def step_semantic_dedup(rows: list[dict], cfg: dict, stats: Counter) -> list[dict]:
    field = cfg.get("field", "question")
    threshold = float(cfg.get("threshold", 0.90))

    try:
        from pipeline.embed_nvidia import embed  # noqa: WPS433
    except Exception as e:  # noqa: BLE001
        print(f"  [semantic] embed import 실패 → 스킵: {e}", flush=True)
        stats["semantic_skipped"] = 1
        return rows

    # 빈 텍스트는 embed에서 에러 → 별도 취급 (빈 값 행은 skip 유지)
    texts_all = [(r.get(field) or "").strip() for r in rows]
    nonempty_idx = [i for i, t in enumerate(texts_all) if t]
    nonempty_texts = [texts_all[i] for i in nonempty_idx]
    if not nonempty_texts:
        return rows
    try:
        embs = embed(nonempty_texts, input_type="passage")
    except Exception as e:  # noqa: BLE001
        print(f"  [semantic] embed 호출 실패 → 스킵: {e}", flush=True)
        stats["semantic_skipped"] = 1
        return rows

    drop_rows: set[int] = set()
    kept_vecs: list[np.ndarray] = []
    for local_i, orig_i in enumerate(nonempty_idx):
        v = embs[local_i]
        if kept_vecs:
            sims = np.stack(kept_vecs) @ v
            if float(sims.max()) >= threshold:
                drop_rows.add(orig_i)
                stats["semantic_dedup_dup"] += 1
                continue
        kept_vecs.append(v)
    return [r for i, r in enumerate(rows) if i not in drop_rows]


def step_length_filter(rows: list[dict], cfg: dict, stats: Counter) -> list[dict]:
    field = cfg.get("field", "reasoning_cot")
    min_w = int(cfg.get("min_words", 50))
    max_w = int(cfg.get("max_words", 2000))
    try:
        from nemo_curator.stages.text.filters import WordCountFilter  # noqa: WPS433
    except Exception as e:  # noqa: BLE001
        print(f"  [length] NeMo Curator import 실패, 수동 계산: {e}", flush=True)
        WordCountFilter = None  # type: ignore

    kept = []
    if WordCountFilter is not None:
        f = WordCountFilter(min_words=min_w, max_words=max_w, lang="ko")
        for r in rows:
            text = (r.get(field) or "").strip()
            score = f.score_document(text)
            if f.keep_document(score):
                kept.append(r)
            else:
                stats["length_drop"] += 1
    else:
        for r in rows:
            text = (r.get(field) or "").strip()
            wc = len(re.findall(r"\w+", text))
            if min_w <= wc <= max_w:
                kept.append(r)
            else:
                stats["length_drop"] += 1
    return kept


_FASTTEXT_MODEL = None


def step_language_filter(rows: list[dict], cfg: dict, stats: Counter) -> list[dict]:
    global _FASTTEXT_MODEL
    field = cfg.get("field", "reasoning_cot")
    target_lang = cfg.get("target_lang", "ko")
    min_score = float(cfg.get("min_score", 0.85))
    try:
        from nemo_curator.stages.text.filters import FastTextLangId  # noqa: WPS433
        if _FASTTEXT_MODEL is None:
            _FASTTEXT_MODEL = FastTextLangId(min_langid_score=min_score)
            if hasattr(_FASTTEXT_MODEL, "model_check_or_download"):
                _FASTTEXT_MODEL.model_check_or_download()
            if hasattr(_FASTTEXT_MODEL, "load_model"):
                _FASTTEXT_MODEL.load_model()
    except Exception as e:  # noqa: BLE001
        print(f"  [lang] FastTextLangId 불가 → 간이 한국어 체크로 대체: {e}", flush=True)
        _FASTTEXT_MODEL = None

    kept = []
    for r in rows:
        text = (r.get(field) or "").strip()
        if _FASTTEXT_MODEL is not None:
            try:
                score = _FASTTEXT_MODEL.score_document(text)
                # FastTextLangId score_document은 (score, lang) 또는 dict일 수 있음
                is_target = False
                if isinstance(score, (tuple, list)) and len(score) >= 2:
                    s, lang = score[0], score[1]
                    is_target = (lang == target_lang) and (float(s) >= min_score)
                elif isinstance(score, dict):
                    lang = score.get("lang") or score.get("language")
                    s = score.get("score", 0)
                    is_target = (lang == target_lang) and (float(s) >= min_score)
                else:
                    is_target = True
                if not is_target:
                    stats["lang_drop"] += 1
                    continue
            except Exception:
                pass
            kept.append(r)
        else:
            # 간이 한국어 체크: 한글 문자 비율
            hangul = sum(1 for c in text if "가" <= c <= "힯")
            if len(text) > 0 and hangul / len(text) >= 0.3:
                kept.append(r)
            else:
                stats["lang_drop"] += 1
    return kept


def step_threshold_filter(rows: list[dict], cfg: dict, stats: Counter) -> list[dict]:
    field = cfg.get("field")
    min_value = cfg.get("min_value")
    max_value = cfg.get("max_value")
    key = (cfg.get("name") or field or "threshold") + "_drop"
    kept = []
    for r in rows:
        v = _get_nested(r, field) if field else None
        if not isinstance(v, (int, float)):
            stats[key + "_missing"] += 1
            continue
        if min_value is not None and v < float(min_value):
            stats[key] += 1
            continue
        if max_value is not None and v > float(max_value):
            stats[key] += 1
            continue
        kept.append(r)
    return kept


def step_cluster_balance(rows: list[dict], cfg: dict, stats: Counter) -> list[dict]:
    from sklearn.cluster import KMeans  # noqa: WPS433

    field = cfg.get("field", "question")
    num_clusters = int(cfg.get("num_clusters", 50))
    max_per_cluster = int(cfg.get("max_per_cluster", 20))
    if len(rows) <= num_clusters * max_per_cluster:
        # 이미 상한 이하 — 굳이 클러스터링 생략
        print(
            f"  [cluster] rows({len(rows)}) <= limit({num_clusters*max_per_cluster}), 스킵",
            flush=True,
        )
        return rows

    try:
        from pipeline.embed_nvidia import embed  # noqa: WPS433
    except Exception as e:  # noqa: BLE001
        print(f"  [cluster] embed import 실패 → 스킵: {e}", flush=True)
        stats["cluster_skipped"] = 1
        return rows

    texts = [(r.get(field) or "").strip() for r in rows]
    embs = embed(texts, input_type="passage")
    k = min(num_clusters, len(rows))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(embs)

    buckets: dict[int, list[int]] = defaultdict(list)
    for i, l in enumerate(labels):
        buckets[int(l)].append(i)
    kept_idx: list[int] = []
    for l, idxs in buckets.items():
        chosen = idxs[:max_per_cluster]
        dropped = len(idxs) - len(chosen)
        if dropped > 0:
            stats["cluster_drop"] += dropped
        kept_idx.extend(chosen)
    kept_idx.sort()
    return [rows[i] for i in kept_idx]


STEP_IMPL = {
    "ExactDuplicatesFilter": step_exact_dedup,
    "FuzzyDuplicatesFilter": step_fuzzy_dedup,
    "SemanticDeduplicator": step_semantic_dedup,
    "WordCountFilter": step_length_filter,
    "FastTextLangId": step_language_filter,
    "ThresholdFilter": step_threshold_filter,
    "SemanticClusterBalance": step_cluster_balance,
}


def run(config: dict, rows: list[dict]) -> tuple[list[dict], dict]:
    stats: Counter = Counter()
    stats["input"] = len(rows)
    for step in config.get("steps", []):
        name = step.get("name")
        stype = step.get("type")
        impl = STEP_IMPL.get(stype)
        if impl is None:
            print(f"  [warn] 알 수 없는 step type {stype} (name={name}) → 스킵", flush=True)
            continue
        t0 = time.time()
        before = len(rows)
        rows = impl(rows, step, stats)
        after = len(rows)
        dt = time.time() - t0
        print(
            f"  [step] {name:22s} ({stype}) {before} → {after} (-{before-after})  {dt:.1f}s",
            flush=True,
        )
    stats["output"] = len(rows)
    return rows, dict(stats)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("pipeline/curator_config.yaml"))
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--stats", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=0, help="0=전량")
    args = ap.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    rows = [
        json.loads(l)
        for l in args.input.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    if args.limit > 0:
        rows = rows[: args.limit]
    print(f"=== input: {args.input} ({len(rows)} rows) ===", flush=True)

    rows, stats = run(config, rows)
    print(f"=== output: {len(rows)} rows ===", flush=True)
    print(f"=== stats: {json.dumps(stats, ensure_ascii=False, indent=2)} ===", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats_path = args.stats or args.output.with_suffix(".stats.json")
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  wrote {args.output}\n  stats {stats_path}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
