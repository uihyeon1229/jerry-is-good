"""S3.7 — B2 Semantic Drift 검사 파이프라인 단계.

사용법:
    python -m pipeline.run_drift_check \
        --input output/cross/tax_cot_v3_1000_crossed.jsonl \
        --output output/drift/tax_cot_v3_1000_drift.jsonl \
        --threshold 0.45
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from .validators.drift_detector import drift_scores_batch


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--threshold", type=float, default=0.45)
    p.add_argument(
        "--keep-all",
        action="store_true",
        help="임계치 미달도 제거하지 않고 플래그만 주입",
    )
    args = p.parse_args()

    rows = [
        json.loads(l)
        for l in args.input.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    pairs = [
        (str(r.get("question") or ""), str(r.get("reasoning_cot") or ""))
        for r in rows
    ]
    print(f"=== drift check {len(rows)} rows (threshold={args.threshold}) ===", flush=True)
    scores = drift_scores_batch(pairs)

    kept: list[dict] = []
    dropped: list[dict] = []
    for row, s in zip(rows, scores):
        row["qc_similarity"] = round(s, 4)
        row["qc_drift_flag"] = s < args.threshold
        if args.keep_all or s >= args.threshold:
            kept.append(row)
        else:
            dropped.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        for r in kept:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(
        f"=== DONE: input={len(rows)}, kept={len(kept)}, dropped={len(dropped)}, "
        f"avg_sim={mean(scores):.3f}, min_sim={min(scores):.3f} ==="
    )
    print(f"  → {args.output}")

    if dropped:
        drop_path = args.output.with_suffix(".dropped.jsonl")
        with drop_path.open("w", encoding="utf-8") as fp:
            for r in dropped:
                fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        print(f"  → dropped: {drop_path}")


if __name__ == "__main__":
    main()
