"""Korean Law MCP (fly.dev) 도구 목록 + verify_citations 최소 호출 테스트."""

from __future__ import annotations

import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

OC = os.getenv("LAW_OC", "didwjs12")
URL = f"https://korean-law-mcp.fly.dev/mcp?oc={OC}"


async def main() -> None:
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("=== tools ===")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description[:120] if t.description else ''}")

            # search_law 호출 테스트
            print("\n=== search_law(소득세법) ===")
            r = await session.call_tool("search_law", {"query": "소득세법"})
            for c in r.content[:1]:
                text = getattr(c, "text", str(c))
                print(text[:800])

            # verify_citations 스키마 출력
            names = {t.name for t in tools.tools}
            if "verify_citations" in names:
                spec = next(t for t in tools.tools if t.name == "verify_citations")
                print("\n=== verify_citations schema ===")
                print(json.dumps(spec.inputSchema, ensure_ascii=False, indent=2)[:1200])

                print("\n=== verify_citations (실제 호출) ===")
                sample = (
                    "본 답변은 소득세법 제20조에 따라 근로소득을 계산하며, "
                    "소득세법 제47조의 근로소득공제를 적용한다. "
                    "존재하지 않는 조문 예시: 부가가치세법 제999조."
                )
                r = await session.call_tool(
                    "verify_citations", {"text": sample}
                )
                for c in r.content[:1]:
                    out = getattr(c, "text", str(c))
                    print(out[:2000])


if __name__ == "__main__":
    asyncio.run(main())
