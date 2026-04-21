"""MCP search_decisions / chain_dispute_prep 응답 구조 탐색."""

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
            for tname in ("search_decisions", "chain_dispute_prep"):
                spec = next((t for t in tools.tools if t.name == tname), None)
                print(f"\n=== {tname} schema ===")
                if spec:
                    print(json.dumps(spec.inputSchema, ensure_ascii=False, indent=2)[:1500])

            print("\n=== search_decisions('소득세법 제47조') ===")
            r = await session.call_tool(
                "search_decisions",
                {"query": "소득세법 제47조", "domain": "precedent"},
            )
            first = r.content[0] if r.content else None
            print((getattr(first, "text", "") if first else "")[:2500])

            print("\n=== search_decisions('소득세법') ===")
            r = await session.call_tool(
                "search_decisions",
                {"query": "소득세법", "domain": "precedent"},
            )
            first = r.content[0] if r.content else None
            print((getattr(first, "text", "") if first else "")[:2500])


if __name__ == "__main__":
    asyncio.run(main())
