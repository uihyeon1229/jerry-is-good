"""벤치마크 채점 — Before/After 답변을 **독립 평가자 4축**으로 채점.

평가자 편향 해소 전략 (v3):
  1순위: expected_laws 커버리지 ← 사람이 지정한 정답 조문 (수작업, 편향 없음)
  2순위: cross_overlap (Super 120B B1) ← 다른 크기 독립 평가자
  3순위: Judge LLM (cot_depth, practical_utility) ← L2와 독립 축
  보조:  L2 valid_ratio ← 학습 필터에 썼으므로 편향 가능, 참고용

사용:
    NVIDIA_BUILD_API_KEY=... LAW_OC=... python -m benchmark.score_judge \
        --before benchmark/answers_base.jsonl \
        --after  benchmark/answers_sft.jsonl \
        --output benchmark/report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from statistics import mean

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.validators.citation_validator import verify_batch  # noqa: E402
from pipeline.validators.build_api_cross import cross_verify_batch  # noqa: E402


def load(path: Path) -> list[dict]:
    return [
        json.loads(l)
        for l in path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def expected_coverage(answer: str, expected: list[str]) -> float:
    """예상 조문 키워드 중 답변 텍스트에 등장한 비율."""
    if not expected:
        return 1.0
    text = (answer or "").replace(" ", "")
    hits = sum(1 for e in expected if e.replace(" ", "") in text)
    return hits / len(expected)


def keyword_coverage(answer: str, kws: list[str]) -> float:
    if not kws:
        return 1.0
    text = answer or ""
    hits = sum(1 for k in kws if k in text)
    return hits / len(kws)


async def amain() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("benchmark/report.md"))
    p.add_argument(
        "--skip-cross",
        action="store_true",
        help="Build API cross verify 스킵 (API 키 없을 때)",
    )
    args = p.parse_args()

    before = by_id(load(args.before))
    after = by_id(load(args.after))
    ids = sorted(set(before) & set(after))
    print(f"=== scoring {len(ids)} pairs (4축 독립 평가자) ===", flush=True)

    texts_before = [before[i].get("answer", "") for i in ids]
    texts_after = [after[i].get("answer", "") for i in ids]

    # --- 2순위: Super 120B 독립 교차 검증 (B1) ---
    if args.skip_cross or not os.getenv("NVIDIA_BUILD_API_KEY"):
        print("  SKIP cross_verify (NVIDIA_BUILD_API_KEY missing)", flush=True)
        b_cross = [None] * len(ids)
        a_cross = [None] * len(ids)
    else:
        questions = [before[i].get("question", "") for i in ids]
        print("  cross-verify BEFORE via Build API (Super 120B)...", flush=True)
        b_cross = await cross_verify_batch(
            list(zip(questions, texts_before)), concurrency=4
        )
        print("  cross-verify AFTER via Build API (Super 120B)...", flush=True)
        a_cross = await cross_verify_batch(
            list(zip(questions, texts_after)), concurrency=4
        )

    # --- 보조: L2 MCP 채점 (참고용, 편향 가능) ---
    print("  [보조] MCP verify_citations BEFORE...", flush=True)
    b_cites = await verify_batch(texts_before, concurrency=8)
    print("  [보조] MCP verify_citations AFTER...", flush=True)
    a_cites = await verify_batch(texts_after, concurrency=8)

    rows: list[dict] = []
    for i, qid in enumerate(ids):
        q = before[qid]
        exp_laws = q.get("expected_laws", [])
        exp_kws = q.get("expected_answer_kw", [])

        b_ans = before[qid].get("answer", "")
        a_ans = after[qid].get("answer", "")

        rows.append(
            {
                "id": qid,
                "세목": q.get("세목"),
                "난이도": q.get("난이도"),
                # ★ 1순위: expected_laws 커버리지 (사람이 지정한 정답 조문)
                "before_expected_law_cov": expected_coverage(b_ans, exp_laws),
                "after_expected_law_cov": expected_coverage(a_ans, exp_laws),
                # ★ 1순위 보조: 정답 키워드 커버리지
                "before_kw_cov": keyword_coverage(b_ans, exp_kws),
                "after_kw_cov": keyword_coverage(a_ans, exp_kws),
                # ★ 2순위: Super 120B cross_overlap (Jaccard)
                "before_cross_overlap": (
                    b_cross[i].cross_overlap if b_cross[i] else None
                ),
                "after_cross_overlap": (
                    a_cross[i].cross_overlap if a_cross[i] else None
                ),
                # 보조: L2 MCP (편향 가능, 참고용)
                "before_valid_ratio_L2": b_cites[i].valid_ratio,
                "after_valid_ratio_L2": a_cites[i].valid_ratio,
                "before_halluc_L2": b_cites[i].has_hallucination,
                "after_halluc_L2": a_cites[i].has_hallucination,
            }
        )

    # 집계
    def _avg(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return mean(vals) if vals else 0.0

    summary = {
        "n": len(rows),
        # ★ 1순위: 사람이 지정한 정답 조문 일치 (편향 없음)
        "before_expected_law_cov": _avg(rows, "before_expected_law_cov"),
        "after_expected_law_cov": _avg(rows, "after_expected_law_cov"),
        "before_kw_cov": _avg(rows, "before_kw_cov"),
        "after_kw_cov": _avg(rows, "after_kw_cov"),
        # ★ 2순위: Super 120B 독립 평가자
        "before_cross_overlap": _avg(rows, "before_cross_overlap"),
        "after_cross_overlap": _avg(rows, "after_cross_overlap"),
        # 보조: L2 (편향 가능)
        "before_valid_L2": _avg(rows, "before_valid_ratio_L2"),
        "after_valid_L2": _avg(rows, "after_valid_ratio_L2"),
        "before_halluc_L2": sum(1 for r in rows if r.get("before_halluc_L2")) / max(len(rows), 1),
        "after_halluc_L2": sum(1 for r in rows if r.get("after_halluc_L2")) / max(len(rows), 1),
    }

    # 세목별 집계
    by_semok: dict[str, list] = {}
    for r in rows:
        by_semok.setdefault(r["세목"], []).append(r)

    # 리포트 작성 (1순위 → 2순위 → 보조 순)
    def _delta(after_v, before_v):
        return after_v - before_v

    lines = [
        "# 벤치마크 Before/After 리포트 (v3 독립 평가자 4축)",
        "",
        f"- N = {summary['n']} pairs",
        "- **채점 전략**: 학습 데이터 필터링에 쓴 L2는 **보조 지표**로 강등, 주 지표는 사람 지정 정답 + Super 120B 독립 평가.",
        "",
        "## 1순위 — 사람이 지정한 정답 조문 일치 (편향 없음)",
        "| 지표 | Before | After | Δ |",
        "|-----|:---:|:---:|:---:|",
        f"| **expected_laws 커버리지** | **{summary['before_expected_law_cov']:.3f}** | **{summary['after_expected_law_cov']:.3f}** | **{_delta(summary['after_expected_law_cov'], summary['before_expected_law_cov']):+.3f}** |",
        f"| 정답 키워드 커버리지 | {summary['before_kw_cov']:.3f} | {summary['after_kw_cov']:.3f} | {_delta(summary['after_kw_cov'], summary['before_kw_cov']):+.3f} |",
        "",
        "## 2순위 — NVIDIA Build API Super 120B (독립 평가자)",
        "| 지표 | Before | After | Δ |",
        "|-----|:---:|:---:|:---:|",
        f"| **cross_overlap (Jaccard)** | **{summary['before_cross_overlap']:.3f}** | **{summary['after_cross_overlap']:.3f}** | **{_delta(summary['after_cross_overlap'], summary['before_cross_overlap']):+.3f}** |",
        "",
        "## 보조 — L2 citation_validator (학습 필터에 사용, 편향 가능, 참고용)",
        "| 지표 | Before | After | Δ |",
        "|-----|:---:|:---:|:---:|",
        f"| (보조) valid_ratio L2 | {summary['before_valid_L2']:.3f} | {summary['after_valid_L2']:.3f} | {_delta(summary['after_valid_L2'], summary['before_valid_L2']):+.3f} |",
        f"| (보조) 환각 비율 L2 | {summary['before_halluc_L2']*100:.1f}% | {summary['after_halluc_L2']*100:.1f}% | {(summary['after_halluc_L2']-summary['before_halluc_L2'])*100:+.1f}pp |",
        "",
        "## 세목별 (1순위 지표 기준)",
        "| 세목 | n | Before expected | After expected | Δ |",
        "|-----|:---:|:---:|:---:|:---:|",
    ]
    for s, rs in sorted(by_semok.items()):
        b = mean(r["before_expected_law_cov"] for r in rs)
        a = mean(r["after_expected_law_cov"] for r in rs)
        lines.append(f"| {s} | {len(rs)} | {b:.3f} | {a:.3f} | {a-b:+.3f} |")

    lines += [
        "",
        "## 문제별 (주 지표)",
        "| ID | 세목 | Before expected | After expected | Before cross | After cross |",
        "|---|---|:---:|:---:|:---:|:---:|",
    ]
    for r in rows:
        bc = r.get("before_cross_overlap")
        ac = r.get("after_cross_overlap")
        lines.append(
            f"| {r['id']} | {r['세목']} | {r['before_expected_law_cov']:.2f} | {r['after_expected_law_cov']:.2f} | "
            f"{(f'{bc:.2f}' if bc is not None else '-')} | {(f'{ac:.2f}' if ac is not None else '-')} |"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")

    # JSON 요약도 저장
    json_path = args.output.with_suffix(".json")
    json_path.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"=== DONE ===")
    print(f"  → {args.output}")
    print(f"  → {json_path}")
    print(f"\nSummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
