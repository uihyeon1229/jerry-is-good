"""L2 재시도 루프 (A1) + Judge 기반 Selective Regen (A2).

입력: 이미 한 번 생성된 JSONL (예: output/raw/*.jsonl — L2 검증 후/전 무관)
동작: 각 행에 대해 아래 조건을 만족 못 하면 프롬프트를 강화해 재생성:
  - has_hallucination == True
  - cited_laws_valid_ratio < threshold
  - (선택) quality_score.cot_depth < 3

재생성은 seed_context 뒤에 '이전 실패 조문 블랙리스트'를 덧붙여 DD로 한 번 더 돌린다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from data_designer.config import DataDesignerConfigBuilder
from data_designer.interface import DataDesigner
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .builder import build_config
from .checkpoint import Checkpoint
from .providers import vllm_provider
from .validators.citation_validator import (
    DEFAULT_URL as MCP_URL,
    verify_text,
)

VALIDITY_THRESHOLD = float(os.getenv("REFINE_VALIDITY_THRESHOLD", "0.7"))
COT_DEPTH_THRESHOLD = int(os.getenv("REFINE_COT_DEPTH_THRESHOLD", "3"))
MAX_RETRIES = int(os.getenv("REFINE_MAX_RETRIES", "2"))


def _needs_retry(row: dict) -> str | None:
    """재시도 필요 사유 (None이면 통과)."""
    if row.get("has_hallucination"):
        return "hallucination"
    if (row.get("cited_laws_valid_ratio") or 0) < VALIDITY_THRESHOLD:
        return "low_valid_ratio"
    # A2: Judge 품질
    qs = row.get("quality_score") or {}
    if isinstance(qs, dict):
        depth = qs.get("cot_depth")
        if isinstance(depth, (int, float)) and depth < COT_DEPTH_THRESHOLD:
            return "shallow_cot"
    return None


def _augment_seed_context(row: dict) -> str:
    """이전 실패한 invalid_refs를 블랙리스트로 seed_context에 추가."""
    base = row.get("seed_context") or ""
    invalid = row.get("invalid_refs") or []
    if not invalid:
        return base
    blacklist = ", ".join(invalid[:10])
    return (
        base
        + "\n\n**이전 답변에서 아래 조문이 법제처 DB 검증에 실패했습니다. "
        + "절대 재사용 금지: " + blacklist + "**"
    )


def _regen_one_row(base_row: dict, builder: DataDesignerConfigBuilder) -> dict | None:
    """재생성: 같은 (세목, 질문유형, 난이도, persona)로 1건 생성.

    DD는 개별 행 직접 재실행 API가 제한적이라 preview(num_records=1)로 샘플링 고정 대신
    context를 다시 만들어 1건 생성. seed_context는 _augment_seed_context로 강화.

    구현 단순화: 현 버전은 base_row의 question을 그대로 쓰고 reasoning_cot만 재생성하는
    single-shot LLM 호출 방식 (DD 파이프라인 재진입 없이).
    """
    from openai import OpenAI

    from .settings import settings

    client = OpenAI(base_url=settings.vllm_base_url, api_key="not-used")
    seed_ctx = _augment_seed_context(base_row)

    # DD COT_PROMPT와 동일 포맷으로 최소 프롬프트 조립
    prompt = f"""당신은 한국 법률 전문가입니다. 다음 질문에 대해 **적용 조문 → 사실관계 → 해석/계산 → 결론** 4단계의 Chain-of-Thought 추론을 한국어로 작성하세요.

도메인/세부: {base_row.get('세목', '')}
질문유형: {base_row.get('질문유형', '')}
난이도: {base_row.get('난이도', '')}

질문:
{base_row.get('question', '')}

**아래는 {base_row.get('세목', '')}와 관련된 실제 한국 법령 조문입니다. 답변에서는 반드시 이 목록 안에 있는 조문만 인용하세요.**

{seed_ctx}

지침:
- 각 단계를 명확히 구분
- 조문 인용은 위 목록에서만 (법령명 + 조문번호)
- 세법 계산문제는 숫자 근거 제시, 민법·노동법은 조문 해석 중심
- 결론은 한두 문장으로 요약
- 답변 말미에 한 줄 고지: "※ 본 답변은 일반적인 정보 제공이며, 구체적 사건에 대한 법률 자문이 아닙니다."
"""
    try:
        resp = client.chat.completions.create(
            model=settings.vllm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=settings.max_tokens_cot,
        )
        content = resp.choices[0].message.content or ""
    except Exception as e:  # noqa: BLE001
        return None
    return {**base_row, "reasoning_cot": content}


async def refine_pipeline(
    input_path: Path,
    output_path: Path,
    *,
    max_retries: int = MAX_RETRIES,
    verbose: bool = True,
) -> dict:
    rows = [
        json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if verbose:
        print(f"=== refine {len(rows)} rows (max_retries={max_retries}) ===", flush=True)

    builder = build_config()  # 현 build 사용 안 하지만 일관성 위해 초기화
    stats = {"total": len(rows), "passed_first": 0, "passed_after_retry": 0, "final_failed": 0}
    final_rows: list[dict] = []

    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            for i, row in enumerate(rows):
                reason = _needs_retry(row)
                if reason is None:
                    stats["passed_first"] += 1
                    row.setdefault("_attempts", 1)
                    row.setdefault("_refine_reason", None)
                    final_rows.append(row)
                    if verbose:
                        print(f"[{i+1}/{len(rows)}] pass (first)", flush=True)
                    continue

                best = row
                success = False
                for attempt in range(1, max_retries + 1):
                    new_row = _regen_one_row(best, builder)
                    if not new_row or not new_row.get("reasoning_cot"):
                        break
                    cit = await verify_text(session, new_row["reasoning_cot"])
                    new_row.update(cit.to_dict())
                    new_row["_attempts"] = 1 + attempt
                    new_row["_refine_reason"] = reason

                    if not _needs_retry(new_row):
                        best = new_row
                        success = True
                        break

                    if (new_row.get("cited_laws_valid_ratio") or 0) > (
                        best.get("cited_laws_valid_ratio") or 0
                    ):
                        best = new_row

                if success:
                    stats["passed_after_retry"] += 1
                else:
                    stats["final_failed"] += 1
                    best.setdefault("_attempts", 1 + max_retries)
                    best.setdefault("_refine_reason", reason)
                final_rows.append(best)

                if verbose:
                    print(
                        f"[{i+1}/{len(rows)}] {reason} → "
                        f"{'OK' if success else 'FAILED'} "
                        f"(attempts={best.get('_attempts')})",
                        flush=True,
                    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        for r in final_rows:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    stats["kept"] = len(final_rows)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-retries", type=int, default=MAX_RETRIES)
    args = parser.parse_args()

    stats = asyncio.run(
        refine_pipeline(args.input, args.output, max_retries=args.max_retries)
    )
    print(f"=== REFINE DONE: {stats} ===")
    print(f"  → {args.output}")


if __name__ == "__main__":
    main()
