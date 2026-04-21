"""문서용 대표 샘플 추출. input JSONL에서 세목별 최고 품질 3건 + 루프 성공 1건 출력."""

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument(
        "--semoks",
        nargs="+",
        default=["세법-부가가치세", "민법-계약임대차", "노동법-임금퇴직금"],
    )
    p.add_argument("--loop-semok", default="민법-상속증여")
    args = p.parse_args()

    rows = [
        json.loads(l)
        for l in args.input.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    picks = []
    for w in args.semoks:
        for r in rows:
            if r.get("세목") == w and r.get("cited_laws_valid_ratio", 0) >= 0.9:
                picks.append(("BEST", r))
                break

    for r in rows:
        if (
            r.get("_attempts", 1) >= 2
            and r.get("cited_laws_valid_ratio", 0) >= 0.9
            and r.get("세목") == args.loop_semok
        ):
            picks.append(("LOOP", r))
            break

    print(f"=== TOTAL SAMPLES: {len(picks)} ===")
    for tag, r in picks:
        sep = "=" * 50
        print(f"\n{sep}")
        print(
            f"[{tag}] 세목={r.get('세목')} "
            f"질문유형={r.get('질문유형')} 난이도={r.get('난이도')}"
        )
        print(
            f"valid_ratio={r.get('cited_laws_valid_ratio', 0):.2f} "
            f"attempts={r.get('_attempts', 1)} "
            f"hallucination={r.get('has_hallucination')}"
        )
        print(f"{sep}")
        if r.get("persona_ref"):
            print(f"[persona] {r.get('persona_ref')}")
        print("--- QUESTION ---")
        print((r.get("question") or "").strip())
        print("--- REASONING_COT ---")
        print((r.get("reasoning_cot") or "").strip())
        print("--- CITATIONS ---")
        inv = r.get("invalid_refs") or []
        warn = r.get("warning_refs") or []
        if inv:
            print(f"invalid: {inv}")
        if warn:
            print(f"warning: {warn[:3]}")


if __name__ == "__main__":
    main()
