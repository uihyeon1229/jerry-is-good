"""C2 — Counter-factual Variation.

통과한 레코드 각각에 대해, 질문 내부의 **수치만 ±30% 범위**에서 변경한 변형을 k개 생성.
같은 구조의 다른 사실관계 → SFT 학습 데이터 3~5배 증폭.

계산문제의 경우 정답 재계산이 필요하므로, reasoning_cot는 비움 (파이프라인 재생성 권장)
또는 --regenerate 플래그로 즉시 재생성.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path


# 한글 숫자 단위 지원: 원, 만원, 억, 천만원, 백만원, %
# "1,234,567원", "50만원", "8천만원", "2억", "10%"
_NUM_WITH_UNIT = re.compile(
    r"(\d[\d,]*)\s*(원|만원|천만원|백만원|억|%|년|개월|월|일|세|명)"
)

# 단독 숫자 (3자리 이상): "2023년" 같은 연도 제외는 단위로 걸러짐
_STANDALONE_NUM = re.compile(r"(?<![\d,])(\d{3,}[\d,]*)(?![\d,%])")


def _perturb_number(n: int, pct: float = 0.3, rng: random.Random | None = None) -> int:
    """n을 ±pct 범위에서 랜덤 변경. 단위 보존 위해 정수."""
    r = rng or random
    factor = r.uniform(1.0 - pct, 1.0 + pct)
    out = int(round(n * factor))
    # 크기가 너무 작으면 원본 유지
    if out < 1:
        return n
    # 단위 규모 유지 위해 반올림 자리수 조정
    if n >= 100_000_000:
        out = round(out, -7)  # 억 단위 이상
    elif n >= 10_000_000:
        out = round(out, -6)  # 천만 단위
    elif n >= 1_000_000:
        out = round(out, -5)  # 백만 단위
    elif n >= 10_000:
        out = round(out, -3)  # 만 단위
    elif n >= 1000:
        out = round(out, -2)  # 백 단위
    return int(out)


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _perturb_text(text: str, rng: random.Random) -> tuple[str, int]:
    """텍스트에서 수치를 찾아 perturbation 적용. 반환: (변형 텍스트, 변경 건수)."""
    changed = 0

    def _with_unit(m: re.Match) -> str:
        nonlocal changed
        raw = m.group(1).replace(",", "")
        unit = m.group(2)
        # 연도/세/명/개월/년/일 등은 변경 스킵
        if unit in {"년", "세", "개월", "월", "일", "명"}:
            return m.group(0)
        try:
            n = int(raw)
        except ValueError:
            return m.group(0)
        # 너무 작거나(%는 100 이하로) 극단 값 스킵
        if unit == "%" and (n < 1 or n > 100):
            return m.group(0)
        new_n = _perturb_number(n, rng=rng)
        if new_n == n:
            return m.group(0)
        changed += 1
        return f"{_fmt_int(new_n)}{unit}"

    def _standalone(m: re.Match) -> str:
        nonlocal changed
        raw = m.group(1).replace(",", "")
        try:
            n = int(raw)
        except ValueError:
            return m.group(0)
        # 4자리(연도로 보이는 것) 스킵
        if 1900 <= n <= 2100:
            return m.group(0)
        new_n = _perturb_number(n, rng=rng)
        if new_n == n:
            return m.group(0)
        changed += 1
        return _fmt_int(new_n)

    # 먼저 단위 붙은 숫자, 그 다음 독립 숫자
    new_text = _NUM_WITH_UNIT.sub(_with_unit, text)
    new_text = _STANDALONE_NUM.sub(_standalone, new_text)
    return new_text, changed


def make_variations(row: dict, *, k: int = 3, seed: int | None = None) -> list[dict]:
    """row에서 k개의 변형 생성. 수치 변경 없으면 빈 리스트."""
    question = str(row.get("question") or "")
    if not question:
        return []

    variations: list[dict] = []
    base_seed = seed if seed is not None else 0

    for i in range(k):
        rng = random.Random(base_seed * 100 + i + 1)
        new_q, changed = _perturb_text(question, rng)
        if changed == 0:
            continue  # 변경할 수치 없음
        variations.append(
            {
                **row,
                "question": new_q,
                # 답변은 다시 생성해야 정답이 맞으므로 비움 (파이프라인 재투입 대상)
                "reasoning_cot": "",
                "metadata": None,
                "quality_score": None,
                # 루프/검증 결과도 리셋
                "cited_laws_valid_ratio": None,
                "has_hallucination": None,
                "_source_uuid": row.get("uuid") or row.get("_row_id"),
                "_variation_idx": i + 1,
                "_variation_changed": changed,
            }
        )
    return variations


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--k", type=int, default=3, help="원본 1건당 변형 수")
    p.add_argument(
        "--only-calc",
        action="store_true",
        help="질문유형=계산문제인 행만 변형 생성",
    )
    args = p.parse_args()

    rows = [
        json.loads(l)
        for l in args.input.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    new_rows: list[dict] = []
    stats = {"input": len(rows), "produced": 0, "no_numbers": 0}
    for i, row in enumerate(rows):
        if args.only_calc and row.get("질문유형") != "계산문제":
            continue
        variations = make_variations(row, k=args.k, seed=i)
        if not variations:
            stats["no_numbers"] += 1
        new_rows.extend(variations)
        stats["produced"] += len(variations)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        for r in new_rows:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"=== DONE: {stats} ===")
    print(f"  → {args.output}")
    print(
        "※ 생성된 변형은 answer(reasoning_cot)가 비어있습니다. "
        "run_generate 또는 refine_loop로 다시 채워주세요."
    )


if __name__ == "__main__":
    main()
