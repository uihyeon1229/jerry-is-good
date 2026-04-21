"""본 생성 실행 스크립트.

사용법:
    python -m pipeline.run_generate --n 50            # 검증용
    python -m pipeline.run_generate --n 1000 --create # 본 생성
    python -m pipeline.run_generate --n 5 --preview   # smoke
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data_designer.interface import DataDesigner

from .builder import build_config
from .providers import vllm_provider
from .settings import ensure_dirs, settings


def _records(result) -> list[dict]:
    ds = getattr(result, "dataset", None)
    if ds is None:
        return []
    try:
        return ds.to_dict(orient="records")
    except AttributeError:
        return list(ds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=settings.num_records)
    parser.add_argument("--name", default="tax_cot")
    parser.add_argument(
        "--mode",
        choices=["preview", "create"],
        default="preview",
        help="preview: 빠른 검증 / create: 본 생성 및 결과 저장",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="출력 JSONL 경로 (기본: output/raw/<name>_<n>.jsonl)",
    )
    args = parser.parse_args()

    ensure_dirs()

    out = args.out or (
        settings.output_dir / "raw" / f"{args.name}_{args.n}.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    builder = build_config()
    dd = DataDesigner(model_providers=[vllm_provider()])

    print(f"=== {args.mode.upper()}: n={args.n}, out={out} ===", flush=True)

    if args.mode == "preview":
        result = dd.preview(builder, num_records=args.n)
    else:
        result = dd.create(
            builder, num_records=args.n, dataset_name=args.name
        )

    records = _records(result)
    print(f"=== GENERATION DONE: {len(records)} records ===", flush=True)

    if not records:
        print("!! no records extracted, result repr:")
        print(repr(result)[:600])
        return

    with out.open("w", encoding="utf-8") as fp:
        for r in records:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    # 요약
    cot_lens = [len(str(r.get("reasoning_cot") or "")) for r in records]
    filled = sum(1 for n in cot_lens if n > 200)
    print(
        f"=== Summary: {filled}/{len(records)} rows with cot_len>200 "
        f"(fill_rate={filled / len(records):.0%}), "
        f"avg={sum(cot_lens) / len(cot_lens):.0f}자 ==="
    )


if __name__ == "__main__":
    main()
