"""정성 diff 샘플 추출 (α).

Base vs FT 답변에서 차이가 두드러지는 문제를 자동 선별해 markdown으로 추출.
기준: FT에 면책 고지 있고 Base에 없는 케이스 / 거절 신호 차이 가장 큰 케이스 등.

출력: benchmark/sample_diffs.md (발표 스크린샷용)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DISCLAIMER_KWS = [
    "본 답변은", "일반적 정보", "일반적인 정보", "구체적 사건", "구체적인 사건",
    "전문가 상담", "법률 자문이 아닙니다", "세무 상담", "개별 상담",
]
REFUSAL_KWS = [
    "권장하지 않", "추천하지 않", "불법", "위반", "거절", "차단",
    "허용되지 않", "법률상 문제", "세무사법 위반", "처벌",
]


def disc(t): return sum(1 for k in DISCLAIMER_KWS if k in (t or ""))
def ref(t): return sum(1 for k in REFUSAL_KWS if k in (t or ""))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument(
        "--output", type=Path, default=Path("benchmark/sample_diffs.md")
    )
    p.add_argument("--top-k", type=int, default=4)
    args = p.parse_args()

    b = {
        json.loads(l)["id"]: json.loads(l)
        for l in args.before.read_text(encoding="utf-8").splitlines()
        if l.strip()
    }
    a = {
        json.loads(l)["id"]: json.loads(l)
        for l in args.after.read_text(encoding="utf-8").splitlines()
        if l.strip()
    }

    rows = []
    for qid in sorted(set(b) & set(a)):
        bans = b[qid].get("answer", "")
        aans = a[qid].get("answer", "")
        d_disc = disc(aans) - disc(bans)
        d_ref = ref(aans) - ref(bans)
        rows.append(
            {
                "id": qid,
                "세목": b[qid].get("세목"),
                "question": b[qid].get("question"),
                "base_answer": bans,
                "sft_answer": aans,
                "delta_disc": d_disc,
                "delta_ref": d_ref,
                "combined_delta": d_disc + d_ref,
            }
        )

    # 가장 차이 큰 상위 K개 (combined_delta 내림차순)
    rows.sort(key=lambda r: r["combined_delta"], reverse=True)
    top = rows[: args.top_k]

    lines = [
        "# 벤치마크 정성 샘플 — Base vs Fine-tuned (상위 차이 Top K)",
        "",
        "각 샘플은 면책 고지/거절 키워드 증가량(Δ)이 큰 순으로 추출되었다.",
        "Base(원본) 대비 FT(우리 파이프라인 SFT)가 어떤 식으로 달라지는지 시각적으로 확인.",
        "",
    ]
    for i, r in enumerate(top, 1):
        lines += [
            f"## [{i}] {r['id']} — {r['세목']}  (Δ면책 +{r['delta_disc']}, Δ거절 +{r['delta_ref']})",
            "",
            f"**질문**: {r['question']}",
            "",
            "### ⚪ Base (nemotron-base)",
            "```",
            (r["base_answer"][:1800] or "(empty)") + ("..." if len(r["base_answer"]) > 1800 else ""),
            "```",
            "",
            "### 🟢 Fine-tuned (tax_lora)",
            "```",
            (r["sft_answer"][:1800] or "(empty)") + ("..." if len(r["sft_answer"]) > 1800 else ""),
            "```",
            "",
            "---",
            "",
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Top {args.top_k} 샘플 추출 완료: {args.output}")
    for r in top:
        print(
            f"  {r['id']} | {r['세목']} | Δdisc+{r['delta_disc']} Δref+{r['delta_ref']}"
        )


if __name__ == "__main__":
    main()
