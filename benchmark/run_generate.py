"""벤치마크 답변 생성 — Base 또는 SFT'd 모델에 20문제 돌림.

사용:
    # Base
    VLLM_MODEL=nemotron python -m benchmark.run_generate \
        --questions benchmark/questions.jsonl \
        --output benchmark/answers_base.jsonl \
        --tag base

    # SFT'd (LoRA)
    VLLM_MODEL=nemotron-lora python -m benchmark.run_generate \
        --questions benchmark/questions.jsonl \
        --output benchmark/answers_sft.jsonl \
        --tag sft
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

# pipeline 모듈 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.seeds import seed_context_for  # noqa: E402
from pipeline.settings import settings  # noqa: E402


SYSTEM_PROMPT = (
    "당신은 한국 법률 전문가입니다. "
    "질문에 대해 적용 조문 → 사실관계 → 해석/계산 → 결론 4단계로 답하세요. "
    "조문은 실제 존재하는 것만 인용하세요."
)


def build_prompt(q: dict) -> str:
    seed_ctx = seed_context_for(q.get("세목") or "")
    parts = [
        f"세목: {q.get('세목', '')}",
        f"질문유형: {q.get('질문유형', '')}",
        f"난이도: {q.get('난이도', '')}",
        "",
        f"질문:\n{q.get('question', '')}",
    ]
    if seed_ctx:
        parts.extend(
            [
                "",
                "**아래 조문을 참고하세요 (답변은 이 목록 안의 조문만 인용):**",
                seed_ctx,
            ]
        )
    parts.append("")
    parts.append("적용 조문 → 사실관계 → 해석/계산 → 결론 4단계로 답하세요.")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--questions", type=Path, default=Path("benchmark/questions.jsonl"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--tag", default="base", help="base 또는 sft 등 식별자")
    p.add_argument("--model", default=settings.vllm_model)
    p.add_argument("--base-url", default=settings.vllm_base_url)
    p.add_argument("--max-tokens", type=int, default=8000)
    p.add_argument("--temperature", type=float, default=0.3)
    args = p.parse_args()

    questions = [
        json.loads(l)
        for l in args.questions.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    print(f"=== benchmark {args.tag} — n={len(questions)} model={args.model} ===", flush=True)

    client = OpenAI(base_url=args.base_url, api_key="not-used")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as fp:
        for i, q in enumerate(questions, 1):
            prompt = build_prompt(q)
            t0 = time.time()
            try:
                resp = client.chat.completions.create(
                    model=args.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                )
                msg = resp.choices[0].message
                content = msg.content or ""
                reasoning = getattr(msg, "reasoning_content", None) or ""
                elapsed = time.time() - t0
                out = {
                    **q,
                    "tag": args.tag,
                    "model": args.model,
                    "answer": content,
                    "reasoning_trace": reasoning[:2000],
                    "elapsed_sec": round(elapsed, 2),
                }
            except Exception as e:  # noqa: BLE001
                out = {**q, "tag": args.tag, "answer": "", "error": str(e)}
            fp.write(json.dumps(out, ensure_ascii=False) + "\n")
            ans_preview = (out.get("answer") or "")[:80].replace("\n", " ")
            print(f"[{i}/{len(questions)}] {q.get('id')} ({elapsed:.1f}s) {ans_preview}", flush=True)

    print(f"=== DONE → {args.output} ===")


if __name__ == "__main__":
    main()
