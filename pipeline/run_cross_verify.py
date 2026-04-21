"""S3.5 단계 — B1 Build API 교차 검증 실행 스크립트.

사용법:
    NVIDIA_BUILD_API_KEY=... python -m pipeline.run_cross_verify \
        --input output/raw/c1_v3_n50.jsonl \
        --output output/cross/c1_v3_n50_crossed.jsonl

입력 JSONL의 각 행에 cross_overlap·cross_common 등 컬럼 추가.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean

from .validators.build_api_cross import cross_verify_batch


async def amain() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--concurrency", type=int, default=4)
    args = p.parse_args()

    rows = [
        json.loads(l)
        for l in args.input.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    items = [
        (str(r.get("question") or ""), str(r.get("reasoning_cot") or ""))
        for r in rows
    ]
    print(f"=== cross-verify {len(rows)} rows via Build API ===", flush=True)

    results = await cross_verify_batch(items, concurrency=args.concurrency)

    for row, res in zip(rows, results):
        row.update(res.to_dict())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    overlaps = [r["cross_overlap"] for r in rows]
    with_nano = [r for r in rows if r.get("cross_nano_refs")]
    with_super = [r for r in rows if r.get("cross_super_refs")]
    print(
        f"=== DONE: n={len(rows)}, "
        f"avg_overlap={mean(overlaps):.3f}, "
        f"nano_refs_present={len(with_nano)}, "
        f"super_refs_present={len(with_super)} ==="
    )
    print(f"  → {args.output}")


if __name__ == "__main__":
    asyncio.run(amain())
