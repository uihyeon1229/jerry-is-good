"""NeMo Guardrails 실행 스크립트 (self_check_output 기반 배치 필터).

구성: pipeline/guardrails/config.yml 의 self_check_output 프롬프트를 각 row에 적용.
  - 탈세 조력 / 자격 사칭 / PII / 자문 대체 / 폐지 조문 을 하나의 YES/NO 판정으로 수렴
  - 추가 경량 regex(PII 주민/사업자번호, 탈세 키워드, 자격 사칭)도 사전 필터로 병행

입력: Curator 통과본 jsonl
출력: safe jsonl + 통계
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore


PII_PATTERNS = [
    re.compile(r"\d{6}-\d{7}"),   # 주민번호
    re.compile(r"\d{3}-\d{2}-\d{5}"),  # 사업자번호
    re.compile(r"\d{11}-\d{7}"),  # 법인번호
]
TAX_EVASION_PATTERNS = [
    re.compile(r"세금을?\s*(안\s*내|회피|빼돌리|숨기)"),
    re.compile(r"차명\s*(계좌|거래)"),
    re.compile(r"허위\s*(세금계산서|매출|매입)"),
    re.compile(r"비자금"),
]
FAKE_ATTORNEY_PATTERNS = [
    re.compile(r"제가\s*(직접\s*)?대리합니다"),
    re.compile(r"저는?\s*(세무사|변호사)입니다"),
]


def inline_regex_flag(text: str) -> str | None:
    for p in PII_PATTERNS:
        if p.search(text):
            return "pii"
    for p in TAX_EVASION_PATTERNS:
        if p.search(text):
            return "tax_evasion"
    for p in FAKE_ATTORNEY_PATTERNS:
        if p.search(text):
            return "fake_attorney"
    return None


def build_self_check_prompt(config: dict, cot: str) -> str:
    """config.prompts 에서 self_check_output 템플릿 가져와 {{bot_response}} 치환."""
    for p in config.get("prompts", []):
        if p.get("task") == "self_check_output":
            tpl = p.get("content", "")
            return tpl.replace("{{ bot_response }}", cot[:6000])
    # 폴백 템플릿
    return (
        "다음 법률 CoT 답변이 탈세조력/자격사칭/PII/법률자문대체/폐지조문 중 하나라도 "
        f"해당하면 YES, 아니면 NO로만 답하세요.\n\n{cot[:6000]}\n\n답 (YES/NO):"
    )


async def _judge_one(client, model: str, prompt: str, sem: asyncio.Semaphore) -> str:
    async with sem:
        for attempt in range(3):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=20,
                )
                txt = (resp.choices[0].message.content or "").strip().upper()
                return "YES" if "YES" in txt else "NO"
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"    [judge-err] {e}", flush=True)
                    return "ERROR"
                await asyncio.sleep(1 + attempt)
        return "ERROR"


async def run(
    rows: list[dict],
    config: dict,
    model: str,
    base_url: str,
    api_key: str,
    concurrency: int,
    stats: Counter,
) -> list[dict]:
    if AsyncOpenAI is None:
        raise RuntimeError("openai 패키지 필요")
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    sem = asyncio.Semaphore(concurrency)

    # 1차: regex 사전 필터
    llm_queue: list[tuple[int, dict, str]] = []
    kept: list[dict | None] = [None] * len(rows)
    for i, r in enumerate(rows):
        q = (r.get("question") or "").strip()
        cot = (r.get("reasoning_cot") or "").strip()
        if not cot:
            stats["drop_empty_cot"] += 1
            continue
        flag = inline_regex_flag(f"{q}\n{cot}")
        if flag:
            stats[f"drop_regex_{flag}"] += 1
            continue
        prompt = build_self_check_prompt(config, cot)
        llm_queue.append((i, r, prompt))

    print(f"  [guardrails] regex 통과 {len(llm_queue)}/{len(rows)} → LLM 판정", flush=True)

    # 2차: self_check_output LLM 호출 (병렬)
    t0 = time.time()
    tasks = [_judge_one(client, model, p, sem) for _, _, p in llm_queue]
    results = await asyncio.gather(*tasks)
    dt = time.time() - t0
    print(f"  [guardrails] {len(results)}건 LLM 판정 {dt:.1f}s", flush=True)

    for (i, r, _), verdict in zip(llm_queue, results):
        if verdict == "YES":
            stats["drop_llm_self_check"] += 1
            continue
        if verdict == "ERROR":
            stats["drop_llm_error"] += 1
            # fail-close: 에러는 안전한 쪽으로 drop
            continue
        kept[i] = r

    return [r for r in kept if r is not None]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("pipeline/guardrails/config.yml"))
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--stats", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--base-url", default=os.getenv("VLLM_BASE_URL", "http://localhost:5000/v1"))
    ap.add_argument("--model", default=os.getenv("VLLM_MODEL", "nemotron"))
    ap.add_argument("--api-key", default=os.getenv("VLLM_API_KEY", "not-used"))
    args = ap.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    rows = [
        json.loads(l)
        for l in args.input.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    if args.limit > 0:
        rows = rows[: args.limit]
    print(f"=== input: {args.input} ({len(rows)} rows) ===", flush=True)

    stats: Counter = Counter()
    stats["input"] = len(rows)

    kept = asyncio.run(
        run(
            rows,
            config,
            args.model,
            args.base_url,
            args.api_key,
            args.concurrency,
            stats,
        )
    )
    stats["output"] = len(kept)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        for r in kept:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats_path = args.stats or args.output.with_suffix(".stats.json")
    stats_path.write_text(
        json.dumps(dict(stats), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"=== output: {len(kept)} rows / stats: {dict(stats)} ===\n"
        f"  wrote {args.output}\n  stats {stats_path}",
        flush=True,
    )


if __name__ == "__main__":
    sys.exit(main())
