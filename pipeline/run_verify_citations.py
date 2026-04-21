"""JSONL 파이프라인 단계 S2 — L2 조문 존재성 검증.

사용법:
    python -m pipeline.run_verify_citations \
        --input output/raw/tax_cot_v1_1000.jsonl \
        --output output/verified/tax_cot_v1_1000.jsonl \
        --threshold 0.7

임계치 미만(혹은 has_hallucination=True)은 filtered에서 제거됨.
검증 수치는 모든 행에 공통으로 주입 (분석용).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .validators.citation_validator import CitationResult, verify_batch


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fp:
        return [json.loads(line) for line in fp if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


async def amain() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--field", default="reasoning_cot", help="검증 대상 컬럼명"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="valid_ratio < threshold 인 행 제거",
    )
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--keep-all",
        action="store_true",
        help="기준 미달이어도 제거하지 않고 플래그만 주입 (분석용)",
    )
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    texts = [str(r.get(args.field) or "") for r in rows]
    print(f"=== verify {len(rows)} rows (field={args.field}) ===", flush=True)

    results: list[CitationResult] = await verify_batch(
        texts, concurrency=args.concurrency
    )

    kept: list[dict] = []
    dropped: list[dict] = []
    for row, res in zip(rows, results):
        row.update(res.to_dict())
        row["_citation_raw"] = res.raw[:500]  # 디버그용 trunc
        if args.keep_all:
            kept.append(row)
            continue
        if res.has_hallucination or res.valid_ratio < args.threshold:
            dropped.append(row)
        else:
            kept.append(row)

    dump_jsonl(args.output, kept)

    stats = {
        "input": len(rows),
        "kept": len(kept),
        "dropped": len(dropped),
        "avg_valid_ratio": sum(r.valid_ratio for r in results) / max(len(results), 1),
        "hallucination_count": sum(1 for r in results if r.has_hallucination),
    }
    print(f"=== DONE: {stats} ===")
    print(f"  → {args.output}")

    if dropped:
        drop_path = args.output.with_suffix(".dropped.jsonl")
        dump_jsonl(drop_path, dropped)
        print(f"  → dropped: {drop_path}")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
