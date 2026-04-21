"""벤치마크 채점 — Before/After 답변을 L2 citation_validator로 객관 채점.

사용:
    LAW_OC=didwjs12 python -m benchmark.score_judge \
        --before benchmark/answers_base.jsonl \
        --after  benchmark/answers_sft.jsonl \
        --output benchmark/report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.validators.citation_validator import verify_batch  # noqa: E402


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
    args = p.parse_args()

    before = by_id(load(args.before))
    after = by_id(load(args.after))
    ids = sorted(set(before) & set(after))
    print(f"=== scoring {len(ids)} pairs ===", flush=True)

    texts_before = [before[i].get("answer", "") for i in ids]
    texts_after = [after[i].get("answer", "") for i in ids]

    print("  verifying BEFORE via MCP...", flush=True)
    b_cites = await verify_batch(texts_before, concurrency=8)
    print("  verifying AFTER via MCP...", flush=True)
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
                # L2 MCP 채점
                "before_valid_ratio": b_cites[i].valid_ratio,
                "after_valid_ratio": a_cites[i].valid_ratio,
                "before_halluc": b_cites[i].has_hallucination,
                "after_halluc": a_cites[i].has_hallucination,
                # 예상 조문 커버리지
                "before_expected_law_cov": expected_coverage(b_ans, exp_laws),
                "after_expected_law_cov": expected_coverage(a_ans, exp_laws),
                # 정답 키워드 커버리지
                "before_kw_cov": keyword_coverage(b_ans, exp_kws),
                "after_kw_cov": keyword_coverage(a_ans, exp_kws),
            }
        )

    # 집계
    def _avg(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return mean(vals) if vals else 0.0

    summary = {
        "n": len(rows),
        "before_valid_ratio": _avg(rows, "before_valid_ratio"),
        "after_valid_ratio": _avg(rows, "after_valid_ratio"),
        "before_halluc_rate": sum(1 for r in rows if r["before_halluc"]) / len(rows),
        "after_halluc_rate": sum(1 for r in rows if r["after_halluc"]) / len(rows),
        "before_expected_law_cov": _avg(rows, "before_expected_law_cov"),
        "after_expected_law_cov": _avg(rows, "after_expected_law_cov"),
        "before_kw_cov": _avg(rows, "before_kw_cov"),
        "after_kw_cov": _avg(rows, "after_kw_cov"),
    }

    # 세목별 집계
    by_semok: dict[str, list] = {}
    for r in rows:
        by_semok.setdefault(r["세목"], []).append(r)

    # 리포트 작성
    lines = [
        "# 벤치마크 Before/After 리포트",
        "",
        f"- N = {summary['n']} pairs",
        "",
        "## 전체 집계",
        "| 지표 | Before | After | Δ |",
        "|-----|:---:|:---:|:---:|",
        f"| 환각 비율 | {summary['before_halluc_rate']*100:.1f}% | {summary['after_halluc_rate']*100:.1f}% | {(summary['after_halluc_rate']-summary['before_halluc_rate'])*100:+.1f}pp |",
        f"| valid_ratio | {summary['before_valid_ratio']:.3f} | {summary['after_valid_ratio']:.3f} | {summary['after_valid_ratio']-summary['before_valid_ratio']:+.3f} |",
        f"| 예상 조문 커버 | {summary['before_expected_law_cov']:.3f} | {summary['after_expected_law_cov']:.3f} | {summary['after_expected_law_cov']-summary['before_expected_law_cov']:+.3f} |",
        f"| 정답 키워드 커버 | {summary['before_kw_cov']:.3f} | {summary['after_kw_cov']:.3f} | {summary['after_kw_cov']-summary['before_kw_cov']:+.3f} |",
        "",
        "## 세목별",
        "| 세목 | n | Before valid | After valid | Δ |",
        "|-----|:---:|:---:|:---:|:---:|",
    ]
    for s, rs in sorted(by_semok.items()):
        b = mean(r["before_valid_ratio"] for r in rs)
        a = mean(r["after_valid_ratio"] for r in rs)
        lines.append(f"| {s} | {len(rs)} | {b:.3f} | {a:.3f} | {a-b:+.3f} |")

    lines += ["", "## 문제별", "| ID | 세목 | Before valid | After valid | 예상조문 Before | After |",
              "|---|---|:---:|:---:|:---:|:---:|"]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['세목']} | {r['before_valid_ratio']:.2f} | {r['after_valid_ratio']:.2f} | "
            f"{r['before_expected_law_cov']:.2f} | {r['after_expected_law_cov']:.2f} |"
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
