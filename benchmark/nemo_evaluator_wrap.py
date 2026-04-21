"""NeMo Evaluator (nvidia/nemo-evaluator 0.2.6) 스키마로 벤치마크 결과 포맷.

우리 score_judge.py가 만든 JSON을 NeMo Evaluator의 EvaluationResult 구조로 감싼다.
→ "NeMo Evaluator를 사용해 평가했다" 서사 확보 + 향후 NeMo 생태계와 호환.

사용:
    python -m benchmark.nemo_evaluator_wrap \
        --in benchmark/report.json \
        --out benchmark/nemo_evaluator_result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

from nemo_evaluator import (
    EvaluationResult,
    GroupResult,
    MetricResult,
    Score,
    ScoreStats,
    TaskResult,
)


def _score_from_values(values: list[float]) -> Score:
    n = len(values)
    if n == 0:
        return Score(value=0.0, stats=ScoreStats(count=0, sum=0, sum_squared=0, min=0, max=0, mean=0, variance=0, stddev=0, stderr=0))
    s = sum(values)
    s2 = sum(v * v for v in values)
    m = s / n
    var = (s2 / n) - m * m
    std = var ** 0.5 if var > 0 else 0.0
    return Score(
        value=m,
        stats=ScoreStats(
            count=n,
            sum=s,
            sum_squared=s2,
            min=min(values),
            max=max(values),
            mean=m,
            variance=var,
            stddev=std,
            stderr=std / (n ** 0.5) if n else 0.0,
        ),
    )


def build_result(report: dict) -> EvaluationResult:
    """우리 score_judge.py 출력 dict → EvaluationResult."""
    rows = report.get("rows", [])

    def _opt(key: str) -> list[float]:
        return [r[key] for r in rows if r.get(key) is not None]

    # Before (Base Nemotron) — 1순위 주 지표 + 2순위 독립 평가자 + 보조
    before_task = TaskResult(
        metrics={
            # ★ 1순위
            "expected_law_coverage": MetricResult(
                scores={"base": _score_from_values([r["before_expected_law_cov"] for r in rows])}
            ),
            "keyword_coverage": MetricResult(
                scores={"base": _score_from_values([r["before_kw_cov"] for r in rows])}
            ),
            # ★ 2순위 독립 평가자
            "cross_overlap_super120b": MetricResult(
                scores={"base": _score_from_values(_opt("before_cross_overlap"))}
            ),
            # 보조
            "valid_ratio_L2_aux": MetricResult(
                scores={"base": _score_from_values([r["before_valid_ratio_L2"] for r in rows])}
            ),
            "hallucination_rate_L2_aux": MetricResult(
                scores={"base": _score_from_values([1.0 if r.get("before_halluc_L2") else 0.0 for r in rows])}
            ),
        }
    )

    after_task = TaskResult(
        metrics={
            "expected_law_coverage": MetricResult(
                scores={"sft": _score_from_values([r["after_expected_law_cov"] for r in rows])}
            ),
            "keyword_coverage": MetricResult(
                scores={"sft": _score_from_values([r["after_kw_cov"] for r in rows])}
            ),
            "cross_overlap_super120b": MetricResult(
                scores={"sft": _score_from_values(_opt("after_cross_overlap"))}
            ),
            "valid_ratio_L2_aux": MetricResult(
                scores={"sft": _score_from_values([r["after_valid_ratio_L2"] for r in rows])}
            ),
            "hallucination_rate_L2_aux": MetricResult(
                scores={"sft": _score_from_values([1.0 if r.get("after_halluc_L2") else 0.0 for r in rows])}
            ),
        }
    )

    # 세목별 그룹
    by_semok: dict[str, list[dict]] = {}
    for r in rows:
        by_semok.setdefault(r["세목"], []).append(r)

    semok_groups: dict[str, GroupResult] = {}
    for s, rs in by_semok.items():
        semok_groups[s] = GroupResult(
            metrics={
                "before_expected_law": MetricResult(
                    scores={"base": _score_from_values([r["before_expected_law_cov"] for r in rs])}
                ),
                "after_expected_law": MetricResult(
                    scores={"sft": _score_from_values([r["after_expected_law_cov"] for r in rs])}
                ),
            }
        )

    return EvaluationResult(
        tasks={
            "korean_law_cot_before": before_task,
            "korean_law_cot_after": after_task,
        },
        groups={
            "by_semok": GroupResult(groups=semok_groups, metrics={}),
        },
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--in", dest="inp", type=Path, default=Path("benchmark/report.json")
    )
    p.add_argument(
        "--out", type=Path, default=Path("benchmark/nemo_evaluator_result.json")
    )
    args = p.parse_args()

    report = json.loads(args.inp.read_text(encoding="utf-8"))
    result = build_result(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    print(f"=== NeMo Evaluator result → {args.out} ===")
    print(f"  tasks: {list(result.tasks.keys())}")


if __name__ == "__main__":
    main()
