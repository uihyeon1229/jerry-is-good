"""부분 A1 루프 — valid_ratio가 낮은 하위 샘플만 재시도.

시간 절약: 1000건 전부 X, 하위 N건만 재생성.
기존 상위 건은 그대로 두고 concat.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .refine_loop import refine_pipeline


async def amain() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--threshold", type=float, default=0.5,
                   help="valid_ratio < threshold 인 행만 루프 대상")
    p.add_argument("--max-retries", type=int, default=2)
    args = p.parse_args()

    rows = [
        json.loads(l) for l in args.input.read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    low = [r for r in rows if (r.get("cited_laws_valid_ratio") or 0) < args.threshold]
    high = [r for r in rows if (r.get("cited_laws_valid_ratio") or 0) >= args.threshold]
    print(
        f"=== partial refine: total={len(rows)}, low(<{args.threshold})={len(low)}, keep_high={len(high)} ===",
        flush=True,
    )

    # 하위 샘플만 임시 파일로 저장 → refine_pipeline 호출
    tmp_in = args.output.with_suffix(".low.tmp.jsonl")
    tmp_out = args.output.with_suffix(".low.refined.tmp.jsonl")
    tmp_in.parent.mkdir(parents=True, exist_ok=True)
    with tmp_in.open("w", encoding="utf-8") as fp:
        for r in low:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    stats = await refine_pipeline(tmp_in, tmp_out, max_retries=args.max_retries)
    print(f"=== refined stats: {stats} ===", flush=True)

    refined = [
        json.loads(l)
        for l in tmp_out.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    # concat: 상위(그대로) + 하위(refined)
    merged = high + refined
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        for r in merged:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    # 정리
    tmp_in.unlink(missing_ok=True)
    tmp_out.unlink(missing_ok=True)
    dropped = tmp_out.with_suffix(".dropped.jsonl")
    dropped.unlink(missing_ok=True)

    print(f"=== DONE: merged {len(merged)} rows → {args.output} ===")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
