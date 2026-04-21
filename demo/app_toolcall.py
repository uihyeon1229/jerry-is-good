"""L5 Tool-use 라이브 데모 — Streamlit UI 버전.

demo/nemotron_tool_call.py 의 CLI 경로를 화면에 예쁘게 렌더.
관객이 실시간으로:
  질문 입력 → Nemotron이 tool_call 결정 → Korean Law MCP 호출 →
  법제처 조문 반환 → Nemotron 최종 답변 순서를 본다.

실행:
    LAW_OC=didwjs12 VLLM_BASE_URL=http://localhost:5000/v1 VLLM_MODEL=nemotron \
        streamlit run demo/app_toolcall.py --server.port 8700 --server.address 0.0.0.0

로컬 접속:
    brev port-forward jerryisgood-h100-80gib-vram-sxm5 -p 8700:8700
    브라우저: http://localhost:8700

vLLM 사전 조건:
    --enable-auto-tool-choice
    --tool-call-parser qwen3_coder
    --reasoning-parser-plugin ./nano_v3_reasoning_parser.py  (있다면)
    --reasoning-parser nano_v3                               (있다면)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time

import streamlit as st
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import OpenAI

BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:5000/v1")
MODEL = os.getenv("VLLM_MODEL", "nemotron")
OC = os.getenv("LAW_OC", "didwjs12")
MCP_URL = f"https://korean-law-mcp.fly.dev/mcp?oc={OC}"

st.set_page_config(
    layout="wide",
    page_title="Nemotron + Korean Law MCP Tool-use",
    page_icon="⚖️",
)
st.title("⚖️ L5 Live Demo — Nemotron이 법제처를 실시간 조회합니다")
st.caption(
    "Nemotron 3 Nano 30B가 질문을 받으면 `search_korean_law` 도구를 호출하고, "
    "우리 코드가 Korean Law MCP(법제처 API 래퍼)에 전달합니다. "
    "조문 원문이 돌아오면 Nemotron이 그 원문을 인용해 최종 답변을 생성합니다."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_korean_law",
            "description": (
                "한국 법령의 조문 전문을 실시간으로 조회합니다. "
                "특정 법령의 특정 조문이 필요할 때 호출하세요. "
                "법령명과 조문번호를 지정하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "law_name": {
                        "type": "string",
                        "description": "법령의 정확한 이름 (예: 소득세법, 민법, 근로기준법)",
                    },
                    "article_no": {
                        "type": "string",
                        "description": "조문 번호, 숫자만 (예: 47, 618)",
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


async def mcp_call(law_name: str, article_no: str) -> str:
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("search_law", {"query": law_name})
            first = res.content[0] if res.content else None
            txt = getattr(first, "text", "") if first else ""
            m = re.search(r"MST:\s*(\d+)", txt)
            if not m:
                return f"(법령 '{law_name}'의 MST를 찾을 수 없습니다)"
            mst = m.group(1)
            res2 = await session.call_tool(
                "get_law_text",
                {"mst": mst, "jo": f"제{article_no}조"},
            )
            body = res2.content[0] if res2.content else None
            return getattr(body, "text", "") if body else ""


def run_mcp(law_name: str, article_no: str) -> str:
    return asyncio.run(mcp_call(law_name, article_no))


SAMPLES = [
    "소득세법 제47조의 현행 근로소득공제 내용을 알려주세요.",
    "민법 제1000조는 상속 순위를 어떻게 정하고 있나요?",
    "근로기준법 제60조에 따라 3년 근속자의 연차유급휴가는 몇 일인가요?",
    "부가가치세법 제26조 제1항에서 면세 대상 재화·용역은 무엇인가요?",
]

sample_sel = st.selectbox("빠른 샘플", [""] + SAMPLES, index=0)
q = st.text_area("질문", value=sample_sel, height=80)

col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
max_tokens = col_cfg1.slider("max_tokens", 500, 4000, 2048, step=100)
temperature = col_cfg2.slider("temperature", 0.0, 1.0, 0.2, step=0.1)
col_cfg3.caption(f"endpoint: `{BASE_URL}` / model: `{MODEL}` / MCP: `{MCP_URL[:60]}…`")


def _serialize_tool_calls(tool_calls):
    return [
        {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        }
        for tc in tool_calls
    ]


if st.button("▶ Nemotron에게 질문 (tool-use 활성)", type="primary") and q.strip():
    client = OpenAI(base_url=BASE_URL, api_key="not-used")
    step1 = st.empty()
    step2 = st.empty()
    step3 = st.empty()

    t0 = time.time()
    with step1.container():
        st.subheader("1️⃣ Nemotron 1차 호출 — tool_call 결정")
        with st.spinner("생각 중..."):
            try:
                resp1 = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": q},
                    ],
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                st.error(f"vLLM 호출 실패: {type(e).__name__}: {e}")
                st.stop()
        msg1 = resp1.choices[0].message
        tool_calls = getattr(msg1, "tool_calls", None) or []
        if not tool_calls:
            st.warning("tool_call이 발생하지 않았습니다. Nemotron이 내부 지식으로만 답변:")
            st.markdown(msg1.content or "")
            st.stop()
        st.success(f"tool_call {len(tool_calls)}건 발생 ({time.time() - t0:.1f}s)")
        for tc in tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            st.code(
                json.dumps(
                    {"name": tc.function.name, "arguments": args},
                    ensure_ascii=False,
                    indent=2,
                ),
                language="json",
            )

    with step2.container():
        st.subheader("2️⃣ Korean Law MCP 실시간 호출 (법제처)")
        tool_messages = []
        for tc in tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            law_name = args.get("law_name", "")
            article_no = str(args.get("article_no", ""))
            with st.spinner(f"{law_name} 제{article_no}조 조회 중..."):
                try:
                    result = run_mcp(law_name, article_no)
                except Exception as e:
                    result = f"(MCP 오류: {type(e).__name__}: {e})"
            st.markdown(f"**{law_name} 제{article_no}조**")
            st.code(result[:2500], language="text")
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": result[:3000],
                }
            )

    with step3.container():
        st.subheader("3️⃣ Nemotron 2차 호출 — 조문을 인용한 최종 답변")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": q},
            {
                "role": "assistant",
                "content": msg1.content or "",
                "tool_calls": _serialize_tool_calls(tool_calls),
            },
            *tool_messages,
        ]
        with st.spinner("최종 답변 생성 중..."):
            resp2 = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        st.markdown(resp2.choices[0].message.content or "(empty)")
        total = time.time() - t0
        st.caption(f"총 소요: {total:.1f}초 · 1차 + MCP + 2차")

st.markdown("---")
st.caption(
    "연관 문서: `19-live-demo-tool-use.md` / `10-architecture-overview.md` §L5 Slide 12"
)
