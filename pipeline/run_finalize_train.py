"""train.jsonl 확정 — SFT용 ChatML 포맷.

필터 (간단 인라인 구현, Guardrails·Curator의 핵심 로직만):
  1. has_hallucination = False
  2. cited_laws_valid_ratio >= 0.5
  3. len(reasoning_cot) >= 300
  4. quality_score.cot_depth 존재 시 >= 3
  5. PII/탈세 키워드 regex (Guardrails 경량 버전)
  6. exact dedup (reasoning_cot 해시)

출력:
  output/final/train.jsonl      — ChatML
  output/final/eval.jsonl        — 5% 분리
  output/final/filter_stats.json — 단계별 통과 집계
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

SYSTEM_PROMPT = (
    "당신은 한국 법률 전문가입니다. 질문에 대해 적용 조문 → 사실관계 → 해석/계산 → 결론 "
    "4단계로 답하세요. 조문은 실제 존재하는 것만 인용하세요."
)

# PII / 탈세 조력 regex (경량)
PII_PATTERNS = [
    re.compile(r"\d{6}-\d{7}"),   # 주민번호
    re.compile(r"\d{3}-\d{2}-\d{5}"),  # 사업자번호
    re.compile(r"\d{11}-\d{7}"),  # 법인번호
]
TAX_EVASION_PATTERNS = [
    re.compile(r"세금을?\s*(안\s*내|회피|빼돌리|숨기)"),
    re.compile(r"차명\s*(계좌|거래)"),
    re.compile(r"허위\s*(세금계산서|매출|매입)"),
    re.compile(r"비자금"),
]
FAKE_ATTORNEY_PATTERNS = [
    re.compile(r"저는?\s*세무사"),
    re.compile(r"저는?\s*변호사"),
    re.compile(r"제가\s*대리합니다"),
]


def check_pii(text: str) -> bool:
    return any(p.search(text) for p in PII_PATTERNS)


def check_tax_evasion(text: str) -> bool:
    return any(p.search(text) for p in TAX_EVASION_PATTERNS)


def check_fake_attorney(text: str) -> bool:
    return any(p.search(text) for p in FAKE_ATTORNEY_PATTERNS)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("output/final"))
    p.add_argument("--min-valid-ratio", type=float, default=0.5)
    p.add_argument("--min-cot-len", type=int, default=300)
    p.add_argument("--min-cot-depth", type=int, default=3)
    p.add_argument("--eval-ratio", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        json.loads(l)
        for l in args.input.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    print(f"=== input: {len(rows)} rows ===", flush=True)

    stats = Counter()
    stats["input"] = len(rows)
    seen_hashes: set[str] = set()
    kept: list[dict] = []

    for r in rows:
        cot = (r.get("reasoning_cot") or "").strip()
        question = (r.get("question") or "").strip()

        # 1. 빈 답변
        if not cot or not question:
            stats["drop_empty"] += 1
            continue

        # 2. 환각 플래그
        if r.get("has_hallucination") is True:
            stats["drop_hallucination"] += 1
            continue

        # 3. valid_ratio 최소
        vr = r.get("cited_laws_valid_ratio") or 0
        if vr < args.min_valid_ratio:
            stats["drop_low_valid"] += 1
            continue

        # 4. CoT 길이
        if len(cot) < args.min_cot_len:
            stats["drop_short_cot"] += 1
            continue

        # 5. Judge cot_depth
        qs = r.get("quality_score") or {}
        if isinstance(qs, dict):
            depth = qs.get("cot_depth")
            if isinstance(depth, (int, float)) and depth < args.min_cot_depth:
                stats["drop_shallow_cot"] += 1
                continue

        # 6. Guardrails (PII/탈세/자격사칭)
        full_text = f"{question}\n{cot}"
        if check_pii(full_text):
            stats["drop_pii"] += 1
            continue
        if check_tax_evasion(full_text):
            stats["drop_tax_evasion"] += 1
            continue
        if check_fake_attorney(full_text):
            stats["drop_fake_attorney"] += 1
            continue

        # 7. Exact dedup
        h = hashlib.sha256(cot.encode("utf-8")).hexdigest()
        if h in seen_hashes:
            stats["drop_duplicate"] += 1
            continue
        seen_hashes.add(h)

        kept.append(r)

    stats["kept"] = len(kept)
    print(f"=== filter stats: {dict(stats)} ===", flush=True)

    # ChatML 변환
    def _to_chatml(r: dict) -> dict:
        return {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (r.get("question") or "").strip()},
                {"role": "assistant", "content": (r.get("reasoning_cot") or "").strip()},
            ],
            "metadata": {
                "세목": r.get("세목"),
                "질문유형": r.get("질문유형"),
                "난이도": r.get("난이도"),
                "persona_ref": r.get("persona_ref"),
                "cited_laws_valid_ratio": r.get("cited_laws_valid_ratio"),
                "_attempts": r.get("_attempts"),
            },
        }

    random.seed(args.seed)
    random.shuffle(kept)
    n_eval = max(1, int(len(kept) * args.eval_ratio))
    eval_rows = kept[:n_eval]
    train_rows = kept[n_eval:]

    train_path = args.output_dir / "train.jsonl"
    eval_path = args.output_dir / "eval.jsonl"
    stats_path = args.output_dir / "filter_stats.json"

    with train_path.open("w", encoding="utf-8") as fp:
        for r in train_rows:
            fp.write(json.dumps(_to_chatml(r), ensure_ascii=False) + "\n")
    with eval_path.open("w", encoding="utf-8") as fp:
        for r in eval_rows:
            fp.write(json.dumps(_to_chatml(r), ensure_ascii=False) + "\n")
    stats_path.write_text(
        json.dumps(dict(stats), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"=== DONE ===")
    print(f"  train: {len(train_rows)} → {train_path}")
    print(f"  eval:  {len(eval_rows)}  → {eval_path}")
    print(f"  stats: {stats_path}")


if __name__ == "__main__":
    main()
