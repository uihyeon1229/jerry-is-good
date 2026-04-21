"""L5 — Nemotron + Korean Law MCP Tool-use 라이브 데모 (발표 하이라이트).

흐름:
  1. 사용자 질문을 Nemotron(vLLM)에 전송 — 'search_korean_law' tool spec 등록
  2. Nemotron이 tool_call 발생 → 법령명·조문번호 결정
  3. 우리 코드가 Korean Law MCP의 get_law_text 호출 (실시간 법제처 조회)
  4. 결과를 Nemotron에 다시 넘겨 최종 자연어 답변 생성

사용:
    LAW_OC=didwjs12 python demo/nemotron_tool_call.py

발표 중 라이브 실행:
    터미널 좌: 이 스크립트 실행 로그
    터미널 우: 법제처 홈페이지에서 같은 조문 검색 → 결과 비교
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.settings import settings  # noqa: E402


OC = os.getenv("LAW_OC", "didwjs12")
MCP_URL = f"https://korean-law-mcp.fly.dev/mcp?oc={OC}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_korean_law",
            "description": (
                "한국 법령의 조문 전문을 실시간으로 조회합니다. "
                "특정 법령의 특정 조문이 필요할 때 호출하세요. "
                "법령명(예: '소득세법')과 조문번호(예: '47')를 지정하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "law_name": {
                        "type": "string",
                        "description": "법령의 정확한 이름 (예: '소득세법', '민법', '근로기준법')",
                    },
                    "article_no": {
                        "type": "string",
                        "description": "조문 번호 (예: '47', '618'). '제'나 '조'는 빼고 숫자만",
                    },
                },
                "required": ["law_name", "article_no"],
            },
        },
    }
]


SYSTEM_PROMPT = (
    "당신은 한국 법률 전문가입니다. 법령 조문이 필요하면 "
    "반드시 search_korean_law 도구를 호출해 **법제처에서 실시간 조회**한 뒤 "
    "그 결과를 인용해 답하세요. 기억에 의존하지 마세요."
)


def _print_box(title: str) -> None:
    line = "=" * 72
    print(f"\n{line}\n[ {title} ]\n{line}", flush=True)


async def _mcp_call(law_name: str, article_no: str) -> str:
    """Korean Law MCP에서 해당 조문 조회."""
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # 1) search_law로 MST 확보
            res = await session.call_tool(
                "search_law", {"query": law_name}
            )
            first = res.content[0] if res.content else None
            txt = getattr(first, "text", "") if first else ""
            # 텍스트에서 MST 추출
            import re

            m = re.search(r"MST:\s*(\d+)", txt)
            if not m:
                return f"(법령 '{law_name}'의 MST를 찾을 수 없습니다)"
            mst = m.group(1)
            # 2) get_law_text로 조문 전문
            res2 = await session.call_tool(
                "get_law_text",
                {"mst": mst, "jo": f"제{article_no}조"},
            )
            body = res2.content[0] if res2.content else None
            return getattr(body, "text", "") if body else ""


async def run_demo(user_question: str) -> None:
    client = OpenAI(base_url=settings.vllm_base_url, api_key="not-used")

    _print_box(f"사용자 질문: {user_question}")

    # 1차 호출 — tool_call 기대
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_question},
    ]
    resp1 = client.chat.completions.create(
        model=settings.vllm_model,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.2,
        max_tokens=2048,
    )
    msg1 = resp1.choices[0].message

    tool_calls = getattr(msg1, "tool_calls", None) or []
    if not tool_calls:
        print("(tool_call 발생 안 함 — content 직접 반환)")
        print(msg1.content or "")
        return

    # tool_call 발생
    _print_box(f"Nemotron tool_call: {len(tool_calls)}건")
    # OpenAI 1.x tool_calls serialize
    messages.append(
        {
            "role": "assistant",
            "content": msg1.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        }
    )

    for tc in tool_calls:
        args = json.loads(tc.function.arguments or "{}")
        print(f"  → {tc.function.name}({args})")
        result = await _mcp_call(
            args.get("law_name", ""),
            str(args.get("article_no", "")),
        )
        result_preview = result[:600].replace("\n", "\n    ")
        print(f"    [법제처 응답]\n    {result_preview}")
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.function.name,
                "content": result[:3000],
            }
        )

    # 2차 호출 — 최종 자연어 답변
    _print_box("Nemotron 최종 답변")
    resp2 = client.chat.completions.create(
        model=settings.vllm_model,
        messages=messages,
        temperature=0.2,
        max_tokens=2048,
    )
    print(resp2.choices[0].message.content or "")


SAMPLE_QUESTIONS = [
    "소득세법 제47조의 현행 근로소득공제 내용을 알려주세요.",
    "민법 제1000조는 상속 순위를 어떻게 정하고 있나요?",
    "근로기준법 제60조에 따라 3년 근속자의 연차유급휴가는 몇 일인가요?",
]


async def main() -> None:
    # CLI 인자로 질문 받기, 없으면 샘플 돌기
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--q", action="append", help="질문 (여러 번 지정 가능)")
    args = p.parse_args()

    questions = args.q or SAMPLE_QUESTIONS
    for q in questions:
        try:
            await run_demo(q)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
